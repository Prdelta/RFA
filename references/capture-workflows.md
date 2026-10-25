# Capture workflows

The capture is the evidence everything else rests on. Spend the first minutes
getting a good one rather than reasoning from a half-loaded page.

## Baseline capture

```bash
node scripts/capture_page.js https://example.com --out ./rfa/example \
  --viewport 1440x900 --viewport 390x844 --full-page
```

Produces one directory per viewport with `capture.json`, `screenshot.png`,
`dom.html`, `styles/` and `har.json`, plus a top-level `summary.json`. Read
`summary.json` first: node count, truncation flag, framework hints, fonts,
custom property count, console errors. A truncated capture (default cap 3000
visible elements) means the page is large; narrow with `--selector` or raise
`--max-elements`.

Pick viewports from what the user ships to, not from habit. Common choices:
`390x844` (phone), `768x1024` (tablet), `1280x800` (laptop), `1440x900` and
`1920x1080` (desktop). Capture the breakpoints you see in `mediaQueries` plus
one pixel on either side when the exact switch matters.

## States that a resting capture misses

| State               | How to capture                                                             |
| ------------------- | -------------------------------------------------------------------------- |
| Hover               | `--hover ".nav a"` then compare that element's styles with the resting run |
| Focus               | `--focus ".btn"` (keyboard focus ring); compare `outline-*` and `box-shadow` with the resting run |
| Open menu / modal   | `--click "[aria-haspopup]"` or `--click ".open-modal"` and `--wait 1200`   |
| Scroll-triggered    | `--scroll-to ".section-3"` or `--scroll-to 1800`; repeat for several offsets |
| Dark mode           | `--dark` emulates `prefers-color-scheme: dark`; for a site with its own toggle use `--click` on it |
| Reduced motion      | `--reduced-motion`; check which animations the site actually disables       |
| Lazy content        | `--wait-for ".pricing-table"` waits for a selector before capturing          |
| Sticky header after scroll | `--scroll-to 600` then inspect the header node's `position`, `box-shadow`, `background-color` |
| Loading / skeleton  | Lower `--wait` to 0 and capture immediately; compare with the settled run   |
| Form validation     | Needs manual interaction; ask the user for a screenshot or HAR of the error state |

Each state is a separate output directory. Name them after the state
(`rfa/example-hover-nav`, `rfa/example-menu-open`) so the report can cite them,
then measure the difference:

```bash
python3 scripts/diff_captures.py rfa/example rfa/example-hover-nav
```

It lists, per matched node, every computed property that changed with old and
new values and the transition declared on the node. Changes that merely follow
`color` through `currentColor` (border, outline) are folded into the colour
change so the list shows causes, not echoes.

## Real sites: what gets in the way

A marketing site is rarely a clean document. Handle these before trusting a capture:

- **Cookie/consent banners** cover the page and skew the screenshot and the
  fold. Use `--dismiss` (clicks OneTrust, Cookiebot, Didomi, Quantcast and
  buttons matching accept/aceptar/agree/got it, then hides any leftover
  full-viewport fixed overlay). Add `--dismiss-selector "<css>"` for a bespoke
  one. Confirm it worked: the capture's `stateActions` lists what was dismissed.
- **Lazy-loaded images and scroll reveals**: `--autoscroll` scrolls the whole
  page to trigger them, then returns to top. Without it, below-fold images are
  blank and reveal elements stay at opacity 0.
- **Anti-bot / Cloudflare challenges**: the capture may land on a challenge page
  instead of content. Say so and fall back to a user-saved HTML or HAR; do not
  try to evade the check.
- **Heavy media** (video backgrounds, huge hero images) can blow the capture
  timeout or the node cap. Raise `--max-elements`, and accept that a `<video>`
  poster frame is what you get.
- **Cross-origin stylesheets** without CORS show `readable:false` in the
  capture; their rules still shaped the computed styles, but you cannot read
  their text. The HAR path recovers them.
- **Modern colour syntax** (hsl(), color(srgb ...)) is parsed by the token
  extractor; oklch() is passed through as-is (rare in computed styles).

## Restricted or offline environments

