#!/usr/bin/env python3
"""
Checks for the display data around the cards: the TRMNL X destination panel,
its footer, and when launch.json is rewritten.

    python3 tests/test_display.py

Stdlib only and no network, like test_cards.py. The launches come from the
same corpus, tests/fixtures/launches.json. The docking events are two real
LL2 records in tests/fixtures/docking_events.json, and both belong to
launches in that corpus (Crew-13 and CRS-35), so the lookup is tested
against real data rather than a payload written to pass.

What changes between cases is the clock and the launch status. Holding the
payload still and moving the clock past the docking time is the only way to
check "a docking time in the past is not proof of docking" without waiting
for a real docking to happen.
"""

import copy
import json
import os
import sys
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cards as C  # noqa: E402
import history as H  # noqa: E402
import update_launch as U  # noqa: E402

from test_cards import Failures, descriptions, FACT, caches_for, pad_year_for  # noqa: E402

FIXTURES = os.path.join(HERE, "fixtures", "launches.json")
DOCKINGS = os.path.join(HERE, "fixtures", "docking_events.json")

CREW_13 = "18441371-8b2e-457c-afb5-1ec1b11ab630"
CRS_35 = "bf2c3027-a314-403e-a416-2bfd5d165ad1"


def load():
    with open(FIXTURES) as f:
        rows = json.load(f)
    with open(DOCKINGS) as f:
        dockings = json.load(f)
    return rows, dockings


def by_id(rows, launch_id):
    return next(r["launch"] for r in rows if r["launch"].get("id") == launch_id)


