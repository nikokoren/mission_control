# TRMNL recipe source

These files were supplied from the recipe editor on November 1, 2026. They
preserve the existing templates, shared styles, and form fields as a baseline,
without layout or logic changes.

The imported recipe currently uses **TRMNL Framework CSS 2.3.7**, confirmed by
the author. New layout work should target the **latest stable framework**;
the author identified **3.4.4** as the likely current release, pending
verification against official documentation. OG compatibility and any needed
OG layout changes will be addressed afterward. This baseline import does not
change the framework version used by the active recipe.

| File | Recipe editor section |
| --- | --- |
| `full.liquid` | Full view |
| `half_horizontal.liquid` | Half horizontal view |
| `half_vertical.liquid` | Half vertical view |
| `quadrant.liquid` | Quadrant view |
| `shared.liquid` | Shared code, including the `<style>` wrapper |
| `form_fields.yml` | Form fields, including the About This Plugin metadata |

## TRMNL X changes

`full.liquid` and `shared.liquid` carry the X layout: a detailed footer, a
destination explanation and a larger info row behind `lg:` classes. The OG
now shares the footer in a compact form, described below. These use Framework **3.4.4** classes
(`lg:grow`, `lg:portrait:h--[Ncqh]`, `data-clamp-lg-portrait`). Switch the
recipe's framework version to 3.4.4 when publishing them. The payload fields
they read are listed in `CLAUDE.md` under "TRMNL X layout".

## Editing and publishing

The OG full view also shows a compact, two-row footer: the next event's
label and title, alongside its countdown. It follows the same lifecycle as
the X footer, starting after liftoff (including in-flight and confirming
states). A future ISS docking takes priority over the next timed launch.
Provider, location, and docking-port details remain in the X footer only.
No eligible event means no footer row.

The OG keeps two cards and uses the same 500-character mission-brief
budget as the X. Mashups retain the 360-character budget. Its
`og_full_slot_a_*` and `og_full_slot_b_*` fields omit a docking already shown
in the footer; the shared `slot_a_*` / `slot_b_*` pair still serves mashups.
Older payloads fall back to that shared pair. Portrait reserves room for the
footer by reducing the text-and-art row.

Long OG briefs use the existing type tiers: above 400 characters, the
brief switches from large to base description text. The 500-character
budget changes the full view's brief only; it does not enable a third card.
Line clamps still apply, including the tighter portrait limits.

The Liquid templates consume the fields generated in `launch.json` by
`scripts/update_launch.py`. Shared code supplies the `mc-clip` and `mc-tl*`
styles used by the views. Each view also contains its portrait layout rules.

GitHub stores the recipe source; this repository has no workflow that
automatically deploys these files to the TRMNL editor. To publish a change,
copy the relevant files into their matching editor sections and save there.
Keep the repository and editor copies in sync.

For layout changes, preview the affected views in landscape and portrait on
both OG (800×480) and X (1040×780), using pre-launch, in-flight or pending,
and resolved launch payloads. These imported files have not been visually
revalidated in the editor as part of adding them to GitHub.
