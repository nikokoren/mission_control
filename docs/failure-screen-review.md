# Failure screen review: Amazon Leo (LV-01), Vulcan VC6L, 2026-11-15

Scope: 16 offline renders (all four views, X and OG, landscape and portrait, Framework 3.4.4) of the real `launch.json` failure payload, read against `markup/*.liquid`, `scripts/cards.py` and `scripts/update_launch.py`. Design review only. Nothing in the repo was changed.

## 1. Diagnosis

The failure is rendered as a normal post-launch screen with a different word in one chip. Nothing about the layout changes, so the eye reads "routine launch, done, next one in 62h".

- **The status treatment is upside down.** In `full.liquid` (lines 110-116) `Success` gets `label--inverted` (solid black) and `Failure` gets `label--outline`. Of all the outcomes, a failure is drawn as the *weakest* one. The halves and the quadrant use `label--outline` for every status, so there a failure and a success look the same.
- **The verdict is carried by small type.** "LAUNCH FAILURE" is a `label--small` header, the same size and weight as BY, FOR, DESTINATION and DID YOU KNOW?. The sentence under it is body text. The largest type on the screen is the mission name, then ROCKET USED "Vulcan VC6L", then the next mission's countdown.
- **The content around it argues against it.** The OG and every half view put upbeat trivia next to the failure ("A spacecraft in low Earth orbit travels at roughly 17,500 mph"). The X shows a future-tense MISSION RECAP ("45 satellites will be carried on each Vulcan launch") and a DESTINATION blurb about LEO being "the most crowded stretch of space". All of these assume the mission worked.
- **The art says nothing.** `rockets/empty.png` is a fully transparent 800x1200 PNG (checked: alpha 0 everywhere). The "empty pad" draws nothing. It leaves a large blank column that reads as a broken image, not as "the rocket is gone".
- **The footer outweighs the event.** The next-mission row has the heaviest rule on the screen (2px `.mc-rule`), a title-sized name and an `lg:label--xlarge` outlined countdown. That countdown is the same size as the FAILURE chip. The screen ends by pointing forward to a Long March 2D.
- **Tone and copy.** "The launch failed. No cause has been announced yet." is correct and sober, but it has no subject: it does not say what failed (vehicle), what was lost (payload), or when. The halves and the quadrant show no time at all, so a failure from 1 hour ago looks the same as one from 15 hours ago.
- **The hold time is a success's hold time.** `choose_target()` treats a failure like any result: at least `FRESH_HOURS` (4h), and only up to `STALE_HOURS` (16h) if the next launch is more than 12h away. This one was at T+15h05m, about an hour from disappearing. That happened only because the next launch was 62h out; with a launch 2h away, the failure would have gone after 4h.

## 2. Findings per view

### Full, TRMNL X, landscape
- The FAILURE chip is outlined, in the top right, and competes with the mission title. The title breaks badly ("Amazon Leo (LV-" / "01)") because the chip and the logo squeeze it.
- The color ULA logo is the largest graphic on screen. A corporate logo is the main image on a failure screen.
- Slot A (LAUNCH FAILURE) is one line in `description--large` weight. It has the same visual rank as the BY/FOR row above it.
- Slot B MISSION RECAP is a dense `label--small` paragraph: pre-flight, future-tense marketing prose ("will offer broadband..."). It reads as the main content because it is the biggest block of text.
- Slot C is empty, and the left column has about 40% blank space below the recap.
- The right column has DESTINATION "Low Earth Orbit" and an upbeat LEO blurb, then about 800px of nothing (the transparent `empty.png`), then ROCKET USED. The panel implies the payload reached LEO.
- The footer has NEXT MISSION Long March 2D, BY/FROM, and an xlarge "T- 62h 04m". It is visually as strong as the header.

### Full, TRMNL X, portrait
- Same content, stacked. The failure card is about 5% of the height. There are two large blank bands (below the recap, and the art area between DESTINATION and ROCKET USED), about 45% of the screen in total.
- The title fits on one line here. The FAILURE chip is still outlined and small next to the title.

### Full, TRMNL OG, landscape and portrait
- 1-bit: the outline chip is a thin rounded border, the weakest mark on screen. The dotted dividers (dithered gray) make everything equally faint.
- Slot B is "DID YOU KNOW?" trivia, set at the same bold weight as the failure sentence, so the two cards read as equals. On landscape the trivia wraps to 2 lines against the failure's 1, so it is the bigger block.
- Right column: DESTINATION then blank space (transparent art) then ROCKET USED. In portrait a second blank band sits between the cards and DESTINATION.
- The title wraps "(LV-" / "01)" in landscape.
- The footer countdown chip is the same size as the FAILURE chip.

