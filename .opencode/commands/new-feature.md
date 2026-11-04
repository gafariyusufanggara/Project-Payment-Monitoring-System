---
description: "Start a non-trivial feature with the structured feature-dev workflow: explore the codebase, clarify, design, implement, review. Use instead of diving straight into code when the feature touches multiple files."
agent: web-dev
subtask: false
---

Use the `feature-dev` skill (power-pack) as the workflow spine. Do not duplicate
its phases here; this command only pins the project-specific gates.

## Sequence

1. Read `AGENTS.md`, `.opencode/sops/WEB_DEV.md`.
2. Read the project documents (`.opencode/sops/WEB_DEV.md` Phase 0a): list `docs/`, read
   what maps to this feature, quote the requirement.
3. `.opencode/STACK.md` — create if missing (`.opencode/sops/STACKS.md` phase 0b).
4. Exploration phase: `graphify query "<feature area>"` first, then read the
   nearest siblings and tests. Invoke the `code-explorer` subagent for depth.
5. Clarify: one numbered list of at most 5 questions with defaults.
6. Architecture phase: invoke `code-architect` when the change adds a module or
   a non-obvious data flow.
7. Implementation: phases 4-6 of `.opencode/sops/WEB_DEV.md`.
8. Review: `reviewer` agent, then `code-review` (global skill).

## Project gates that always apply

- UI work: `.opencode/skills/hallmark` or `.opencode/skills/refactoring-ui`, plus sloplint and
  screenshots. No exceptions.
- `.opencode/sops/QUALITY_GATE.md` is the definition of done.
- No comments in code unless asked. No commit unless asked.

## Output

A short status per phase, then the standard handoff block:

```
Works: ...
See it: ...
Not done: ...
Risks: ...
Next: ...
```
