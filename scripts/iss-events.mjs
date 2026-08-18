// scripts/iss-events.mjs
// Runs in GitHub Actions every 30 minutes. Asks LL2 what's happening at
// the ISS, then sends the answer to the Cloudflare worker.
//
// This version is patient and sturdy: each call to LL2 gets up to 30
// seconds, and if a call fails the script logs it and moves on instead
// of crashing.
//
// EVA DETECTION NOTES
// -------------------
// /spacewalks/ is a flat historical list, not an upcoming/previous pair.
// Two things make an in-progress EVA easy to miss:
//
//   1. LL2 may only publish a spacewalk record once it has been logged,
//      which can be after the EVA ends. So we ALSO look for one that
//      finished recently and report it as just-completed.
//   2. Planned EVAs appear in /event/ before they appear in /spacewalks/.
//      Confirmed live on 2026-08-18: US EVA-97 was in /event/previous/
//      with type "EVA" while /spacewalks/ still ended at 6 August. The
//      regex below matches both "EVA" and "Spacewalk" since the API has
//      used both.
//
// Every LL2 call and every candidate record is logged, so if this still
// reports no event the Action log says exactly which stage saw what.

const LL2_API_BASE = "https://ll.thespacedevs.com/2.2.0";
const POST_EVENT_WINDOW_HOURS = 4;
const ISS_STATION_ID = 4;
const CALL_TIMEOUT_MS = 30000; // how long we wait for LL2 to answer
const EVA_ASSUMED_HOURS = 6.5; // used when a record has no end time. US EVAs
                               // run about 6 to 7 hours; Russian ones can go
                               // longer, so this errs slightly short rather
                               // than showing a finished EVA as active.

const PUSH_TOKEN = process.env.PUSH_TOKEN;
const WORKER_URL = process.env.WORKER_URL;

if (!PUSH_TOKEN || !WORKER_URL) {
  console.error("Missing PUSH_TOKEN or WORKER_URL env");
  process.exit(1);
}

const now = Date.now();

// Location strings vary: "International Space Station" is what the API
// uses today, but "ISS" appears on some older records.
const isISS = (loc) => {
  const s = String(loc || "");
  return s.includes("International Space Station") || /\bISS\b/.test(s);
};

const hoursFrom = (ms) => (now - ms) / 36e5;

// "0h in" reads like a rounding error in the first hour, so report minutes
// until there is a whole hour to report.
// Russian ISS spacewalks are VKD (внекорабельная деятельность), numbered
// separately from the US EVA series, so "VKD-65" rather than "US EVA-97".
// Checked against the name and the crew's agency, because either can be
// missing depending on which endpoint the record came from.
const isRussian = (name, agencyNames) => {
  if (/\bvkd\b/i.test(String(name || ""))) return true;
  return (agencyNames || []).some(a => /roscosmos|russian federal/i.test(String(a || "")));
};

// Alternate the wording each run. Derived from the clock rather than
// Math.random() so it actually alternates: random would repeat itself half
// the time, which on a 30 minute cron means stretches of two hours with no
// change. This flips every 30 minutes, matching the cron.
const phraseIndex = Math.floor(now / 18e5) % 2;

