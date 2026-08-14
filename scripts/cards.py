"""
Card text generation for the mission control TRMNL plugin.

Two ideas hold this together:

1. Every fragment is a COMPLETE sentence with its own guard. Fragments are
   collected into a list and joined. Because none of them depends on its
   neighbours, any subset joins into correct English. There is no way to
   produce "Last flew , 26 days ago." because the version of the sentence
   with the missing value is never added.

2. Each card can return None, meaning "I have nothing useful". The slot
   filler walks a priority list and takes the first card that returns text,
   so a launch with sparse data degrades instead of printing blanks.
"""

import re


# ============================================================
# small helpers
# ============================================================

def dig(d, *keys, default=None):
    """Walk nested dicts safely. Treats an explicit null like a missing key."""
    for k in keys:
        if not isinstance(d, dict):
            return default
        d = d.get(k)
    return default if d is None else d


def ordinal(n):
    """1 -> 1st, 11 -> 11th, 21 -> 21st, 23 -> 23rd"""
    n = int(n)
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def plural(n, word, suffix="s"):
    """1 day / 2 days"""
    n = int(n)
    return f"{n} {word}" if n == 1 else f"{n} {word}{suffix}"


def ago(days):
    """A day count written the way a person would say it."""
    days = int(days)
    if days <= 0:
        return "earlier today"
    if days == 1:
        return "yesterday"
    if days < 60:
        return f"{days} days ago"
    months = round(days / 30.0)
    return f"about {plural(months, 'month')} ago"


def parse_iso_duration(s):
    """'P3DT12H11M45S' -> (3, 12) as days and hours. None if unparseable."""
    if not s:
        return None
    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", str(s))
    if not m:
        return None
    d, h = int(m.group(1) or 0), int(m.group(2) or 0)
    return (d, h)


def gap_phrase(days, hours):
    """A pad turnaround, written naturally."""
    if days == 0 and hours == 0:
        return "hours after the last one"
    if days == 0:
        return f"just {plural(hours, 'hour')} after the last one"
    if days == 1:
        return "a day after the last one"
    if days < 7:
        return f"{plural(days, 'day')} after the last one"
    return f"{plural(days, 'day')} since the last one"


NUM_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
             7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven",
             12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
             16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen",
             20: "twenty"}


def num_word(n):
    """Small numbers read better as words in prose."""
    return NUM_WORDS.get(int(n), str(int(n)))


def join_list(items):
    """['a', 'b', 'c'] -> 'a, b, and c'. Handles one and two item lists."""
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# Mission families worth naming. Anything unmatched is counted as "other".
MISSION_FAMILIES = [
    "Starlink", "Transporter", "Bandwagon", "NROL", "Crew", "Cargo Dragon",
    "SDA Tranche", "Globalstar", "O3b", "Galileo", "Kuiper", "OneWeb",
    "Axiom", "SES", "Intelsat", "Eutelsat", "GPS", "USSF", "Koreasat",
]


def mission_family(name):
    n = (name or "").strip().lower()
    for fam in MISSION_FAMILIES:
        if n.startswith(fam.lower()):
            return fam
    return None


def days_between(iso_a, iso_b):
    """Whole days between two ISO timestamps. None if either is unusable."""
    from datetime import datetime
    try:
        a = datetime.fromisoformat(str(iso_a).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(iso_b).replace("Z", "+00:00"))
        return abs((b - a).days)
    except (ValueError, TypeError):
        return None


def short_pad(name):
    return (name or "").replace("Space Launch Complex ", "SLC-").replace("Launch Complex ", "LC-")


# ============================================================
# is the mission description worth showing?
# ============================================================

def is_boilerplate(launch, description):
    """
    True when the description is really about the programme rather than this
    flight. Catches Starlink, Kuiper, OneWeb, Guowang and anything else where
    the constellation name is also the mission name.
    """
    if not description or not description.strip():
        return True

    programs = launch.get("program") or []
    if programs:
        pname = (dig(programs[0], "name", default="") or "").strip().lower()
        mname = (launch.get("name") or "").lower()
        if pname and len(pname) > 3 and pname in mname:
            return True

    # A description that is basically the programme blurb adds nothing.
    if programs:
        pdesc = (dig(programs[0], "description", default="") or "").strip().lower()
        if pdesc and pdesc[:60] and pdesc[:60] in description.lower():
            return True

    return False


# ============================================================
# cards
# ============================================================

