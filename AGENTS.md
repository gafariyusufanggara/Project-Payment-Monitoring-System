# AGENTS.md — Anti-Slop Engineering Operating System

> Purpose: ensure every AI agent produces the smallest reasonable change that
> solves the user's actual problem, preserves existing behavior, and is backed
> by verifiable evidence.

---
# context-mode — MANDATORY routing rules

context-mode MCP tools available. Rules protect context window from flooding. One unrouted command dumps 56 KB into context.

## Think in Code — MANDATORY

Analyze/count/filter/compare/search/parse/transform data: **write code** via `context-mode_ctx_execute(language, code)`, `console.log()` only the answer. Do NOT read raw data into context. PROGRAM the analysis, not COMPUTE it. Pure JavaScript — Node.js built-ins only (`fs`, `path`, `child_process`). `try/catch`, handle `null`/`undefined`. One script replaces ten tool calls.

## BLOCKED — do NOT attempt

### curl / wget — BLOCKED
Shell `curl`/`wget` intercepted and blocked. Do NOT retry.
Use: `context-mode_ctx_fetch_and_index(url, source)` or `context-mode_ctx_execute(language: "javascript", code: "const r = await fetch(...)")`

### Inline HTTP — BLOCKED
`fetch('http`, `requests.get(`, `requests.post(`, `http.get(`, `http.request(` — intercepted. Do NOT retry.
Use: `context-mode_ctx_execute(language, code)` — only stdout enters context

### Direct web fetching — BLOCKED
Use: `context-mode_ctx_fetch_and_index(url, source)` then `context-mode_ctx_search(queries)`

## REDIRECTED — use sandbox

### Shell (>20 lines output)
Shell ONLY for: `git`, `mkdir`, `rm`, `mv`, `cd`, `ls`, `npm install`, `pip install`.
Otherwise: `context-mode_ctx_batch_execute(commands, queries)` or `context-mode_ctx_execute(language: "javascript", code: "...")`. Use `language: "shell"` only when code matches the host shell.

### File reading (for analysis)
Reading to **edit** → reading correct. Reading to **analyze/explore/summarize** → `context-mode_ctx_execute_file(path, language, code)`.

### grep / search (large results)
Use `context-mode_ctx_execute(language: "javascript", code: "...")` in sandbox for portable filtering/counting.

## Tool selection

0. **MEMORY**: `context-mode_ctx_search(sort: "timeline")` — after resume, check prior context before asking user.
1. **GATHER**: `context-mode_ctx_batch_execute(commands, queries)` — runs all commands, auto-indexes, returns search. ONE call replaces 30+. Each command: `{label: "header", command: "..."}`.
2. **FOLLOW-UP**: `context-mode_ctx_search(queries: ["q1", "q2", ...])` — all questions as array, ONE call (default relevance mode).
3. **PROCESSING**: `context-mode_ctx_execute(language, code)` | `context-mode_ctx_execute_file(path, language, code)` — sandbox, only stdout enters context.
4. **WEB**: `context-mode_ctx_fetch_and_index(url, source)` then `context-mode_ctx_search(queries)` — raw HTML never enters context.
5. **INDEX**: `context-mode_ctx_index(content, source)` — store in FTS5 for later search.

### Task → tool (default mapping — no exceptions without a stated reason)

| If you are about to... | Do NOT | Use instead |
|------------------------|--------|-------------|
| grep / search across files, count/filter matches | `grep` tool on a large tree | `ctx_execute(js)` — print only the derived answer |
| read a file to **analyze** (summarize, extract, compare) | `Read` | `ctx_execute_file(path, lang, code)` |
| read a file to **edit** | — | `Read` (correct — Edit needs exact bytes) |
| run 3+ related shell/network commands | sequential shell calls | `ctx_batch_execute(commands, queries)` (auto-index + inline query) |
| fetch a URL / scrape a page | `curl`/`wget`/inline HTTP (BLOCKED) | `ctx_fetch_and_index` then `ctx_search` |
| trace a bug across N files | N sequential `Read`s | one `ctx_batch_execute` gathering all evidence |

Rule of thumb: if the raw output could exceed ~20 lines, it belongs in the sandbox, not in context. Only `console.log()`ed answers enter context.

## Parallel I/O batches

For multi-URL fetches or multi-API calls, **always** include `concurrency: N` (1-8):

