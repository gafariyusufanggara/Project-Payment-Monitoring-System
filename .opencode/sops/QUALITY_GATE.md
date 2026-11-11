# SOP — Quality Gate (Definition of Done)

Done = every applicable gate passed, or explicitly waived with a reason the user
accepted. Design commands live in `.opencode/sops/DESIGN.md`; this file is the
checklist.

## Gate 0 — Requirement traceability (always)

- [ ] Requirement quoted from `docs/`, or stated as "not documented; user said X".
- [ ] Nothing contradicts `docs/PRD.md`, `docs/STACK.md`, `DESIGN.md`, or a feature doc.
- [ ] Doc-vs-code conflict reported, not silently resolved.
- [ ] No library API written from memory; each verified this session or in repo.

## Gate 1 — Correctness (always)

- [ ] Behaviour works, verified by running it.
- [ ] No new `any` / `unknown` cast / `# type: ignore` without a one-line reason.
- [ ] No dead code, commented-out blocks, or debug `console.log`.
- [ ] No new `TODO` / `FIXME`.
- [ ] Error paths handled: network failure, empty result, invalid input.
- [ ] No hardcoded secret, token, or credential.

## Gate 2 — Mechanical build (always)

Run with `rtk` prefix. Take the exact commands from the stack file's **Verify**
section; the examples below are illustrative only. Missing script = gap, not
pass: record `N/A <check>: <reason>` and ask for the command. Do not claim a gate
passed.

- [ ] Build: `rtk npm run build` / `rtk python -m build` / `rtk go build ./...`
- [ ] Typecheck: `rtk npx tsc --noEmit` / `vue-tsc` / `svelte-check` / `astro check` / `mypy`
- [ ] Lint zero **new** warnings vs a baseline captured before the change:
      `rtk npx eslint .` / `rtk ruff check` / `rtk cargo clippy`
- [ ] Tests: `rtk npx vitest run` / `rtk pytest` / `rtk go test ./...` / `rtk cargo test`

If a baseline cannot be captured, report the absolute count and list pre-existing
warnings as `N/A pre-existing`. Never "fix" unrelated lint debt in the same
change.

## Gate 3 — Test coverage (when logic changed)

- [ ] New pure logic has at least one test.
- [ ] Bug fix has a regression test that fails before the fix.
- [ ] Tests assert behaviour, not implementation detail.
- [ ] No test skipped or deleted to make the suite green.

No test runner and the user did not ask for one: say so, do not add a framework
silently.

## Gate 4 — Design floor (when UI changed)

- [ ] `sloplint --render` reports **0 FAIL** (command: `DESIGN.md`).
- [ ] Every `REFLEX` fixed or waived in the CSS stamp with evidence.
- [ ] All Layer-1 floor items in `DESIGN.md` hold.
- [ ] No item from the `DESIGN.md` ban table.

## Gate 5 — Visual evidence (when UI changed)

**Ask the user first.** Screenshots and DevTools cost real time. If the user
declines, record `WAIVED G5/G6` and state "UI not visually verified"; never claim
it passed.

- [ ] User approved browser verification.
- [ ] Screenshots at 320 / 768 / 1280 / 1440 from `playwright` MCP.
- [ ] No horizontal scrollbar at 320.
- [ ] Hero headline + one sentence + primary action visible at 1280x800.
- [ ] Keyboard Tab reaches every control; focus ring visible.
- [ ] `prefers-reduced-motion: reduce` degrades all animation.
- [ ] Empty, loading, and error states exist for any async surface.
- [ ] Dark mode implemented or declared out of scope.

## Gate 6 — Accessibility and performance (when UI changed)

`chrome-devtools` MCP against the production/preview server, never the dev server.

- [ ] Console: zero errors (warnings triaged).
- [ ] Network: no 404 on fonts, images, or assets.
- [ ] a11y: zero critical violations.
- [ ] Body text contrast >= 4.5:1; large text >= 3:1.
- [ ] LCP < 2.5 s on the desktop viewport.
- [ ] CLS < 0.1.
- [ ] Images have `width`/`height` or a sized parent (no layout shift).

## Gate 7 — Review (any change > 1 file)

- [ ] `code-review` (global skill) run; blockers addressed.
- [ ] `security-review` (global skill) when auth, input parsing, network, file
      I/O, or dependencies changed.
- [ ] Diff is one concern. Unrelated refactors split out or dropped.

## Gate 8 — Handoff quality

State, in this order:

1. **What now works** — concrete, observable.
2. **How to see it** — exact command, URL, or path.
3. **What is deliberately not done** — and why.
4. **Open risks** — anything that could bite later.
5. **Next action** — one thing, under two minutes.

No "let me know if you need anything else". No recap of the plan.

## Waiving a gate

Only when the user accepts it. Record in the handoff:

```
WAIVED G4 sloplint --render: Chrome not installed.
Static tier clean. Install Chrome then re-run to close this.
```

Never silently downgrade a gate. Never report a waived gate as passed.

## Time estimates (be concrete)

| Work | Estimate |
|---|---|
| One component, tokens and states existing | 15-30 min |
| One page from scratch, design included | 1-2 h |
| Feature across API + UI + tests | half a day |
| Fixing slop across an existing page | 1-3 h per page |
| New stack scaffold | 30-60 min |

State the estimate before starting when the task is larger than one component.