def cadence_card(launch):
    """Where this launch sits in the year. The reliable floor: almost never None."""
    provider = dig(launch, "launch_service_provider", "name", default="")
    year_n = launch.get("agency_launch_attempt_count_year")
    all_n = launch.get("agency_launch_attempt_count")
    pad_year = launch.get("pad_launch_attempt_count_year")
    world_year = launch.get("orbital_launch_attempt_count_year")
    pad = short_pad(dig(launch, "pad", "name", default=""))
    rocket = dig(launch, "rocket", "configuration", "name", default="")
    streak = dig(launch, "rocket", "configuration", "consecutive_successful_launches")
    turnaround = parse_iso_duration(launch.get("pad_turnaround"))

    parts = []

    if provider and year_n:
        if all_n:
            parts.append(f"{provider}'s {ordinal(year_n)} launch of the year, {ordinal(all_n)} all time.")
        else:
            parts.append(f"{provider}'s {ordinal(year_n)} launch of the year.")

    # A busy pad and a quiet pad tell opposite stories, so the wording switches.
    if pad_year and pad:
        if pad_year == 1:
            parts.append(f"First flight from {pad} this year.")
        elif turnaround:
            d, h = turnaround
            parts.append(f"{ordinal(pad_year)} from {pad} this year, {gap_phrase(d, h)}.")
        else:
            parts.append(f"{ordinal(pad_year)} from {pad} this year.")

    if world_year:
        parts.append(f"The {ordinal(world_year)} orbital launch attempt worldwide this year.")

    if streak and streak > 20 and rocket:
        parts.append(f"{rocket} is on a {streak} flight success streak.")

    return " ".join(parts) if parts else None


# LL2 net_precision abbrevs that mean the T-0 is softer than it looks.
VAGUE_PRECISION = {
    "HOUR": "The T-0 is only firm to the hour.",
    "DAY": "Only the launch day is set, so the time will move.",
    "WEEK": "Scheduled to the week, with no firm time yet.",
    "MONTH": "Scheduled to the month, with no firm date yet.",
    "QUARTER": "Only the quarter is set.",
    "YEAR": "Only the year is set.",
}

SCHEDULE_HINTS = (
    "now targeting", "moved", "delayed", "slipped", "scrubbed", "postponed",
    "rescheduled", "reverted", "pushed", "updated launch window", "tweaked t-0",
)


def is_schedule_change(comment):
    """LL2 writes slips several ways, including a bare 'NET August.'"""
    low = (comment or "").lower().strip()
    return low.startswith("net ") or any(h in low for h in SCHEDULE_HINTS)


def outlook_card(launch, mode):
    """
    Pre-launch only. How much to trust the countdown.
    Returns None on a clean launch, which is the common case and correct:
    there is no value in printing "everything is fine".
    """
    if mode != "PRE_LAUNCH":
        return None

    parts = []

    status = dig(launch, "status", "abbrev", default="")
    if status == "TBC":
        parts.append("The T-0 is unconfirmed.")
    elif status == "TBD":
        parts.append("No confirmed launch time yet.")

    note = VAGUE_PRECISION.get((dig(launch, "net_precision", "abbrev", default="") or "").upper())
    if note:
        parts.append(note)

    # Slip history is the best predictor of another slip.
    updates = launch.get("updates") or []
    changes = [u for u in updates if is_schedule_change(u.get("comment"))]
    if len(changes) >= 2:
        first = min((u.get("created_on") or "")[:4] for u in changes)
        n = len(changes)
        if first and first.isdigit() and int(first) < 2026:
            parts.append(f"This one has moved {n} times since it was first scheduled in {first}.")
        else:
            parts.append(f"This one has already moved {n} times.")

    prob = launch.get("probability")
    if isinstance(prob, int) and prob >= 0:
        if prob >= 80:
            parts.append(f"Weather is {prob}% favourable.")
        elif prob >= 50:
            parts.append(f"Weather sits at {prob}% favourable.")
        else:
            parts.append(f"Weather is only {prob}% favourable.")

    concerns = (launch.get("weather_concerns") or "").strip()
    if concerns:
        parts.append(f"Forecasters are watching {concerns.rstrip('.').lower()}.")

    hold = (launch.get("holdreason") or "").strip()
    if hold:
        parts.append(f"Currently holding: {hold.rstrip('.')}.")

    return " ".join(parts) if parts else None