### Half horizontal (X and OG, both orientations)
- The header row has MISSION title plus an outlined FAILURE chip. The two cards sit side by side (landscape) or stacked (portrait): LAUNCH FAILURE and DID YOU KNOW? at equal weight. The trivia gets half the context area.
- The art column is blank above ROCKET USED. The template does not treat `empty.png` as "no art" (only `half_vertical.liquid` does), so the column keeps its width and looks broken.
- The footer (NEXT MISSION plus countdown) spans the full width under the heaviest rule in the panel.
- OG portrait: the FAILURE chip is crammed against the title at the far right of a narrow column.

### Half vertical (X and OG, both orientations)
- `v_has_art` is false for `empty.png` and the second card is enabled, as designed, but the freed height is not used. Both cards sit at the top, with 50-65% of the panel blank between them and ROCKET USED.
- DID YOU KNOW? trivia directly follows the failure in every orientation.
- X portrait: the title wraps to 2 lines and the chip floats beside it. The panel is about 70% empty.

### Quadrant (X and OG, both orientations)
- This is the most coherent of the set, because there is no trivia: header, LAUNCH FAILURE card, next-mission row.
- The failure sentence is regular-weight `description--large`. Below it is 40-60% blank, and then a next-mission row with an outlined countdown that matches the FAILURE chip in size.
- `q_has_next` replaces the rocket block with the next event, so a resolved failure loses ROCKET USED. On a failure the vehicle is the key fact, and the quadrant never says "Vulcan".

## 3. Ideas, ranked by impact over effort

Tags: **[M]** markup/layout only, **[G]** generator (`cards.py` / `update_launch.py`), **[A]** new art, **[?]** needs an author decision (see section 4).

