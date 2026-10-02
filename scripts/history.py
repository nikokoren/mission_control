"""
Cached lookups for booster history.

Both of these hit extra API endpoints, so everything is cached in the repo:

  boosters/B1088.json      one booster's flight list
  boosters/_fleet.json     every core LL2 knows, for ranking within a type

A booster's history only changes when it flies, so we refetch only when the
serial is new or its flight count has gone up. The fleet list moves slowly,
so it refreshes weekly. In the steady state this adds no API calls at all.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://ll.thespacedevs.com/2.2.0"
UA = "mission-control-trmnl (github.com/nikokoren)"
CACHE_DIR = "boosters"
FLEET_MAX_AGE = 7 * 24 * 3600  # a week

# If the serial_number filter is ignored, the API returns the entire launch
# database. Anything above this is obviously not one booster's history.
SANITY_MAX_COUNT = 500


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as e:
        print(f"Warning: request failed for {url}: {e}")
        return None


def _name_of(value):
    """
    LL2 returns nested objects in detailed mode but bare strings in list mode
    for some fields. Accept either without exploding.
    """
    if isinstance(value, dict):
        return (value.get("name") or "").strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def _cache_path(name):
    # Keep serials with spaces or slashes from turning into odd filenames
    # or stray directories.
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(name))
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _read_cache(name):
    path = _cache_path(name)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not read cache {path}: {e}")
        return None


def _write_cache(name, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(name), "w") as f:
            json.dump(data, f, separators=(",", ":"))
        return True
    except Exception as e:
        print(f"Warning: could not write cache {name}: {e}")
        return False


# ============================================================
# one booster's flight list
# ============================================================

def get_booster_history(serial, flights_now):
    """
    Returns {'serial', 'flights', 'launches': [{'name','net','pad'}, ...]}
    or None if unavailable. Never raises: the career card is a bonus and
    must never be able to stop launch.json being written.
    """
    try:
        return _get_booster_history(serial, flights_now)
    except Exception as e:
        print(f"Warning: booster history lookup failed for {serial}: {e}")
        return None


def _get_booster_history(serial, flights_now):
    if not serial:
        return None

    cached = _read_cache(serial)
    if cached and cached.get("flights") == flights_now and cached.get("launches"):
        print(f"Booster history for {serial}: cache hit")
        return cached

    print(f"Booster history for {serial}: fetching")
    # Serials are not always a single token: Zhuque-3's is "ZQ-3 F2", and a
    # raw space makes urllib refuse the request outright. Every serial seen
    # before this was one word, so the bug sat unnoticed until a Chinese
    # reusable turned up. quote with an empty safe list covers spaces, slashes
    # and anything else that would corrupt the query.
    # The limit has to clear the most-flown core with room to spare. At 40,
    # B1067 was three flights from losing its newest flights off the end of
    # the page, after which its career card would have frozen.
    url = (
        f"{API}/launch/?serial_number={urllib.parse.quote(str(serial), safe='')}"
        "&mode=list&limit=100&format=json"
    )
    data = _get(url)
    if not data:
        return cached  # stale beats nothing

    count = data.get("count")
    if count is None or count > SANITY_MAX_COUNT:
        # The filter was ignored and we got the whole database back.
        print(f"Warning: serial_number filter looks unsupported (count={count}). Skipping history.")
        return None

    launches = []
    try:
        for r in data.get("results") or []:
            if not isinstance(r, dict):
                continue
            net = r.get("net")
            if not net:
                continue
            launches.append({
                "name": _name_of(r.get("name")).split(" | ")[-1].strip(),
                "net": net,
                "pad": _name_of(r.get("pad")),
            })
    except Exception as e:
        print(f"Warning: could not parse booster history for {serial}: {e}")
        return None

    if not launches:
        return None

    launches.sort(key=lambda x: x["net"])
    record = {"serial": serial, "flights": flights_now, "launches": launches}
    _write_cache(serial, record)
    return record


# ============================================================
# when a pad first flew
# ============================================================

# Keyed by LL2's pad id: names repeat ("Orbital Launch Pad", "LC-1"). The
# first launch from a pad never changes, so an entry is fetched once and kept.
PADS_CACHE = "_pads"


def get_pad_first_year(pad_id, pad_name=""):
    """
    The year of the first launch LL2 records from this pad, or None. That is
    the span the pad's total_launch_count covers, so it is what gives the
    total a scale: 200 launches since 2024 and 200 since 1965 are different
    pads. One extra call per pad, ever. Never raises.
    """
    if not pad_id:
        return None
    try:
        return _get_pad_first_year(pad_id, pad_name)
    except Exception as e:
        print(f"Warning: first launch lookup failed for pad {pad_id}: {e}")
        return None


def _get_pad_first_year(pad_id, pad_name):
    pads = _read_cache(PADS_CACHE) or {}
    entry = pads.get(str(pad_id))
    if entry and isinstance(entry.get("first_year"), int):
        print(f"First launch from pad {pad_id}: cache hit")
        return entry["first_year"]

    print(f"First launch from pad {pad_id}: fetching")
    url = f"{API}/launch/?pad={pad_id}&ordering=net&limit=1&mode=list&format=json"
    data = _get(url)
    results = (data or {}).get("results") or []
    if not results:
        return None
    first = results[0]

    # The fleet lookup taught this one: LL2 ignores a filter it does not know
    # and returns the whole table, which here would date every pad to
    # Sputnik. The first launch has to have flown from the pad we asked about.
    flown_from = _name_of(first.get("pad"))
    if pad_name and flown_from and flown_from != pad_name:
        print(f"Warning: pad filter looks unsupported ({flown_from!r} is not {pad_name!r}).")
        return None
    try:
        year = int(str(first.get("net"))[:4])
    except ValueError:
        return None

    pads[str(pad_id)] = {"name": pad_name or flown_from, "first_year": year}
    _write_cache(PADS_CACHE, pads)
    return year


# ============================================================
# fleet ranking
# ============================================================

def get_docking(spacecraft_name, station_id=4):
    """
    For an ISS-bound launch: when does the spacecraft actually arrive?
    One extra call, cached like the others, and it never raises.
    Returns {"hours_until", "port", "spacecraft"} or None.
    """
    if not spacecraft_name:
        return None
    try:
        return _get_docking(spacecraft_name, station_id)
    except Exception as e:
        print(f"Warning: docking lookup failed for {spacecraft_name}: {e}")
        return None


def _get_docking(spacecraft_name, station_id):
    from datetime import datetime, timezone
    url = (f"{API}/docking_event/?limit=10&ordering=-docking"
           f"&space_station__id={station_id}")
    data = _get(url)
    if not data:
        return None
    now = datetime.now(timezone.utc)
    want = str(spacecraft_name).lower()

    for ev in (data.get("results") or []):
        craft = ((ev.get("flight_vehicle") or {}).get("spacecraft") or {}).get("name") or ""
        if want not in craft.lower() and craft.lower() not in want:
            continue
        raw = ev.get("docking")
        if not raw:
            continue
        try:
            when = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        hours = (when - now).total_seconds() / 3600.0
        # Only interesting within a few days either side of the event.
        if hours < -24 or hours > 120:
            continue
        return {
            "hours_until": hours,
            "port": ((ev.get("docking_location") or {}).get("name") or ""),
            "spacecraft": craft or "The spacecraft",
        }
    return None


def get_fleet(config_id):
    """
    Returns [{'serial','flights'}, ...] for one rocket type, sorted most flown
    first, or None. Never raises, for the same reason as get_booster_history.
    """
    try:
        return _fleet_of(_get_all_cores(), config_id)
    except Exception as e:
        print(f"Warning: fleet lookup failed for config {config_id}: {e}")
        return None


def _fleet_of(cores, config_id):
    """The cores of one rocket type, most flown first. None if there are none."""
    if not config_id:
        return None
    fleet = [{"serial": c["serial"], "flights": c["flights"]}
             for c in cores or [] if c.get("config") == config_id]
    fleet.sort(key=lambda c: c["flights"], reverse=True)
    return fleet or None


# LL2 2.2.0 ignores a launcher_config filter on /launcher/, under that name
# and as launcher_config__id: both return the whole table. The old per-type
# fetch therefore cached the same first 100 launchers of the database under
# every rocket type, Starship test articles included, and ranked a core
# against whatever happened to be in it. The table is small (under 200
# rows), so take all of it in one weekly pass and filter here. That is also
# fewer calls than one fetch per rocket type.
FLEET_CACHE = "_fleet"
FLEET_MAX_PAGES = 5


def _get_all_cores():
    cached = _read_cache(FLEET_CACHE)
    if cached and (time.time() - cached.get("fetched_at", 0)) < FLEET_MAX_AGE:
        print("Fleet list: cache hit")
        return cached.get("cores")

    print("Fleet list: fetching")
    cores = []
    url = f"{API}/launcher/?limit=100&format=json"
    for _ in range(FLEET_MAX_PAGES):
        data = _get(url)
        if not data:
            # A partial table would rank a core against half its fleet.
            return (cached or {}).get("cores")
        for r in data.get("results") or []:
            serial = r.get("serial_number")
            flights = r.get("flights")
            config = (r.get("launcher_config") or {}).get("id")
            if serial and isinstance(flights, int) and config:
                cores.append({"serial": serial, "flights": flights, "config": config})
        url = data.get("next")
        if not url:
            break
    else:
        print(f"Warning: launcher table runs past {FLEET_MAX_PAGES} pages. Keeping the cached fleet.")
        return (cached or {}).get("cores")

    if not cores:
        return (cached or {}).get("cores")

    _write_cache(FLEET_CACHE, {"fetched_at": int(time.time()), "cores": cores})
    return cores
