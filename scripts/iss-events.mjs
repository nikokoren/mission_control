// scripts/iss-events.mjs
// Runs in GitHub Actions every 30 minutes. Asks LL2 what's happening at
// the ISS, then sends the answer to the Cloudflare worker.
//
// This version is patient and sturdy: each call to LL2 gets up to 30
// seconds, and if a call fails the script logs it and moves on instead
// of crashing.

const LL2_API_BASE = "https://ll.thespacedevs.com/2.2.0";
const POST_EVENT_WINDOW_HOURS = 4;
const ISS_STATION_ID = 4;
const CALL_TIMEOUT_MS = 30000; // how long we wait for LL2 to answer

const PUSH_TOKEN = process.env.PUSH_TOKEN;
const WORKER_URL = process.env.WORKER_URL;

if (!PUSH_TOKEN || !WORKER_URL) {
  console.error("Missing PUSH_TOKEN or WORKER_URL env");
  process.exit(1);
}

const now = Date.now();

// One call to LL2. Never throws: on any problem it logs what went
// wrong and returns an empty result so the script can continue.
const getJson = async (path) => {
  const started = Date.now();
  try {
    const res = await fetch(`${LL2_API_BASE}${path}`, {
      signal: AbortSignal.timeout(CALL_TIMEOUT_MS)
    });
    const secs = ((Date.now() - started) / 1000).toFixed(1);
    if (!res.ok) {
      console.log(`LL2 ${res.status} on ${path} (after ${secs}s)`);
      return {};
    }
    console.log(`LL2 OK on ${path} (${secs}s)`);
    return res.json();
  } catch (e) {
    const secs = ((Date.now() - started) / 1000).toFixed(1);
    console.log(`LL2 no answer on ${path} (gave up after ${secs}s): ${e.name}`);
    return {};
  }
};

async function computeEvent() {
  let activeEvent = null;

  // 1. PRIORITY: SPACEWALKS (EVA)
  {
    const data = await getJson("/spacewalks/?limit=5&ordering=-start");
    for (const eva of (data.results || [])) {
      if (!eva.location || !eva.location.includes("International Space Station")) continue;
      const start = new Date(eva.start);
      if (isNaN(start)) continue;
      const end = eva.end ? new Date(eva.end) : new Date(start.getTime() + (8 * 36e5));
      if (now >= start.getTime() && now <= end.getTime()) {
        const crewNames = (eva.crew || [])
          .map(c => c?.astronaut?.name?.split(" ").pop())
          .filter(Boolean)
          .join(" & ");
        const hoursIn = Math.floor((now - start.getTime()) / 36e5);
        activeEvent = {
          has_event: true,
          type: "EVA",
          short_info: `EVA Active (${hoursIn}h in): Astronauts ${crewNames || "crew"} are working outside.`
        };
      }
      if (activeEvent) break;
    }
  }

  // 2. PRIORITY: DOCKING / UNDOCKING
  if (!activeEvent) {
    const data = await getJson(`/docking_event/?limit=5&ordering=-docking&space_station__id=${ISS_STATION_ID}`);
    for (const event of (data.results || [])) {
      const stationName = event.docking_location?.spacestation?.name || "";
      if (stationName && !stationName.includes("International Space Station")) continue;

      const dockTime = event.docking ? new Date(event.docking) : null;
      const undockTime = event.departure ? new Date(event.departure) : null;
      const vehicle = event.flight_vehicle?.spacecraft?.name || "Spacecraft";
      const port = event.docking_location?.name || "Station Port";

      if (dockTime && !isNaN(dockTime)) {
        const diff = (now - dockTime.getTime()) / 36e5;
        if (diff >= 0 && diff <= POST_EVENT_WINDOW_HOURS) {
          activeEvent = {
            has_event: true, type: "Docking",
            short_info: `Docking confirmed: ${vehicle} attached to ${port} ${Math.floor(diff * 60)}m ago.`
          };
        } else if (diff < 0 && diff >= -1) {
          activeEvent = {
            has_event: true, type: "Docking",
            short_info: `Approach active: ${vehicle} closing in on ${port}.`
          };
        }
      }

      if (!activeEvent && undockTime && !isNaN(undockTime)) {
        const diff = (now - undockTime.getTime()) / 36e5;
        if (diff >= 0 && diff <= POST_EVENT_WINDOW_HOURS) {
          activeEvent = {
            has_event: true, type: "Undocking",
            short_info: `Undocking confirmed: ${vehicle} departed ${port} ${Math.floor(diff * 60)}m ago.`
          };
        } else if (diff < 0 && diff >= -1) {
          activeEvent = {
            has_event: true, type: "Undocking",
            short_info: `Departure prep: ${vehicle} preparing to undock from ${port}.`
          };
        }
      }
      if (activeEvent) break;
    }
  }

  // 3. PRIORITY: LAUNCHES
  if (!activeEvent) {
    const prev = await getJson("/launch/previous/?limit=5");
    const upcoming = await getJson("/launch/upcoming/?limit=5");
    const allLaunches = [...(prev.results || []), ...(upcoming.results || [])];
    for (const launch of allLaunches) {
      const isIss = (launch.program || []).some(p => (p.name || "").includes("International Space Station"));
      if (!isIss) continue;
      const net = new Date(launch.net);
      if (isNaN(net)) continue;
      const diffHours = (now - net.getTime()) / 36e5;
      const mission = launch.mission?.name || "Mission";
      const provider = launch.launch_service_provider?.name || "Agency";

      if (diffHours >= 0 && diffHours <= POST_EVENT_WINDOW_HOURS) {
        const minsAgo = Math.floor(diffHours * 60);
        activeEvent = {
          has_event: true, type: "Launch",
          short_info: `Launch Success (T+${minsAgo}m): ${provider} ${mission} en route to ISS.`
        };
      } else if (diffHours < 0 && diffHours >= -1) {
        const minsTo = Math.abs(Math.floor(diffHours * 60));
        activeEvent = {
          has_event: true, type: "Launch",
          short_info: `Liftoff in ${minsTo}m: ${provider} ${mission} launching to ISS.`
        };
      }
      if (activeEvent) break;
    }
  }

  return activeEvent || { has_event: false, type: "", short_info: "" };
}

const event = await computeEvent();
console.log("Computed event:", JSON.stringify(event));

const res = await fetch(`${WORKER_URL}/push`, {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${PUSH_TOKEN}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify(event),
  signal: AbortSignal.timeout(15000)
});

if (!res.ok) {
  console.error(`Push failed: ${res.status} ${await res.text()}`);
  process.exit(1);
}
console.log("Pushed to worker:", await res.text());
