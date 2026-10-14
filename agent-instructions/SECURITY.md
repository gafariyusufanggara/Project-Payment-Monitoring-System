# Security & Data Integrity Policy

Apply to authentication, authorization, finance, payments, personal data, schema migrations,
public APIs, and other high-risk workflows.

## Consider
- trust boundaries
- authorization checks
- input validation
- secrets/tokens/credentials
- sensitive logging
- idempotency and duplicate requests
- race conditions
- replay and partial failure
- regression tests for critical behavior
- API/type safety

## Never
- weaken security controls for convenience
- expose secrets/private data
- bypass authorization
- disable security checks to pass tests
- guess material security requirements

When a critical security requirement is unclear, escalate the uncertainty rather than
silently inventing a rule.
