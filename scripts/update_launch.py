#!/usr/bin/env python3
"""
Builds launch.json for the mission control TRMNL plugin.

Reads upcoming.json and previous.json (fetched by the workflow), decides
which launch to show, builds the card text, and writes launch.json.

Run locally with:
    python3 scripts/update_launch.py
"""

import json
import os
import sys
from datetime import datetime, timezone

from cards import build_slots, dig, short_pad, is_placeholder
from history import get_booster_history, get_fleet
from facts import get_rocket_fact

# ============================================================
# config
# ============================================================

REPO_BASE = "https://raw.githubusercontent.com/nikokoren/mission_control/main"

# Rocket names as the API writes them. Used for the recovery footer text.
REUSABLE_ROCKETS = ["falcon", "starship", "new glenn", "electron", "new shepard"]

# Image file key prefixes (no spaces). Used to decide if a _landed drawing exists.
# Keys that get a _landed drawing after a successful landing. A key listed
# here MUST have a <key>_landed.png in the repo, or the image 404s and the
# onerror fallback shows a rocket standing on a pad after it has already
# flown, which is worse than the empty pad. Add "zhuque3" and "neutron" here
# once their landed art exists; until then they correctly show empty.png.
# Variant art falls back to the family drawing before it falls back to
# generic. This is what lets you add a variant PNG later and have it picked
# up with no code change: draw atlasv_551_idle.png, commit it, done. Until
# then an Atlas V 551 quietly shows the plain Atlas V.
#
# Keys not listed here have no family drawing and go straight to generic.
BASE_KEY = {
    "falcon9_crew": "falcon9",
    "soyuz_crew":   "soyuz",
    "atlasv_551":   "atlasv",
    "atlasv_n22":   "atlasv",
    "ariane_62":    "ariane6",
    "ariane_64":    "ariane6",
    "ceres_2":      "ceres",
    "cz_5b":        "cz_5",
    "cz_6a":        "cz_6",
    "cz_6c":        "cz_6",
    "cz_7a":        "cz_7",
    # Any Long March without its own drawing falls back to the generic
    # Long March silhouette, which is much closer than the question-mark
    # rocket. cz_classic is itself undrawn, so today these still reach
    # generic; drawing cz_classic once would improve every one of them.
    "cz_2c": "cz_classic", "cz_2d": "cz_classic", "cz_2f": "cz_classic",
    "cz_3a": "cz_classic", "cz_3b": "cz_classic", "cz_3c": "cz_classic",
    "cz_4b": "cz_classic", "cz_4c": "cz_classic", "cz_7":  "cz_classic",
    "cz_8":  "cz_classic", "cz_11": "cz_classic", "cz_12": "cz_classic",
}

LANDABLE_KEYS = ["falcon9", "falconheavy", "starship", "newglenn", "electron", "newshepard"]

# Fields that change every run and should not force a commit on their own.
VOLATILE_FIELDS = ["countdown", "next_countdown"]

# --- how long each launch holds the screen ---
IMMINENT_HOURS = 1.5   # next launch this close always wins
FRESH_HOURS = 4.0      # a result holds the screen at least this long
QUIET_HOURS = 6.0      # if the next launch is further off than this, keep showing the result
STALE_HOURS = 24.0     # but never show a result older than this


# ============================================================
# helpers
# ============================================================

def normalize_org_name(name):
    replacements = {
        "China Aerospace Science and Technology Corporation": "CASC",
        "National Aeronautics and Space Administration": "NASA",
        "Space Exploration Technologies": "SpaceX",
        "United Launch Alliance": "ULA",
        "Rocket Lab Ltd": "Rocket Lab",
        "European Space Agency": "ESA",
        "Indian Space Research Organisation": "ISRO",
        "Japan Aerospace Exploration Agency": "JAXA",
        "Roscosmos State Corporation": "Roscosmos",
        "Isar Aerospace": "Isar Aerospace",
    }
    for old, new in replacements.items():
        if old in name:
            return new
    return name


def normalize_location_name(name):
    for old, new in {
        "Of Course I Still Love You": "OCISLY",
        "Just Read The Instructions": "JRTI",
        "A Shortfall of Gravitas": "ASOG",
    }.items():
        name = name.replace(old, new)
    return name


