---
description: "Detect the project stack, write .opencode/STACK.md, and report which MCP servers and skills apply. Use at the start of a session, when the stack is unclear, or after switching projects."
agent: web-dev
subtask: false
---

Read `.opencode/sops/STACKS.md` and execute phase 0b only (stack detection).

## Procedure

1. Detect with one batch call, not ten reads. Commands run from the session
   cwd — if the session cwd is not the project root, use absolute paths or
   `cd <project-root>` first:

```js
ctx_batch_execute(commands: [
  {label:"manifest-js",  command:"rtk json package.json"},
  {label:"manifest-py",  command:"rtk find . -maxdepth 2 -name pyproject.toml"},
  {label:"manifest-go",  command:"rtk find . -maxdepth 2 -name go.mod"},
  {label:"manifest-rs",  command:"rtk find . -maxdepth 2 -name Cargo.toml"},
  {label:"configs",      command:"rtk find . -maxdepth 2 -name *.config.*"},
  {label:"locks",        command:"rtk find . -maxdepth 1 -name *lock*"}
], queries: ["framework","package manager","styling","test runner","component library"])
```

A failing label is information, not an error: `rtk json package.json` fails when
the file is absent, and `rtk find` prints `0 for <pattern>` when nothing
matches. Never re-run a failing label with different flags to "fix" it.

2. Fill the `.opencode/STACK.md` template from `.opencode/sops/STACKS.md`. Create the
   folder if needed. Overwrite an existing file only when the user asks for a
   re-detect.

3. Report:

```
Stack: <framework> / <language> / <package manager>
Styling: <...>   Components: <...>   Dark mode: <...>
Test: <...>   Lint: <...>   Typecheck: <...>
Build: <command>   Dev: <command> on :<port>

MCP for this stack: <list>
Skills for this stack: <list>
Commands to verify: build / typecheck / lint / test
```

## If nothing is detected

Stop and say exactly:

> No `package.json`, `pyproject.toml`, `go.mod`, or `Cargo.toml` in `<path>`.
> Nothing to detect. Point me at the project root, or tell me the stack and I
> will scaffold it.

Do not guess. Do not scaffold uninvited.

## If detection is partial

Say what is missing rather than filling it with a default. Example:

> Framework detected (Vue 3 + Vite). No test runner and no lint config found.
> Verification will be build + `vue-tsc` only unless you want one added.
