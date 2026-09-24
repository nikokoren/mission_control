#!/usr/bin/env python3
"""
Rebuild tests/fixtures/launches.json from the live Launch Library API.

The fixtures are real API payloads, pruned to the fields cards.py reads. The
pruning is what makes them committable: 90 detailed launches arrive as 1.4 MB
of mostly URLs, images and agency biographies, and the card code touches a few
dozen keys of it.

    python3 tests/make_fixtures.py

Run it when a launch shows up that the cards get wrong: the fixture set is the
regression corpus, so the fix and the launch that prompted it land together.
Be aware the API rate-limits anonymous callers to a handful of requests an
hour, and that test_cards.py verifies the pruning itself, so a key this script
forgets is caught there rather than silently changing what the tests cover.
"""

import json
import os
import sys
import urllib.request

API = "https://ll.thespacedevs.com/2.2.0"
UA = "mission-control-trmnl (github.com/nikokoren)"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures", "launches.json")

# What to fetch. Upcoming and previous launches exercise the two modes, and a
# wide sweep is the point: the interesting cases are the launches nobody would
# think to write a fixture for by hand -- an unnamed core, a pad LL2 has no
# name for, a landing record that disagrees with the flight count.
# Each entry is (render mode, API path). The mode is the one build_slots is
# called with for that launch: its caller picks it from the clock, so the
# fixture records it rather than making the tests guess.
QUERIES = [
    ("PRE_LAUNCH", "upcoming/?limit=10&mode=detailed&hide_recent_previous=true"),
    ("PRE_LAUNCH", "upcoming/?limit=30&offset=10&mode=detailed&hide_recent_previous=true"),
    ("POST_LAUNCH", "previous/?limit=10&mode=detailed"),
    ("POST_LAUNCH", "previous/?limit=40&offset=10&mode=detailed"),
]

# The shape cards.py reads. A string keeps a leaf value as it is; a dict
# descends into an object; a list of one item descends into every element of
# an array.
SHAPE = {
    "id": str, "name": str, "net": str, "pad_turnaround": str,
    "probability": str, "weather_concerns": str, "holdreason": str,
    "failreason": str, "window_start": str, "window_end": str,
    "agency_launch_attempt_count": str,
    "agency_launch_attempt_count_year": str,
    "orbital_launch_attempt_count_year": str,
    "pad_launch_attempt_count_year": str,
    "status": {"abbrev": str, "name": str},
    "net_precision": {"abbrev": str},
    "pad": {"name": str, "total_launch_count": str},
    "launch_service_provider": {
        "name": str, "successful_landings": str, "attempted_landings": str},
    "mission": {
        "description": str, "type": str,
        "orbit": {"name": str},
        "agencies": [{"name": str}],
    },
    "program": [{"name": str, "description": str}],
    "updates": [{"comment": str, "created_on": str}],
    "mission_patches": [{"image_url": str}],
    "rocket": {
        "configuration": {
            "name": str, "id": str, "consecutive_successful_launches": str},
        "spacecraft_stage": {"spacecraft": {"name": str}},
        "launcher_stage": [{
            "type": str, "reused": str, "launcher_flight_number": str,
            "turn_around_time_days": str,
            "previous_flight": {"name": str},
            "launcher": {"serial_number": str, "flights": str,
                         "successful_landings": str, "attempted_landings": str},
            "landing": {
                "attempt": str, "success": str, "downrange_distance": str,
                "type": {"abbrev": str},
                "location": {"name": str, "abbrev": str},
            },
        }],
    },
}


def prune(value, shape):
    """Copy `value` down to the keys named in `shape`, keeping nulls as nulls."""
    if value is None or shape is str:
        return value
    if isinstance(shape, list):
        if not isinstance(value, list):
            return value
        return [prune(v, shape[0]) for v in value]
    if not isinstance(value, dict):
        return value
    return {k: prune(value.get(k), sub) for k, sub in shape.items()
            if k in value}


def fetch(path):
    req = urllib.request.Request(f"{API}/launch/{path}&format=json",
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def sources(argv):
    """
    (mode, payload) pairs, from the API or from files already on disk.

        python3 tests/make_fixtures.py                    # fetch
        python3 tests/make_fixtures.py PRE=up.json ...    # reuse a saved payload

    The file form takes MODE=path arguments and exists because the API
    rate-limits hard: a saved response can be re-pruned without spending a
    request on it.
    """
    if not argv:
        for mode, path in QUERIES:
            print(f"fetching {path}")
            try:
                yield mode, fetch(path)
            except Exception as e:
                print(f"  failed: {e}")
        return

    for arg in argv:
        mode, _, path = arg.partition("=")
        mode = "PRE_LAUNCH" if mode.upper().startswith("PRE") else "POST_LAUNCH"
        print(f"reading {path} as {mode}")
        with open(path) as f:
            yield mode, json.load(f)


def main(argv):
    out = []
    seen = set()
    for mode, data in sources(argv):
        for launch in data.get("results") or []:
            if launch.get("id") in seen:
                continue
            seen.add(launch.get("id"))
            out.append({"mode": mode, "launch": prune(launch, SHAPE)})

    if not out:
        print("nothing fetched, leaving the existing fixtures alone")
        return 1

    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    size = os.path.getsize(OUT)
    print(f"wrote {len(out)} launches to {OUT} ({size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
