# White-labeling: from replica to reusable template

The goal of this phase is a **brand-neutral template**: the structure and
patterns of the original, with every brand decision turned into a variable and
a neutral default in place of the original's identity. Someone can then drop in
their own brand and get a finished, differently-branded site. This is the
standard product of UI template marketplaces, and it is legitimate precisely
because the brand itself is removed, not re-used.

## Build themeable from the start

Do not hardcode the captured values and then try to de-brand later. While you
reconstruct (see `reconstruction.md`), reference variables from the beginning:

- Colour: `background: var(--brand-primary)`, never the captured `#2563eb`.
- Font: `font-family: var(--brand-font-body)`, never `"ProprietarySans"`.
- Logo: a `<Logo/>` component or `--brand-logo` slot, never their SVG.
- Name: `{{BRAND_NAME}}` or `var(--brand-name)`, never the literal brand.
- Radius/elevation: `var(--radius-2)`, `var(--shadow-1)` from the shared scale.

Then white-labeling is just: generate the config, ship the neutral theme, and
confirm nothing brand-specific leaked into component code.

## Run the de-brand pass

```bash
python3 scripts/whitelabel.py --tokens ./rfa/site/tokens/tokens.json \
  --capture ./rfa/site/1440x900 --capture ./rfa/site/390x844 \
  --brand-name "Acme" --stack tailwind --out ./template/brand
```

It writes:

- **brand.config.json** — the single source of brand truth. Two themes:
  `neutral` (an unbranded indigo/slate default to ship) and `captured-example`
  (the original's values, kept only for parity and as a worked example). Plus
  the generic `scale` (radius, spacing base, shadows, breakpoints, type scale,
  motion) that carries over unchanged because it is not brand-specific.
- **theme.neutral.css** — `:root` variables with the neutral default and a dark
  block. This is the theme the template ships with.
- **theme.captured.css** — the same variables with the original's values.
  Use it only to check parity against the original; do not distribute it as the
  default of a general-use template.
- **tailwind.theme.js** — `theme.extend` whose colours read the CSS variables,
  so the config and the CSS stay the single control surface.
- **brand-assets.md** — the checklist of everything to replace: brand name
  occurrences, logo and favicon, fonts (with licence flags and open
  substitutes), imagery, and marketing copy.

## The theming contract

The script prints a short list of variables that, flipped together, re-skin the
whole template: primary and its hover, secondary, accent, display and body
fonts, base radius, logo and name. Keep that list small and documented in the
template's README; everything else (neutrals, spacing, shadows, breakpoints) is
the shared base a brand should rarely touch. A good test: changing only the
contract variables should produce a convincingly different brand with no edits
to component files.

## Replace, do not carry over

`brand-assets.md` is a worklist, not a formality:

- **Name**: find and replace every occurrence, including `<title>`, nav, footer
  and meta, with the name variable.
- **Logo / favicon**: swap for a neutral placeholder mark. Never ship the
  original's logo file.
- **Fonts**: ship the open substitutes the script suggests (Inter, Source
  Serif 4, JetBrains Mono, Plus Jakarta Sans). A font flagged self-hosted or
  paid must not be redistributed with the template; the substitute keeps metrics
  close so the layout holds.
- **Imagery**: replace photos and illustrations with placeholders of the same
  aspect ratio. These are almost never licensed for reuse.
- **Copy**: rewrite marketing text to neutral placeholder copy
  (lorem-like but on-topic). Verbatim copy is both copyrighted and brand-bound.

## Verify the template is actually neutral

1. Grep the component code for the captured hues, the original font names, the
   brand name and any original asset path. Zero hits is the bar.
2. Apply a second, obviously different theme (swap the contract variables) and
   screenshot. If the result still reads as the original brand, something is
   hardcoded; find it with `diff_captures.py --mode parity` against the neutral
   render.
3. Confirm `brand-assets.md` has no unchecked item.

## Ship

A white-label template is usually: the component library, the `brand.config`
plus `theme.neutral.css`, a Tailwind/CSS base, placeholder assets, and a README
documenting the theming contract and how to add a brand. Offer the faithful
replica (captured theme) alongside only as an example brand, clearly labelled.
