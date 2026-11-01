# Mission Control

A TRMNL e-ink plugin ("recipe") showing the next or most recent rocket launch.

## Recipe source

This repo builds `launch.json`, hosts the rocket art, and stores the recipe's
Liquid templates, shared styles, and form fields in `markup/`. The author
supplied the editor copies on November 1, 2026; see `markup/README.md` for the
file-to-editor mapping and manual publishing instructions. A GitHub push does
not automatically update the TRMNL editor.

The imported recipe uses **TRMNL Framework CSS 2.3.7**. New layout work targets
the **latest stable framework** (the author suggested **3.4.4**, pending
verification). OG compatibility and any needed OG layout changes will be
addressed afterward. Read the templates before making layout claims, and
distinguish repository source from any later changes made only in the editor.

For layout, responsive or rocket-art-sizing questions, use the
`trmnl-framework` skill in `.claude/skills/`.

## Layout

- `markup/` - full, half horizontal, half vertical, and quadrant templates,
  shared styles, and form fields from the TRMNL recipe editor.
- `scripts/update_launch.py` - entry point. Picks which launch gets the screen,
  builds the output, writes `launch.json`.
- `scripts/cards.py` - the card builders and the slot/rotation logic.
- `scripts/facts.py` - the rocket fact pool.
- `scripts/history.py` - booster history, fleet and docking lookups, cached in
  `boosters/`. LL2 ignores a `launcher_config` filter on `/launcher/`, so the
  fleet is the whole launcher table in `boosters/_fleet.json`, filtered by
  rocket type in Python. `boosters/_pads.json` holds each pad's first launch
  year, fetched once per pad, for the pad card's lifetime total.
- `rockets/` - rocket art. Mostly PNG, a few JPEG.
- `launch.json` - **generated output, do not hand-edit.** The workflow rebuilds
  and commits it about every 15 minutes. Pre-launch it changes on every run
  because of `countdown`, and that is deliberate: TRMNL skips generating a new
  screen when a polled payload is unchanged, so a countdown computed in the
  markup from `date_ts` would freeze. Post-launch, where the countdown is not
  shown, a run that only moves it writes nothing.

Data source is the Launch Library 2 API (`ll.thespacedevs.com`).

## How the display decides what to show

Two independent layers, both **pure functions of the clock** - there is no
stored state or rotation index anywhere.

1. `choose_target()` in `update_launch.py` picks which launch owns the screen,
   from `hours_since` the previous launch and `hours_until` the next.
   `IMMINENT_HOURS` / `FRESH_HOURS` / `QUIET_HOURS` / `STALE_HOURS` tune it.
2. `build_slots()` in `cards.py` picks the two cards. Twelve builders each
   return text or `None`; ranked order lists per mode; first non-empty wins and
   slot A's pick is excluded from slot B. Whatever is left rotates by time -
   monotonic tiers pre-launch, a simple cycle post-launch.

## Three states, not two

`is_resolved()` in `cards.py` is the tense signal, and is deliberately **not**
the same as `POST_LAUNCH` mode, which flips at liftoff:

- pre-launch -> future tense
- In Flight / awaiting confirmation -> present tense, outcome unknown
- `Success` / `Failure` / `Partial Failure` -> past tense

A failure also pins an outcome card to slot A for the whole result window.

## Copy conventions

- **American English.** One exception: the `"Indian Space Research Organisation"`
  key in `normalize_org_name` keeps the British spelling because it matches
  what the API sends.
- Short sentences, closer to NASA internal comms than to marketing.
- **Agency names**: header chips use the short forms from `normalize_org_name`;
  cards use `card_org_name` in `cards.py`, which gives country-plus-acronym
  ("China's CASC", "Europe's ESA") and leaves famous or self-describing names
  alone. `org_possessive` exists because "China's CASC's" reads badly.
- **Drone ships** are named in full and called drone ships - `landing_place`
  in `cards.py`. Never surface bare `OCISLY` / `JRTI` / `ASOG` to a reader.
- Never truncate with a bare slice. Use `clip()` in `cards.py`: it prefers a
  sentence boundary and falls back to a word boundary plus an ellipsis.

## Tests - run these

    python3 tests/test_cards.py           # the checks
    python3 tests/test_cards.py --show    # print every distinct card
    python3 tests/test_display.py         # X destination panel, footer, writes

Stdlib only, no network, no framework: it walks a corpus of ~90 real API
payloads in `tests/fixtures/` plus hand-written degenerate cases. **Run it
before pushing anything under `scripts/`.** CI runs it too
(`.github/workflows/test-cards.yml`), on changes to `scripts/` or `tests/`
only, and prints the whole corpus into the job summary so a reviewer can judge
wording from the pull request.

The checks assert *properties* - punctuation, length, tense, self-consistency -
not exact strings, so rewording a card does not break them. What they cannot
judge is whether the prose reads well; that is what `--show` is for.

If you add a check, **first confirm it fails** by breaking the code in the way
it is meant to catch. A check that cannot fail is worse than no check.

