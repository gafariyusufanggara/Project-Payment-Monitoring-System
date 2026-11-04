# SOP — Design Law (Anti-Slop)

Three layers. Lower number beats higher number when they disagree.

- **Layer 1 — Hallmark Floor.** Non-waivable. Every output, every stack.
- **Layer 2 — refactoring-ui.** The diagnostic rulebook (151 rules from
  *Refactoring UI*, the book by Tailwind's authors).
- **Layer 3 — design-taste / impeccable.** Craft depth: OKLCH colour, motion,
  interaction states, the concrete ban catalogue.

A task that touches user-visible UI is not done until Layer 1 passes
`sloplint`, and Layer 2 has been walked.

---

## Layer 1 — Hallmark Floor (never waivable)

Copied verbatim in intent from `.opencode/skills/hallmark/SKILL.md`. Read that file before
building any new page.

1. Every colour and every font goes through a token declared at `:root` (or a
   declared theme block). No literal colour or `font-family` past the token
   block.
2. Never `transition: all`. Never animate `width`, `height`, `top`, or `left`.
3. Never one italic word inside a roman heading.
4. `overflow-x: clip` on both `html` and `body`. Never `hidden`, never `100vw`.
5. Image-bearing grid tracks use `minmax(0, 1fr)`; display heads carry
   `overflow-wrap: break-word; min-width: 0`.
6. Every interactive element has `:focus-visible`, appearing instantly.
7. Every animation has a `prefers-reduced-motion: reduce` fallback, and content
   is visible with scripting off.
8. Never an invented metric, testimonial, logo wall, or case-study count.
9. Never an eyebrow, and never a label in tracked capitals or small caps.
   Labels, captions, table heads, tags, and nav links are the body face (or the
   theme's label face), a step smaller, sentence or lower case, untracked.
10. Never middle-dot-joined meta strings, arrows glued to link text, or
    decorative status dots.
11. Never a purple-to-blue gradient, a card inside a card, an emoji as an icon,
    or a hand-drawn browser or OS window.
12. The hero's headline, one sentence, and primary action are all visible at
    1280x800 without scrolling.
13. About 80 words on any one screen; the hero's text is the headline, one
    sentence, and its actions.
14. The container is capped and centred: at 1920 the gutters grow, the measure
    and the grids do not.
15. The first non-empty line of the CSS source carries the critique stamp.
16. Run `sloplint` before handing back. Fix every `FAIL`; fix or waive every
    `REFLEX`.

## Layer 2 — refactoring-ui: detect before you judge

Prime directive: **an existing system always wins.** Translate the rules into
the project's vocabulary; never silently migrate, never overwrite.

Before any design judgment, state briefly:

1. Framework (React/Vue/Svelte/plain HTML; SSR or SPA).
2. Tailwind, and which major version (v4 `@theme` in CSS vs v3 config file).
3. Existing design tokens (CSS vars, theme object, `tokens.json`, `theme/`).
4. Component library (shadcn/Radix/MUI/Ant/Chakra) — these carry their own token
   contracts.
5. Dark mode: present, planned, or absent.

Then walk the seven views in causal order. The order matters: fixing hierarchy
changes what counts as a spacing problem, and fixing spacing often removes the
perceived need for a border.

```
hierarchy -> layout/spacing -> typography -> colour -> depth -> imagery -> finishing
```

See `.opencode/skills/refactoring-ui/references/` — one file per view, plus
`13-audit-rubric.md` and `14-antipatterns.md`.

## Layer 3 — concrete bans (design-taste catalogue)

Match-and-refuse. If you are about to write any of these, rewrite the element
with a different structure.

| Ban | Instead |
|---|---|
| Side-stripe border (`border-left/right` > 1px as accent) | Full border, background tint, leading number/icon, or nothing |
| Gradient text (`background-clip: text` + gradient) | Single solid colour; emphasise with weight or size |
| Glassmorphism as a default | Rare and purposeful, or nothing |
| Hero-metric template (big number + small label + stats + gradient) | One idea, one screen; real content |
| Identical card grids (icon + heading + text, repeated) | Vary structure, or drop the grid for a list/table/prose |
| Tiny uppercase tracked eyebrow above every section | Untracked sentence-case label, or no kicker at all |
| `01 / 02 / 03` above every section | Numbers only for a real sequence the reader needs |
| Ghost card (`1px border` + `box-shadow` blur >= 16px) | Pick one: solid border, or a shadow |
| `border-radius: 32px+` on cards/sections/inputs | 12-16px on cards; pill only for pills |
| Hand-drawn/sketchy SVG illustration | Real photography, or clean geometry |
| `repeating-linear-gradient` stripe backgrounds | Flat surface or image |
| "X theater" / "not just X, it's Y" copy | Plain claim with a specific fact |
| Em dash mid-sentence in UI copy | Comma, colon, period, or two sentences |

## Verification (mandatory before claiming done)

### Static + render lint

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <file-or-dir> --render
```

- Exit `0` = clean.
- Exit `1` = slop found. Every `FAIL` must be fixed. Every `REFLEX` must be
  fixed or waived on the record in the CSS stamp block with real evidence.
- Exit `2` = no `.html` found. For a dev-server build, pass `--url`.

`--render` needs Chrome. Without Chrome the static tier still runs; say so
instead of pretending the render checks passed.

For an HTML/CSS export, the second opinion is:

```bash
npx -y @gessobuild/anti-slop check <file-or-dir> --json
```

### Real screenshots

Use the `playwright` MCP, not imagination. A UI claim without a screenshot is a
guess.

```text
browser_resize 320x800    -> screenshot  (mobile)
browser_resize 768x1024   -> screenshot  (tablet)
browser_resize 1440x900   -> screenshot  (desktop)
```

Check on each: hero fits without scroll, no horizontal scrollbar, heading does
not overflow, focus ring visible via keyboard Tab, no layout shift on load.

### Accessibility and performance

Use the `chrome-devtools` MCP against the running dev server:

- Console: zero errors.
- Network: no 404 on assets or fonts.
- a11y tree / axe: zero critical.
- Performance trace: LCP < 2.5 s, CLS < 0.1 on the desktop viewport.

## Rules of engagement

- **Never invent content.** No fake numbers, testimonials, logos, or
  case-study counts. Placeholder text is labelled as placeholder, or the section
  is omitted.
- **Never invent images.** Use what the project ships, or state that an asset is
  needed.
- **One idea per screen.** If the screen needs two primary actions, the design
  is not finished.
- **Contrast.** Body text >= 4.5:1, large text >= 3:1. Verify, do not estimate.
- **Reduced motion is a requirement, not a nicety.**
- **Dark mode** must be explicitly either implemented or declared out of scope.
  Half-way dark mode is a defect.
- **Don't redesign what the user did not ask to redesign.** If the user asked
  for a new feature, match the existing system. Only run Hallmark when the user
  asks for a new page/design, or names Hallmark.
