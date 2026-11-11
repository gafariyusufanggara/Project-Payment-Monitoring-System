---
description: "Audit existing UI for slop, hierarchy, spacing, type, colour, a11y and performance, with real screenshots at four viewports. Reports findings ranked by severity. Use when a UI looks off, feels generated, or before shipping a page."
agent: ui-designer
subtask: false
---

Audit only. Do not rewrite unless the user asks for the fix afterwards.

## Inputs

- Target: a route, an HTML file, or a component directory. If not stated, ask
  which one in one line.

## Procedure

### 1. Detect the system

Framework, Tailwind version, tokens, component library, dark mode
(`.opencode/sops/STACKS.md` phase 0b + one `stacks/*.md`). State it in one line.

### 2. Deterministic pass

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <target> --render
```

If the target is a dev-server route rather than a file:

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <url> --url
```

For exported HTML/CSS, add the independent second opinion:

```bash
npx -y @gessobuild/anti-slop check <target> --json
```

Report raw counts: FAIL, REFLEX, WARN.

### 3. Seven-view walk (refactoring-ui)

In causal order, reading `.opencode/skills/refactoring-ui/references/`:

1. Hierarchy (02)
2. Layout and spacing (03)
3. Typography (04)
4. Colour and contrast (05)
5. Depth and shadows (06)
6. Imagery (07)
7. Finishing touches (08)

### 4. Real rendering

**Ask the user first.** Browser verification takes time. If declined, record
`WAIVED G5/G6`, report the static findings only, and state "not visually
verified".

`playwright` MCP: 320 / 768 / 1280 / 1440, screenshot each. Look for horizontal
scroll, heading overflow, hero not fitting, focus invisible, misaligned grid.

`chrome-devtools` MCP against the production/preview server: console errors,
network 404s, a11y critical, LCP, CLS.

### 5. Judge

Apply the anti-slop test from `.opencode/sops/DESIGN.md`:
- Could the theme be guessed from the category alone?
- Does it survive the squint test?
- Could any product own this, or is it generic?

## Report

```
## Verdict
<one line: passes floor / fails floor / passes floor but generic>

## Blocking
- [<rule id or gate>] <issue> — <evidence: file:line or screenshot> — <fix>

## Should fix
- ...

## Nitpicks
- ...

## Numbers
sloplint: N FAIL / N REFLEX / N WARN
a11y: N critical
LCP: x.x s   CLS: 0.0x
Screenshots: <paths>
```

Rank by severity, most damaging first. Every finding cites evidence. If the UI
is clean, say so in one line and stop.