def load_json(filename):
    try:
        with open(filename) as f:
            data = json.load(f)
            if "detail" in data:
                print(f"Warning: API returned an error in {filename}: {data.get('detail')}")
                return None
            if not data.get("results"):
                print(f"Warning: no results in {filename}")
                return None
            return data["results"]
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None


def parse_time(t_str):
    """Parse an API timestamp. Returns None instead of raising on bad input."""
    if not t_str:
        return None
    try:
        dt = datetime.fromisoformat(str(t_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        print(f"Warning: could not parse timestamp {t_str!r}")
        return None


def get_countdown(dt_event):
    now = datetime.now(timezone.utc)
    diff = dt_event - now
    total = int(abs(diff.total_seconds()))
    hours, rem = divmod(total, 3600)
    minutes, _ = divmod(rem, 60)
    sign = "T-" if diff.total_seconds() >= 0 else "T+"
    return f"{sign} {hours:02}h {minutes:02}m"


def get_rocket_image_url(rocket_name, status, landing_success, mission_type, mission_name, repo_url):
    r = (rocket_name or "").lower()
    m_type = str(mission_type).lower()
    m_name = str(mission_name).lower()

    key = "generic"
    if rocket_name == "generic":
        key = "generic"
    else:
        if "falcon 9" in r:
            if "human" in m_type or "crew" in m_name or "axiom" in m_name or "polaris" in m_name:
                key = "falcon9_crew"
            else:
                key = "falcon9"
        elif "falcon heavy" in r: key = "falconheavy"
        elif "starship" in r: key = "starship"
        elif "sls" in r: key = "sls"
        elif "artemis" in r: key = "sls"
        elif "new glenn" in r: key = "newglenn"
        elif "delta iv heavy" in r: key = "delta4"
        elif "long march 5b" in r: key = "cz_5b"
        elif "long march 5" in r: key = "cz_5"
        elif "long march 12" in r: key = "cz_12"
        elif "lvm3" in r: key = "lvm3"
        elif "ariane 64" in r: key = "ariane_64"
        elif "vulcan" in r: key = "vulcan"
        elif "atlas" in r:
            if "n22" in r: key = "atlasv_n22"
            elif "551" in r: key = "atlasv_551"
            else: key = "atlasv"
        elif "ariane 62" in r: key = "ariane_62"
        elif "ariane" in r: key = "ariane6"
        elif "soyuz" in r: key = "soyuz"
        elif "h3" in r: key = "h3"
        elif "antares" in r: key = "antares"
        elif "delta" in r: key = "delta4"
        elif "long march 7a" in r: key = "cz_7a"
        elif "long march 7" in r: key = "cz_7"
        elif "long march 8" in r: key = "cz_8"
        elif "long march 6a" in r: key = "cz_6a"
        elif "long march 6c" in r: key = "cz_6c"
        elif "long march 6" in r: key = "cz_6"
        elif "long march 2f" in r: key = "cz_2f"
        elif "long march 2c" in r: key = "cz_2c"
        elif "long march 2d" in r: key = "cz_2d"
        elif "long march 3a" in r: key = "cz_3a"
        elif "long march 3b" in r: key = "cz_3b"
        elif "long march 3c" in r: key = "cz_3c"
        elif "long march 4b" in r: key = "cz_4b"
        elif "long march 4c" in r: key = "cz_4c"
        elif "long march 11" in r: key = "cz_11"
        elif "long march" in r: key = "cz_classic"

        # --- Chinese commercial vehicles ---
        # Checked before the generic fallbacks. Zhuque-3 must come before the
        # plain "zhuque" test or the reusable would be caught by the Zhuque-2
        # branch. LL2 uses both the Chinese and the western name for some of
        # these, so match either.
        elif "zhuque-3" in r or "zq-3" in r: key = "zhuque3"
        elif "zhuque" in r or "zq-2" in r: key = "zhuque2"
        elif "kinetica" in r or "lijian" in r: key = "kinetica1"
        elif "tianlong" in r: key = "tianlong3"
        elif "gravity-1" in r or "yinli" in r: key = "gravity1"

        elif "neutron" in r: key = "neutron"
        elif "electron" in r: key = "electron"
        elif "firefly" in r: key = "firefly"
        elif "minotaur" in r: key = "minotaur"
        elif "pslv" in r: key = "pslv"
        elif "vega" in r: key = "vega"
        elif "nuri" in r: key = "nuri"
        elif "ceres-2" in r: key = "ceres_2"
        elif "ceres" in r: key = "ceres"
        elif "hanbit" in r: key = "hanbitnano"
        elif "new shepard" in r: key = "newshepard"
        elif "spectrum" in r or "isar" in r: key = "spectrum"

    suffix = "_idle"
    if status in ("In Flight", "AWAITING CONFIRMATION"):
        suffix = "_ascent"
    elif status in ("Success", "Failure", "Partial Failure"):
        # An empty pad after launch is intentional: it shows the rocket is gone.
        # Match on the image key, not the API rocket name, or newglenn and
        # newshepard never match because of the space.
        if landing_success and any(key.startswith(p) for p in LANDABLE_KEYS):
            suffix = "_landed"
        else:
            key, suffix = "empty", ""

    url = f"{repo_url}/rockets/{key}{suffix}.png"

    # The family drawing for this key, if there is one and it is not the key
    # itself. Same suffix, so an ascent variant falls back to an ascent family
    # drawing rather than an idle one.
    base = BASE_KEY.get(key)
    alt = f"{repo_url}/rockets/{base}{suffix}.png" if base and base != key else ""
    return url, alt


def is_resolved(launch):
    """True once we know how the launch went."""
    return dig(launch, "status", "abbrev", default="") in ("Success", "Failure", "Partial Failure")


# ============================================================
# per-launch processing
# ============================================================

def process_launch_data(launch, mode_override=None, with_history=False):
    if not launch:
        return None

    target_dt = parse_time(launch.get("net"))
    if target_dt is None:
        print("Warning: launch has no usable NET time, skipping")
        return None

    now = datetime.now(timezone.utc)
    seconds_since_t0 = (now - target_dt).total_seconds()

    if not isinstance(launch.get("status"), dict):
        launch["status"] = {"abbrev": "TBD", "name": "TBD"}

    api_status = dig(launch, "status", "abbrev", default="TBD")
    final = api_status in ("Success", "Failure", "Partial Failure", "In Flight")

    # Work out the mode first so the AWAITING CONFIRMATION status change still
    # happens even when the caller passes a mode_override.
    if final:
        computed_mode = "POST_LAUNCH"
    elif seconds_since_t0 > 600:  # 10 minutes past T-0 with no result yet
        computed_mode = "POST_LAUNCH"
        launch["status"]["abbrev"] = "PENDING"
        launch["status"]["name"] = "AWAITING CONFIRMATION"
    else:
        computed_mode = "PRE_LAUNCH"

    mode = mode_override or computed_mode

    programs = launch.get("program") or []

    provider_raw = dig(launch, "launch_service_provider", "name", default="Unknown")
    provider = normalize_org_name(provider_raw)

    agency = ""
    agencies = dig(launch, "mission", "agencies", default=[]) or []
    if agencies:
        raw_agency = dig(agencies[0], "name", default="")
        if raw_agency and raw_agency != provider_raw:
            agency = normalize_org_name(raw_agency)

    description = ""
    desc = dig(launch, "mission", "description", default="")
    if not is_placeholder(desc, launch.get("name", "")):
        description = desc.replace("\n", " ")[:600]

    program_description = ""
    if programs:
        p_desc = dig(programs[0], "description", default="")
        if not is_placeholder(p_desc):
            program_description = p_desc.replace("\n", " ")[:400]

    # A real mission patch is square by convention and fills a square box
    # nicely. The provider logo fallback is usually a wide wordmark, which
    # either distorts or shrinks to illegibility in the same box, so the
    # views need to know which one they were handed.
    image_url = ""
    image_is_patch = False
    patches = launch.get("mission_patches") or []
    if patches:
        image_url = dig(patches[0], "image_url", default="")
        image_is_patch = bool(image_url)
    if not image_url:
        image_url = dig(launch, "launch_service_provider", "logo_url", default="")
        image_is_patch = False

    pad_name = short_pad(dig(launch, "pad", "name", default="Unknown Pad"))
    if pad_name.isdigit():
        pad_name = f"Pad {pad_name}"
    loc_name = dig(launch, "pad", "location", "name", default="Unknown").split(",")[0].strip()
    country = dig(launch, "pad", "location", "country_code", default="")
    location_str = f"{pad_name} @ {loc_name}, {country}" if country else f"{pad_name} @ {loc_name}"

    stage = {}
    s_list = dig(launch, "rocket", "launcher_stage", default=[]) or []
    if s_list:
        stage = s_list[0] or {}
    landing = dig(stage, "landing", default={}) or {}
    attempt = landing.get("attempt")
    success = landing.get("success")
    l_loc = normalize_location_name(dig(landing, "location", "name", default="Unknown"))

    rocket_name = dig(launch, "rocket", "configuration", "name", default="Unknown Rocket")
    launch_name = launch.get("name") or rocket_name

    # --- footer: the recovery plan only, since the booster card carries the rest ---
    is_reusable = any(r in rocket_name.lower() for r in REUSABLE_ROCKETS)
    if not is_reusable or attempt is False:
        footer_recovery = "Single-use configuration. No recovery planned."
    elif l_loc == "Unknown":
        footer_recovery = "Recovery planned. Location to be confirmed."
    else:
        footer_recovery = f"Planned recovery at {l_loc}."

    fact_seed = str(launch.get("id") or launch_name)
    try:
        rocket_fact = get_rocket_fact(rocket_name, fact_seed)
    except Exception as e:
        print(f"Warning: fact generation failed for {rocket_name}: {e}")
        rocket_fact = "Rockets are cool."

    # --- booster career, cached so it costs nothing in the steady state ---
    history = None
    fleet = None
    if with_history:
        launcher = dig(stage, "launcher", default={}) or {}
        serial = launcher.get("serial_number")
        flights = launcher.get("flights")
        if serial:
            history = get_booster_history(serial, flights)
            if history:
                fleet = get_fleet(dig(launch, "rocket", "configuration", "id"))

    # --- the two variable slots ---
    slot_a, slot_b = build_slots(launch, mode, description, program_description,
                                 rocket_fact, history=history, fleet=fleet)

    vis_status = dig(launch, "status", "abbrev", default="TBD")
    if vis_status == "PENDING":
        vis_status = "AWAITING CONFIRMATION"
    mission_type = dig(launch, "mission", "type", default="")

    vis_url, vis_alt = get_rocket_image_url(rocket_name, vis_status, success, mission_type, launch_name, REPO_BASE)
    generic_url, _ = get_rocket_image_url("generic", vis_status, success, mission_type, launch_name, REPO_BASE)

    date_ts = int(target_dt.timestamp())
    w_start = parse_time(launch.get("window_start"))
    w_end = parse_time(launch.get("window_end"))
    win_start_ts = int(w_start.timestamp()) if w_start else date_ts
    win_end_ts = int(w_end.timestamp()) if w_end else date_ts

    # LL2 uses the literal string "Unknown" for an unknown orbit, which is
    # noise in a one line sidebar field. Fall back to the destination we do
    # know something about, or nothing at all.
    orbit_name = dig(launch, "mission", "orbit", "name", default="")
    if orbit_name.strip().lower() in ("", "unknown", "n/a", "tbd"):
        orbit_name = "TBD"

    m_name = launch_name.split(" | ")[-1]
    if "Unknown Payload" in m_name:
        m_name = rocket_name

    return {
        "mode": mode,
        "name": m_name,
        "agency": agency,
        "provider": provider,
        "location_str": location_str,
        "date_ts": date_ts,
        "window_start_ts": win_start_ts,
        "window_end_ts": win_end_ts,
        "countdown": get_countdown(target_dt),
        "status": dig(launch, "status", "abbrev", default="TBD"),
        "image": image_url,
        "image_is_patch": image_is_patch,
        "rocket": rocket_name,
        "orbit": orbit_name,

        # new: the two variable slots
        "slot_a_label": slot_a["label"],
        "slot_a_text": slot_a["text"],
        "slot_b_label": slot_b["label"],
        "slot_b_text": slot_b["text"],

        # new: footer is now just the recovery plan
        "footer_recovery": footer_recovery,

        "rocket_visual": vis_url,
        "rocket_visual_alt": vis_alt,
        "generic_visual": generic_url,

        # kept so the current template keeps working until you swap it
        "description": description,
        "program_description": program_description,
        "rocket_fact": rocket_fact,
        "footer_left": "",
        "footer_right": footer_recovery,
    }


# ============================================================
# which launch gets the screen
# ============================================================

def choose_target(previous, upcoming, now):
    """
    First match wins. Returns (launch, mode, reason).

    1. Next launch is imminent            -> show it
    2. Previous launch is unresolved      -> hold the result
    3. Previous launch is still fresh     -> hold the result
    4. Next is far off, previous recent   -> hold the result
    5. Otherwise                          -> show the upcoming launch
    """
    if previous and not upcoming:
        return previous, "POST_LAUNCH", "only a previous launch is available"
    if upcoming and not previous:
        return upcoming, "PRE_LAUNCH", "only an upcoming launch is available"

    prev_dt = parse_time(previous.get("net"))
    next_dt = parse_time(upcoming.get("net"))
    if prev_dt is None:
        return upcoming, "PRE_LAUNCH", "previous launch had no usable time"
    if next_dt is None:
        return previous, "POST_LAUNCH", "upcoming launch had no usable time"

    hours_since = (now - prev_dt).total_seconds() / 3600
    hours_until = (next_dt - now).total_seconds() / 3600
    print(f"Decision input: {hours_since:.1f}h since previous, {hours_until:.1f}h until next")

    if hours_until <= IMMINENT_HOURS:
        return upcoming, "PRE_LAUNCH", "next launch is imminent"
    if not is_resolved(previous):
        return previous, "POST_LAUNCH", "previous launch has no confirmed result yet"
    if hours_since < FRESH_HOURS:
        return previous, "POST_LAUNCH", "previous launch is still fresh"
    if hours_until > QUIET_HOURS and hours_since < STALE_HOURS:
        return previous, "POST_LAUNCH", "next launch is a long way off"
    return upcoming, "PRE_LAUNCH", "counting down to the next launch"


def strip_volatile(d):
    return {k: v for k, v in (d or {}).items() if k not in VOLATILE_FIELDS}


# ============================================================
# main
# ============================================================

def main():
    print("Loading launch data...")
    upcoming_results = load_json("upcoming.json")
    previous_results = load_json("previous.json")

    upcoming = upcoming_results[0] if upcoming_results else None
    next_upcoming = upcoming_results[1] if upcoming_results and len(upcoming_results) > 1 else None
    previous = previous_results[0] if previous_results else None

    if not upcoming and not previous:
        print("Error: no valid launch data available")
        return 0

    now = datetime.now(timezone.utc)
    target, mode, reason = choose_target(previous, upcoming, now)
    print(f"Selected: {mode} because {reason}")

    output = process_launch_data(target, mode, with_history=True)
    if not output:
        print("Error: failed to process launch data")
        return 0

    # Post-launch the footer becomes NEXT UP, so we need the following launch.
    if mode == "POST_LAUNCH":
        follow = next_upcoming if (target is upcoming and next_upcoming) else upcoming
        next_data = process_launch_data(follow, "PRE_LAUNCH")
        if next_data:
            output["next_name"] = next_data["name"]
            output["next_provider"] = next_data["provider"]
            output["next_rocket"] = next_data["rocket"]
            output["next_countdown"] = next_data["countdown"]
            output["next_status"] = next_data["status"]
            output["next_date_ts"] = next_data["date_ts"]
        else:
            print("Warning: could not build next launch data")

    # Skip writes that only move the countdown while we are post launch,
    # where the countdown is not displayed anyway.
    old = None
    if os.path.exists("launch.json"):
        try:
            with open("launch.json") as f:
                old = json.load(f)
        except Exception:
            old = None

    if old is not None and strip_volatile(old) == strip_volatile(output):
        if output["mode"] == "POST_LAUNCH":
            print("Only the countdown moved and we are post launch. Leaving launch.json alone.")
            return 0
        print("Only the countdown moved, but we are pre launch so the display needs it.")

    print(f"Writing launch.json for {output['name']}...")
    with open("launch.json", "w") as f:
        json.dump(output, f, separators=(",", ":"))
    print("Done.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        # Leave the existing launch.json in place rather than failing the run.
        print(f"Error: unexpected failure: {e}")
        sys.exit(0)