def booster_card(launch, mode):
    """
    This specific core's story. None when there is no reusable stage,
    which is most non-SpaceX launches.
    """
    stages = dig(launch, "rocket", "launcher_stage", default=[]) or []
    if not stages:
        return None
    stage = stages[0] or {}

    launcher = dig(stage, "launcher", default={}) or {}
    serial = dig(launcher, "serial_number", default="")
    if not serial:
        return None

    flight_n = stage.get("launcher_flight_number")
    succ = launcher.get("successful_landings")
    att = launcher.get("attempted_landings")
    turn = stage.get("turn_around_time_days")
    prev = dig(stage, "previous_flight", "name", default="")
    landing = dig(stage, "landing", default={}) or {}
    l_loc = dig(landing, "location", "abbrev", default="") or dig(landing, "location", "name", default="")
    l_type = dig(landing, "type", "abbrev", default="")
    dist = landing.get("downrange_distance")
    attempt = landing.get("attempt")
    success = landing.get("success")
    provider = dig(launch, "launch_service_provider", "name", default="")

    # Mission names arrive as "Falcon 9 Block 5 | Starlink Group 17-40"
    if prev and " | " in prev:
        prev = prev.split(" | ")[-1]

    parts = []

    # 1. Identity
    if flight_n == 1 or (flight_n is None and not stage.get("reused")):
        parts.append(f"{serial} is a brand new core.")
    elif flight_n:
        parts.append(f"{serial} on its {ordinal(flight_n)} flight.")
    else:
        parts.append(f"Flying booster {serial}.")

    # 2. Landing record. Never claim perfection on a flight we know was lost.
    if att and att > 0 and succ is not None:
        if succ == att and success is not False:
            parts.append(f"Perfect {succ} for {succ} on landings.")
        elif succ < att:
            parts.append(f"{succ} of {att} landings stuck.")

    # 3. Where it has been
    if prev and turn:
        parts.append(f"Last flew {prev} {ago(turn)}.")
    elif turn:
        parts.append(f"Back on the pad {ago(turn)}.")
    elif prev:
        parts.append(f"Last flew {prev}.")

    # 4. Where it is going, or where it went.
    # RTLS distances are fractions of a km, so rounding them reads as a bug.
    is_rtls = (l_type == "RTLS") or (dist is not None and dist < 5)
    if attempt is False:
        parts.append("Expended on this flight, with no recovery planned.")
    elif l_loc:
        if mode == "POST_LAUNCH" and success:
            if is_rtls:
                parts.append(f"Flew itself back to {l_loc}.")
            elif dist:
                parts.append(f"Down on {l_loc}, {int(dist)} km downrange.")
            else:
                parts.append(f"Down on {l_loc}.")
        elif mode == "POST_LAUNCH" and success is False:
            parts.append(f"Lost on the way back to {l_loc}.")
        elif is_rtls:
            parts.append(f"Flying back to {l_loc} rather than a drone ship.")
        elif dist:
            parts.append(f"Targeting {l_loc}, {int(dist)} km downrange.")
        else:
            parts.append(f"Targeting {l_loc}.")

    # 5. Floor. If we learned almost nothing, borrow an always-present stat.
    if len(parts) < 2:
        a_succ = dig(launch, "launch_service_provider", "successful_landings")
        a_att = dig(launch, "launch_service_provider", "attempted_landings")
        if provider and a_succ and a_att:
            parts.append(f"{provider} has landed {a_succ} of {a_att} boosters.")

    return " ".join(parts) if parts else None


def booster_label(launch):
    """Dynamic slot label, e.g. 'BOOSTER B1103'."""
    stages = dig(launch, "rocket", "launcher_stage", default=[]) or []
    serial = dig(stages[0] if stages else {}, "launcher", "serial_number", default="")
    return f"BOOSTER {serial}" if serial else "BOOSTER"


