#!/usr/bin/env python3
"""
Card checks against a corpus of real launches.

    python3 tests/test_cards.py           # run the checks
    python3 tests/test_cards.py --show    # print every distinct card

No test framework and no network: it walks tests/fixtures/launches.json, which
holds real API payloads (90 of them at the time of writing) pruned to the
fields cards.py reads -- see make_fixtures.py -- plus the handful of degenerate
payloads in EDGE_CASES below that live data rarely produces. Stdlib only, so it
runs anywhere the update workflow does.

What it is for. The cards are prose assembled from whatever the API happened to
send, and almost every bug found while writing them was a sentence that read
wrong rather than code that raised: "Russian Space Forces's 6th launch",
"Targeting Gulf of Mexico", "1 landings", "Unknown F9 is a brand new core",
"B1097's 12th flight" alongside "all thirteen of its landings". So the checks
here are mostly about the text: its punctuation, its length, and whether it
contradicts itself. They assert properties rather than exact strings, so
rewording a card does not break them -- use --show to read the corpus back and
judge the wording yourself, which is the part a test cannot do.

Each check was confirmed to fail by breaking cards.py in the way it is meant to
catch: reverting the possessive fix, unseeding pick(), letting a card skip
assemble(), inverting a tense branch, and so on -- 17 in all. A check that
cannot fail is worse than no check, so do that with any new one.

Two things the fixtures cannot pin down. Cards that phrase a duration from the
clock ("it last moved 5 days ago") drift as the frozen payloads age, and the
booster history and fleet caches come from boosters/, which the workflow
refreshes. Both are why nothing here is a golden snapshot.
"""

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cards as C  # noqa: E402  (after the path is set up)

FIXTURES = os.path.join(HERE, "fixtures", "launches.json")
BOOSTERS = os.path.join(ROOT, "boosters")

# Rotation points to render each launch at: inside the settle window, and out
# at the tiers that reach deeper into the ranked list.
HOURS = (None, 1, 9, 20, 40, 80)

# A stand-in for the trivia bank, so the DID YOU KNOW? fallback has something
# to return without pulling facts.py into the comparison.
FACT = "Ion thrusters produce about as much force as a sheet of paper weighs."

# A stand-in docking lookup, which is a live API call in the real pipeline.
DOCKING = {"hours_until": 22, "port": "Node 2 Forward", "spacecraft": "Dragon"}

# Nothing should ever reach the screen longer than this, whoever wrote it.
HARD_MAX = 400


class Failures:
    """Collects every failure instead of stopping at the first, because one
    bad phrasing usually means a dozen launches show it."""

    def __init__(self):
        self.items = []

    def check(self, ok, what, detail=""):
        if not ok:
            self.items.append(f"{what}\n      {detail}" if detail else what)
        return ok

    def report(self, name):
        if not self.items:
            print(f"  ok   {name}")
            return True
        print(f"  FAIL {name}")
        for item in self.items[:12]:
            print(f"    - {item}")
        if len(self.items) > 12:
            print(f"    ... and {len(self.items) - 12} more")
        return False