## Working here

- Push directly to `main`. **Always `git fetch` and rebase first** - the
  workflow pushes to `main` every ~15 minutes and a stale push is rejected.
- **Other agents work in this repo concurrently.** Re-read a file before
  editing if the session has been long, and never assume your last-known state
  of `main` is current.
- Verify changes against live API data or the fixture corpus, never against
  payloads you invent. Fabricated input produced at least one false bug report
  in this repo's history.
- Restore `launch.json` with `git checkout launch.json` after any local test
  run; it belongs to the workflow.
- `upcoming.json` and `previous.json` are fetched inputs and are gitignored.

## TRMNL X layout (full view)

The X gets its own arrangement through `lg:` classes; the OG renders as
before. Markup in `markup/full.liquid` targets Framework **3.4.4** (confirmed
as the current release, 2026-10-24), and every class it adds was checked
against the 3.4.4 stylesheet.

- **Info row** (BY / FOR / ON / FROM): values are `lg:description--large`,
  one step up. `xlarge` is two steps and too heavy for four fields. On the X
  BY and ON keep their width; FOR and FROM shrink in proportion to their
  length and wrap, and labels align at the top (`mc-info` in shared.liquid,
  scoped to `.screen--lg`).
- **Destination panel**: DESTINATION, `destination` (the station for an
  ISS-bound flight, else the orbit; `orbit` itself is unchanged), then
  `destination_explanation` (generic context, never mission-specific; empty
  means the block is dropped), then the rocket, then ROCKET USED. The notes
  are `PANEL_NOTES` / `ISS_NOTES` in `cards.py`, several variants per
  destination (six for LEO), at most `PANEL_NOTE_MAX` characters, shuffled
  per launch and stepped every `PANEL_ROTATE_HOURS`. Keep them clear of what
  the fact pool already says.
- **X slots**: `build_slots(..., lg=True)` gives `lg_slot_a_*` / `_b_*` /
  `_c_*`, without the cards the panel and footer already show (`dest`, and
  `docking` when the footer is a docking). The X's brief may run to
  `LG_BRIEF_BUDGET`; the `crew` card exists only here. Slot C is the first
  `THIRD_SLOT` card the pair did not use - flight-specific cards only, never
  trivia, cadence, pad or program - and is empty otherwise, so a routine
  flight keeps two cards. `slot_a_*` / `slot_b_*` stay the OG contract.
- **Footer**: `footer_*` fields, post-launch only, chosen by `choose_footer()`
  in `update_launch.py`: a scheduled docking still ahead for this ISS-bound
  spacecraft, else the next launch with real timing (`net_precision` of
  SEC/MIN/HR, status Go/TBC/TBD), else nothing and the row is removed. A past
  docking time is not proof of docking (LL2 has no docking status), so it
  never holds the footer. This does not change `choose_target()`.
- **Writes**: `needs_write()` writes whenever a countdown that is on screen
  moved, which post-launch now includes the footer's. Expect a commit every
  run while a footer is shown.
- Docking events are matched by `launch_id` in `history.match_docking()`.

## Design work queued - TRMNL X

Observed on a real TRMNL X (2026-10-17), not in preview: **the top is cramped
and there is a lot of empty space below it.** The X is 1040x780 against the
OG's 800x480, so its columns are proportionally much taller. Anything sized by
width - which is most of this layout, built for the OG - keeps its original
proportions and leaves vertical slack underneath. Same root cause as the
rocket-art problem in the `trmnl-framework` skill; fixing one may inform the
other.

- **Rework the BY / ON / FROM line further.** On the X the text is one step
  bigger and long FOR / FROM values now share the width instead of one
  squeezing the other, but it is still the OG's single row; the OG row
  still has the squeeze. Long agency names could also use LL2's agency
  abbreviation (not in the fixtures yet). The data side is here: `provider` (short form from
  `normalize_org_name`) and `location_str`, assembled at
  `update_launch.py:401` as `"{pad} @ {location}, {country}"` - e.g.
  `SLC-40 @ Cape Canaveral SFS, USA`. The arrangement is in
  `markup/full.liquid`. Worth deciding whether the X should stack or re-flow
  these rather than reuse the OG's single row.
- **Rethink the top bar and the left-side text fields** (exploratory, not
  decided). The whole upper-left block was composed for the OG's 800x480 and
  may want a different arrangement at `lg:` rather than a scaled one.

For both, read `markup/full.liquid` and `markup/shared.liquid` before proposing
changes. The framework's responsive prefixes
(`sm:` / `lg:` / `portrait:`) allow a genuinely different arrangement per
device, not just a rescaled one; see the `trmnl-framework` skill.

## Known open items

- `is_placeholder` misses "Details TBD" style stubs when the description is
  over 60 characters, so they reach the card.
- `cadence_card` and `pad_card` can both be on screen stating the same pad
  count in different words.
- Rotation is keyed to `hours_until`, so a launch that slips jumps backward
  through the tiers.
