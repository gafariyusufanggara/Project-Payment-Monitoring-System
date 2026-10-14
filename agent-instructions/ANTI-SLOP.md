# Anti-Slop Policy

## Objective
Prevent unnecessary verbosity, speculative architecture, unrelated refactoring,
duplicate abstractions, dependency inflation, cosmetic churn, debug residue,
and unverified claims.

## Rules
1. Solve the requested problem, not a larger hypothetical one.
2. Search existing patterns before inventing alternatives.
3. Prefer the smallest correct change.
4. Do not add complexity merely because it is cleaner, more scalable, future-proof,
   or might be useful later.
5. Record unrelated issues rather than silently fixing them.
6. Review the actual final diff; intent is not evidence.

## Complexity Test
Before adding a dependency, abstraction, layer, pattern, or service:
- Is it required by acceptance criteria?
- Does an existing solution already exist?
- Can the requirement be solved more simply?
- Is the added complexity justified now?
- Is it in scope?
- How will it be verified?

## Never
- disable tests/lint/type checks to make work appear successful
- use broad replacements when semantic editing is safer
- add speculative extensibility
- introduce formatting churn unrelated to the task
- hide failures or uncertainty

Before DONE, verify requirement, scope, changed files, complexity, evidence, and limitations.
