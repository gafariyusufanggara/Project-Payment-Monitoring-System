# SOP — Web / App Development (phases 0a-7)

The end-to-end procedure. Each phase has an exit condition. Do not skip forward
past an unmet exit condition; do not loop back without saying why.

---

## Phase 0a — Read the project documents (always first)

**Exit:** you can quote the requirement you are implementing, or you have stated
that no project documents exist.

`docs/` contents differ per project. Never assume filenames. Discover, then read
only what is relevant:

```js
ctx_batch_execute(commands: [
  {label:"docs-tree", command:"rtk find docs -type f -name *.md"},
  {label:"docs-root", command:"rtk find . -maxdepth 1 -name *.md"}
], queries: ["requirements","stack","features","design system"])
```

Read the files whose names map to the task. Common ones:

| File | Wins over |
|---|---|
| `docs/PRD.md` | Your assumptions about scope |
| `docs/STACK.md` | Any framework guess |
| `docs/features/*.md` | Your idea of acceptance criteria |
| `DESIGN.md` / `docs/DESIGN.md` | Hallmark themes |
| `docs/adr/*.md` | Any later shortcut |

Rules:

- These documents are the source of truth. They beat upstream library docs and
  your training data.
- Quote the requirement before you write code.
- Read to understand, not to quote at length. `ctx_execute_file` for anything
  over ~200 lines.
- Never edit these documents unless asked.
- If a document and the code disagree, report the conflict. Do not silently pick
  one side.
- If `docs/` does not exist, say so once and continue.

## Phase 0b — Detect stack

**Exit:** `.opencode/STACK.md` exists in the project, or the agent has said
"no stack detected" and stopped.

Read `.opencode/sops/STACKS.md`. Detect with a single batch call, write `.opencode/STACK.md`
once, then load only that stack's MCP and skills.

If `docs/STACK.md` exists it is authoritative; `.opencode/STACK.md` records what
the code actually contains. When they differ, report the difference rather than
overwriting either.

Never assume a framework. Never scaffold into an unknown directory.

## Phase 1 — Understand the codebase

**Exit:** you can name the files you will touch and the existing pattern you
will follow.

```bash
graphify query "<the feature area>"     # when graphify-out/ exists
graphify explain "<concept>"
```

If there is no graph and the repo is non-trivial:

```bash
graphify .        # build it once, then query
```

Read existing sibling components and the nearest tests **before** writing code.
Match their conventions: file naming, import style, error handling, state
management.

## Phase 2 — Spec (only when the change spans >1 file or >1 concern)

**Exit:** the user has a concrete spec and has approved the scope.

- Use `to-spec` (global skill) (or `to-tickets` (global skill) when it should become tickets).
- Ambiguity in requirements, data shape, or UX means ask **once**, in a short
  numbered list, then proceed. Do not ask one question per turn.
- For a design-heavy feature, run a short grill first: `grill-me` (global skill).

Skip this phase for a one-file bug fix. Say you are skipping it.

## Phase 3 — Plan

**Exit:** an ordered list of steps, each naming a file.

- `code-architect` (global skill) for a new module or a non-obvious data flow.
- Otherwise write the plan inline: 3-7 numbered steps.

## Phase 4 — Build

**Exit:** the change compiles and runs locally.

Order of work:

1. **Data / types first.** Types, schema, API contract.
2. **Logic.** Plain functions, pure where possible.
3. **UI shell.** Structure with real content, no placeholder hero.
4. **UI polish.** Tokens, states, motion.

Rules during build:

- **UI work loads `.opencode/skills/hallmark` first** (new page/design) or
  `.opencode/skills/refactoring-ui` (existing UI that must be improved). Read
  `.opencode/sops/DESIGN.md` for the floor and the bans.
- No comments unless asked. No dead code. No `TODO` left in a handoff.
- No new dependency without saying why and confirming it is not already present.
- Follow security basics: never log secrets, never put secrets in client
  bundles, validate at the boundary, encode output.
- Keep diffs small and reviewable. One concern per change.

## Phase 5 — Verify (mechanical)

**Exit:** all commands pass, or every failure is explained and accepted by the
user.

Use `.opencode/sops/STACKS.md` for exact commands. With `rtk` prefix:

```bash
rtk npm run build
rtk npx tsc --noEmit        # or vue-tsc / svelte-check / astro check
rtk npx eslint .            # or biome check
rtk npx vitest run          # or pytest / go test / cargo test
```

Then start the dev server (background) and move to Phase 6. Do not stop at
"build passes" for anything that renders.

## Phase 6 — Verify (visual and real)

**Exit:** screenshots at three viewports, zero `sloplint` FAIL, no console
errors, no critical a11y issue.

```bash
node .opencode/skills/hallmark/scripts/sloplint.mjs <path> --render
```

Then `playwright` MCP: resize 320 / 768 / 1440, screenshot each. Then
`chrome-devtools` MCP: console, network, a11y, performance trace.

Checklist to state explicitly in the handoff:

- [ ] Mobile 320: no horizontal scroll, text readable, taps >= 44px
- [ ] Tablet 768: grid does not collapse oddly
- [ ] Desktop 1440: hero content above the fold, measure capped
- [ ] Keyboard: Tab reaches every control, focus ring visible
- [ ] Reduced motion: animations degrade to instant
- [ ] Empty / loading / error states exist
- [ ] Dark mode implemented or declared out of scope

## Phase 7 — Review and hand off

**Exit:** an independent review pass found nothing blocking.

- `code-review` (global skill) for logic and convention bugs.
- `security-review` (global skill) for anything touching auth, input, network, or files.
- Report in this order: **what now works**, **how to see it**, **what is
  deliberately not done**, **open risks**.

Never claim a UI looks right without the Phase 6 evidence.

---

## Definition of done

See `.opencode/sops/QUALITY_GATE.md`. A task is done when every box is checked or
explicitly waived with a reason the user accepted.

## Failure modes to avoid

| Sloppy behaviour | Correct behaviour |
|---|---|
| Assuming Next.js in a Vue repo | Detect first, write `.opencode/STACK.md` |
| Reading 40 files to "understand" | `graphify query`, then read 3 |
| Writing the whole page before rendering | Build the hero, render it, then continue |
| "Should look good now" | Screenshot at 3 viewports, paste evidence |
| Fixing 9 things in one diff | Smallest change that satisfies the task |
| Adding a dependency for a 5-line util | Write the 5 lines |
| Leaving placeholder copy in a handoff | Real copy, or label it as placeholder |
