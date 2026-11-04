# SOP — Quality Gate (Definition of Done)

A task is not done because the code exists. It is done when every gate that
applies has passed, or is explicitly waived with a reason the user accepted.

---

## Gate 0 — Requirement traceability (always applies)

- [ ] The requirement being implemented is quoted from a project document under
      `docs/`, or stated explicitly as "not documented; user said X in this
      session".
- [ ] Nothing implemented contradicts `docs/PRD.md`, `docs/STACK.md`,
      `DESIGN.md`, or a feature doc.
- [ ] Any conflict between a document and the existing code was reported to the
      user, not silently resolved.
- [ ] No library API call was written from memory. Each one is verifiable
      against documentation fetched this session, or against code already in
      the repo.

## Gate 1 — Correctness (always applies)

- [ ] The requested behaviour works, verified by running it, not by reading it.
- [ ] No new `any` / `unknown` cast / `# type: ignore` without a one-line
      justification in the handoff.
- [ ] No dead code, commented-out blocks, or debug `console.log` left behind.
- [ ] No `TODO` or `FIXME` introduced in a handoff.
- [ ] Error paths handled: network failure, empty result, invalid input.
- [ ] No hardcoded secret, token, or credential anywhere.

## Gate 2 — Mechanical build (always applies)

Run with `rtk` prefix. Missing script = not applicable, say so.

- [ ] Build passes: `rtk npm run build` / `rtk python -m build` / `rtk go build ./...`
- [ ] Typecheck passes: `rtk npx tsc --noEmit` / `vue-tsc` / `svelte-check` / `astro check` / `mypy`
- [ ] Lint passes with **zero new** warnings: `rtk npx eslint .` / `rtk ruff check` / `rtk cargo clippy`
- [ ] Tests pass: `rtk npx vitest run` / `rtk pytest` / `rtk go test ./...` / `rtk cargo test`

Zero new warnings, not zero warnings total. Do not "fix" unrelated lint debt in
the same change.

## Gate 3 — Test coverage (applies when logic changed)

- [ ] New pure logic has at least one test.
- [ ] A bug fix has a regression test that fails before the fix.
- [ ] Tests assert behaviour, not implementation detail.
- [ ] No test skipped or deleted to make the suite green.

If the project has no test runner and the user did not ask for one, say so
rather than adding a framework silently.

## Gate 4 — Design floor (applies when UI changed)

- [ ] `node .opencode/skills/hallmark/scripts/sloplint.mjs <path> --render` reports
      **0 FAIL**.
- [ ] Every `REFLEX` is either fixed or waived in the CSS stamp with real
      evidence.
- [ ] All Layer-1 floor items from `.opencode/sops/DESIGN.md` hold.
- [ ] No item from the concrete ban table in `.opencode/sops/DESIGN.md`.

## Gate 5 — Visual evidence (applies when UI changed)

- [ ] Screenshot at 320 / 768 / 1440 from `playwright` MCP.
- [ ] No horizontal scrollbar at 320.
- [ ] Hero headline + one sentence + primary action visible at 1280x800.
- [ ] Keyboard Tab reaches every control; focus ring visible.
- [ ] `prefers-reduced-motion: reduce` degrades all animation.
- [ ] Empty, loading, and error states exist for any async surface.
- [ ] Dark mode implemented or declared out of scope in the handoff.

## Gate 6 — Accessibility and performance (applies when UI changed)

Via `chrome-devtools` MCP against the dev server:

- [ ] Console: zero errors (warnings triaged).
- [ ] Network: no 404 on fonts, images, or assets.
- [ ] a11y: zero critical violations.
- [ ] Body text contrast >= 4.5:1; large text >= 3:1.
- [ ] LCP < 2.5 s on the desktop viewport.
- [ ] CLS < 0.1.
- [ ] Images have `width`/`height` or a sized parent (no layout shift).

## Gate 7 — Review (applies to any change > 1 file)

- [ ] `code-review` (global skill) run; blockers addressed.
- [ ] `security-review` (global skill) run when auth, input parsing, network, file I/O,
      or dependency changes are involved.
- [ ] Diff is one concern. Unrelated refactors split out or dropped.

## Gate 8 — Handoff quality

The final message states, in this order:

1. **What now works** — concrete, observable.
2. **How to see it** — exact command, URL, or path.
3. **What is deliberately not done** — and why.
4. **Open risks** — anything that could bite later.
5. **Next action** — one thing, doable in under two minutes.

No "let me know if you need anything else". No recap of the plan.

---

## Waiving a gate

A gate may be waived only when the user accepts it. Record waivers in the
handoff as:

```
WAIVED G4 sloplint --render: Chrome not installed on this machine.
Static tier clean. Install Chrome then re-run to close this.
```

Never silently downgrade a gate. Never report a waived gate as passed.

## Time estimates (be concrete)

| Work | Estimate |
|---|---|
| One component, tokens and states existing | 15-30 min |
| One page from scratch, design included | 1-2 h |
| A feature across API + UI + tests | half a day |
| Fixing slop across an existing page | 1-3 h per page |
| Setting up a new stack scaffold | 30-60 min |

State the estimate before starting when the task is larger than one component.
