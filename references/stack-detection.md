# Stack detection

Knowing the stack tells you which reconstruction is cheap and which is a
rewrite. A Tailwind site maps almost one-to-one onto Tailwind; a
styled-components site means the styles live in JavaScript and the class names
are hashes; a Webflow site has a generated class system you should not copy.

## Run it

```bash
python3 scripts/detect_stack.py https://example.com            # live
python3 scripts/detect_stack.py ./rfa/example                  # from a capture dir (uses runtime hints too)
python3 scripts/detect_stack.py ./saved/index.html --json      # saved HTML only
```

Each finding has a category, a confidence and the literal evidence string
that matched. Put that evidence in the report; "looks like React" is not a
finding, `__reactFiber$` on `<div id="root">` is.

## How to read the categories

- **framework / meta-framework**: React alone says "components"; Next.js or
  Remix adds server rendering, file routing and an image pipeline. For
  reconstruction this matters less than you think: you rebuild the UI in the
  user's stack, not the original's. It matters for *reading* the capture:
  Next.js pages carry `__NEXT_DATA__` with props that often reveal the data
  shape behind each component.
- **css**: the strategy decides where the design decisions live.
  - Tailwind: decisions are in class names on each element. `dom.html` is the
    design spec. Tokens are in the config, which you rarely get; recover them
    with `extract_tokens.py`.
  - CSS Modules / Sass: readable rules in `styles/`, class names like
    `Button_root__a1b2c`. Strip the hash, keep the semantic part.
  - styled-components / Emotion: rules are injected at runtime into `<style>`
    tags; the capture's `styles/inline-*.css` files contain them. Class names
    are meaningless; group rules by the elements they land on.
  - Bootstrap / MUI / Ant / Chakra: a known component library. Reproduce with
    the same library if the user's stack allows; otherwise map to equivalents
    (MUI Button → shadcn Button with the same variants).
- **ui-library**: Radix, Headless UI and shadcn signal accessible primitives
  (`data-state`, `aria-*` contracts). Reuse those contracts verbatim; they
  are the behaviour spec for menus, dialogs, tabs.
- **motion**: Framer Motion or GSAP means animations are defined in JS, not in
  `keyframes`. Capture triggered states and infer durations from
  `transition-duration` on the animated nodes; read the bundle only when a
  specific curve matters.
- **builder** (Webflow, Wix, Squarespace, Framer, Shopify themes): generated
  markup with layered utility classes. Treat it as a rendered design, not as
  code to learn from. Extract tokens and layout, ignore the class system.
- **bundler** and **analytics**: context only. Analytics hosts are useful for
  the third-party inventory in the report and nothing else.

## Rendering mode

`renderingMode` distinguishes a client-rendered shell (empty `<div id="root">`
before JS) from server-rendered HTML. The capture always waits for JS, so
both produce a full DOM; the difference matters when the user wants to work
from a HAR or saved HTML, where a client-rendered shell has no content.

## Going deeper on bundles

When a question needs the source (an easing curve, a breakpoint constant, a
component's prop variants), look for `sourceMappingURL` in `styles/` and in
scripts listed in `capture.json.scripts`. Public source maps are a gift:
fetch the `.map`, read `sourcesContent`, find the component file. Without
maps, search the minified bundle for the literal you already know (a hex
colour from the tokens, a class name, a visible string) and read outward
from there. Do not reproduce the bundle; read it to understand one decision.

## Modern technologies

- **Web components (shadow DOM)**: `detect_stack.py` reports the custom element
  tags and, from a capture, the number of shadow hosts and nodes the capture
  pierced. Named libraries (Lit, Stencil, Shoelace, Adobe Spectrum, Material
  Web, FAST/Fluent) have their own signatures. The styles live in each
  component's shadow root; the capture reads open ones. A closed shadow root
  (`attachShadow({mode:'closed'})`) cannot be read; say so.
- **Tailwind v4** is distinguished from v3 by `@property --tw-*`, the
  `@layer theme, base, components, utilities` statement, and `color-mix(in oklab`
  opacity modifiers. v4 ships oklch colours.
- **Container queries** (`@container`, `container-type`) are a per-component
  responsive mechanism; they appear separately from media-query breakpoints.
- **Modern CSS/APIs** flagged: cascade layers (`@layer`), `:has()`/nesting/`@scope`,
  oklch/display-p3 colour, View Transitions (`view-transition-name`,
  `startViewTransition`), the Popover API, and scroll-driven animations
  (`animation-timeline`).

## Limits

Signatures match shipped text. A match proves a marker exists, not that the
library drives the part of the UI the user cares about (a marketing page may
load React only for one widget). Absence of a match proves nothing; minified
bundles can strip every readable marker. When two findings conflict, trust the
runtime hints from the capture over the static regex.
