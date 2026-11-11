# Stack — Go

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk go vet ./...` | built in | `rtk go test ./...` | `rtk go build ./...` |

A missing tool is a gap, not a pass: record `N/A <check>: <reason>`.

## Anti-slop

- Return errors; never panic on request-path input.
- Validate at the boundary. No secrets in logs.
- Match the existing package layout and error-wrapping style.
- No new dependency for a small utility; write the few lines.
