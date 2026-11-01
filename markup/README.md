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

`full.liquid` and `shared.liquid` now carry the X layout: a footer, a
destination explanation and a larger info row, all behind `lg:` classes, so
the OG renders as before. These use Framework **3.4.4** classes
(`lg:grow`, `lg:portrait:h--[Ncqh]`, `data-clamp-lg-portrait`). Switch the
recipe's framework version to 3.4.4 when publishing them. The payload fields
they read are listed in `CLAUDE.md` under "TRMNL X layout".

## Editing and publishing

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
