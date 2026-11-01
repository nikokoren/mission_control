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
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import cards as C  # noqa: E402
import history as H  # noqa: E402
import update_launch as U  # noqa: E402

from test_cards import Failures, descriptions, FACT  # noqa: E402

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
                    got["footer_rocket"] == C.dig(l, "rocket", "configuration", "name"),
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


def main():
    rows, dockings = load()
    checks = [check_docking_match(rows, dockings),
              check_footer_lifecycle(rows, dockings),
              check_next_launch(rows),
              check_writes(rows),
              check_destination(rows)]
    failed = checks.count(False)
    print(f"\n{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