A cloud sandbox often has no outbound internet, or only an allowlist. Symptoms:
`capture_page.js` fails with a net error; `curl` to the host returns 403 from
the proxy or the DNS does not resolve. This is an environment limit, not a
skill failure. Options, in order:

1. **Capture from a HAR** the user exports from their own browser
   (`ingest_har.py`, above). This needs no network and is the fastest unblock.
2. **A proxy that does reach the host**: `--proxy http://host:port` (or
   `--proxy-from-env` to use `HTTPS_PROXY`), plus `--ignore-https-errors` only
   if that proxy terminates TLS with its own certificate.
3. **Enable network access** for the host in the environment settings, then
   start a fresh session (a running container keeps its original network
   policy). Verify with `curl -I <url>` before capturing.

Never substitute a guessed or mocked design for a site you could not load.

## Pages behind authentication

Do not ask for passwords. Options, best first:

1. The user starts their own Chrome with `--remote-debugging-port=9222`, logs
   in as usual, and you attach with `--cdp http://127.0.0.1:9222`. Nothing is
   copied; the capture reads the page they already have open. Close the
   attachment when done; their browser stays as it was.
2. The user runs `npx playwright codegen --save-storage=state.json <url>`, logs
   in by hand, closes the window, and hands over `state.json`. Capture with
   `--storage-state state.json`. The file contains their session cookies: treat
   it as a secret, do not copy it into the report or the project.
3. The user saves the page from their browser ("Save as, Web page, complete")
   and you capture the saved `index.html` from `file://`. Computed styles will
   be faithful if the CSS was saved; JavaScript-driven state will be frozen.
4. The user exports a HAR from DevTools (Network tab, Export HAR). You get
   every CSS and JS body but no rendered DOM; combine with screenshots.

## Electron renderers

```bash
npx @electron/asar extract /path/to/app.asar ./unpacked
node scripts/capture_page.js ./unpacked/renderer/index.html --out ./rfa/app
```

Many Electron apps need their preload and IPC to render anything useful from
`file://`. If the capture is an empty shell, start the app with
`--remote-debugging-port=9222` and capture with
`--cdp http://127.0.0.1:9222`; the renderer is a normal page from then on.
Anything about the main process, IPC handlers or native modules is REA's
domain.

## Reading capture.json

- `nodes[]`: visible elements in document order with `parent` ids, `rect`
  (page coordinates), `styles` (computed), `pseudo` (`::before`/`::after`
  content) and a short `text`. Reconstruct the tree from `parent`.
- `customProperties`: every `--var` declaration found in readable stylesheets
  with the selector it was declared on. `customPropertiesRoot` is the resolved
  value on `:root`. These are the closest thing to the author's token names.
- `keyframes`, `mediaQueries`, `fontFaces`, `loadedFonts`: straight from CSSOM
  and the Font Loading API.
- `stylesheets[].readable=false` means a cross-origin sheet without CORS; its
  rules still applied to the computed styles but you cannot read its text. The
  `styles/` folder fetch may still succeed when the CDN allows it.
- `frameworkHints`: runtime probes (globals, DOM markers). Confirm with
  `detect_stack.py`.
- `network.thirdPartyHosts`: a quick view of CDNs, font hosts, analytics.

## What the capture reads now (modern tech)

- **Open shadow roots** are pierced: web-component internals appear in `nodes`
  with `shadow:true`, and their adopted/`<style>` sheets feed the custom
  properties and keyframes. `capture.json.customElements` and `shadow` summarise
  them. Closed shadow roots stay opaque.
- **Container queries** are in `capture.json.containerQueries` (and the tokens'
  `layout.containerQueries`), separate from media queries.
- **Modern props** per node: `view-transition-name`, `animation-timeline`,
  `animation-range-*`, `container-type/name`, `content-visibility`,
  `scroll-snap-*`, `color-scheme`, `mix-blend-mode`, `clip-path`.
- **Modern colour** (oklch/oklab/display-p3) is parsed by the token extractor.

## What the capture does not do

It never submits forms, never types into fields, never reads the user's
browser profile, and never executes anything beyond loading the page and the
optional hover/click/scroll you asked for. Pages that detect automation may
show a challenge instead of content; say so and fall back to a user-saved
HTML or HAR rather than trying to evade the check.
