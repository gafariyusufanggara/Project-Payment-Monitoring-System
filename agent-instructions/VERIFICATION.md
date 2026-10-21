# Verification & Definition of Done

Verification is proportional to risk, change surface, and acceptance criteria.

## Discover Once
Inspect real config (package.json scripts, Makefile, CI, pyproject, etc.) once per session.
Index the discovered commands (`ctx_index`) and reuse them. Don't run every check by default.

## Escalation (stop at the lowest sufficient level)
1. static/code checks → 2. targeted unit/integration tests → 3. rendered UI →
4. focused browser check → 5. broad E2E/regression

## Browser Gate
Justified for: new/major screens, substantial layout or responsive changes, material
interaction/form/navigation/modal changes, critical workflows, browser-only bugs,
explicit browser-testing requirements, or no cheaper evidence available.
Normally unnecessary for: text/label, small spacing/color, localized CSS, logic-only changes.
A screenshot proves visuals, not backend correctness, authorization, or data integrity.

## Failures
Never bypass a failing check. Classify: caused by change / pre-existing / environmental.
Fix in-scope root causes, rerun, report unresolved failures honestly.
PASS = it ran, succeeded, applies to the current code, and is relevant to the claim.

## Definition of Done
- [ ] Requirement, acceptance criteria, constraints understood
- [ ] Relevant context inspected (no more than needed)
- [ ] Existing patterns reused; no unjustified dependency/abstraction; no unrelated refactor
- [ ] Applicable checks run; results classified PASS / FAIL / NOT RUN
- [ ] UI inspected only if materially affected
- [ ] `graphify update .` run after final code changes (or NOT RUN with reason)
- [ ] Final diff and git status reviewed; no debug artifacts or secrets
- [ ] Limitations and NOT RUN checks disclosed; claims are evidence-based
