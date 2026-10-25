# Design tokens

A token is a design decision that repeats: the blue every primary action uses,
the 8px rhythm every padding follows, the 150ms every hover takes. The job is
to find those decisions in a sea of computed values and give them names the
user's project can use.

## Run it

```bash
python3 scripts/extract_tokens.py ./rfa/example/1440x900 ./rfa/example/390x844 --out ./rfa/example/tokens
```

Pass every viewport and state capture you have; counts add up across them.
Outputs `tokens.json` (everything, with usage counts), `tokens.css` (`:root`
custom properties) and `tailwind.theme.js` (a `theme.extend` snippet).

## Deciding what is a token

Usage count is the first filter. In `tokens.json` each value carries `uses`;
a colour used on 40 elements is a token, one used on a single hero gradient
is a one-off. The CSS and Tailwind outputs apply `--min-uses` (default 2).

The second filter is intent. The capture lists `props`: the custom property
names whose declared value equals this one. `#2563eb` with
`props: ["--color-primary"]` is the author telling you its name. Prefer those
names over invented ones; the script already does this when it can.

The third filter is role. `colors.byRole` splits text, background and border
usage. The same hex can be a text colour on buttons and a background colour on
badges; name it once (`--color-primary`) and let roles be where it is applied.

## Modern colour (oklch / display-p3)

Tailwind v4 and current design systems author colour in `oklch()`. The
extractor converts oklch/oklab/`color(display-p3 ...)` to hex, so the palette
and contrast still work. When the user's stack is modern, keep the token in its
original oklch form in the theme (wider gamut, nicer interpolation) and use the
hex only as a fallback and for the report. `color-mix()` tints resolve to
`color(srgb ...)` in the capture and are canonicalised on comparison.

## Colour

- `page.background` and `page.text` come from `<body>` when it declares them,
  otherwise from the largest painted area. Everything else is measured against
  that background with WCAG contrast (`contrastOnPageBg`); flag text colours
  under 4.5:1 in the report, the user may want to keep or fix them knowingly.
- `accent` versus `neutral` is a chroma/luminance split. Dark inks and light
  greys land in neutral even when slightly tinted (a navy `#111827` is "ink",
  not "blue").
- Alpha colours (`#00000014`) are usually borders and overlays; keep them as
  separate tokens, do not flatten them onto the background.
- Dark mode is a second capture, not a derived palette. If the site has a
  toggle, capture it and extract a second set; map pairs by role.
- Gradients live in `background-image` on the nodes, not in the colour
  counts; grep `capture.json` for `linear-gradient` when the design uses them.

## Typography

- `families` ranks resolved first families. Check `fontFaces` for the actual
  `src` and `loaded` for what the browser really rendered. A family in CSS that
  never appears in `loaded` fell back to the next in the stack.
- `scale` groups tag + family + size + weight + line-height combinations. Read
  it as the type scale: h1 48/1.1/800, h2 32/1.2/700, body 16/1.6/400. Turn it
  into named steps (`display`, `h1`, `body`, `caption`) rather than raw pixels.
- Line heights come back as pixels; divide by the font size to recover the
  unitless ratio the author almost certainly wrote.
- Letter spacing on headings (`-0.02em`) is a deliberate choice worth keeping.
- Licensing: a font served from the target's own domain or a paid foundry CDN
  (Typekit, fonts.com, Monotype) is theirs. Suggest an open substitute with
  similar metrics: Inter for Helvetica/SF/Aktiv, Source Serif for Georgia-likes,
  JetBrains Mono for proprietary monos. Google Fonts and Fontsource are safe.

## Spacing

- `baseUnitGuess` is the grid the most frequent paddings and margins share
  (4 or 8 in most modern sites, 5 in older ones). Express the scale as
  multiples of it: `--space-1: 4px` through `--space-16: 64px`.
- `gaps` are flex/grid gaps; they are usually the same scale.
- Values that do not fit the grid (`14px`, `18px`) are often font-relative
  (`0.875rem`, `1.125rem`). Check whether the author used rem.

## Radii, shadows, borders

Radii cluster into two or three steps (`4/8/12`, `6/12/24`) plus `9999px` for
pills. Shadows are returned as the computed string; name them by elevation
(`--shadow-sm`, `--shadow-md`) ordered by blur radius. A 1px border in a light
grey is the most common border token; note whether it is a hairline
(`#e5e7eb`) or a translucent black.

## Breakpoints and layout

`layout.breakpoints` lists every `min-width`/`max-width` in the stylesheets
with rule counts. The ones with many rules are the real breakpoints. Match
them to a convention when they fit (Tailwind 640/768/1024/1280/1536,
Bootstrap 576/768/992/1200/1400). `containerMaxWidths` gives the content
width (1080, 1200, 1280 are typical).

## Motion

`motion.durations` and `easings` are the timing vocabulary: typically 150ms
for hovers, 200 to 300ms for reveals, `ease`/`ease-out`/a custom
cubic-bezier. Keyframe names are listed; their steps are in `capture.json`.
See `interactions-and-motion.md` for how to capture what they do.

## Output naming

Use the project's existing convention if it has tokens already. Otherwise:
`--color-{role}`, `--font-{role}`, `--text-{step}`, `--space-{n}`,
`--radius-{size}`, `--shadow-{level}`, `--duration-{speed}`,
`--ease-{name}`. For Tailwind, paste `tailwind.theme.js` into
`theme.extend` and rename the generated keys (`r1`, `s1`) to semantic ones.
