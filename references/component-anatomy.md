# Component anatomy

A page is a handful of components repeated with variations. Finding them turns
a 3000-node capture into a dozen things to build.

## Finding repeated structures

```bash
python3 scripts/inventory_components.py rfa/example/1440x900 --markdown
```

groups elements that share an author-named class root (`card`,
`Button_root__x1` minus the hash) or, failing that, the same tag, child
sequence and box styling. Each candidate comes with instance count, box range,
common styles, the properties that vary between instances (your variants),
child composition, interaction hints and a11y warnings. Treat it as a first
cut: merge groups that are one component with different content, split groups
that merely look alike. The signals it uses, which you can apply by hand on
the parts it misses:

- Several children of one parent with identical child tag sequences
  (`div > img + h3 + p + a`) are cards in a list.
- Elements sharing a class prefix (`card`, `Card_root__x`, `sc-abc`) or the
  same `data-slot`/`data-testid` value.
- Elements with identical padding, radius, shadow and border even when their
  classes differ: hashed CSS-in-JS still produces identical computed styles.
- Landmark roles and tags: `header`, `nav`, `main`, `aside`, `footer`,
  `[role=dialog]`, `[role=tablist]`, `[role=menu]`.

For each candidate, write down: a name, the selector that finds all
instances, the instance count, and the bounding box range (from `rect`).

## Variants and states

Instances that differ in one or two properties are variants of one component,
not separate components. Look for:

- A primary/secondary/ghost split on buttons (background filled vs outlined vs
  none; same padding and radius).
- A featured card (different border colour, a badge child, maybe a `scale`
  transform).
- Sizes (same shape, padding and font size step up together).

States need their own captures (see `capture-workflows.md`): hover, focus,
active, disabled (`[disabled]`, `aria-disabled`, reduced opacity), selected
(`aria-selected`, `data-state=active`), open (`aria-expanded=true`), loading
(skeleton, spinner child), empty and error (usually only reachable by hand).
Record for each state which properties change and over what transition.

## Web components (shadow DOM)

A custom element (`<sl-button>`, `<brand-card>`) renders its UI inside a shadow
root. The capture pierces open shadow roots, so those nodes are in
`capture.json` with `shadow:true`, and the host carries `shadowHost:true` and a
hyphenated `tag`. Treat one custom element as one component: its shadow subtree
is the internal structure, its attributes and `slot`/`part` are the public API.
Rebuild it as a component in the user's framework with the same slots, parts and
`aria` contract. A closed shadow root is unreadable; capture its screenshot and
rebuild from the visual plus the element's public attributes, and say it was
closed.

## Accessibility contract

The attributes in `attrs` carry the behavioural spec. Keep them in the rebuild:

- `role`, `aria-label`, `aria-expanded`, `aria-controls`, `aria-haspopup`,
  `aria-selected`, `aria-current`, `aria-hidden`, `tabindex`.
- Native semantics: a `button` that looks like a link, a `a` that looks like
  a button, headings in order, lists for lists, `label` for inputs.
- Focus outline: `outline-*` values in `styles`, often only on
  `:focus-visible` in the stylesheet text.
- Reduced motion: `prefers-reduced-motion` rules in `mediaQueries`.

If the original gets these wrong (a clickable `div`, missing labels), say so
and do better in the rebuild; parity does not mean copying mistakes.

## Component spec format

One block per component in the report:

```
### PricingCard
Selector: .grid > .card            Instances: 3 (1440), 3 (390)
Box: 328x312 @1440, 342x312 @390   Padding 24   Radius 12   Border 1px #e5e7eb   Shadow md
Children: h3 (20/700) · .price (36/800) · ul (14/1.6 muted) · Button[primary]
Variants: featured (border --color-primary, Badge child top -12px right 16px)
States: entrance animation fadeUp 400ms ease-out; no hover
A11y: plain divs, no role; heading level jumps h1 -> h3 (flag)
Rebuild: components/PricingCard.tsx + Badge.tsx, uses Button
```

## Layout structure

Separate layout components (page shell, container, grid, stack) from content
components. Read `display`, `grid-template-columns`, `flex-direction`, `gap`,
`max-width`, `margin: auto` on the ancestors of your components. Then
compare the same ancestors across viewports: a `repeat(3, 1fr)` that becomes
`1fr` at 390 is the responsive rule to carry over.

Note sticky and fixed elements (`position` in styles) and their `z-index`; the
`zIndex` list in the tokens gives the layering scheme.

## Icons and images

`icons` in the capture counts inline SVGs, `<use>` sprites, images and icon
fonts. Inline SVG paths are copyrightable artwork; identify the icon set
instead (Lucide, Heroicons, Feather, Phosphor, Material, Font Awesome) by
viewBox, stroke width and shapes, and use that set or an open equivalent.
Photos and illustrations are never copied; use placeholders of the same
aspect ratio and tell the user.