# Payloads the API rarely sends but the code has branches for, written by hand
# because waiting for a real launch to arrive with a pad LL2 cannot name is not
# a test strategy. Each one exists to reach a branch the live corpus misses:
# without the third entry, the pad card's tense could be broken on a thin
# payload and every check here would still pass.
EDGE_CASES = [
    # Nothing at all. The slot filler has to reach its fallback line.
    {"mode": "PRE_LAUNCH", "launch": {}},
    {"mode": "POST_LAUNCH", "launch": {}},
    # A pad with a count for this year but no lifetime total, resolved.
    {"mode": "POST_LAUNCH", "launch": {
        "id": "edge-pad-year-only", "name": "Thin | Pad Data",
        "status": {"abbrev": "Success"}, "net": "2026-09-01T00:00:00Z",
        "pad": {"name": "Launch Complex 39A"}, "pad_launch_attempt_count_year": 4,
        "launch_service_provider": {"name": "Some Agency"},
        "agency_launch_attempt_count_year": 4}},
    # The mirror image: a lifetime total with no count for this year.
    {"mode": "PRE_LAUNCH", "launch": {
        "id": "edge-pad-total-only", "name": "Thin | Pad Total",
        "status": {"abbrev": "Go"}, "net": "2026-09-01T00:00:00Z",
        "pad": {"name": "Space Launch Complex 6", "total_launch_count": 40}}},
    # First launch of the year from a named pad, still to fly.
    {"mode": "PRE_LAUNCH", "launch": {
        "id": "edge-pad-first", "name": "First | Of The Year",
        "status": {"abbrev": "Go"}, "net": "2026-09-01T00:00:00Z",
        "pad": {"name": "Launch Complex 1", "total_launch_count": 12},
        "pad_launch_attempt_count_year": 1}},
    # A provider whose name ends in s, resolved: the possessive case.
    {"mode": "POST_LAUNCH", "launch": {
        "id": "edge-possessive", "name": "Plural | Provider",
        "status": {"abbrev": "Failure"}, "net": "2026-09-01T00:00:00Z",
        "failreason": "Second stage failed to reach orbit",
        "launch_service_provider": {"name": "Russian Space Forces"},
        "agency_launch_attempt_count_year": 6,
        "agency_launch_attempt_count": 158,
        "rocket": {"configuration": {"name": "Soyuz 2.1b",
                                     "consecutive_successful_launches": 25}}}},
    # A pad and a core LL2 has no names for, and a landing site it does not
    # know either. None of these placeholders may reach the screen.
    {"mode": "PRE_LAUNCH", "launch": {
        "id": "edge-placeholders", "name": "Unknown | Everything",
        "status": {"abbrev": "TBD"}, "net": "2026-09-01T00:00:00Z",
        "pad": {"name": "Unknown Pad"}, "pad_launch_attempt_count_year": 17,
        "launch_service_provider": {"name": "SpaceX",
                                    "successful_landings": 674,
                                    "attempted_landings": 702},
        "rocket": {"launcher_stage": [{
            "launcher": {"serial_number": "Unknown F9"},
            "landing": {"attempt": True, "location": {"name": "N/A"}}}]}}},
    # A known core aiming at a landing site LL2 has not filled in. The
    # placeholder has to be dropped from the sentence, not printed in it --
    # and unlike the entry above, this core is named, so the card gets as far
    # as saying where it is going.
    {"mode": "PRE_LAUNCH", "launch": {
        "id": "edge-landing-na", "name": "Known | Core, Unknown Site",
        "status": {"abbrev": "Go"}, "net": "2026-09-01T00:00:00Z",
        "rocket": {"launcher_stage": [{
            "launcher_flight_number": 7,
            "launcher": {"serial_number": "B1099", "successful_landings": 6,
                         "attempted_landings": 6},
            "landing": {"attempt": True, "location": {"name": "N/A", "abbrev": "N/A"}}}]}}},
    # A splashdown zone, which needs its article.
    {"mode": "PRE_LAUNCH", "launch": {
        "id": "edge-splashdown", "name": "Water | Landing",
        "status": {"abbrev": "Go"}, "net": "2026-09-01T00:00:00Z",
        "rocket": {"launcher_stage": [{
            "reused": False, "launcher_flight_number": 1,
            "launcher": {"serial_number": "Booster 21"},
            "landing": {"attempt": True, "location": {"name": "Gulf of Mexico"}}}]}}},
]


def load_fixtures():
    """The live corpus, plus the hand-written edge cases."""
    if not os.path.exists(FIXTURES):
        sys.exit(f"no fixtures at {FIXTURES} -- run python3 tests/make_fixtures.py")
    with open(FIXTURES) as f:
        return json.load(f) + EDGE_CASES