const elapsedSince = (ms) => {
  const mins = Math.max(0, Math.floor((now - ms) / 6e4));
  return mins < 60 ? `${mins}m` : `${Math.floor(mins / 60)}h`;
};

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
      // The body usually explains a 400 (bad filter) or a 429 (throttled),
      // and that distinction matters a lot when debugging.
      let hint = "";
      try { hint = (await res.text()).slice(0, 200); } catch (e) {}
      console.log(`LL2 ${res.status} on ${path} (after ${secs}s) ${hint}`);
      return {};
    }
    const data = await res.json();
    console.log(`LL2 OK on ${path} (${secs}s, ${(data.results || []).length} results)`);
    return data;
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
    const rows = data.results || [];

    // Log every candidate before filtering. If this list is empty, LL2 has
    // no record yet; if it is full of Tiangong walks, the ISS filter is
    // doing its job and the ISS EVA simply is not published.
    for (const eva of rows) {
      console.log(`  spacewalk: "${eva.name}" @ ${eva.location} ` +
                  `start=${eva.start} end=${eva.end || "(none)"}`);
    }

    let recentlyEnded = null;

    for (const eva of rows) {
      if (!isISS(eva.location)) continue;
      const start = new Date(eva.start);
      if (isNaN(start)) continue;
      const end = eva.end
        ? new Date(eva.end)
        : new Date(start.getTime() + EVA_ASSUMED_HOURS * 36e5);

      const crewNames = (eva.crew || [])
        .map(c => c?.astronaut?.name?.split(" ").pop())
        .filter(Boolean)
        .join(" & ");

      if (now >= start.getTime() && now <= end.getTime()) {
        const agencies = (eva.crew || []).map(c => c?.astronaut?.agency?.name);
        const noun = isRussian(eva.name, agencies) ? "Cosmonauts" : "Astronauts";
        const who = crewNames || "crew";
        const line = phraseIndex === 0
          ? `${noun} ${who} are working outside.`
          : `${crewNames || "Crew"} are outside the station.`;
        activeEvent = {
          has_event: true,
          type: "EVA",
          short_info: `EVA Active (${elapsedSince(start.getTime())} in): ${line}`
        };
        break;
      }

      // Keep the most recent finished EVA as a fallback. LL2 sometimes only
      // publishes the record after the fact, in which case this is the
      // earliest we can say anything at all.
      if (!recentlyEnded) {
        const sinceEnd = hoursFrom(end.getTime());
        if (sinceEnd >= 0 && sinceEnd <= POST_EVENT_WINDOW_HOURS) {
          const mins = Math.floor(sinceEnd * 60);
          recentlyEnded = {
            has_event: true,
            type: "EVA",
            short_info: `EVA complete: ${crewNames || "Crew"} back inside, hatch closed ${mins}m ago.`
          };
        }
      }
    }

    if (!activeEvent && recentlyEnded) activeEvent = recentlyEnded;

    // 1b. FALLBACK: planned spacewalks often land in /event/ first.
    if (!activeEvent) {
      const ev = await getJson("/event/upcoming/?limit=10");
      const prevEv = await getJson("/event/previous/?limit=5");
      for (const e of [...(prevEv.results || []), ...(ev.results || [])]) {
        const typeName = e.type?.name || "";
        if (!/spacewalk|eva|vkd/i.test(typeName + " " + (e.name || ""))) continue;
        if (!isISS(e.location) && !isISS(e.name)) continue;
        // Press events about spacewalks are not spacewalks.
        if (/briefing|preview|press|conference/i.test(e.name || "")) continue;

        const start = new Date(e.date);
        if (isNaN(start)) continue;
        const end = new Date(start.getTime() + EVA_ASSUMED_HOURS * 36e5);
        console.log(`  event candidate: "${e.name}" type=${typeName} date=${e.date} ` +
                    `loc="${e.location || ""}" dur=${e.duration || "(none)"} ` +
                    `desc="${String(e.description || "").slice(0, 120)}"`);

        if (now >= start.getTime() && now <= end.getTime()) {
          const agencies = (e.agencies || []).map(a => a?.name);
          const noun = isRussian(e.name, agencies) ? "Cosmonauts" : "Astronauts";
          const line = phraseIndex === 0
            ? `${noun} are working outside.`
            : "Crew are outside the station.";
          activeEvent = {
            has_event: true,
            type: "EVA",
            short_info: `EVA Active (${elapsedSince(start.getTime())} in): ${line}`
          };
          break;
        }
      }
    }
  }

  // 2. PRIORITY: DOCKING / UNDOCKING
  if (!activeEvent) {
    const data = await getJson(`/docking_event/?limit=5&ordering=-docking&space_station__id=${ISS_STATION_ID}`);
    for (const event of (data.results || [])) {
      const stationName = event.docking_location?.spacestation?.name || "";
      if (stationName && !isISS(stationName)) continue;

      const dockTime = event.docking ? new Date(event.docking) : null;
      const undockTime = event.departure ? new Date(event.departure) : null;
      const vehicle = event.flight_vehicle?.spacecraft?.name || "Spacecraft";
      const port = event.docking_location?.name || "Station Port";

      if (dockTime && !isNaN(dockTime)) {
        const diff = hoursFrom(dockTime.getTime());
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
        const diff = hoursFrom(undockTime.getTime());
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
      const isIss = (launch.program || []).some(p => isISS(p.name));
      if (!isIss) continue;
      const net = new Date(launch.net);
      if (isNaN(net)) continue;
      const diffHours = hoursFrom(net.getTime());
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

console.log(`Run at ${new Date(now).toISOString()}`);
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
