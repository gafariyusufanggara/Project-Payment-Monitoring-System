# Agent Workflow

## REQUEST
Translate the user's request into the actual task. Do not enlarge it.

## INTENT
Establish problem, affected user/system, expected behavior, acceptance criteria,
constraints, non-goals, and uncertain assumptions.

Use Matt Pocock skills when ambiguity materially affects correctness. Never invent
business rules or missing project decisions.

## CONTEXT
Inspect the smallest relevant evidence set. Prefer project instructions,
product/PRD docs, architecture/design/IA/ADR docs, implementation, tests, and CI.
Use Graphify when structural impact is uncertain.

Classify findings:
- FACT — directly observed
- INFERENCE — reasoned but unconfirmed
- DECISION — explicitly chosen

## PLAN
For normal or larger work, make a concise plan containing goal, acceptance criteria,
non-goals, affected modules/symbols, expected change surface, tools, risks, and verification.

Do not create planning ceremony that adds no decision value.

## IMPLEMENT
Make the smallest coherent change. Preserve existing behavior unless the requirement changes it.
Prefer semantic edits and established project patterns.

## VERIFY
Run the smallest verification set that can reasonably establish the acceptance criteria.
Escalate only when evidence is insufficient.

## ANTI-SLOP REVIEW
Inspect the final diff/status for unrelated changes, unnecessary abstractions/dependencies,
duplicate logic, debug artifacts, and unverified claims.

## DONE
Declare completion only when the evidence supports the claims being made.