def booster_career_card(launch, history=None, fleet=None):
    """
    The booster's career rather than this one flight. Needs the cached
    history from history.py, so it returns None until that exists.
    """
    if not history or not history.get("launches"):
        return None

    serial = history.get("serial") or ""
    flights = history.get("launches") or []
    n = len(flights)
    if n < 3:
        # One or two flights is not a career worth summarising.
        return None

    parts = []

    # 1. Span. How long it has been flying, and how often.
    span = days_between(flights[0]["net"], flights[-1]["net"])
    if span and span > 60:
        months = round(span / 30.0)
        parts.append(f"{serial} has flown {num_word(n)} times over {plural(months, 'month')}.")
    else:
        parts.append(f"{serial} has flown {num_word(n)} times.")

    # 2. Mission mix. Grouped by family so it reads as a career, not a list.
    counts = {}
    for f in flights:
        fam = mission_family(f.get("name")) or "other"
        counts[fam] = counts.get(fam, 0) + 1

    named = sorted(((k, v) for k, v in counts.items() if k != "other"),
                   key=lambda kv: -kv[1])
    if named:
        top_fam, top_n = named[0]
        if top_n == n:
            # A single-purpose core. Listing one item as a breakdown reads badly.
            parts.append(f"Every one of those was a {top_fam} mission.")
        elif top_n >= n - 1:
            parts.append(f"All but {plural(n - top_n, 'flight')} were {top_fam} missions.")
        else:
            bits = [f"{num_word(v)} {k}" for k, v in named[:3]]
            leftover = n - sum(v for _, v in named[:3])
            if leftover > 0:
                bits.append(f"{num_word(leftover)} other")
            parts.append(f"Its flights break down as {join_list(bits)}.")

    # 3. Personal best turnaround.
    gaps = []
    for i in range(1, len(flights)):
        g = days_between(flights[i - 1]["net"], flights[i]["net"])
        if g is not None and g > 0:
            gaps.append(g)
    if gaps:
        parts.append(f"Its quickest turnaround was {plural(min(gaps), 'day')}.")

    # 4. Pad spread. Only interesting when it has moved around.
    pads = {f.get("pad") for f in flights if f.get("pad")}
    if len(pads) >= 3:
        parts.append(f"It has flown from {num_word(len(pads))} different pads.")

    # 5. Fleet rank. The best line available, when we have the fleet list.
    if fleet and serial:
        ahead = sum(1 for c in fleet if c.get("flights", 0) > n)
        if ahead == 0:
            parts.append("No core in the fleet has flown more.")
        elif ahead <= 4:
            parts.append(f"Only {num_word(ahead)} cores in the fleet have flown more.")

    return " ".join(parts) if len(parts) >= 2 else None


def career_label(history):
    serial = (history or {}).get("serial") or ""
    return f"{serial} CAREER" if serial else "BOOSTER CAREER"


def program_card(launch, program_description):
    return program_description.strip() if program_description and program_description.strip() else None


def pad_card(launch):
    """Placeholder. Needs the cached pad history endpoint, built later."""
    return None


# ============================================================
# slot selection
# ============================================================

def build_slots(launch, mode, description, program_description, rocket_fact,
                history=None, fleet=None):
    """
    Returns (slot_a, slot_b), each a dict with 'label' and 'text'.
    A card claimed by slot A is skipped by slot B, so nothing appears twice.
    """
    brief = None if is_boilerplate(launch, description) else description.strip()

    cards = {
        "brief":   ("MISSION BRIEF", brief),
        "booster": (booster_label(launch), booster_card(launch, mode)),
        "career":  (career_label(history), booster_career_card(launch, history, fleet)),
        "pad":     ("PAD HISTORY", pad_card(launch)),
        "program": ("PROGRAM CONTEXT", program_card(launch, program_description)),
        "outlook": ("LAUNCH OUTLOOK", outlook_card(launch, mode)),
        "cadence": ("LAUNCH CADENCE", cadence_card(launch)),
        "fact":    ("DID YOU KNOW?", (rocket_fact or "").strip() or None),
    }

    order_a = ["brief", "booster", "pad", "program"]
    # Slot A usually takes the booster, which leaves the career for slot B.
    # When slot A takes a real mission brief instead, the booster wins slot B
    # and the career stands down. That is deliberate: this flight matters more
    # than the back catalogue.
    if mode == "PRE_LAUNCH":
        order_b = ["outlook", "booster", "career", "cadence", "fact"]
    else:
        order_b = ["booster", "career", "cadence", "fact"]

    used = set()

    def take(order):
        for key in order:
            if key in used:
                continue
            label, text = cards[key]
            if text:
                used.add(key)
                return {"label": label, "text": text}
        return None

    slot_a = take(order_a) or {
        "label": "MISSION STATUS",
        "text": "Specific details are currently classified or unavailable.",
    }
    slot_b = take(order_b) or {"label": "", "text": ""}

    return slot_a, slot_b