def caches_for(launch):
    """The booster history and fleet list, as update_launch.py would pass them.

    Read from boosters/, so coverage of the career cards depends on which cores
    happen to be cached there. A launch with no cache still renders; its career
    card just stands down, which is the same thing that happens in production
    the first time a core flies.
    """
    serial = C.booster_serial(launch)
    if not serial:
        return None, None
    path = os.path.join(BOOSTERS, serial.replace("/", "_") + ".json")
    history = None
    if os.path.exists(path):
        with open(path) as f:
            history = json.load(f)

    fleet = None
    for name in sorted(glob.glob(os.path.join(BOOSTERS, "_fleet_*.json"))):
        with open(name) as f:
            cores = (json.load(f) or {}).get("cores")
        if cores:
            fleet = cores
            break
    return history, fleet


def descriptions(launch):
    """The two text fields, pre-processed exactly as update_launch.py does."""
    desc = (C.dig(launch, "mission", "description", default="") or "")
    programs = launch.get("program") or []
    pdesc = (C.dig(programs[0], "description", default="") if programs else "") or ""
    return (C.clip(desc.replace("\n", " "), 600),
            C.clip(pdesc.replace("\n", " "), 400))


def slots_for(launch, mode, hours):
    """(slot_a, slot_b) at one rotation point, pre- or post-launch."""
    history, fleet = caches_for(launch)
    desc, pdesc = descriptions(launch)
    return C.build_slots(
        launch, mode, desc, pdesc, FACT, history=history, fleet=fleet,
        hours_until=hours if mode == "PRE_LAUNCH" else None,
        hours_since=hours if mode == "POST_LAUNCH" else None,
        docking=DOCKING)


def generated_cards(launch, mode):
    """Only the cards this repo writes itself, keyed by function name.

    The pass-through cards are excluded on purpose: the mission brief and the
    programme blurb are the API's prose and the orbit notes are hand-written
    constants, so the sentence-shape rules below are not theirs to obey.
    """
    history, fleet = caches_for(launch)
    out = {
        "cadence": C.cadence_card(launch),
        "outlook": C.outlook_card(launch, mode),
        "booster": C.booster_card(launch, mode),
        "career": C.booster_career_card(launch, history, fleet),
        "pad": C.pad_card(launch),
        "next": C.booster_next_card(launch, history),
        "record": C.record_card(launch, history),
        "docking": C.docking_card(launch, DOCKING),
    }
    return {k: v for k, v in out.items() if v}


# ============================================================
# checks
# ============================================================

def check_renders(fixtures):
    """Every launch renders in both slots at every rotation point."""
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        name = launch.get("name", "?")
        for hours in HOURS:
            try:
                slot_a, slot_b = slots_for(launch, mode, hours)
            except Exception as e:
                f.check(False, f"{name} at {hours}h raised",
                        f"{type(e).__name__}: {e}")
                continue
            # Slot A always says something: its last resort is the fallback
            # line, so an empty slot A means the priority list fell through.
            f.check(bool(slot_a.get("text")), f"{name} at {hours}h: slot A empty")
            # A label with no text, or text with no label, renders as a
            # stray heading or an orphan paragraph.
            for which, slot in (("A", slot_a), ("B", slot_b)):
                f.check(bool(slot.get("text")) == bool(slot.get("label")),
                        f"{name} at {hours}h: slot {which} half filled",
                        f"{slot!r}")
    return f.report(f"renders every launch at {len(HOURS)} rotation points")


def check_deterministic(fixtures):
    """The same launch renders identically twice.

    The display refreshes every 15 minutes and the workflow commits the result,
    so wording that varied per run would flicker on screen and write a commit
    each time. `pick` is seeded from the launch for exactly this reason.
    """
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        for hours in HOURS:
            first = slots_for(launch, mode, hours)
            second = slots_for(launch, mode, hours)
            f.check(first == second, f"{launch.get('name','?')} at {hours}h varies",
                    f"{first}\n      {second}")
    return f.report("renders the same launch identically twice")