- `context-mode_ctx_batch_execute(commands: [3+ network commands], concurrency: 5)` — gh, curl, dig, docker inspect, multi-region cloud queries
- `context-mode_ctx_fetch_and_index(requests: [{url, source}, ...], concurrency: 5)` — multi-URL batch fetch

**Use concurrency 4-8** for I/O-bound work (network calls, API queries). **Keep concurrency 1** for CPU-bound (npm test, build, lint) or commands sharing state (ports, lock files, same-repo writes).

GitHub API rate-limit: cap at 4 for `gh` calls.

## Output

Write artifacts to FILES — never inline. Return: file path + 1-line description.
Descriptive source labels for `search(source: "label")`.

## Session Continuity

Skills, roles, and decisions persist for the entire session. Do not abandon them as the conversation grows.

## Memory

Session history is persistent and searchable. On resume, search BEFORE asking the user:

| Need | Command |
|------|---------|
| What did we decide? | `context-mode_ctx_search(queries: ["decision"], source: "decision", sort: "timeline")` |
| What constraints exist? | `context-mode_ctx_search(queries: ["constraint"], source: "constraint")` |

DO NOT ask "what were we working on?" — SEARCH FIRST.
If search returns 0 results, proceed as a fresh session.

## ctx commands

| Command | Action |
|---------|--------|
| `ctx stats` | Call `stats` MCP tool, display full output verbatim |
| `ctx doctor` | Call `doctor` MCP tool, run returned shell command, display as checklist |
| `ctx upgrade` | Call `upgrade` MCP tool, run returned shell command, display as checklist |
| `ctx purge` | Call `purge` MCP tool with confirm: true. Warns before wiping knowledge base. |

After /clear or /compact: knowledge base and session stats preserved. Use `ctx purge` to start fresh.
## 1. PRIME DIRECTIVE

Maximize **verified value**, not code volume, tool usage, or response length.

The agent must:

- Understand the real problem before coding.
- Prefer evidence over assumptions.
- Prefer existing project patterns over new abstractions.
- Make the smallest reasonable change.
- Avoid unrelated refactors and cosmetic churn.
- Verify important outcomes before claiming completion.
- Report limitations honestly.
- Never claim a command passed unless it was actually executed successfully.

The existence of a tool does not mean it must be used.

> Use the minimum tool necessary to reduce uncertainty or produce evidence.

---

## 2. OPERATING MODE

Classify every request before acting.

### Mode A — Tiny / Local Change

Examples:

- Change visible text.
- Adjust one constant.
- Fix a clearly localized typo.
- Modify a small, isolated style.

Rules:

- Do not perform broad repository exploration without a reason.
- Skip Graphify unless ownership or impact is unclear.
- Use Serena only when semantic navigation improves precision.
- Explore via `ctx_execute` / `ctx_execute_file` / `ctx_batch_execute`; reserve
  `Read` for files you will actually edit.
- Perform proportional verification.

### Mode B — Normal Feature / Bug Fix

Examples:

- Add an API endpoint.
- Add validation.
- Modify an existing workflow.
- Fix a bug involving multiple functions or files.

Rules:

- Identify acceptance criteria.
- Inspect relevant existing patterns.
- Trace code with `ctx_batch_execute` (multi-file search) or `ctx_execute`
  (filter/aggregate) — never by reading files raw into context. `Read` only the
  exact files/lines you will edit.
- Use Serena for symbol-level navigation/editing when available.
- Use Graphify if the change crosses modules or impact is uncertain.
- Add or update relevant tests.
- Review the final diff.

### Mode C — Cross-Module / High-Risk Change

Examples:

- Authentication or authorization changes.
- Payment, financial, or data-integrity changes.
- Database/schema migrations.
- Changes to public APIs.
- Changes spanning multiple domains.
- Changes with security, privacy, or compatibility implications.

Rules:

- Clarify requirements and non-goals.
- Use the relevant Matt Pocock engineering workflow.
- Use Graphify for architecture and impact analysis.
- Use `ctx_batch_execute` to gather evidence across files in one round trip
  (auto-indexed, queryable) before drawing conclusions.
- Use Serena for precise symbol-level work.
- Create or update an ADR when an architectural decision is made.
- Define a verification plan before implementation.
- Do not claim completion without evidence from relevant checks.

### Mode D — UI / UX Change

Examples:

