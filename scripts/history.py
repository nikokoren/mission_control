"""
Cached lookups for booster history.

Both of these hit extra API endpoints, so everything is cached in the repo:

  boosters/B1088.json      one booster's flight list
  boosters/_fleet_164.json every core of one rocket type, for ranking

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
    # reusable turned up. quote() covers spaces and anything else unsafe.
    url = (
        f"{API}/launch/?serial_number={urllib.parse.quote(serial)}"
        "&mode=list&limit=40&format=json"
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
# fleet ranking
# ============================================================

def get_fleet(config_id):
    """
    Returns [{'serial','flights'}, ...] sorted most flown first, or None.
    Never raises, for the same reason as get_booster_history.
    """
    try:
        return _get_fleet(config_id)
    except Exception as e:
        print(f"Warning: fleet lookup failed for config {config_id}: {e}")
        return None


def _get_fleet(config_id):
    if not config_id:
        return None

    name = f"_fleet_{config_id}"
    cached = _read_cache(name)
    if cached and (time.time() - cached.get("fetched_at", 0)) < FLEET_MAX_AGE:
        print(f"Fleet list for config {config_id}: cache hit")
        return cached.get("cores")

    print(f"Fleet list for config {config_id}: fetching")
    url = f"{API}/launcher/?launcher_config={config_id}&limit=100&format=json"
    data = _get(url)
    if not data:
        return (cached or {}).get("cores")

    cores = []
    for r in data.get("results") or []:
        serial = r.get("serial_number")
        flights = r.get("flights")
        if serial and isinstance(flights, int):
            cores.append({"serial": serial, "flights": flights})

    if not cores:
        return (cached or {}).get("cores")

    cores.sort(key=lambda c: c["flights"], reverse=True)
    _write_cache(name, {"fetched_at": int(time.time()), "cores": cores})
    return cores
