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
from datetime import datetime, timedelta, timezone


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
    try:
        a = datetime.fromisoformat(str(iso_a).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(iso_b).replace("Z", "+00:00"))
        return abs((b - a).days)
    except (ValueError, TypeError):
        return None


def short_pad(name):
    return (name or "").replace("Space Launch Complex ", "SLC-").replace("Launch Complex ", "LC-")


# ============================================================
# junk detection
# ============================================================

# Things the API says when it has nothing to say. Matched after lowercasing
# and stripping trailing punctuation, so "Details TBD." catches on "details tbd".
PLACEHOLDER_TEXT = (
    "tbd", "details tbd", "details are tbd", "to be determined",
    "unknown", "details unknown", "payload unknown", "unknown payload",
    "no description", "no description available", "n/a", "na", "none",
    "information unavailable", "no information", "not available",
    "classified", "details forthcoming",
)

# Shortest description that could plausibly say something. "Yaogan-42 remote
# sensing satellite." is 35 characters and is legitimate, so the floor sits
# below that. Anything under it is a stub rather than a brief.
MIN_USEFUL_CHARS = 25


def is_placeholder(text, name=""):
    """
    True when a description field is a stub rather than actual content.

    The old check compared against the literal string "TBD", so "Details TBD."
    passed straight through and rendered as a mission brief.
    """
    if not text:
        return True

    t = text.strip().rstrip(".!").strip().lower()
    if not t:
        return True

    if t in PLACEHOLDER_TEXT:
        return True

    # "Details TBD" and friends, wherever the stub phrase sits in a short string
    if len(t) < 60:
        for p in PLACEHOLDER_TEXT:
            if p in t and len(t) - len(p) < 15:
                return True

    # A description that only restates the mission name tells you nothing
    if name and t == name.strip().rstrip(".").lower():
        return True

    return len(t) < MIN_USEFUL_CHARS


# ============================================================
# is the mission description worth showing?
# ============================================================

# Programmes that fly often enough that their blurb stops being news. Not a
# judgement on the programme, just on how many times you have read the same
# sentence: Starlink alone is roughly 40% of world launches.
HIGH_CADENCE_PROGRAMS = (
    "starlink", "kuiper", "oneweb", "guowang", "satnet", "qianfan",
    "thousand sails", "transporter", "bandwagon",
)


def is_boilerplate(launch, description):
    """
    True when the description is really about the programme rather than this
    flight. Catches Starlink, Kuiper, OneWeb, Guowang and anything else where
    the constellation name is also the mission name.
    """
    if is_placeholder(description, launch.get("name", "")):
        return True

    programs = launch.get("program") or []
    if programs:
        pname = (dig(programs[0], "name", default="") or "").strip().lower()
        mname = (launch.get("name") or "").lower()
        # Only for programmes that fly constantly. This used to fire on ANY
        # name match, which quietly binned the mission brief for Artemis II,
        # Shenzhou 22 and Gaofen 14: their names contain the programme name
        # but they fly rarely and their descriptions are real. The signal
        # that makes a blurb worthless is frequency, not naming.
        # Match on significant words, not the whole string: the programme is
        # "Project Kuiper" while the mission is "Kuiper Atlas 3", so a plain
        # substring test misses it.
        pwords = [w for w in pname.split() if len(w) > 3]
        if pwords and any(w in mname for w in pwords):
            if any(h in pname for h in HIGH_CADENCE_PROGRAMS):
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


def _iso(value):
    """Parse an LL2 timestamp, or None. Never raises."""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _ago(dt, now=None):
    """'4 days ago', 'yesterday', 'this morning'. None if undatable."""
    if dt is None:
        return None
    now = now or datetime.now(timezone.utc)
    try:
        days = (now - dt).total_seconds() / 86400.0
    except TypeError:
        return None
    if days < 0:
        return None
    if days < 0.5:
        return "in the last few hours"
    if days < 1.5:
        return "yesterday"
    if days < 14:
        return f"{int(round(days))} days ago"
    if days < 60:
        return f"{int(round(days / 7))} weeks ago"
    return f"{int(round(days / 30))} months ago"


