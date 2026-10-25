---
name: reverse-engineer-frontend
description: Replicate the entire frontend of any website, web app or Electron renderer in the user's own stack, and optionally turn that replica into a brand-neutral white-label ("marca blanca") template that can be re-skinned for general reuse. Use this skill whenever the user wants to clone, copy, replicate, "make it look like", recreate, port, re-theme, white-label, de-brand or study the UI, design, layout, components, animations, CSS, design tokens (colors, fonts, spacing), responsive behaviour or interaction patterns of an existing site or app, or wants a reusable template/starter kit derived from one, even if they never say "reverse engineering". Also use it to detect which frontend framework or CSS approach a site uses, to compare two UIs or two versions of the same UI, or to produce a design-system / component inventory from a live page. Do not use it for backend, API, binary, native or protocol analysis (that is what REA, Reverse Engineer Anything, is for) nor for ordinary work on the user's own source repository.
metadata:
  version: "7"
---

# RFA: Reverse-engineer Frontend Anything

REA (Reverse Engineer Anything) answers "how does this feature work under the
hood". This skill answers the sibling question: **"how is this interface built,
how do I rebuild all of it, and how do I turn it into a template I can reuse?"**
The target is the shipped frontend: the DOM, the CSS, the fonts, the motion,
the responsive rules and the client bundle. Backend logic, APIs and native
code are out of scope; hand those to REA.

There are two phases, and the second is usually the real goal:

- **Phase 1 — Replicate the whole front.** Rebuild the complete interface
  (layout, every component, responsive behaviour, states and motion) faithfully
  in the user's stack, measured against captured evidence. Default to the whole
  front, not one component, unless the user scopes it down.
- **Phase 2 — White-label it ("marca blanca").** Lift every brand decision
  (hues, fonts, logo, name, imagery, marketing copy) out of the replica into a
  single `brand.config` of named variables, and ship a NEUTRAL default theme.
  The result is a generic, re-skinnable template: the structure and patterns
  are reusable, and the original's protected assets are replaced rather than
  carried over. Build the replica themeable from the start (reference
  `--brand-primary`, not the captured hex; use a logo slot, not their logo) so
  white-labeling is a de-brand pass, not a second rebuild.

Every conclusion rests on captured evidence (a DOM snapshot, computed styles,
a screenshot, a network list, a script fingerprint). Keep the evidence, name
its limits, and never present a guess as a measurement. A reconstruction is
judged by visual and behavioural parity against that evidence, not by how
plausible the code looks.

## Workflow in one glance

1. **Scope the ask.** Default to replicating the whole front and producing a
   white-label template. Narrow only if the user asks for one component, one
   interaction or just tokens. Which target stack (React + Tailwind, Vue, plain
   HTML/CSS, Svelte, ...)? Which viewports matter? Will they want the neutral
   template, the faithful replica, or both? Pick the obvious reading and state
   it rather than blocking.
2. **Capture** the live target with `scripts/capture_page.js` (DOM, computed
   styles of visible elements, CSS custom properties, fonts, stylesheets,
   screenshot, network inventory, framework hints) at each viewport the user
   cares about, plus one capture per state that matters (`--hover`, `--focus`,
   `--click`, `--scroll-to`, `--dark`). It pierces open **shadow DOM** so web
   components are captured, reads their stylesheets, and records **container
   queries**, **custom elements**, and modern props (`view-transition-name`,
   `animation-timeline`, `container-type`). Add `--autoscroll` and `--dismiss`
   on real sites. Read
   [references/capture-workflows.md](references/capture-workflows.md) for
   options, auth-walled pages, attaching to a running browser and limits.
3. **Detect the stack** with `scripts/detect_stack.py` (framework, meta-framework,
   CSS strategy, bundler, UI library, analytics). Knowing that a site is Next.js
   with Tailwind and Radix changes which reconstruction is cheapest. See
   [references/stack-detection.md](references/stack-detection.md).
4. **Extract design tokens** with `scripts/extract_tokens.py` from the capture:
   color palette by usage, type scale, spacing scale, radii, shadows, breakpoints,
   z-index layers. See [references/design-tokens.md](references/design-tokens.md)
   for how to normalise them and when a value is a token versus noise.
5. **Decompose into components** with `scripts/inventory_components.py`
   (repeated structures, variants, interaction hints, a11y warnings), then
   refine by judgment: states (hover, focus, active, disabled, loading, empty,
   error) and accessibility contract (roles, names, keyboard behaviour). See
   [references/component-anatomy.md](references/component-anatomy.md).
6. **Measure interactions and motion** with `scripts/diff_captures.py` between
   a resting capture and each state capture: which properties change, by how
   much, with which transition. See
   [references/interactions-and-motion.md](references/interactions-and-motion.md).
7. **Reconstruct** in the target stack, capture the rebuild the same way, and
   **verify parity** with `scripts/compare_screenshots.py` (pixels) and
   `scripts/diff_captures.py --mode parity` (structure, type, box, colour,
   layout agreement). See [references/reconstruction.md](references/reconstruction.md).
