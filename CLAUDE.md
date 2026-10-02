# Mission Control

A TRMNL e-ink plugin ("recipe") showing the next or most recent rocket launch.

## This repo is half the recipe

This repo is the **data half**: it builds `launch.json` and hosts the rocket
art. The **markup half** lives in TRMNL's plugin editor and is not in git -
verified by searching every path and every blob in the full history. Never
claim to have read the markup; ask for the Markup tab, or say explicitly that
you are reasoning from screenshots.

For layout, responsive or rocket-art-sizing questions, use the
`trmnl-framework` skill in `.claude/skills/`.

## Layout

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

## Known open items

- `is_placeholder` misses "Details TBD" style stubs when the description is
  over 60 characters, so they reach the card.
- `cadence_card` and `pad_card` can both be on screen stating the same pad
  count in different words.
- Rotation is keyed to `hours_until`, so a launch that slips jumps backward
  through the tiers.
