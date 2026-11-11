# Stack — Rust

## Verify (phase 5)

| Lint | Typecheck | Test | Build |
|---|---|---|---|
| `rtk cargo clippy` | built in | `rtk cargo test` | `rtk cargo build` |

A missing tool is a gap, not a pass: record `N/A <check>: <reason>`.

## Anti-slop

- No `unwrap()` / `expect()` on request-path input; propagate errors.
- Validate at the boundary. No secrets in logs.
- Match the existing module layout and error type.
- No new crate for a small utility; write the few lines.
