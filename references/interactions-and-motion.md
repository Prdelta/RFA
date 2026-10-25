# Interactions and motion

Motion is where "looks the same" and "feels the same" part ways. The capture
gives you declared transitions and keyframes; the rest you measure by
capturing before and after a trigger.

## What the capture already has

- Per node: `transition-property`, `transition-duration`,
  `transition-timing-function`, `transition-delay`, `animation-name`,
  `animation-duration`, `animation-timing-function`,
  `animation-iteration-count`, `transform`, `transform-origin`, `opacity`.
- `keyframes`: every `@keyframes` with its steps.
- `mediaQueries`: look for `prefers-reduced-motion`.
- `frameworkHints` / stack detection: Framer Motion, GSAP, Lottie, Lenis,
  AOS, Swiper tell you the animation is script-driven.

## Measuring a hover or click

```bash
node scripts/capture_page.js URL --out ./rfa/x-rest  --selector ".btn-primary" --no-har
node scripts/capture_page.js URL --out ./rfa/x-hover --selector ".btn-primary" --hover ".btn-primary" --no-har
```

```bash
python3 scripts/diff_captures.py ./rfa/x-rest ./rfa/x-hover
```

Properties that changed are the animated ones; the transition line on each
node gives the timing. On the skill's own test page this reads: background
`rgb(37,99,235)` to `rgb(29,78,216)` and `transform` to `translateY(-1px)`,
transition `transform, background-color 0.15s, 0.2s ease`. Same recipe with
`--focus` for focus rings and `--click` for open/closed states.

For script-driven motion (no transition declared, but the style changed), the
duration is not in CSS. Estimate by capturing with `--wait 0`, `--wait 150`,
`--wait 300` after the trigger and noting when the values settle; report it as
an estimate with the sampling you used.

## Scroll effects

Capture at several `--scroll-to` offsets and compare: parallax (background
position or transform changes with scroll), reveal-on-scroll (opacity 0 to 1
and a small translate; AOS, IntersectionObserver), sticky headers that gain a
shadow or shrink, progress bars. Record the trigger offset and the final
state. Rebuild with `IntersectionObserver` plus CSS transitions, or the
user's motion library; do not port a 40 kB scroll library for one reveal.

## Page and route transitions

Single-page apps animate route changes (fade, slide). Capture the before and
after pages; the transition itself is usually a 200 to 300ms opacity/transform
on the page container. In Next.js or Nuxt this is view transitions or a
layout wrapper; say which the stack suggests.

## Gestures and touch

Carousels, swipe-to-dismiss, pull-to-refresh and drag are script-driven and
not observable from a static capture. Identify the library (Swiper, Embla,
Keen, Framer Motion drag) from stack detection and document the behaviour
from the library's defaults plus what you can see (dots, arrows, loop,
autoplay delay from `transition-duration` on the track).

## Scroll-driven animations and View Transitions

Two newer mechanisms the capture records as node props:

- **Scroll-driven** (`animation-timeline: view()` or `scroll()`,
  `animation-range`): the animation is tied to scroll position, not time. The
  `@keyframes` and the timeline/range are in the capture; reproduce with the
  same CSS where supported, or an IntersectionObserver + transition fallback for
  older targets.
- **View Transitions** (`view-transition-name` on elements,
  `document.startViewTransition()`): smooth morphs between states/pages. Capture
  the named elements; rebuild with the same names and let the browser tween, or
  a crossfade fallback.

## Writing it down

One line per motion in the report:

```
| What                | Trigger        | Properties             | Duration | Easing     | Source                |
| Primary button      | hover          | background, translateY | 150/200ms| ease       | CSS transition        |
| Pricing card        | load           | opacity, translateY    | 400ms    | ease-out   | @keyframes fadeUp     |
| Section reveal      | scroll 60%     | opacity, translateY 24 | ~300ms   | est.       | IntersectionObserver? |
```

Mark estimates as estimates. Respect `prefers-reduced-motion` in the rebuild
whether or not the original does.
