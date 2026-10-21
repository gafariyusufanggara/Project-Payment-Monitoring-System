# Security & Data Integrity

Apply to: authentication, authorization, finance/payments, personal data, schema migrations,
public APIs, and other high-risk workflows.

## Checklist (answer only the relevant items)
- Trust boundaries and where input enters
- Authorization on every access path
- Input validation/sanitization at the boundary
- Secrets/tokens/credentials: never hardcoded, never logged
- Sensitive data in logs/errors
- Idempotency and duplicate requests
- Race conditions, replay, partial failure
- Regression tests for the critical behavior
- API/type safety

## Never
- Weaken or bypass security controls for convenience or to pass tests
- Expose secrets/private data
- Guess a material security requirement → escalate the uncertainty to the user instead
