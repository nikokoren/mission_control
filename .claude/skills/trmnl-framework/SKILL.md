---
name: trmnl-framework
description: Reference for designing TRMNL e-ink recipes - device dimensions, responsive prefixes, aspect ratio and image utilities, and how this repo's half of the recipe relates to the markup half. Use when working on how the Mission Control display looks: layout, rocket art sizing, per-device or per-orientation behaviour, view sizes, or any question about TRMNL Framework classes.
---

# TRMNL Framework reference

## Read this first: always re-fetch

**Assume the user is on the latest framework version.** Use the **unversioned**
doc URLs (`https://trmnl.com/framework/docs/<page>`) - they track latest.
Never cite a pinned tree (`/3.0/`, `/3.1/`) as current.

This file is a **snapshot, verified 2026-09-27 against v3.3**. The framework
moves fast and versions differ materially: `aspect_ratio` was Beta in 3.0 and
is stable in 3.3; 3.3 added themes, a TRMNLPaint JS API, adaptive charts, maps
and icons. Version trees seen so far: 1.2, 2.3, 3.0, 3.1, 3.3.

**Before giving load-bearing advice, re-fetch the page you are relying on.**
If what you find disagrees with this file, the web wins - and update this file.

Docs index: https://trmnl.com/framework/docs
~40 subpages under Guides, Arrangement, Responsive Utilities, Styling,
Typography, Modulations, Foundation, Elements, Components. Fetch the two or
three that matter rather than sweeping all of them.

## Device dimensions

| device | full | notes |
|---|---|---|
| TRMNL OG | 800x480 | 1-bit, 5:3 |
| TRMNL X / V2 | 1040x780 | 4:3, high-res |
| Kindle 2024 | 718x540 | 4-bit |

Views subdivide the full screen: `full`, `half_horizontal`, `half_vertical`,
`quadrant`. Portrait orientation swaps width and height.

Consequence worth remembering: the OG's columns are **proportionally wider**
than the X's. An element sized by width fills much more of an OG column than
an X column - roughly 27% more for a typical one-third split. Art that was
tuned to overflow on the OG will float with dead space on the X.

## Responsive prefixes

Combine freely, e.g. `lg:4bit:value--large`, `lg:landscape:aspect--3/4`.

| prefix | meaning |
|---|---|
| `sm:` | TRMNL OG 800x480 (`screen--sm`) |
| `md:` | medium (`screen--md`) |
| `lg:` | TRMNL X 1040x780 (`screen--lg`) |
| `portrait:` | portrait orientation |
| `landscape:` | landscape (also the unprefixed default) |
| `1bit:` `2bit:` `4bit:` | bit depth |

Mobile-first: `md:` applies at medium **and up**.

This is the mechanism for serving different markup - or a different image - per
device. It works, but prefer a solution that holds for every device over one
tuned per device: there are already three sizes plus an orientation axis, and
each new device multiplies anything maintained by hand.

## Aspect ratio

Stable as of 3.3 (was Beta in 3.0). Takes responsive prefixes; **no** bit-depth
variants. No arbitrary ratios - only these:

`aspect--auto` `aspect--1/1` `aspect--4/3` `aspect--3/2` `aspect--16/9`
`aspect--21/9` `aspect--3/4` `aspect--2/3` `aspect--9/16` `aspect--9/21`

## Images

`image--fill` (stretch) · `image--contain` (fit inside) · `image--cover`
(fill and clip) · `image--small` (<=80px wide) · `image--xsmall` (<=40px)
· `image-dither` (1-bit grayscale) · `invert` · `image--adaptive`

**There is no `object-position` / crop-anchor utility.** Anchoring a crop
(e.g. clipping a tall rocket at the top while keeping its engines) needs
inline CSS: `style="object-position: bottom"`.

## Container-relative sizing

The Layout element establishes a CSS Container Query context. Utilities
`w--[Ncqw]` and `h--[Ncqh]` accept 0-100 and support responsive variants.
They are relative to the layout, so they work correctly inside mashup slots
where space is a fraction of the screen.

For deliberate overflow (>100%) the utilities cap out - write the `cqh` value
in your own CSS. Container queries are plain CSS; only the generated utilities
are capped.

## This repo is only half the recipe

`nikokoren/mission_control` generates `launch.json` and hosts the rocket art.
**The markup lives in TRMNL's plugin editor and is not in git** - confirmed by
searching every path and every blob in the full history. Do not claim to have
read the markup. Ask the user to paste the Markup tab, or reason explicitly
from screenshots and say that you are doing so.

## The rocket art scale system

Every rocket is an identical **800x1200** canvas (2:3 - exactly `aspect--2/3`).
The canvas is the scale reference: a `100m` rule and a `You` human figure are
drawn into it, and each vehicle occupies its true relative share of the frame.
Electron sits small; Starship fills it and is drawn **running off the top edge
of its own canvas**, which is where the deliberate "too tall to contain" effect
comes from.

That effect is therefore **baked into the art, not produced by the viewport**,
and it only reads as intentional when the frame feels tight. Two ways to keep
it device-independent:

1. **Taller canvas for tall vehicles** (no markup change). Make canvas height
   proportional to the vehicle's real height, same 800 width, same
   pixels-per-meter, so the `100m` rule is identical in every file. Width-sizing
   then does the scale work automatically. Watch out: the `100m` label sits at
   the top of the canvas and is the first thing lost to an overflow crop.
2. **Aspect-locked box** (`aspect--3/4` wrapper + `image--cover` +
   `object-position: bottom`). Art at 2:3 inside a 3:4 box overflows the top by
   ~12.5% on every device. Identical everywhere, but it crops *every* rocket -
   so the markup needs to know which vehicles are tall, e.g. a height or flag
   emitted in `launch.json`.

## Open questions - do not guess these, ask

- Which framework version the recipe declares.
- The pixel width and height of the rocket column in each view.
Both were unknown as of this snapshot, and canvas-height math depends on them.