8. **White-label** with `scripts/whitelabel.py`: it reads the tokens and
   captures and writes `brand.config.json`, a neutral `theme.neutral.css` to
   ship, a `theme.captured.css` for parity reference, a Tailwind theme wired to
   the variables, and `brand-assets.md` listing the logo, name, fonts, images
   and copy to replace. Then wire the replica's components to those variables
   and swap in placeholder brand slots. See
   [references/white-labeling.md](references/white-labeling.md).
9. **Report**: `scripts/generate_report.py` pre-fills `assets/report-template.md`
   from the JSON outputs; fill the TODO lines (scope, mapping, licensing
   decisions) yourself. Measured facts and inferences stay separate.

Skip steps that the question does not need. "What font does this site use?"
is a capture plus a one-line answer, not a full reconstruction. But "replicate
this site as a template I can reuse" needs all nine, the whole front, every
breakpoint, and the white-label pass.

## Route the target first

Pick the first action from what the user supplied:

- **A public URL**: `node scripts/capture_page.js <url> --out <dir>`. Add
  `--viewport 390x844` and `--viewport 1440x900` for mobile and desktop,
  `--full-page` when the page scrolls, `--autoscroll` to trigger lazy images and
  scroll reveals, and `--dismiss` to close cookie/consent banners first. Then
  `python3 scripts/detect_stack.py <url>`. If the browser cannot reach the host
  (restricted sandbox network, 403 from a proxy, DNS failure), do not fake a
  capture: switch to the HAR path below, or tell the user to enable network
  access / run locally. See `references/capture-workflows.md`.
- **A URL behind login**: ask the user to export a HAR or save the page
  (Save as, complete) from their logged-in browser, or capture with
  `--storage-state <file>` after they produce one. Never ask for their password.
- **A saved HTML/CSS folder**: capture from `file://` for the HTML. A
  single-file ("Web page, complete") save keeps its CSS in a sibling folder;
  point the capture at the saved `.html`.
- **A HAR** (DevTools -> Network -> export): run
  `python3 scripts/ingest_har.py capture.har --out ./site`, which rebuilds a
  local renderable copy (HTML + CSS + fonts + images, references rewritten),
  then capture `./site/index.html` normally. This is the reliable path when the
  live site is unreachable. Runtime-fetched content the HAR did not record is
  absent; everything captured is faithful (verified to 100% parity on a test).
- **A screenshot or design image only**: there is no DOM. Treat colours,
  spacing and type as *estimates* read from pixels, say so in the report, and
  prefer rebuilding from proportions rather than exact values.
- **An Electron app**: unpack the ASAR (`npx @electron/asar extract app.asar out`)
  and capture the renderer HTML from `file://`, or attach to the running app
  with `--remote-debugging-port`. Main-process and IPC questions go to REA.
- **A component inside a page** (a navbar, a pricing card, a modal): capture
  the whole page, then narrow with `--selector "<css selector>"` so the
  styles and screenshot cover just that subtree.
- **An animation or interaction**: capture the resting state, then the
  triggered state with `--hover`, `--focus`, `--click` or `--scroll-to`, and
  run `diff_captures.py` on the pair; it lists the changed properties and the
  transition declared on each changed node.
- **Dark mode or reduced motion**: `--dark` and `--reduced-motion` emulate the
  media features; diff against the light/normal capture.
- **A page open in the user's own browser or a running Electron app**: start
  it with `--remote-debugging-port=9222` and capture with
  `--cdp http://127.0.0.1:9222`; no login handling needed, the session is theirs.

## Modern web technologies

The capture and tokens already handle the stack most new sites ship; don't
treat these as blockers:

- **Web components / shadow DOM**: the capture walks into open shadow roots, so
  a `<sl-button>` or a Lit component is in `nodes` (marked `shadow:true`), and
  its `:host`/adopted stylesheets feed `customProperties` and `keyframes`.
  `capture.json.customElements` lists the custom tags; closed shadow roots stay
  opaque (note them). Rebuild these as the user's framework components, keeping
  the same `part`/`slot`/`aria` contract.
- **oklch / oklab / display-p3 colour** (Tailwind v4, modern design systems):
  `extract_tokens.py` converts them to hex, so the palette is real. Keep the
  original as an oklch token in the theme when the user's stack supports it.
- **Container queries** (`@container`): recorded in `tokens.layout.containerQueries`.
  They are component-level responsive rules; reproduce with the same
  `container-type` and `@container` breakpoints, not global media queries.
- **Scroll-driven animations** (`animation-timeline: view()/scroll()`) and the
  **View Transitions API** (`view-transition-name`): captured as node props and
  flagged by `detect_stack.py`. Rebuild with the same CSS; fall back to
  IntersectionObserver only where the user's browser targets need it.
- **Popover API, `<dialog>`**: captured via the `popover`/`open` attributes;
  keep the native element rather than re-implementing a modal.