### Tier 1: high impact, low effort
1. **Invert the failure chip, everywhere [M].** At minimum, swap the conditional so `Failure` and `Partial Failure` get `label--inverted` (verified in 3.4.4; solid black, legible on 1-bit) and `Success` gets `label--outline`. Apply this in `full.liquid` and in the status chip in `half_horizontal`, `half_vertical` and `quadrant` (the quadrant's "always `label--outline`" rule needs an exception for failure). On the X go one step up: `lg:label--xxlarge` (verified) for FAILURE only.
2. **Drop trivia and upbeat filler on a failure [G].** `OG_B_FALLBACK["fail"] = [STATS, "fact"]` is what puts DID YOU KNOW? next to the failure. Set it to `[]`, or to factual, non-celebratory cards only. Also exclude `fact` from the fail stage's C pool if it is ever added. An empty slot B is better than trivia; let the outcome card take the space (idea 5).
3. **Make the outcome sentence say what was lost [G].** It currently has no subject. Build it from fields the generator already has:
   - No cause: "Vulcan VC6L failed during flight. Amazon Leo LV-01 did not reach orbit. No cause announced." Only say "did not reach orbit" if LL2 supports it; otherwise "Payload status not confirmed."
   - With `failreason`: "Vulcan VC6L failed. {failreason}". Keep `clip()` at a sentence boundary.
   - Partial: "Vulcan VC6L reached space, but the mission fell short. {failreason or 'Details not yet announced.'}"
   Keep it short, NASA-internal, American English. Use "announced", not "released" or "confirmed", for cause.
4. **Stop spending space on a transparent image [M + G].** Short term: treat `empty.png` as no-art in `full.liquid` and `half_horizontal.liquid` the way `half_vertical.liquid` already does (`v_has_art`). Collapse the art block and give the height to the outcome card. Alternatively, have the generator emit `rocket_visual: ""` on failure, so every template takes its existing "no art" path.

### Tier 2: high impact, moderate effort
5. **A failure banner instead of a card [M].** On a failure, replace slot A's small label with a full-width black strip at the top of the main column: `bg--black text--white` (both verified) with `title` or `lg:title--xlarge` text "LAUNCH FAILURE" or "PARTIAL FAILURE". Put the outcome sentence under it at `description--large` on the OG and `lg:title--small`/`title--base` on the X. A solid black band is the cheapest high-contrast mark on e-ink and reads across a room on both 1-bit and 4-bit. The same pattern fits all four views:
   - Half and quadrant: the banner replaces the MISSION/STATUS header row; the mission name sits under it.
   - X: optionally invert the whole main column for the first hours (see open question 1).
6. **Demote the next-mission footer on a failure [M].** Keep it; people still want to know what is next. But on failure:
   - Use the light `.divider` instead of `.mc-rule`.
   - Use `label--small` / `lg:label--base` outline for the countdown (no `lg:label--xlarge`).
   - On the X, drop the BY/FROM row.
   An alternative to try: hide it for the first N hours, which also removes the every-run commit (see open question 3).
7. **Repurpose the destination panel [M + G].** On failure, relabel DESTINATION to **INTENDED ORBIT** (or TARGET ORBIT) and drop `destination_explanation` (generator: empty string on stage `fail`, which the template already handles). On the X, the freed panel can hold a **PAYLOAD** block (what was aboard and its count, if LL2 has it).
8. **Fix the X MISSION RECAP on failure [G].** The pre-flight description is future tense and reads as stale. Either drop the brief from the fail B pool (`POOLS["fail"]["B"]`) in favor of booster/vehicle-record facts, or relabel it **PAYLOAD** and clip it to the first sentence. Any rewrite of tense must not invent outcomes.
9. **Show elapsed time on every view [M].** Add "T+ 15h 05m" (already in `countdown`) or "Failed Nov 15 17:40" to the halves and the quadrant, which currently have no time cue. In the full view, `ON` already carries the date. For "is this new?", a small "T+" chip beside the inverted status would do.
10. **Keep the vehicle on the quadrant [M].** On failure, keep ROCKET USED (or fold "Vulcan VC6L" into the outcome sentence, idea 3), and either drop the next-event row or put it under the vehicle.

### Tier 3: new data or art
11. **Vehicle-impact cards [G].** These are the facts that convey consequence. `cards.py` already has the streak data and suppresses it on failure (`not failed`, line 562). Turn that around:
    - "First Vulcan failure in N flights." / "First failure since {date}."
    - "Next Vulcan launch: {name}, {status}". LL2's TBD/On Hold signals a stand-down.
    These belong in fail slot B and slot C. Verify against the fixture corpus, not invented payloads.
12. **Failure art [A].** Replace the transparent PNG with a deliberate drawing: the bare pad and tower (the "rocket is gone" idea, actually drawn), or a dashed-outline silhouette of the vehicle. It must be 1-bit-safe: solid strokes, no gray fills. Do not draw an explosion; that tone would be wrong, and the cause is often unknown.
13. **Partial failure as its own state [G + M].** "PARTIAL FAIL" is an abbreviation forced by chip width. On the X write PARTIAL FAILURE in full; on the OG, use the banner (idea 5), which has room. Copy should say what worked and what did not, from `failreason`. Art: the ascent or idle drawing rather than an empty pad, since the vehicle did fly.
14. **Hold time for failures [G, ?].** Give `choose_target()` a failure-specific floor, separate from `FRESH_HOURS`/`STALE_HOURS`. Also consider a rule to bring the failure back briefly when LL2 first populates `failreason`. Do not set numbers without the author.
15. **Logo on failure [M, ?].** Consider hiding the provider logo, or letting it shrink, in favor of the banner.

## 4. Open questions for the author

1. **How loud should a failure be?** Options: an inverted chip only; a black banner; or a full inverted main column or whole screen for the first hours. A whole-screen inversion is the strongest e-ink signal, but in a mashup it is also the loudest neighbor.
2. **How long should a failure hold the screen,** and should it beat an imminent launch (`IMMINENT_HOURS`)? Should the screen come back when a cause is announced?
3. **Footer on a failure:** demote it, hide it for some hours, or keep it as is? Hiding it also stops the every-run commit post-launch.
4. **Trivia:** should any trivia or "fun" content appear while a failure is on screen, or should the rule be "facts about this vehicle and this mission only"?
5. **Payload loss wording:** can the screen say "payload lost" or "did not reach orbit" when LL2's `failreason` is empty, or only what LL2 states?
6. **Art:** a drawn empty pad, a ghosted vehicle outline, or no art (give the space to text)?
7. **Partial failures:** the same weight as a failure, or a distinct, lighter treatment?
8. **Crewed failures:** these need a separate, more careful treatment (no countdown footer, no trivia, possibly no art). Should we design for them now, before one happens?