def outlook_card(launch, mode):
    """
    Pre-launch only. How much to trust the countdown.
    Returns None on a clean launch, which is the common case and correct:
    there is no value in printing "everything is fine".

    The card only earns a slot when it has something real to say. A single
    slip on its own is not news; two or more, a hold, an unconfirmed T-0 or
    a weather call are.
    """
    if mode != "PRE_LAUNCH":
        return None

    parts = []
    strong = False   # does this card deserve to outrank the fallbacks?

    status = dig(launch, "status", "abbrev", default="")
    if status == "TBC":
        parts.append("The T-0 is unconfirmed.")
        strong = True
    elif status == "TBD":
        parts.append("No confirmed launch time yet.")
        strong = True

    note = VAGUE_PRECISION.get((dig(launch, "net_precision", "abbrev", default="") or "").upper())
    if note:
        parts.append(note)
        strong = True

    # Slip history is the best predictor of another slip. Two or more is a
    # pattern; one is just a launch.
    updates = launch.get("updates") or []
    changes = [u for u in updates if is_schedule_change(u.get("comment"))]
    if len(changes) >= 2:
        strong = True
        first = min((u.get("created_on") or "")[:4] for u in changes)
        n = len(changes)
        if first and first.isdigit() and int(first) < 2026:
            parts.append(f"This one has moved {n} times since it was first scheduled in {first}.")
        else:
            parts.append(f"This one has already moved {n} times.")

        # When it last moved matters as much as how often. A launch that
        # slipped four times but has held for a fortnight is in better shape
        # than one that moved this morning.
        latest = max((_iso(u.get("created_on")) for u in changes if _iso(u.get("created_on"))),
                     default=None)
        when = _ago(latest)
        if when:
            if status == "Go":
                parts.append(f"The current time was set {when} and has held since.")
            else:
                parts.append(f"It last moved {when}.")

    prob = launch.get("probability")
    if isinstance(prob, int) and prob >= 0:
        strong = True
        if prob >= 80:
            parts.append(f"Weather is {prob}% favourable.")
        elif prob >= 50:
            parts.append(f"Weather sits at {prob}% favourable.")
        else:
            parts.append(f"Weather is only {prob}% favourable.")

    concerns = (launch.get("weather_concerns") or "").strip()
    if concerns:
        strong = True
        parts.append(f"Forecasters are watching {concerns.rstrip('.').lower()}.")

    hold = (launch.get("holdreason") or "").strip()
    if hold:
        strong = True
        parts.append(f"Currently holding: {hold.rstrip('.')}.")

    # The launch window is context rather than a warning, so it never makes
    # the card strong on its own, but it adds substance when the card exists.
    if parts:
        ws = _iso(launch.get("window_start"))
        we = _iso(launch.get("window_end"))
        if ws and we:
            mins = (we - ws).total_seconds() / 60.0
            if mins <= 1:
                parts.append("The window is instantaneous, so it goes on time or not at all.")
            elif mins < 60:
                # Sub-hour windows are common and were silently skipped by an
                # earlier version of this rule, which only handled the two
                # extremes. A 37 minute window is worth saying out loud.
                parts.append(f"The window is only {int(round(mins))} minutes wide.")
            else:
                hours = mins / 60.0
                shown = int(hours) if abs(hours - round(hours)) < 0.1 else round(hours, 1)
                parts.append(f"There is a {shown} hour window to work with.")

    if not parts or not strong:
        return None
    return " ".join(parts)


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


def booster_serial(launch):
    """Just the serial, or empty. Used by the new card labels."""
    stages = dig(launch, "rocket", "launcher_stage", default=[]) or []
    return dig(stages[0] if stages else {}, "launcher", "serial_number", default="")