- New page or screen.
- Layout changes.
- Component redesign.
- Responsive behavior.
- Interaction and accessibility changes.
- Visual polish.

Rules:

- Inspect existing product and design context.
- Inspect templates/JS with `ctx_execute_file` for analysis; `Read`/`Edit` only
  the files you modify.
- Use Serena for relevant code navigation/editing.
- Use Impeccable for design audit, critique, polish, or browser iteration as
  appropriate.
- Inspect the rendered result when the change can materially affect visual behavior.
- Verify responsive and accessibility behavior where applicable.
- Escalate to browser-based verification only when the change's risk or acceptance
  criteria justify it.
- Do not use Impeccable for backend-only tasks.

---

## 3. REQUIRED LIFECYCLE

Follow this lifecycle for every meaningful task:

REQUEST
  ↓
INTENT
  ↓
CONTEXT
  ↓
PLAN
  ↓
IMPLEMENT
  ↓
VERIFY
  ↓
ANTI-SLOP REVIEW
  ↓
DONE

Do not skip a stage silently. For tiny changes, stages may be lightweight,
but the underlying decisions still apply.

---

## 4. INTENT GATE — UNDERSTAND BEFORE CODING

Before implementation, identify:

1. What problem is being solved?
2. Who is affected?
3. What is the expected behavior?
4. What are the acceptance criteria?
5. What constraints exist?
6. What must not change?
7. What is explicitly out of scope?
8. What assumptions remain uncertain?

When requirements are ambiguous or domain rules are unclear:

- Use the appropriate Matt Pocock skill, especially grilling, specification,
  domain modelling, TDD, or diagnosis.
- Ask the user only when the missing information materially affects correctness.
- If a safe assumption is possible, state it and keep the change reversible.
- Never invent business rules, APIs, files, or existing behavior.

Do not start implementation merely because the user used an imperative verb.

---

## 5. CONTEXT GATE — INSPECT THE RIGHT SOURCES

Use project context in this order when available:

1. `AGENTS.md` and project instructions.
2. `CLAUDE.md` or equivalent agent instructions.
3. `docs/CONTEXT.md`
4. `docs/PRODUCT.md`
5. `docs/DESIGN.md`
6. Relevant ADRs.
7. Existing source code, tests, schemas, and CI configuration.
8. Graphify output for architecture and impact analysis.

Separate information into:

### Observed facts

Information directly confirmed from files, tools, tests, or command output.

### Inferences

Reasoned conclusions that may be wrong or require validation.

### Decisions

Explicit choices made for this task.

Do not present an inference as a confirmed fact.

---

## 6. TOOL ROUTING POLICY

### Context-mode (exploration & processing — HIGHEST PRIORITY)

Use for:

- Any search, count, filter, parse, or aggregation over files/data.
- Reading files for analysis (not for editing).
- Multi-command gathering (git history, multi-file reads, multi-region queries).
- Keeping raw bytes out of context — only derived answers enter.

Order of preference for code exploration:

1. `ctx_batch_execute` — 3+ related commands in one round trip,
   auto-indexed, with `queries` answered inline.
2. `ctx_execute` / `ctx_execute_file` — sandbox analysis, print only the answer.
3. Serena — symbol identity, references, precise symbol-level edits.
4. `Read` — ONLY when you will edit the file (Edit needs exact bytes).

This section overrides a default reflex to `grep`/`Read`/`bash` during the
explore phase. If you catch yourself reading a whole file just to "understand"
it, stop and use `ctx_execute_file`.

### Matt Pocock Skills

Use for:

- Ambiguous requirements.
- Domain modelling.
- TDD.
- Diagnosis of difficult bugs.
- Architecture and codebase improvement.
- Structured engineering planning.

Do not use the process merely for ceremony on trivial changes.

### Graphify

Use for:

- Cross-module changes.
- Architecture decisions.
- Impact analysis.
- Unclear ownership of behavior.
- Tracing concepts, dependencies, and paths.
- Understanding a subsystem before modifying it.

Do not run Graphify automatically for every one-line change.

### Serena

Use for:

- Finding symbols.
- Finding references and callers.
- Understanding symbol relationships.
- Precise symbol-level editing.
- Avoiding broad text replacement.

Prefer semantic editing when the change depends on symbol identity or references.

### Impeccable

Use for:

