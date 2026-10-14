# Verification Policy

Verification is proportional to risk, change surface, and acceptance criteria.

## Code Checks
Inspect the repository's real configuration first. Run applicable unit/integration tests,
typecheck, lint, build, or E2E. Do not run every available check by default.

## Escalation
Use the lowest-cost evidence that can reasonably prove the requirement:

1. static/code checks
2. targeted unit/integration tests
3. rendered UI inspection
4. focused browser verification
5. broader E2E/browser regression

Escalate only when lower-level evidence is insufficient.

## Browser Gate
Browser verification is justified for major/new screens, substantial layout changes,
responsive behavior, material interaction/navigation/form/modal changes, multiple affected
UI areas, critical workflows, browser-only bugs, compatibility/visual-regression risk,
explicit browser-testing requirements, or insufficient lower-cost evidence.

It is normally unnecessary for isolated text, label, small spacing/color/typography,
localized CSS, or logic-only changes with no browser-dependent behavior.

## UI Verification
When triggered:
1. render the affected page/state
2. verify changed visual/behavioral result
3. check responsive behavior only when relevant
4. check accessibility only when relevant
5. use Impeccable when visual critique/refinement adds value
6. use focused browser/E2E checks when workflow/regression risk justifies them

A screenshot proves visual output, not backend correctness, authorization, or data integrity.

## Failures
Never bypass a failing check just to get green output. Determine whether it is caused
by the change, pre-existing, or environmental; fix in-scope root causes; rerun; report
unresolved failures honestly.

A check is PASS only if it actually ran, succeeded, applies to the current implementation,
and is relevant to the claim.