def booster_career_card(launch, history=None, fleet=None):
    """
    The booster's career rather than this one flight. Needs the cached
    history from history.py, so it returns None until that exists.
    """
    if not history or not history.get("launches"):
        return None

    serial = history.get("serial") or ""
    all_flights = history.get("launches") or []

    # The API returns upcoming launches too, so drop anything that has not
    # happened yet. Otherwise a booster still on the pad gets credited with
    # a flight it has not made.
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    flights = []
    for f in all_flights:
        try:
            when = datetime.fromisoformat(str(f.get("net")).replace("Z", "+00:00"))
            if when <= now:
                flights.append(f)
        except (ValueError, TypeError):
            continue

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
                noun = "other" if leftover == 1 else "others"
                bits.append(f"{num_word(leftover)} {noun}")
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
    """
    Context on the wider programme, for launches where that is not already
    obvious from the mission name.

    This used to be a bare passthrough, which meant the exact text
    is_boilerplate had just rejected as a mission brief came straight back
    under a different heading. A Starlink launch printed "Starlink is a
    satellite internet constellation operated by SpaceX" as PROGRAM CONTEXT,
    which is the least informative sentence the plugin can produce.

    Three ways a programme blurb earns nothing:

      1. The programme name is in the mission name. "Starlink Group 10-39"
         already says Starlink. So does Kuiper, OneWeb and Transporter.
      2. It repeats the mission description we are already showing.
      3. The programme flies constantly. Frequency is the real signal here:
         the blurb is worth reading the first time and worthless the
         fortieth, and how often you have seen it tracks how often that
         programme launches.
    """
    text = (program_description or "").strip()
    if not text:
        return None

    programs = launch.get("program") or []
    pname = (dig(programs[0], "name", default="") if programs else "") or ""
    pname = pname.strip().lower()
    mname = (launch.get("name") or "").lower()

    # 1. The mission name already carries the programme name AND the
    #    description was boilerplate, so there is nothing else being shown
    #    and the blurb would be the only thing on screen saying the same
    #    word twice.
    #
    #    Conditioning on the description matters: "Artemis II" contains
    #    "Artemis", but Artemis flies once a year or two and its blurb is
    #    real context alongside a real mission description. A blanket
    #    name-match test suppressed it, which was wrong.
    if pname and len(pname) > 3 and pname in mname:
        if is_boilerplate(launch, dig(launch, "mission", "description", default="") or ""):
            return None

    # 2. the same text as the description already on screen
    desc = (dig(launch, "mission", "description", default="") or "").lower()
    if desc and text[:60].lower() in desc:
        return None

    # 3. high-cadence programmes. These fly often enough that the blurb is
    #    familiar long before it is useful, and none of them are mysterious.
    if pname and any(h in pname for h in HIGH_CADENCE_PROGRAMS):
        return None

    return text


ORBIT_NOTES = {
    "low earth orbit": (
        "Low Earth orbit is anywhere from about 160 to 2,000 km up, where a "
        "satellite laps the planet roughly every 90 minutes. Everything there "
        "is falling; it just keeps missing the ground."
    ),
    "sun-synchronous orbit": (
        "A sun-synchronous orbit is tilted so the satellite crosses the equator "
        "at the same local time on every pass. Shadows fall the same way in "
        "every image, which is why almost all Earth-observation satellites use it."
    ),
    "geostationary transfer orbit": (
        "A transfer orbit is a long ellipse. Over the coming weeks the satellite "
        "raises its own low point until the whole orbit sits 36,000 km up, where "
        "one lap takes exactly a day and it appears to hover over one spot."
    ),
    "geosynchronous orbit": (
        "At 36,000 km a satellite takes exactly one day to circle the Earth, so "
        "it hangs over the same patch of ground and a dish on the roof can be "
        "bolted in place and never moved again."
    ),
    "medium earth orbit": (
        "Medium Earth orbit sits between the low satellites and the "
        "geostationary belt. It is where navigation constellations live, high "
        "enough that a handful of satellites cover the whole planet at once."
    ),
    "polar orbit": (
        "A polar orbit passes near both poles, so as the planet turns beneath "
        "it the satellite eventually flies over every point on the surface."
    ),
    "highly elliptical orbit": (
        "A highly elliptical orbit loiters for hours near its high point and "
        "whips through the low one in minutes, which gives long coverage of "
        "high latitudes that a geostationary satellite cannot see well."
    ),
    "trans lunar injection": (
        "A trans-lunar injection is the burn that stops the spacecraft orbiting "
        "Earth and sends it out to meet the Moon, a trip of about three days."
    ),
    "heliocentric orbit": (
        "This one leaves Earth behind entirely and goes into orbit around the "
        "Sun, which is where every interplanetary mission starts."
    ),
    "suborbital": (
        "A suborbital flight goes up and comes back down without ever going "
        "fast enough sideways to stay up. Altitude is the easy part; speed is "
        "what orbit actually costs."
    ),
}


def _flight_gaps(history):
    """Days between consecutive flights of this core, derived the same way
    the career card does it. The cache stores flights, not gaps."""
    # The cache stores the flight list under "launches"; "flights" is an
    # integer count, and reading that one instead is what produced
    # "object of type 'int' has no len()".
    flights = (history or {}).get("launches") or []
    if not isinstance(flights, list):
        return []
    gaps = []
    for i in range(1, len(flights)):
        g = days_between(flights[i - 1].get("net"), flights[i].get("net"))
        if g is not None and g > 0:
            gaps.append(g)
    return gaps