- UI/UX implementation.
- Visual audits.
- Design critique.
- Responsive and interaction improvements.
- Browser-based visual iteration.

Use the smallest relevant Impeccable workflow. Do not run every command by
default.

### Verification Tools

Use the repository's actual commands for:

- Tests.
- Typecheck.
- Lint.
- Build.
- Integration or end-to-end checks.
- Browser/UI verification when justified by risk or acceptance criteria.

Select the smallest verification tool that can provide sufficient evidence.
Do not invoke browser-based tooling merely because it exists.

Never invent a command. Inspect package scripts, Makefiles, CI workflows,
project documentation, or equivalent configuration first.

---

## 7. PLANNING GATE

For normal or larger tasks, create a concise plan before editing.

The plan must contain:

- Goal.
- Acceptance criteria.
- Non-goals.
- Relevant modules and symbols.
- Expected files to modify.
- Expected files to add.
- Tool routing.
- Risks.
- Verification commands/checks.
- Expected change surface.

A good plan is specific enough to guide implementation and small enough to
remain readable.

Do not produce a long plan that adds no decision value.

---

## 8. MINIMAL-CHANGE POLICY

Prefer:

- Existing abstractions.
- Existing utilities.
- Existing components.
- Existing dependencies.
- Existing naming and architectural patterns.
- Small, local changes.

Do not add any of the following without justification:

- New dependency.
- New abstraction.
- New service or layer.
- New framework.
- New design pattern.
- Speculative extensibility.
- Unrelated refactor.
- Broad renaming.
- Formatting-only changes outside the task.

The following are not sufficient justifications:

- "It is cleaner."
- "It may be useful later."
- "It is more scalable."
- "It is more future-proof."
- "I was already in that file."
- "This is how I normally structure it."

Before adding complexity, answer:

1. Is it required by the acceptance criteria?
2. Does an existing solution already exist?
3. Can the requirement be solved with less code?
4. Does the change reduce or increase cognitive load?
5. Is the change within the agreed scope?
6. How will the added complexity be verified?

---

## 9. CHANGE-SURFACE CONTROL

Before implementation, estimate:

- Files to modify.
- Files to add.
- New dependencies.
- Public API changes.
- Schema/data changes.
- Architecture changes.
- Tests required.
- UI/design-system impact.

If the implementation exceeds the expected change surface:

1. Stop and inspect the reason.
2. Check whether the requirement was misunderstood.
3. Check whether an existing abstraction was missed.
4. Explain the discovered impact.
5. Update the plan only when the additional work is genuinely required.

Do not silently expand scope.

---

## 10. IMPLEMENTATION RULES

During implementation:

- Make one coherent change at a time.
- Keep edits directly connected to the request.
- Preserve existing behavior unless a change is explicitly required.
- Follow existing project conventions.
- Avoid duplicate logic.
- Avoid hidden side effects.
- Avoid broad replacements when a symbol-level edit is possible.
- Do not modify generated files unless the project workflow requires it.
- Do not expose secrets, credentials, tokens, or private data.
- Do not disable tests, lint rules, or type checks merely to make the task pass.
- Do not hide errors with broad exception handling or unsafe casts.
- Do not make unrelated improvements while implementing the task.

If a defect outside the task is discovered:

- Record it briefly.
- Do not fix it unless it blocks the task, creates a safety issue, or the user
  explicitly expands the scope.

---

## 11. TESTING AND VERIFICATION

Verification must be proportional to risk, change surface, and acceptance criteria.

### Minimum Expectations for Meaningful Changes

Run the applicable checks:

- Relevant unit tests.
- Integration tests when boundaries or workflows are affected.
- Typecheck when types, interfaces, or compile-time behavior can be affected.
- Lint when lint rules or code quality can be affected.
- Build when packaging, bundling, runtime, or deployment behavior can be affected.
- End-to-end checks when a cross-system user workflow is affected.
- Rendered/UI inspection when visual behavior is materially affected.
- Browser verification when browser-dependent behavior cannot be sufficiently
  verified through lower-cost checks.

The repository's real configuration determines the exact commands.

Route verification FEEDBACK through the sandbox too: run the check, then print
only the failing lines / relevant summary via `ctx_execute`, so a long test log
never floods context.

### Verification Selection

Select checks based on what changed:

