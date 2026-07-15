// scripts/iss-events.mjs
// Runs in GitHub Actions. Fetches LL2 from GitHub runner IPs (not rate
// starved like Cloudflare egress), computes the active ISS event using
// the same logic as the worker, and POSTs the result to the worker's
// /push endpoint, which writes it to KV.
//
// Required env:
//   PUSH_TOKEN  - shared secret, must match the worker's REFRESH_TOKEN
//   WORKER_URL  - e.g. https://iss-events.5g5wqr7kzx-466.workers.dev

const LL2_API_BASE = "https://ll.thespacedevs.com/2.2.0";
const POST_EVENT_WINDOW_HOURS = 4;
const ISS_STATION_ID = 4;

const PUSH_TOKEN = process.env.PUSH_TOKEN;
const WORKER_URL = process.env.WORKER_URL;

if (!PUSH_TOKEN || !WORKER_URL) {
  console.error("Missing PUSH_TOKEN or WORKER_URL env");
  process.exit(1);
}

const now = Date.now();

const getJson = async (path) => {
  const res = await fetch(`${LL2_API_BASE}${path}`, {
    signal: AbortSignal.timeout(10000)
  });
  if (!res.ok) {
    console.log(`LL2 ${res.status} on ${path}`);
    return {};
  }
  return res.json();
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
    const [prev, upcoming] = await Promise.all([
      getJson("/launch/previous/?limit=5"),
      getJson("/launch/upcoming/?limit=5")
    ]);
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
  signal: AbortSignal.timeout(10000)
});

if (!res.ok) {
  console.error(`Push failed: ${res.status} ${await res.text()}`);
  process.exit(1);
}
console.log("Pushed to worker:", await res.text());