def destination_card(launch):
    """What the orbit actually means. No API call: a lookup on the orbit
    name we already fetch. Works before and after launch."""
    orbit = (dig(launch, "mission", "orbit", "name", default="") or "").strip().lower()
    if not orbit or orbit in ("unknown", "n/a", "tbd"):
        return None
    if orbit in ORBIT_NOTES:
        return ORBIT_NOTES[orbit]
    for key, text in ORBIT_NOTES.items():
        if key in orbit or orbit in key:
            return text
    return None


def pad_card(launch):
    """What this pad has been doing. Both figures are already in the payload."""
    pad = short_pad(dig(launch, "pad", "name", default="")) or "This pad"
    year = dig(launch, "pad_launch_attempt_count_year", default=None)
    total = dig(launch, "pad", "total_launch_count", default=None)
    parsed = parse_iso_duration(launch.get("pad_turnaround"))
    turn = parsed[0] + parsed[1] / 24.0 if parsed else None

    parts = []
    if isinstance(year, int) and year > 1:
        parts.append(f"{year} launches from {pad} so far this year.")
    elif isinstance(total, int) and total > 1:
        parts.append(f"{pad} has supported {total} launches.")
    else:
        return None

    if isinstance(total, int) and total > 1 and parts and "supported" not in parts[0]:
        parts.append(f"{total} in total since it opened.")
    if turn is not None and turn >= 0:
        if turn < 1:
            parts.append("It turned around in under a day.")
        elif turn < 10:
            parts.append(f"It turns around in about {int(round(turn))} days.")
    return " ".join(parts) if parts else None


def booster_next_card(launch, history):
    """When this core is likely to fly again, from its own cached record."""
    stage = (dig(launch, "rocket", "launcher_stage", default=[]) or [{}])[0]
    serial = dig(stage, "launcher", "serial_number", default="")
    if not serial or not history:
        return None
    gaps = _flight_gaps(history)
    if len(gaps) < 2:
        return None

    avg = sum(gaps) / len(gaps)
    best = min(gaps)
    parts = [f"{serial} has averaged {int(round(avg))} days between flights, "
             f"with a best of {int(round(best))}."]

    # A date beats a duration: "around mid October" is something you can read,
    # where "in about 43 days" is arithmetic. Counted from THIS launch, not
    # from now, so the answer does not drift as the card sits on screen.
    #
    # An earlier version restated the average here ("within about 43 days"),
    # which repeated the number in the first sentence and misused a mean as
    # an upper bound: by definition half its flights take longer than that.
    when = _iso(launch.get("net"))
    if when is not None:
        try:
            nxt = when + timedelta(days=avg)
            day = nxt.day
            part = "early" if day <= 10 else ("mid" if day <= 20 else "late")
            parts.append(f"On that form it should fly again around {part} "
                         f"{nxt.strftime('%B')}.")
        except (OverflowError, ValueError):
            pass
    return " ".join(parts)


def record_card(launch, history):
    """Did this flight set a personal best for the core? Fires rarely, which
    is what makes it worth showing when it does."""
    stage = (dig(launch, "rocket", "launcher_stage", default=[]) or [{}])[0]
    serial = dig(stage, "launcher", "serial_number", default="")
    turn = dig(stage, "turn_around_time_days", default=None)
    if not serial or not history or not isinstance(turn, (int, float)):
        return None
    gaps = _flight_gaps(history)
    if len(gaps) < 2:
        return None

    # The current flight's own gap is in the cached list, so comparing
    # against min(gaps) compares the flight with itself and every flight
    # looks like a record. Exclude gaps at or below this one first.
    previous = [g for g in gaps if g > turn]
    flights = dig(stage, "launcher", "flights", default=None)

    if previous and len(previous) == len(gaps):
        saved = min(previous) - turn
        return (f"That was {serial}'s fastest turnaround yet: {int(round(turn))} days, "
                f"{int(round(saved))} quicker than its previous best.")
    if isinstance(flights, int) and flights >= 20:
        return (f"{serial} has now flown {flights} times, putting it among the "
                f"most-flown rockets ever built.")
    return None