def check_no_repeats(fixtures):
    """Slot A and slot B never show the same card."""
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        for hours in HOURS:
            slot_a, slot_b = slots_for(launch, mode, hours)
            if slot_a.get("text") and slot_b.get("text"):
                f.check(slot_a["text"] != slot_b["text"],
                        f"{launch.get('name','?')} at {hours}h shows one card twice",
                        slot_a["text"][:90])
                f.check(slot_a["label"] != slot_b["label"],
                        f"{launch.get('name','?')} at {hours}h repeats a label",
                        slot_a["label"])
    return f.report("never shows the same card in both slots")


def check_rotates(fixtures):
    """A display left on for two days does not show one pairing the whole time.

    Only launches with enough cards to rotate are asked: build_slots keeps the
    canonical pair when there is nothing behind it, which is correct.
    """
    f = Failures()
    asked = 0
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        available = len(generated_cards(launch, mode))
        if available < 4:
            continue
        asked += 1
        seen = {(slot_a.get("label"), slot_b.get("label"))
                for slot_a, slot_b in (slots_for(launch, mode, h) for h in HOURS)}
        f.check(len(seen) > 1, f"{launch.get('name','?')} never rotates",
                f"{available} cards available, one pairing shown at every tier")
    f.check(asked > 0, "no launch had enough cards to test rotation")
    return f.report(f"rotates the pairing over time ({asked} launches)")


def check_lengths(fixtures):
    """Generated cards respect the budget; nothing at all is absurd."""
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        for key, text in generated_cards(launch, mode).items():
            # assemble() lets a single sentence through over budget rather
            # than dropping the card, so a one-sentence card is exempt.
            sentences = len(split_sentences(text))
            f.check(len(text) <= C.CARD_BUDGET or sentences == 1,
                    f"{key} over budget at {len(text)} chars", text)
        for hours in HOURS:
            for slot in slots_for(launch, mode, hours):
                text = slot.get("text") or ""
                f.check(len(text) <= HARD_MAX,
                        f"{slot.get('label')} at {len(text)} chars", text[:120])
    return f.report(f"keeps generated cards within {C.CARD_BUDGET} characters")


def split_sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?…]) ", text) if s.strip()]


def check_prose(fixtures):
    """
    The sentence-level rules, over every card the repo writes.

    Each of these has a bug behind it. The possessive one is "Russian Space
    Forces's"; the "None" one is a format string reached with a value the guard
    above it did not cover; the repeated-opener one is a card that read "That
    was the 44th launch ... That was the 221st orbital launch attempt".
    """
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        for key, text in generated_cards(launch, mode).items():
            where = f"{key} ({launch.get('name','?')})"
            f.check("  " not in text, f"{where}: double space", text)
            f.check(not re.search(r"\s[.,;:]", text), f"{where}: space before punctuation", text)
            f.check(text[0].isupper() or text[0].isdigit(), f"{where}: lowercase opener", text)
            f.check(text.endswith((".", "!", "?", "…")), f"{where}: unterminated", text)
            f.check("None" not in text, f"{where}: leaked a None", text)
            f.check("s's" not in text, f"{where}: awkward possessive", text)
            # Placeholders the API uses when it knows nothing. None of them
            # mean anything to a reader.
            for junk in ("Unknown Pad", "N/A", "TBD", "Unknown F9", "Unknown FH"):
                f.check(junk not in text, f"{where}: shows the placeholder {junk!r}", text)

            sentences = split_sentences(text)
            openers = [" ".join(s.split()[:2]).lower().rstrip(",") for s in sentences]
            repeated = {o for o in openers if openers.count(o) > 1 and o != "it is"}
            f.check(not repeated, f"{where}: repeats the opening {repeated}", text)
    return f.report("writes clean sentences")


# A place name sitting straight after a preposition, so "on the Gulf of Mexico"
# does not match while "on Gulf of Mexico" does. The name may carry lowercase
# connectors ("Gulf of Mexico"), which is why they are spelled out here: a
# pattern that stopped at the first lowercase word captured only "Gulf" and
# then found nothing wrong with it.
BARE_PLACE = re.compile(
    r"\b(?:to|for|on|at|into)\s+"
    r"([A-Z][\w'-]*(?:\s+(?:of|the|de|del|[A-Z][\w'-]*)){0,3})")


