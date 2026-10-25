# Frontend reverse-engineering report: {{target name}}

## 1. Target and scope
- URL / file: {{url}}   Captured: {{date}}   Viewports: {{list}}
- Asked for: {{whole page | component X | tokens only | interaction Y}}
- Target stack for the rebuild: {{e.g. React + Tailwind}}
- Captured states: {{resting, hover nav, menu open, scroll 600}}
- Not captured: {{auth-only pages, error states, ...}}

## 2. Stack detection
| Category | Finding | Confidence | Evidence |
| -------- | ------- | ---------- | -------- |
| framework | | | |
| css | | | |
| ui-library | | | |
| motion | | | |
Rendering mode: {{server/static | client shell}}   Source maps: {{yes/no}}

## 3. Design tokens
Colors (role, hex, uses, contrast on page bg, original var if any):
| Role | Hex | Uses | Contrast | Original name |
| ---- | --- | ---- | -------- | ------------- |
Typography (family, sources/licence, scale steps):
Spacing (base unit, scale), radii, shadows, borders:
Breakpoints and container widths:
Motion vocabulary (durations, easings):

## 4. Component inventory
### {{ComponentName}}
Selector · instances · box · padding · radius · border · shadow
Children · variants · states · a11y notes · rebuild file

## 5. Layout and responsive rules
Per breakpoint: what changes (grid columns, nav collapse, type sizes, hidden elements).

## 6. Motion and interaction
| What | Trigger | Properties | Duration | Easing | Source |
| ---- | ------- | ---------- | -------- | ------ | ------ |

## 7. Reconstruction
Files written, with the original selector each derives from. Tokens file. Dependencies added.

## 8. Parity check
| Viewport | pixelMatch | perceptual | Main differences |
| -------- | ---------- | ---------- | ---------------- |
Checklist results (structure, type, spacing, breakpoints, states, keyboard, reduced motion).

## 9. Unknowns and limitations
States not captured, cross-origin stylesheets not readable, truncated node lists, estimates.

## 10. White-label template
- Brand name lifted to `--brand-name`: {{original}} -> {{BRAND_NAME}}
- Theming contract (variables to flip to re-skin): {{list}}
- Neutral default theme shipped; captured theme kept for parity only.
- Brand assets replaced: logo, favicon, fonts (-> open substitutes), imagery (-> placeholders), copy (-> rewritten).
- Generic scale carried into the template: radius, spacing base, breakpoints, type scale, motion.

## 11. Licensing notes
Fonts (source, licence, substitute used), icons, images, brand elements, anything deliberately not copied.