def docking_card(launch, docking):
    """For ISS-bound flights: when the spacecraft actually arrives. Needs the
    one extra /docking_event/ lookup passed in from the caller."""
    if not docking:
        return None
    when = docking.get("hours_until")
    port = docking.get("port") or ""
    craft = docking.get("spacecraft") or "The spacecraft"
    if when is None:
        return None
    if when < 0:
        return f"{craft} is already docked at {port}." if port else None
    if when < 1:
        timing = "within the hour"
    elif when < 48:
        timing = f"in about {int(round(when))} hours"
    else:
        timing = f"in about {int(round(when / 24))} days"
    tail = f", docking at {port}" if port else ""
    return (f"{craft} catches up with the station {timing}{tail}. Rendezvous is a "
            f"slow chase: the station will not wait, so the spacecraft has to "
            f"arrive in the same place at the same speed.")


# ============================================================
# slot selection
# ============================================================

# ============================================================
# card rotation
# ============================================================

SETTLE_HOURS = 8      # pre-launch: inside this, always the canonical pair
ROTATE_EVERY = 6      # pre-launch: hours per tier beyond that
POST_SETTLE_HOURS = 2 # post-launch: the result holds the screen this long
POST_ROTATE_HOURS = 2 # post-launch: hours per pairing

# Pre-launch tiers. Tier 0 is closest to launch and always the canonical
# pair, so the run up to a launch is untouched. Later tiers are further out
# and reach deeper into the ranked list. Monotonic by design: content only
# ever gets more important as T-0 approaches.
# Slot B order behind a pinned mission brief. Explicit rather than derived:
# the docking countdown is the most time-critical thing on a crewed flight,
# a record is rare enough to lead with, and the evergreen explainers sit
# behind the things that are specific to this launch.
POST_ROTATION = ["docking", "record", "dest", "pad", "next", "fact"]

ROTATION_SCHEDULE = [
    (0, 1),   # inside SETTLE_HOURS
    (0, 2),
    (1, 3),
    (2, 4),
    (3, 5),
    (4, 5),   # furthest out: the deep cuts
]