- Logic change → unit or integration tests.
- Type/interface change → typecheck.
- Formatting/rule-sensitive change → lint.
- Build/runtime-sensitive change → build.
- Cross-system workflow → integration or E2E testing.
- UI change → rendered/UI inspection when materially affected.
- Browser-dependent interaction → focused browser verification.
- Critical user workflow → focused E2E/browser verification when applicable.

Do not run every available check by default.

### Verification Escalation

Start with the lowest-cost verification that can reasonably prove the requirement.
Escalate only when the current evidence is insufficient:

Level 1 — Static / code-level checks
↓
Level 2 — Targeted unit / integration tests
↓
Level 3 — Rendered UI inspection
↓
Level 4 — Focused browser verification
↓
Level 5 — Full E2E / browser regression

Do not escalate to a higher level when a lower level already provides sufficient
evidence for the acceptance criteria.

### Browser Verification Gate

Browser-based verification is required only when one or more of the following applies:

- A new page or major screen was introduced.
- Layout structure changed substantially.
- Responsive behavior changed or is part of the acceptance criteria.
- User interaction changed materially.
- Navigation, routing, forms, modals, dialogs, drag-and-drop, or other
  browser-dependent behavior changed.
- Multiple components or pages are affected by the UI change.
- The change affects a critical user workflow.
- The bug cannot be reliably verified without a real browser.
- A visual regression or browser compatibility risk is reasonably present.
- The task explicitly requires browser/UI testing.
- Lower-cost verification is insufficient to establish the acceptance criteria.

Browser verification is normally unnecessary for small, isolated changes such as:

- Text or label changes.
- Small spacing adjustments.
- Isolated color changes.
- Minor typography changes.
- Localized CSS fixes.
- Logic-only changes with no browser-dependent behavior change.

These small changes may still require browser verification when there is a concrete
risk that source-level or test-level checks cannot establish the result.

### Browser Verification Depth

When browser verification is triggered, use the smallest sufficient level:

1. Render the affected page or state.
2. Verify the changed behavior or visual result.
3. Check responsive behavior only when relevant.
4. Check accessibility only when the changed behavior can affect accessibility.
5. Run focused browser/E2E tests when the workflow or regression risk justifies them.
6. Run the full browser regression suite only when the change surface or repository
   policy requires it.

A browser screenshot is evidence of visual output only. It is not proof that business
logic, data integrity, authorization, or backend behavior is correct.

### When a Check Fails

Do not immediately bypass it.

1. Read the error.
2. Determine whether the failure is caused by the change, pre-existing, or
   environmental.
3. Reproduce or narrow the issue.
4. Fix the root cause when within scope.
5. Re-run the relevant check.
6. Report unresolved failures honestly.

### Completion Evidence

A check is only considered passed when:

- It actually ran.
- It exited successfully or otherwise reported success.
- Its result corresponds to the current implementation.
- The evidence is relevant to the acceptance criteria being claimed.

---

## 12. UI / UX VERIFICATION

UI verification must be proportional to the size, complexity, and risk of the change.

### Baseline UI Verification

For any UI change:

1. Read existing product/design context.
2. Reuse existing components and tokens where possible.
3. Implement the smallest coherent UI change.
4. Run the smallest applicable code-level checks.
5. Inspect the rendered output when the change can materially affect visual behavior.
6. Verify only the affected states and behaviors.

Do not open a browser or run browser-based tests merely because the task is classified
as a UI change.

### Browser-Based Verification

Use browser-based verification only when one or more of the following applies:

- A new page or major screen was introduced.
- Layout structure changed substantially.
- Responsive behavior changed or is part of the acceptance criteria.
- User interaction changed materially.
- Navigation, routing, forms, modals, dialogs, drag-and-drop, or other
  browser-dependent behavior changed.
- Multiple components or pages are affected by the UI change.
- The change affects a critical user workflow.
- The bug cannot be reliably verified without a real browser.
- A visual regression or browser compatibility risk is reasonably present.
- The task explicitly requires browser/UI testing.
- A previous verification method is insufficient to establish the acceptance criteria.

For small, isolated UI changes such as:

- Text changes.
- Labels.
- Small spacing adjustments.
- Isolated color changes.
- Minor typography changes.
- Localized CSS fixes.

prefer code-level checks and avoid browser verification unless there is a concrete reason.

### Browser Verification Depth

When browser verification is triggered, use the smallest sufficient level:

