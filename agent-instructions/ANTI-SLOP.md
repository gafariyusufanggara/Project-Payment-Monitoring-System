# Anti-Slop

Prevent: verbosity, speculative architecture, unrelated refactors, duplicate abstractions,
dependency inflation, cosmetic churn, debug residue, unverified claims.

## Rules
1. Solve the requested problem, not a larger hypothetical one.
2. Search for existing patterns/utilities before writing new ones.
3. Smallest correct change.
4. No complexity "because it is cleaner / scalable / future-proof".
5. Record unrelated issues; don't silently fix them.
6. Review the actual diff; intent is not evidence.

## Complexity Gate (before adding a dependency, abstraction, layer, service)
Required by acceptance criteria? Existing solution? Simpler way? Justified now? In scope?
How will it be verified? Any "no" → don't add it.

## Final Diff Review (cheap)
1. `git status -s` and `git diff --stat` in the sandbox.
2. Every changed file must map to the requirement.
3. Scan diff (in sandbox) for debug prints, TODOs, commented code, secrets, formatting-only hunks.
4. Remove anything unrelated.

## Never
- Disable tests/lint/type checks to look green.
- Broad replacements when targeted edits are safer.
- Hide failures or uncertainty.