def rotation_tier(hours_until):
    """Which pre-launch tier applies."""
    if hours_until is None or hours_until <= SETTLE_HOURS:
        return 0
    tier = int((hours_until - SETTLE_HOURS) // ROTATE_EVERY) + 1
    return min(tier, len(ROTATION_SCHEDULE) - 1)


def post_pair(n, hours_since):
    """
    Post-launch indexes into the ranked list.

    Nothing is approaching, so the monotonic logic that governs the run up
    to a launch has nothing to say here. Instead the pairing simply cycles,
    which at a two hour step works through every card several times during
    the roughly 22 hours a result stays on screen at current launch cadence.
    """
    if n < 2:
        return 0, 0
    if hours_since is None or hours_since <= POST_SETTLE_HOURS:
        return 0, 1
    idx = int((hours_since - POST_SETTLE_HOURS) // POST_ROTATE_HOURS) + 1
    return (2 * idx) % n, (2 * idx + 1) % n


def build_slots(launch, mode, description, program_description, rocket_fact,
                history=None, fleet=None, hours_until=None, hours_since=None,
                docking=None):
    """
    Returns (slot_a, slot_b), each a dict with 'label' and 'text'.
    A card claimed by slot A is skipped by slot B, so nothing appears twice.

    When a launch is more than SETTLE_HOURS away, the pairing rotates through
    the deeper cards so a display watched over two days does not show the same
    two cards the whole time. Everything shown is still about the launch in
    the header; only which cards are chosen changes.
    """
    brief = None if is_boilerplate(launch, description) else description.strip()

    cards = {
        "brief":   ("MISSION BRIEF", brief),
        "booster": (booster_label(launch), booster_card(launch, mode)),
        "career":  (career_label(history), booster_career_card(launch, history, fleet)),
        "pad":     ("PAD HISTORY", pad_card(launch)),
        "dest":    ("DESTINATION EXPLAINED", destination_card(launch)),
        "next":    (f"{booster_serial(launch) or 'BOOSTER'} NEXT", booster_next_card(launch, history)),
        "record":  ("A RECORD", record_card(launch, history)),
        "docking": ("NEXT MILESTONE", docking_card(launch, docking)),
        "program": ("PROGRAM CONTEXT", program_card(launch, program_description)),
        "outlook": ("LAUNCH OUTLOOK", outlook_card(launch, mode)),
        "cadence": ("LAUNCH CADENCE", cadence_card(launch)),
        "fact":    ("DID YOU KNOW?", (rocket_fact or "").strip() or None),
    }

    # Cadence and fact sit at the end as real fallbacks. Without them a
    # launch with a stub description dropped straight to the hardcoded
    # "details unavailable" line, which is just a different stub. Better to
    # promote a card that always has something to say.
    order_a = ["brief", "booster", "pad", "program", "cadence", "fact"]
    if mode == "POST_LAUNCH":
        order_a = ["brief", "booster", "docking", "record", "dest",
                   "pad", "program", "cadence", "fact"]
    # Slot A usually takes the booster, which leaves the career for slot B.
    # When slot A takes a real mission brief instead, the booster wins slot B
    # and the career stands down. That is deliberate: this flight matters more
    # than the back catalogue.
    if mode == "PRE_LAUNCH":
        # Outlook normally sits AFTER the booster cards: "this has moved
        # twice" is thinner than a named booster on its 18th flight.
        #
        # But a BRAND NEW core has no history to tell. "ZQ-3 F2 is a brand
        # new core" is thinner than a slip record, so on a first flight the
        # order flips and outlook goes first. This is the Zhuque-3 case.
        first_flight = True
        try:
            stage = (dig(launch, "rocket", "launcher_stage", default=[]) or [{}])[0]
            flights = dig(stage, "launcher", "flights", default=None)
            n = dig(stage, "launcher_flight_number", default=None)
            first_flight = not ((isinstance(flights, int) and flights > 1)
                                or (isinstance(n, int) and n > 1))
        except (IndexError, TypeError, AttributeError):
            pass

        if first_flight:
            order_b = ["career", "outlook", "booster", "cadence", "fact"]
        else:
            order_b = ["booster", "career", "outlook", "cadence", "fact"]
    else:
        # Post-launch the interesting question is what happens NEXT to the
        # hardware and the payload, so the forward-looking cards rank above
        # the fallbacks.
        order_b = ["docking", "record", "career", "next", "dest",
                   "pad", "cadence", "fact"]

    used = set()
    picked = []

    def take(order):
        for key in order:
            if key in used:
                continue
            label, text = cards[key]
            if text:
                used.add(key)
                picked.append(key)
                return {"label": label, "text": text}
        picked.append(None)
        return None

    slot_a = take(order_a) or {
        "label": "MISSION STATUS",
        "text": "Specific details are currently classified or unavailable.",
    }
    slot_b = take(order_b) or {"label": "", "text": ""}

    def as_slot(key):
        label, text = cards[key]
        return {"label": label, "text": text}

    # ---- rotation ----
    ranked = [k for k in picked if k]
    for key in order_a + order_b:
        if key in ranked:
            continue
        if cards[key][1]:
            ranked.append(key)

    # ---- what stays put, and what rotates under it ----
    #
    # POST-LAUNCH, a real mission description holds slot A outright, crewed
    # or not. Pre-launch the monotonic tiers bring the brief back as T-0
    # approaches, so rotating it out is temporary; after launch nothing is
    # approaching, so a rotated-out brief would never return, and "what was
    # this thing for" is the question that outlives the countdown.
    #
    # A boilerplate description never becomes the brief card in the first
    # place, so a Starlink has nothing to pin and rotates both slots freely.
    if mode == "POST_LAUNCH" and cards["brief"][1]:
        rest = [k for k in POST_ROTATION if cards[k][1]]
        if not rest:
            return as_slot("brief"), {"label": "", "text": ""}
        if hours_since is None or hours_since <= POST_SETTLE_HOURS:
            step = 0
        else:
            step = int((hours_since - POST_SETTLE_HOURS) // POST_ROTATE_HOURS)
        return as_slot("brief"), as_slot(rest[step % len(rest)])

    if len(ranked) < 3:
        return slot_a, slot_b

    if mode == "PRE_LAUNCH":
        tier = rotation_tier(hours_until)
        if tier == 0:
            return slot_a, slot_b
        a_i, b_i = ROTATION_SCHEDULE[tier]
        a_i = min(a_i, len(ranked) - 1)
        b_i = min(b_i, len(ranked) - 1)
    else:
        a_i, b_i = post_pair(len(ranked), hours_since)

    if a_i == b_i:
        b_i = a_i - 1 if a_i > 0 else 1
        b_i = min(b_i, len(ranked) - 1)

    return as_slot(ranked[a_i]), as_slot(ranked[b_i])
