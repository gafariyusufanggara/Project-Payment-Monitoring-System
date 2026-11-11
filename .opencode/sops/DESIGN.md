# SOP — Design Law (Anti-Slop)

Three layers. Lower number beats higher number when they disagree.

- **Layer 1 — Hallmark Floor.** Non-waivable, every user-visible UI. Load the
  Hallmark skill only for new pages.
- **Layer 2 — refactoring-ui.** Diagnostic rulebook (151 rules).
- **Layer 3 — design-taste / impeccable.** OKLCH colour, motion, interaction
  states, concrete bans.

A UI task is not done until Layer 1 passes `sloplint` and Layer 2 has been
walked. Verification commands and gate checklists: see **Verification** below and
`.opencode/sops/QUALITY_GATE.md` gates 4-6.

## Layer 1 — Hallmark Floor (never waivable)

Copied in intent from `.opencode/skills/hallmark/SKILL.md`. Read that before
building a new page.

1. Every colour and font goes through a token at `:root` or a declared theme
   block. No literal colour or `font-family` past the token block.
2. Never `transition: all`. Never animate `width`, `height`, `top`, `left`.
3. Never one italic word inside a roman heading.
4. `overflow-x: clip` on `html` and `body`. Never `hidden`, never `100vw`.
5. Image grid tracks use `minmax(0, 1fr)`; display heads carry
   `overflow-wrap: break-word; min-width: 0`.
6. Every interactive element has `:focus-visible`, appearing instantly.
7. Every animation has a `prefers-reduced-motion: reduce` fallback; content is
   visible with scripting off.
8. Never an invented metric, testimonial, logo wall, or case-study count.
9. Never an eyebrow, and never a label in tracked capitals or small caps.
   Labels, captions, table heads, tags, nav links use the body face (or theme
   label face), one step smaller, sentence/lower case, untracked.
10. Never middle-dot-joined meta strings, arrows glued to link text, or
    decorative status dots.
11. Never a purple-to-blue gradient, a card inside a card, an emoji as an icon,
    or a hand-drawn browser/OS window.
12. Hero headline, one sentence, and primary action all visible at 1280x800
    without scrolling.
13. About 80 words on one screen; the hero's text is the headline, one sentence,
    and its actions.
14. Container capped and centred: at 1920 gutters grow, measure and grids do not.
15. First non-empty line of the CSS source carries the critique stamp.
16. Run `sloplint` before handing back. Fix every `FAIL`; fix or waive every
    `REFLEX`.

## Layer 2 — refactoring-ui: detect before you judge

Prime directive: **an existing system always wins.** Translate rules into the
project's vocabulary; never silently migrate or overwrite.

Before judging, state: framework (SSR/SPA), Tailwind version (v4 `@theme` vs v3
config), existing tokens, component library, dark mode.

Walk the seven views in causal order — fixing hierarchy changes what counts as a
spacing problem:

```
hierarchy -> layout/spacing -> typography -> colour -> depth -> imagery -> finishing
```

One file per view in `.opencode/skills/refactoring-ui/references/`, plus
`13-audit-rubric.md` and `14-antipatterns.md`.

## Layer 3 — concrete bans (design-taste catalogue)

Match-and-refuse. Rewrite the element, do not decorate it.

| Ban | Instead |
|---|---|
| Side-stripe border (`border-left/right` > 1px accent) | full border, background tint, leading number/icon, or nothing |
| Gradient text (`background-clip: text` + gradient) | single solid colour; emphasise with weight or size |
| Glassmorphism as default | rare and purposeful, or nothing |
| Hero-metric template (big number + label + stats + gradient) | one idea, one screen, real content |
| Identical card grids (icon + heading + text) | vary structure, or use a list/table/prose |
| Tiny uppercase tracked eyebrow | untracked sentence-case label, or no kicker |
| `01 / 02 / 03` above every section | numbers only for a real sequence |
| Ghost card (`1px border` + blur >= 16px) | solid border, or shadow; pick one |
| `border-radius: 32px+` on cards/sections/inputs | 12-16px on cards; pill only for pills |
| Hand-drawn/sketchy SVG illustration | real photography, or clean geometry |
| `repeating-linear-gradient` stripes | flat surface or image |
| "X theater" / "not just X, it's Y" copy | plain claim with a specific fact |
| Em dash mid-sentence in UI copy | comma, colon, period, or two sentences |

## Verification (mandatory before claiming done)

### Static + render lint

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <file-or-dir> --render
```

- Exit `0` clean.
- Exit `1` slop found. Fix every `FAIL`; fix or waive every `REFLEX` on record in
  the CSS stamp with real evidence.
- Exit `2` no `.html` found. For a dev-server build, pass `--url`.
- `--render` needs Chrome. Without Chrome the static tier still runs; say so.

HTML/CSS export second opinion:

```bash
npx -y @gessobuild/anti-slop check <file-or-dir> --json
```

### Real screenshots

Ask the user before the browser pass. If declined, record `WAIVED G5/G6` and say
"UI not visually verified"; never imply otherwise. Use `playwright` MCP, never
imagination. A UI claim without a screenshot is a guess. Resize 320x800,
768x1024, 1280x800, 1440x900 and screenshot each. Checklist:
`.opencode/sops/QUALITY_GATE.md` gates 5-6.

### Accessibility and performance

Use `chrome-devtools` MCP against the production/preview server (`build` then
`start`/`preview`), never the dev server. Run the performance trace
(`performance_start_trace` -> `stop_trace` -> `analyze_insight`). Pass: LCP
< 2.5 s, CLS < 0.1 on desktop; zero console errors; zero critical a11y.

## Rules of engagement

- Never invent content or images. Placeholder text is labelled, or the section is
  omitted.
- One idea per screen. Two primary actions means the design is unfinished.
- Contrast: body >= 4.5:1, large text >= 3:1. Verify, do not estimate.
- Reduced motion is a requirement. Dark mode is implemented or declared out of
  scope; half-way is a defect.
- Do not redesign what the user did not ask to redesign. Match the existing
  system. Run Hallmark only for a new page/design the user asked for.