def check_articles(fixtures):
    """
    Bodies of water keep their article.

    LL2 names a splashdown zone "Gulf of Mexico", and dropping it into a
    sentence verbatim produced "It is aiming for Gulf of Mexico" -- grammatical
    nonsense of the specific kind that tells a reader a machine wrote this.
    """
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        for key, text in generated_cards(launch, mode).items():
            for match in BARE_PLACE.finditer(text):
                place = match.group(1).strip()
                f.check(not C.ARTICLE_PLACE_RE.search(place),
                        f"{key}: {place!r} is missing its article", text)
    return f.report("gives bodies of water their article")


# Phrases that can only be said about a launch that has not happened. None of
# them are about wording, so rewording a card does not put them at risk.
FORWARD_LOOKING = (
    "is aiming for", "is targeting", "will be", "is flying back",
    "so far this year", "is unconfirmed", "no confirmed launch time",
    "it is the ", "is up to",
)


def check_tense(fixtures):
    """
    A finished launch is not described in the future.

    The file draws this line with is_resolved(), which is deliberately not the
    same as POST_LAUNCH mode: a launch that is In Flight has happened but has
    no result yet. Every card that switches tense reads that flag, and getting
    one of them backwards puts "It is the 229th orbital launch attempt of the
    year" under a card headed MISSION RECAP.
    """
    f = Failures()
    checked = 0
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        if not C.is_resolved(launch):
            continue
        checked += 1
        for key, text in generated_cards(launch, mode).items():
            low = text.lower()
            for phrase in FORWARD_LOOKING:
                f.check(phrase not in low,
                        f"{key}: {phrase!r} on a launch that has already flown", text)
    f.check(checked > 0, "no resolved launches in the fixtures to check tense against")
    return f.report(f"uses the past tense on finished launches ({checked} launches)")


# The pad card's two figures, found independently of the order they appear in.
# pad_card picks between several phrasings, so matching whole sentences meant
# the check quietly skipped whichever wording it had not been taught -- which
# is how a contradiction slipped past it once already.
PAD_YEAR = re.compile(r"(\d+) launches(?: from [^,.]+?)? this year|(\d+) of them this year")
PAD_TOTAL = re.compile(r"(\d+)(?: launches)?(?: have left [^,.]+?)? (?:since it opened|in its lifetime)")


def pad_figures(text):
    """(this year, lifetime) from a rendered pad card, either value None."""
    def first(match):
        return int(next(g for g in match.groups() if g)) if match else None
    return first(PAD_YEAR.search(text)), first(PAD_TOTAL.search(text))


def check_contradictions(fixtures):
    """
    Statements inside one card that cannot all be true.

    Every rule here is a shape of wrong the API can hand us rather than a
    mistake in arithmetic: LL2's launcher record is a live career total while
    the flight number is this flight's index, it reports a lifetime pad total
    below that pad's own count for this year, and the success streak it sends
    was counted before the launch it is attached to.
    """
    f = Failures()
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        name = launch.get("name", "?")
        cards = generated_cards(launch, mode)

        # A booster on its Nth flight cannot have landed more than N times.
        text = cards.get("booster")
        if text:
            flight = re.search(r"(\d+)(?:st|nd|rd|th) (?:flight|time)", text)
            landings = re.search(
                r"(?:Perfect (\d+) for|stuck all (\d+)|its (\d+) landings)", text)
            if flight and landings:
                n = int(flight.group(1))
                got = int(next(g for g in landings.groups() if g))
                f.check(got <= n, f"{name}: {got} landings on flight {n}", text)

        # A pad cannot have flown fewer launches in its life than this year.
        text = cards.get("pad")
        if text:
            year, total = pad_figures(text)
            if year is not None and total is not None:
                f.check(year <= total,
                        f"{name}: {year} launches this year out of {total} ever", text)

        # A launch that failed did not leave a success streak intact.
        if C.dig(launch, "status", "abbrev", default="") in ("Failure", "Partial Failure"):
            for key, text in cards.items():
                f.check("streak" not in text and "has not lost" not in text
                        and "has failed in" not in text,
                        f"{name}: {key} claims a success streak on a failed launch", text)
    return f.report("never states two things that cannot both be true")