`detect_stack.py` flags Tailwind v4, Lit/Stencil/Shoelace/Spectrum/Material Web,
container queries, cascade layers, `:has()`, and the above APIs.

## Evidence discipline

Captures are the source of truth. A few habits keep the work honest:

- Computed styles are what the browser resolved, not what the author wrote.
  `rgb(37, 99, 235)` in a capture may be `--color-primary` in the author's CSS.
  Prefer the custom property when the capture lists one with that value.
- A rule you did not observe at a viewport does not exist at that viewport.
  Capture each breakpoint instead of inferring responsive behaviour.
- Fonts: report the resolved family from the capture *and* the `@font-face`
  sources. A font that loads from the target's own CDN is usually licensed to
  them, not to the user; say so and suggest a metric-compatible substitute.
- Hover, focus and open states are not in a resting capture. Trigger them.
- Minified class names (`css-1x2y3z`, `sc-bdfBwQ`) are build artefacts, not
  design decisions. Describe the role of the element, not its hash.
- When a screenshot comparison scores below the threshold, list the regions
  that differ and why. Do not round a 78 % match up to "basically identical".

## Legal and ethical boundary

Replicating a whole front to reuse it is legitimate when the output is a
de-branded template built from measurements, not a copy of a specific product
wearing a new logo. The white-label pass is what keeps it clean, so do it
properly rather than treating it as an afterthought:

- Structure, layout, spacing systems, responsive rules, interaction and motion
  patterns, the type/radius/shadow scale: generic. These are the template and
  are fine to carry over.
- Verbatim CSS, JavaScript bundles, icons, illustrations, photos, proprietary
  fonts and copy text: protected by copyright or licence. Rebuild rules from
  computed styles rather than pasting the original's stylesheet; replace icons
  and fonts with open sets (Lucide, Heroicons; Google Fonts, Fontsource); use
  placeholder imagery; rewrite copy. `whitelabel.py` lists each of these.
- Logo, brand name and distinctive trade dress (a specific colour+font+shape
  combination that identifies the brand): trademark. The neutral default theme
  exists precisely so the template is not mistakable for the original. Never
  ship the captured theme as the default of a "general use" template.
- Content behind a login or paywall belongs to that service and its users;
  capture it only from the user's own account.
- When the user asks for an "identical" copy of a known brand for redistribution
  rather than a de-branded template, say plainly that the deliverable is the
  white-label version and build that.

## Scripts

All scripts are standalone, print JSON to stdout or write files into an output
directory, and have `--help`.

| Script                              | Needs                        | Produces                                                              |
| ----------------------------------- | ---------------------------- | --------------------------------------------------------------------- |
| `scripts/capture_page.js`           | Node 18+, `playwright` npm   | `capture.json`, `screenshot.png`, `dom.html`, `styles/*.css`, `har.json` |
| `scripts/detect_stack.py`           | Python 3.9+                  | framework, CSS strategy, bundler, libraries, confidence and evidence  |
| `scripts/extract_tokens.py`         | Python 3.9+                  | `tokens.json` plus `tokens.css` (custom properties) and a Tailwind theme snippet |
| `scripts/compare_screenshots.py`    | Python 3.9+, Pillow          | similarity %, diff image, bounding boxes of changed regions           |
| `scripts/diff_captures.py`          | Python 3.9+                  | state mode: changed properties per node with transitions; parity mode: structure/typography/box/colour/layout agreement |
| `scripts/inventory_components.py`   | Python 3.9+                  | component candidates with instances, common styles, variants, interaction hints, a11y warnings |
| `scripts/whitelabel.py`             | Python 3.9+                  | `brand.config.json`, `theme.neutral.css`, `theme.captured.css`, Tailwind theme, `brand-assets.md` — the de-branded template |
| `scripts/ingest_har.py`             | Python 3.9+                  | rebuilds a local, renderable copy of a page from a HAR so capture runs offline when the live site is unreachable |
| `scripts/generate_report.py`        | Python 3.9+                  | `report.md` pre-filled from the JSON outputs of the other scripts     |

If `playwright` is missing, install it next to the skill
(`npm i playwright` then `npx playwright install chromium`) or point the script
at an existing Chromium with `--executable-path`. Do not install anything into
the user's project without telling them.

## Report structure

`generate_report.py --capture <dir> --stack stack.json --tokens tokens.json --components comps.json --parity parity.json --state-diff hover.json`
writes the skeleton below with the measured sections filled; the template is
in `assets/report-template.md`. The sections exist so a reader can tell
measured facts from inferences:

1. Target and scope (URL, viewports, date, what was and was not captured)
2. Stack detection (with the evidence string for each claim)
3. Design tokens (table per category, with usage counts)
4. Component inventory (name, selector, variants, states, a11y notes)
5. Layout and responsive rules (per breakpoint)
6. Motion and interaction (what, trigger, duration, easing)
7. Reconstruction (files written, mapping from original to rebuilt)
8. Parity check (screenshot similarity per viewport, known differences)
9. Unknowns and limitations
10. Licensing notes (fonts, assets, brand)