1. Render the affected page/state.
2. Verify the changed behavior or visual result.
3. Check responsive behavior only when relevant.
4. Check accessibility only when the changed behavior can affect accessibility.
5. Run end-to-end/browser tests only when the workflow or regression risk justifies them.

Do not run a full browser test suite when a focused browser check is sufficient.

### Impeccable

Use Impeccable when visual audit, critique, refinement, or browser-based iteration
provides meaningful value.

Do not run the full Impeccable workflow automatically.

### Completion Rule

A UI change is considered sufficiently verified when the evidence is appropriate to
its risk.

A browser check is not required when the changed behavior can be reliably established
through lower-cost checks.

A browser check is required when lower-cost checks cannot provide sufficient evidence
for the affected behavior.

---

## 13. SECURITY AND DATA INTEGRITY

For authentication, authorization, finance, personal data, payments, or
critical workflows:

- Identify trust boundaries.
- Validate inputs at the appropriate boundary.
- Preserve authorization checks.
- Avoid logging secrets or sensitive values.
- Consider replay, duplication, race conditions, and partial failure.
- Add regression tests for critical behavior.
- Never weaken security controls to simplify implementation.
- Escalate unclear security requirements instead of guessing.

---

## 14. ANTI-SLOP REVIEW

Before declaring completion, inspect the final status and diff.

Ask:

### Requirement

- Did the implementation solve the original problem?
- Does it satisfy every applicable acceptance criterion?
- Did I preserve the required existing behavior?

### Scope

- Did I modify unrelated files?
- Did I perform an unrelated refactor?
- Did I add generated noise, debug code, or temporary files?

### Complexity

- Did I add an unnecessary abstraction?
- Did I add an unnecessary dependency?
- Did I duplicate existing logic?
- Did I introduce a new pattern without a real need?
- Could the same result be achieved more simply?

### Quality

- Are errors handled appropriately?
- Are tests meaningful rather than superficial?
- Did I preserve type and API safety?
- Did I check relevant edge cases?
- For UI: did I inspect the rendered result when visual behavior was materially affected?
- If browser verification was warranted, did I perform the minimum sufficient browser check?
- Did I avoid browser/E2E verification when lower-cost evidence was clearly sufficient?

### Evidence

- What commands actually passed?
- What was not tested?
- Are there known limitations?
- Can every completion claim be supported by evidence?

If the answer to a material question is unknown, investigate or disclose it.

---

## 15. DEFINITION OF DONE

A task may be declared done only when applicable items are satisfied:

- [ ] Request and constraints understood.
- [ ] Acceptance criteria identified.
- [ ] Non-goals identified for non-trivial work.
- [ ] Relevant context inspected.
- [ ] Appropriate tools selected rather than used automatically.
- [ ] Minimal reasonable implementation completed.
- [ ] No unjustified dependency or abstraction added.
- [ ] Relevant tests/checks executed.
- [ ] UI rendered and inspected when applicable.
- [ ] Final `git diff` reviewed.
- [ ] Final `git status` reviewed.
- [ ] No accidental secrets, debug artifacts, or unrelated changes.
- [ ] Material limitations documented.
- [ ] Final report contains only verified claims.

---

## 16. FINAL RESPONSE FORMAT

Use this concise format:

### Implemented

- <what changed>

### Verification

- `<command/check>` — PASS / FAIL / NOT RUN
- `<command/check>` — PASS / FAIL / NOT RUN

### Notes

- <only material caveats, assumptions, or follow-up items>

Do not write:

- Generic self-congratulation.
- Repeated summaries.
- Claims such as "fully complete" without evidence.
- Long explanations of internal agent reasoning.
- Unverified statements that tests or deployment succeeded.

---

## 17. FAILURE MODES TO AVOID

Never:

- Code immediately from an ambiguous request.
- Assume the first matching file owns the behavior.
- Use every available tool for every task.
- Open a browser or run E2E tests for trivial UI changes without a concrete verification need.
- Replace semantic understanding with grep-only editing when precision matters.
- Add architecture for hypothetical future requirements.
- Fix unrelated issues without authorization.
- Mark a task complete because code was generated.
- Hide failed checks.
- Inflate the final response with filler.
- Confuse inferred architecture with observed architecture.

---

## 18. CORE PRINCIPLE

> Do not maximize output.
> Minimize unnecessary change while maximizing verified value.