def at(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def with_status(launch, abbrev):
    out = copy.deepcopy(launch)
    out["status"] = {"abbrev": abbrev, "name": abbrev}
    return out


def eligible_upcoming(rows):
    """Upcoming launches the footer may promote, by the documented rule."""
    out = []
    for r in rows:
        l = r["launch"]
        if r["mode"] != "PRE_LAUNCH":
            continue
        prec = C.dig(l, "net_precision", "abbrev", default="")
        if prec in ("SEC", "MIN", "HR") and C.dig(l, "status", "abbrev") in ("Go", "TBC", "TBD"):
            out.append(l)
    return out


# ============================================================
# checks
# ============================================================

def check_docking_match(rows, dockings):
    """The docking event is found by launch id, and never by an empty name."""
    f = Failures()
    event = dockings["results"][0]
    docked = at(event["docking"])
    before = docked - timedelta(hours=6)

    d = H.match_docking(dockings, "Crew Dragon Grace", CREW_13, before)
    f.check(d and d["event_id"] == 644, "Crew-13 finds its own docking event", d)
    f.check(d and d["docking_ts"] == int(docked.timestamp()),
            "the raw docking time is kept, not rebuilt from hours", d)
    f.check(d and d["port"] == "Harmony forward" and
            d["station"] == "International Space Station", "port and station kept", d)

    # The id wins over the name: CRS-35's Dragon must not answer for Crew-13.
    d = H.match_docking(dockings, "Cargo Dragon C211", CREW_13, before)
    f.check(d and d["event_id"] == 644, "a launch id beats a misleading name", d)

    d = H.match_docking(dockings, "", CRS_35, at(dockings["results"][1]["docking"]) - timedelta(hours=1))
    f.check(d and d["event_id"] == 645, "a flight with no spacecraft name finds it by id", d)

    d = H.match_docking(dockings, "", None, before)
    f.check(d is None, "no name and no id matches nothing", d)

    d = H.match_docking(dockings, "Crew Dragon Grace", "not-a-launch-id", before)
    f.check(d is None, "an id that matches no event is not rescued by the name", d)

    return f.report("finds the docking event by launch id")


def check_footer_lifecycle(rows, dockings):
    """The paired states: one launch, one docking, the status and clock moved."""
    f = Failures()
    crew = by_id(rows, CREW_13)
    candidates = eligible_upcoming(rows)
    docked = at(dockings["results"][0]["docking"])
    before, after = docked - timedelta(hours=6), docked + timedelta(hours=1)
    # Candidates still in the future at both clock points.
    later = [c for c in candidates if at(c["net"]) > after]
    f.check(bool(later), "the corpus has a launch to promote", "")

    def footer(status, mode, now, docking_now=None):
        launch = with_status(crew, status)
        docking = H.match_docking(dockings, "Crew Dragon Grace", CREW_13, docking_now or now)
        return U.choose_footer(launch, mode, docking, later, now)

    for status in ("Go", "TBD"):
        got = footer(status, "PRE_LAUNCH", before)
        f.check(got == {}, f"pre-launch ({status}) has no footer", got)

    for status in ("In Flight", "PENDING", "Success"):
        got = footer(status, "POST_LAUNCH", before)
        f.check(got.get("footer_kind") == "docking",
                f"{status}: an upcoming docking wins the footer", got)
        f.check(got.get("footer_label", "").startswith("NEXT MILESTONE"),
                f"{status}: a docking is not labelled as a launch", got.get("footer_label"))
        f.check("ISS" in got.get("footer_title", "") and "Grace" in got.get("footer_title", ""),
                f"{status}: names the spacecraft and the station", got.get("footer_title"))
        f.check(not got.get("footer_rocket") and not got.get("footer_provider"),
                f"{status}: no next-launch field rides along with a docking", got)

    for status in ("Failure", "Partial Failure"):
        got = footer(status, "POST_LAUNCH", before)
        f.check(got.get("footer_kind") == "launch",
                f"{status}: a failed flight keeps no docking appointment", got)

    got = footer("Success", "POST_LAUNCH", after)
    f.check(got.get("footer_kind") == "launch",
            "a docking time now past gives the footer back to the next launch", got)

    got = U.choose_footer(with_status(crew, "Success"), "POST_LAUNCH", None, later, before)
    f.check(got.get("footer_kind") == "launch", "no docking data falls back to the next launch", got)

    got = U.choose_footer(with_status(crew, "Success"), "POST_LAUNCH", None, [], before)
    f.check(got == {}, "no docking and no next launch: no footer", got)

    # A non-ISS launch never gets a docking footer, even handed one.
    other = next(r["launch"] for r in rows
                 if r["mode"] == "POST_LAUNCH" and not C.is_iss_bound(r["launch"]))
    docking = H.match_docking(dockings, "Crew Dragon Grace", CREW_13, before)
    got = U.choose_footer(other, "POST_LAUNCH", docking, later, before)
    f.check(got.get("footer_kind") != "docking", "only an ISS-bound flight gets the docking", got)

    return f.report("footer follows the launch lifecycle")


def check_next_launch(rows):
    """A next launch is promoted only with real timing, and as one event."""
    f = Failures()
    upcoming = [r["launch"] for r in rows if r["mode"] == "PRE_LAUNCH"]
    shown = 0
    for l in upcoming:
        net = at(l["net"])
        got = U.launch_footer([l], net - timedelta(hours=3))
        prec = C.dig(l, "net_precision", "abbrev", default="")
        ok = prec in ("SEC", "MIN", "HR") and C.dig(l, "status", "abbrev") in ("Go", "TBC", "TBD")
        f.check(bool(got) == ok, f"{l['name']}: promoted only with timing ({prec})", got)
        if got:
            shown += 1
            f.check(got["footer_ts"] == int(net.timestamp()) and
                    got["footer_title"] == U.display_name(l) and
                    got["footer_event_id"] == l["id"] and
                    got["footer_rocket"] == C.dig(l, "rocket", "configuration", "name") and
                    got["footer_location"] == U.location_string(l) and
                    got["footer_provider"] == U.normalize_org_name(
                        C.dig(l, "launch_service_provider", "name", default="")),
                    f"{l['name']}: every footer field is from the same launch", got)
            f.check(got["footer_countdown"].startswith("T- "),
                    f"{l['name']}: counts down, not up", got["footer_countdown"])
        late = U.launch_footer([l], net + timedelta(minutes=1))
        f.check(late == {}, f"{l['name']}: no countdown once its time has passed", late)

    # An ineligible launch is skipped for the next eligible one, not shown.
    vague = [l for l in upcoming if C.dig(l, "net_precision", "abbrev") in ("M", "Q4")]
    good = eligible_upcoming(rows)
    if vague and good:
        now = min(at(vague[0]["net"]), at(good[0]["net"])) - timedelta(hours=1)
        got = U.launch_footer([vague[0], good[0]], now)
        f.check(got.get("footer_event_id") == good[0]["id"],
                "a month-precision NET is skipped for the next real one", got)
    f.check(shown > 0, "the corpus exercises a promoted launch", "")
    return f.report(f"promotes a next launch only with real timing ({shown} launches)")


def check_writes(rows):
    """A countdown on screen is written as it moves; one off screen is not."""
    f = Failures()
    base = {"mode": "POST_LAUNCH", "name": "x", "countdown": "T+ 01h 00m",
            "next_countdown": "T- 05h 00m"}
    f.check(not U.needs_write(base, dict(base, countdown="T+ 01h 15m",
                                          next_countdown="T- 04h 45m")),
            "post-launch, no footer: a moving countdown alone is not written")
    footed = dict(base, footer_kind="launch", footer_countdown="T- 05h 00m")
    f.check(U.needs_write(footed, dict(footed, footer_countdown="T- 04h 45m")),
            "post-launch with a footer: its moving countdown is written")
    f.check(not U.needs_write(footed, dict(footed, countdown="T+ 01h 15m")),
            "post-launch with a footer: the hidden header countdown alone is not")
    pre = {"mode": "PRE_LAUNCH", "name": "x", "countdown": "T- 02h 00m"}
    f.check(U.needs_write(pre, dict(pre, countdown="T- 01h 45m")),
            "pre-launch: the header countdown is written")
    f.check(U.needs_write(footed, dict(footed, footer_kind="", footer_countdown="")),
            "the footer going away is written")
    f.check(U.needs_write(None, base), "a first run is written")
    return f.report("writes exactly when something on screen moved")


def check_destination(rows):
    """The panel's name and explanation, and the X slots that make room for it."""
    f = Failures()
    iss = 0
    for r in rows:
        launch, mode = r["launch"], r["mode"]
        orbit = C.dig(launch, "mission", "orbit", "name", default="") or ""
        label = C.destination_label(launch, orbit)
        if C.is_iss_bound(launch):
            iss += 1
            f.check(label == "International Space Station",
                    f"{launch['name']}: an ISS flight shows the station", label)
        else:
            f.check(label == orbit, f"{launch['name']}: others show the orbit", label)

        text = C.destination_explanation(launch)
        if orbit.lower() in ("", "unknown", "tbd", "n/a") and not C.is_iss_bound(launch):
            f.check(not text, f"{launch['name']}: no filler for an unknown orbit", text)
        if text:
            f.check(text[-1] in ".!?", f"{launch['name']}: explanation is a sentence", text)
            f.check(len(text) <= C.PANEL_NOTE_MAX,
                    f"{launch['name']}: explanation fits the panel ({len(text)})", text)

        desc, pdesc = descriptions(launch)
        for hours in (None, 1, 9, 20, 40, 80):
            kw = dict(hours_until=hours if mode == "PRE_LAUNCH" else None,
                      hours_since=hours if mode == "POST_LAUNCH" else None)
            og = C.build_slots(launch, mode, desc, pdesc, FACT, **kw)
            dest = C.destination_card(launch)
            lg = C.build_slots(launch, mode, desc, pdesc, FACT, exclude=["dest"], **kw)
            for slot in lg:
                f.check(not dest or slot["text"] != dest,
                        f"{launch['name']}: the X slots never repeat the panel", slot)
            f.check(lg[0]["text"] != lg[1]["text"] or not lg[0]["text"],
                    f"{launch['name']}: the X slots differ from each other", lg)
            again = C.build_slots(launch, mode, desc, pdesc, FACT, **kw)
            f.check(og == again, f"{launch['name']}: the OG slots are untouched", og)
    f.check(iss > 0, "the corpus has ISS flights", "")
    return f.report(f"destination panel and X slots ({iss} ISS flights)")


def check_panel_variants(rows):
    """Every destination note fits, and the clock walks a launch through all of them."""
    f = Failures()
    pools = list(C.PANEL_NOTES.items()) + [("iss", C.ISS_NOTES)]
    for key, notes in pools:
        f.check(len(notes) >= 2, f"{key}: has variants to rotate", notes)
        f.check(len(set(notes)) == len(notes), f"{key}: variants are distinct", notes)
        for text in notes:
            f.check(len(text) <= C.PANEL_NOTE_MAX, f"{key}: fits the panel ({len(text)})", text)
            # The note sits right under the destination's name; opening by
            # saying the name again ("Low Earth Orbit / Low Earth orbit
            # starts...") is the echo that makes it read machine-written.
            heading = "international space station" if key == "iss" else key
            f.check(heading not in text.lower()[:40],
                    f"{key}: does not open by repeating its heading", text)
            f.check(text[-1] in ".!?", f"{key}: is a sentence", text)
    f.check(len(C.PANEL_NOTES["low earth orbit"]) >= 5,
            "low Earth orbit, where most launches go, has the most variants", "")

    step = timedelta(hours=C.PANEL_ROTATE_HOURS)
    t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
    starts = set()
    for r in rows:
        launch = r["launch"]
        pool = C._panel_variants(launch)
        if not pool:
            continue
        seen = [C.destination_explanation(launch, t0 + i * step) for i in range(len(pool))]
        f.check(set(seen) == set(pool),
                f"{launch['name']}: every variant shows within {len(pool)} steps", seen)
        f.check(C.destination_explanation(launch, t0 + step / 3) == seen[0],
                f"{launch['name']}: stable within a step", "")
        starts.add((pool[0], seen[0]))
    leo_starts = {s for p, s in starts if p == C.PANEL_NOTES["low earth orbit"][0]}
    f.check(len(leo_starts) > 1, "LEO launches do not all start on the same note", leo_starts)
    return f.report("rotates the destination notes")



def family(launch, history, fleet, slot):
    """Which family a rendered slot belongs to, read off its text."""
    text = slot.get("text") or ""
    if not text:
        return None
    if text in {C.booster_card(launch, m) for m in ("PRE_LAUNCH", "POST_LAUNCH")} | {
            C.booster_career_card(launch, history, fleet),
            C.booster_next_card(launch, history),
            C.record_card(launch, history, fleet)} - {None}:
        return "booster"
    if slot["label"] in ("PAD HISTORY", "LAUNCH CADENCE"):
        return "stats"
    return None


def check_slot_rules(rows):
    """The ranking rules agreed in November 2026, on both devices."""
    f = Failures()
    three = crew_seen = 0
    # The corpus has no failed crewed flight; Crew-13 with its status set to
    # Failure stands in, so the failure rule has a crew to keep off screen.
    failed_crew = {"mode": "POST_LAUNCH", "launch": with_status(by_id(rows, CREW_13), "Failure")}
    for r in rows + [failed_crew]:
        launch, mode = r["launch"], r["mode"]
        desc, pdesc = descriptions(launch)
        history, fleet = caches_for(launch)
        stage = C.launch_stage(launch, mode)
        crew = C.crew_card(launch)
        for hours in (None, 1, 9, 20, 40, 80):
            kw = dict(history=history, fleet=fleet, pad_first_year=pad_year_for(launch),
                      hours_until=hours if mode == "PRE_LAUNCH" else None,
                      hours_since=hours if mode == "POST_LAUNCH" else None)
            og = C.build_slots(launch, mode, desc, pdesc, FACT, **kw)
            x = C.build_slots(launch, mode, desc, pdesc, FACT, lg=True,
                              exclude=["dest"], **kw)
            og_full = C.build_slots(launch, mode, desc, pdesc, FACT,
                                    brief_budget=C.LG_BRIEF_BUDGET, **kw)
            name = f"{launch['name']} at {hours}h"
            f.check(len(og_full) == 2, f"{name}: OG full view keeps two cards")
            f.check([s["label"] for s in og_full] == [s["label"] for s in og],
                    f"{name}: longer OG briefs preserve its card selection")
            for device, slots in (("OG", og), ("X", x), ("OG full", og_full)):
                shown = [s for s in slots if s["text"]]
                fams = [family(launch, history, fleet, s) for s in shown]
                f.check(fams.count("booster") <= 1,
                        f"{name} ({device}): one booster card at a time",
                        [s["label"] for s in shown])
                f.check(fams.count("stats") <= 1,
                        f"{name} ({device}): one launch-stats card at a time",
                        [s["label"] for s in shown])
                f.check(slots[0]["label"] != "DID YOU KNOW?",
                        f"{name} ({device}): trivia never takes slot A", slots[0])
                if slots[0]["label"] in ("PAD HISTORY", "LAUNCH CADENCE"):
                    better = [x for x in (
                        None if C.is_boilerplate(launch, desc) else C.tidy_brief(desc),
                        C.booster_card(launch, mode),
                        C.booster_career_card(launch, history, fleet),
                        C.record_card(launch, history, fleet),
                        C.booster_next_card(launch, history),
                        C.outlook_card(launch, mode) if mode == "PRE_LAUNCH" else None) if x]
                    f.check(not better,
                            f"{name} ({device}): launch stats take slot A only as a fallback",
                            slots[0]["label"])
                texts = [s["text"] for s in shown]
                f.check(len(texts) == len(set(texts)), f"{name} ({device}): no card twice", texts)
                if crew and stage != "fail":
                    crew_seen += 1
                    f.check(slots[1]["text"] == crew,
                            f"{name} ({device}): the crew holds slot B", slots[1])
                if stage == "fail":
                    f.check(crew not in texts or not crew,
                            f"{name} ({device}): no crew card on a failure", texts)
            a, b, c = x
            if c["text"]:
                three += 1
            filler = ("DID YOU KNOW?", "PAD HISTORY", "LAUNCH CADENCE")
            f.check(not (b["label"] in filler and c["text"] and c["label"] not in filler),
                    f"{name} (X): stats and trivia never sit above a card about the flight",
                    (b, c))
            f.check(b["text"] or not c["text"], f"{name} (X): no gap in slot B", (b, c))
        brief = None if C.is_boilerplate(launch, desc) else C.tidy_brief(desc)
        lg_brief = None if C.is_boilerplate(launch, desc) else \
            C.tidy_brief(desc, C.LG_BRIEF_BUDGET)
        if brief and lg_brief:
            f.check(len(lg_brief) <= C.LG_BRIEF_BUDGET + 1,
                    f"{launch['name']}: X brief within its budget", len(lg_brief))
    f.check(crew_seen > 0, "the corpus has a crewed flight", "")
    return f.report(f"slot rules on both devices (X shows three cards in {three} renders)")


def check_og_full_slots(rows, dockings):
    """The full OG can omit footer content without changing mashup cards."""
    f = Failures()
    docking_cases = extended_briefs = 0
    build_slots = U.build_slots
    for row in rows:
        launch, mode = row["launch"], row["mode"]
        out = U.process_launch_data(launch, mode, with_history=False)
        for slot in "ab":
            full = out.get(f"og_full_slot_{slot}_text", "")
            label = out.get(f"og_full_slot_{slot}_label")
            f.check(label == out[f"slot_{slot}_label"],
                    f"{launch['name']}: longer briefs keep the same card selection")
            if label in ("MISSION BRIEF", "MISSION RECAP"):
                f.check(0 < len(full) <= C.LG_BRIEF_BUDGET + 1,
                        f"{launch['name']}: full OG brief stays within the 500-character budget")
                f.check(len(out[f"slot_{slot}_text"]) <= C.BRIEF_BUDGET + 1,
                        f"{launch['name']}: mashup brief keeps its shorter budget")
                extended_briefs += len(full) > C.BRIEF_BUDGET + 1
            else:
                f.check(full == out[f"slot_{slot}_text"],
                        f"{launch['name']}: other mashup cards are unchanged")
        f.check("og_full_slot_c_text" not in out, "OG full view supplies only two cards")
    f.check(extended_briefs > 0, "real fixtures exercise briefs beyond the old 360-character limit")

    for event in dockings["results"]:
        launch_id = event.get("launch_id")
        matching = [r["launch"] for r in rows if r["launch"].get("id") == launch_id]
        if not matching:
            continue
        launch = matching[0]
        before = at(event["docking"]) - timedelta(hours=6)
        docking = H.match_docking(dockings, "", launch_id, before)
        if not docking:
            continue

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return before

        # Sample rotation independently of the docking clock, as in the
        # slot-rule checks. The cargo fixture's NET has since slipped past
        # its recorded docking; at step zero its booster hides the duplicate.
        for hours in (1, 3, 9, 20):
            def at_rotation(*args, **kwargs):
                kwargs["hours_since"] = hours
                return build_slots(*args, **kwargs)

            with patch.object(U, "datetime", Clock), \
                 patch.object(U, "build_slots", side_effect=at_rotation), \
                 patch.object(U, "get_docking", return_value=docking), \
                 patch.object(U, "get_booster_history", return_value=None), \
                 patch.object(U, "get_fleet", return_value=None), \
                 patch.object(U, "get_pad_first_year", return_value=None):
                out = U.process_launch_data(launch, "POST_LAUNCH", with_history=True)
            f.check(out.get("footer_kind") == "docking", "real docking fixture reaches the footer")
            for slot in "ab":
                f.check(out.get(f"og_full_slot_{slot}_label") != "NEXT MILESTONE",
                        "OG full slots do not repeat the docking footer")
            docking_cases += 1
    f.check(docking_cases > 0, "exercised real docking fixtures")
    return f.report("OG full cards preserve mashups and exclude footer docking")


def main():
    rows, dockings = load()
    checks = [check_docking_match(rows, dockings),
              check_footer_lifecycle(rows, dockings),
              check_next_launch(rows),
              check_writes(rows),
              check_destination(rows),
              check_panel_variants(rows),
              check_slot_rules(rows),
              check_og_full_slots(rows, dockings)]
    failed = checks.count(False)
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
