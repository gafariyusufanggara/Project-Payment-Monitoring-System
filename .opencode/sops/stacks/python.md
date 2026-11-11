# Stack — Python (FastAPI / Django / Flask)

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk ruff check` | `rtk mypy .` | `rtk pytest` | `rtk python -m build` |

A missing tool is a gap, not a pass: record `N/A <check>: <reason>`. Do not add
a framework silently.

## Anti-slop

- Validate at the boundary; never trust request input.
- No secrets in code, logs, or responses. Use the project's settings layer.
- Match the existing project layout, import style, and error-handling pattern.
- No new dependency for a small utility; write the few lines.
