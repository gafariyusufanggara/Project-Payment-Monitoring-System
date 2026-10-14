# Tool Routing Policy

> Use the minimum tool necessary to reduce uncertainty or produce evidence.

## Matt Pocock Skills
Use for ambiguous requirements, grilling/specification, domain modelling, TDD,
difficult bug diagnosis, and structured engineering reasoning.

## Graphify
Use for cross-module work, architecture/impact analysis, dependency tracing,
unclear ownership, unfamiliar subsystems, or non-local consequences.

## Serena
Use for symbol discovery, references/callers, semantic navigation, and precise
symbol-level editing. Prefer semantic edits when symbol identity matters.

## Impeccable
Use for UI/UX implementation, visual audit/critique, responsive behavior,
interaction states, and browser-based visual iteration. Use only the relevant workflow.

## Context Mode
Use for large-scale search/exploration, file analysis, aggregation/filtering/parsing,
multi-command gathering, and web/data processing. See `CONTEXT-MODE.md`.

## Verification
Use repository-native tests, typecheck, lint, build, integration/E2E, and focused
browser/UI checks when justified.

### Typical Routing
Tiny/local → inspect → edit → proportional verification.

Normal feature/bug → intent → relevant context → semantic edit → targeted verification.

Cross-module/high-risk → Matt when needed → Graphify → plan → Serena → stronger verification.

UI → relevant context → Serena → Impeccable/browser when justified → verification.
