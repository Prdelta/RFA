# Reconstruction and parity

The goal is a component the user can ship, not a pixel-exact forgery. Build
from tokens and component specs, verify against the captures, and list what
you chose to do differently.

## Choose the mapping

| Original stack            | User's stack        | Approach                                                           |
| ------------------------- | ------------------- | ------------------------------------------------------------------ |
| Tailwind                  | Tailwind            | Near one-to-one; copy the *pattern* of utilities, use the user's theme |
| Tailwind                  | CSS / CSS Modules   | Translate utilities to rules; group by component                   |
| CSS-in-JS / CSS Modules   | Anything            | Read computed styles per component; write fresh rules               |
| Bootstrap / MUI / Ant     | Same library        | Same components and variants; theme the tokens                      |
| Bootstrap / MUI / Ant     | Different library   | Map to equivalents (Button, Card, Dialog); accept small differences  |
| Builder (Webflow, Wix)    | Anything            | Treat as a rendered design; rebuild layout from tokens and rects     |
| Radix / Headless / shadcn | React               | Use the same primitives; they define the a11y and state behaviour    |

Ask the user for the target stack only if the project does not already show
it (check `package.json`, existing components, a `tailwind.config`).

## Build order

1. Tokens first: `tokens.css` or `tailwind.theme.js` adapted to the project's
   naming. Everything else references them; never hard-code a hex twice.
2. Layout shell: container width, grid, breakpoints, sticky header.
3. Leaf components in order of reuse (Button, Badge, Input) then composites
   (Card, Nav, Hero, Footer).
4. States and motion.
5. Content: placeholders for text, images and icons unless the user supplies
   their own.

Keep each component in its own file with a short header comment naming the
original selector it was derived from, so the mapping survives.

## Verify parity

Render the rebuild at the same viewports (any dev server works; capture it
with `capture_page.js` exactly like the original) and compare:

```bash
python3 scripts/compare_screenshots.py ./rfa/orig/1440x900/screenshot.png ./rfa/mine/1440x900/screenshot.png --out ./rfa/diff-1440.png
```

Read the number honestly. Placeholder images and different copy will cost
points; mask them in your head by looking at the `regions` list and the diff
image, which draws red boxes on the worst cells. A structural difference (a
grid that wraps, a header 12px taller) shows as a horizontal band; a token
difference (wrong grey) shows as scattered low-share cells.

Then compare the captures themselves, which is where the actionable detail is:

```bash
python3 scripts/diff_captures.py ./rfa/orig/1440x900 ./rfa/mine/1440x900 --mode parity
```

It reports agreement per category (typography, box, colour, layout) over the
nodes it could match by structural path, lists structure differences per depth
and tag, and names the mismatched nodes with old and new values. A size
difference on a deep node cascades to every ancestor, so fix the deepest one
first and re-run. Unmatched nodes usually mean the rebuild nests elements
differently; fix structure before chasing pixels.

Beyond the scripts, run a checklist per viewport:

- Same element count and order inside each component (compare `capture.json`
  trees, not screenshots).
- Same computed font family, size, weight and line-height on headings and body.
- Same padding, gap and radius on each component instance.
- Same breakpoints switching the same layouts.
- Hover/focus/open states transition with the same properties and durations.
- Keyboard: tab order reaches the same controls; Escape closes what Escape
  closed in the original.
- `prefers-reduced-motion` disables the non-essential animation.

## When not to match

Say in the report when you deliberately diverged, and why:

- Licensed font replaced with a metric-compatible open one.
- Icons replaced with an open set.
- Accessibility fixes (real buttons, labels, contrast raised to 4.5:1).
- Brand elements left out to avoid trade-dress confusion.
- Simplifications the user asked for (no carousel, no parallax).

## Web components and modern CSS

- **Web components**: rebuild each custom element as a component in the target
  framework (React/Vue/Svelte), mirroring its slots, `part`s and `aria`. If the
  user's stack is itself web components, keep the custom element and re-theme via
  its `:host` custom properties.
- **Container queries**: keep `container-type` on the wrapper and `@container`
  rules on the children; don't flatten them to media queries, the component must
  stay responsive to its own box.
- **oklch colour**: ship the theme in oklch when the target supports it; the
  hex from the tokens is the fallback.
- **Scroll-driven / view transitions**: reproduce the CSS; add a reduced-motion
  and an older-browser fallback.

## Report

```bash
python3 scripts/generate_report.py --capture ./rfa/orig --stack stack.json --tokens tokens.json \
  --components comps.json --parity parity-1440.json --parity parity-390.json --state-diff hover.json
```

pre-fills `assets/report-template.md` from the `--json` outputs of the other
scripts and leaves TODO lines where judgment is needed. The parity section should carry the
similarity per viewport and the known differences; the unknowns section should
carry every state you could not capture (auth-only screens, error states,
gestures) so nobody mistakes "not captured" for "not present".