def check_fixture_shape(fixtures):
    """
    The fixtures still carry every field the cards read.

    The fixtures are pruned, so a card that starts reading a new API field
    would quietly see None here and the corpus would stop covering it. This
    catches the common case -- a key named in cards.py that make_fixtures.py
    has never heard of -- by comparing the key literals in the source against
    the pruning shape.

    It is a reminder, not a proof: it matches key names wherever they appear in
    the shape rather than by their full path, so a genuinely new field on a
    nested object still needs adding to SHAPE by hand.
    """
    f = Failures()
    sys.path.insert(0, HERE)
    import make_fixtures

    def shape_keys(shape, into):
        if isinstance(shape, dict):
            for k, sub in shape.items():
                into.add(k)
                shape_keys(sub, into)
        elif isinstance(shape, list):
            shape_keys(shape[0], into)
        return into

    known = shape_keys(make_fixtures.SHAPE, set())
    # Keys of the caches and lookups this repo builds itself, which are not
    # API launch fields and so are not in the pruning shape.
    known |= {"serial", "launches", "cores", "flights", "hours_until", "port",
              "spacecraft", "pad", "net", "name"}

    with open(os.path.join(ROOT, "scripts", "cards.py")) as fh:
        source = fh.read()
    used = set(re.findall(r'\bdig\([^)]*?((?:"[a-z_]+"\s*,\s*)*"[a-z_]+")', source))
    literals = set()
    for group in used:
        literals |= set(re.findall(r'"([a-z_]+)"', group))
    literals |= set(re.findall(r'\.get\("([a-z_]+)"', source))

    for key in sorted(literals - known):
        f.check(False, f"cards.py reads {key!r}, which the fixtures prune away",
                "add it to SHAPE in tests/make_fixtures.py and regenerate")
    return f.report(f"fixtures cover the {len(literals)} fields the cards read")


# ============================================================
# --show
# ============================================================

def show(fixtures):
    """Print every distinct card, to read the wording back."""
    by_kind = {}
    for row in fixtures:
        launch, mode = row["launch"], row["mode"]
        for key, text in generated_cards(launch, mode).items():
            by_kind.setdefault(key, {}).setdefault(text, launch.get("name", "?"))
        for hours in HOURS:
            for slot in slots_for(launch, mode, hours):
                if slot.get("text"):
                    by_kind.setdefault("_" + slot["label"], {}) \
                           .setdefault(slot["text"], launch.get("name", "?"))

    for kind in sorted(by_kind):
        if kind.startswith("_"):
            continue
        print(f"\n=== {kind} ({len(by_kind[kind])} distinct) " + "=" * 30)
        for text in sorted(by_kind[kind]):
            print(f"  [{len(text):3}] {text}")

    lengths = sorted(len(t) for k, v in by_kind.items()
                     if not k.startswith("_") for t in v)
    if lengths:
        print(f"\n{len(lengths)} distinct generated cards | "
              f"median {lengths[len(lengths) // 2]} | max {lengths[-1]}")


def main(argv):
    fixtures = load_fixtures()
    print(f"{len(fixtures)} launches: {len(fixtures) - len(EDGE_CASES)} from "
          f"{os.path.relpath(FIXTURES, ROOT)}, {len(EDGE_CASES)} hand-written")

    if "--show" in argv:
        show(fixtures)
        return 0

    checks = [check_renders, check_deterministic, check_no_repeats,
              check_rotates, check_lengths, check_prose, check_articles,
              check_tense, check_contradictions, check_fixture_shape]
    passed = [check(fixtures) for check in checks]
    failed = passed.count(False)
    print(f"\n{len(passed) - failed}/{len(passed)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
