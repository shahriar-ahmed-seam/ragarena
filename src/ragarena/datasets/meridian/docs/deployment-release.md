# Deployment and Release Process

## Environments

Three environments are maintained: `dev`, `staging` and `prod`. Staging runs the
same infrastructure topology as production at one quarter of the capacity and is
seeded nightly from anonymised production shapes, never from raw production data.

## Branching

Development is trunk-based. Feature branches are short lived and merged within
two working days. Incomplete work ships behind a LaunchDarkly feature flag rather
than living on a long-running branch.

Every flag has an owner and a removal date. Flags older than 90 days are
reported to the owning team weekly until they are removed.

## Continuous integration gates

A pull request cannot merge until all of these pass: lint, unit tests,
integration tests, and the container image vulnerability scan. A failing scan
blocks the merge when it reports a critical or high finding.

## Production deploys

Deploys to production are fully automated and permitted between 09:00 and 16:00
UTC, Monday to Thursday. Deploying outside that window requires an approved
exception from the Director of Engineering.

Change freezes apply on Fridays and during the last 3 business days of every
quarter. Only incident mitigations ship during a freeze.

## Canary and rollback

Every production deploy first routes 5% of traffic to the new revision for 20
minutes. Automated rollback triggers if, during the canary window, the error rate
exceeds 2% or p95 latency exceeds 800 ms. Rollback is automatic and does not wait
for human confirmation.

A rolled-back release must have a written cause noted on the pull request before
it is redeployed.

## Database migrations

Migrations follow expand-contract. A release may add a column, backfill it, and
start writing to it; the destructive step that removes the old column ships in a
later release. A single release must never contain both the expand and the
contract phase.

Migrations that touch more than 10 million rows run as a background job with a
documented kill switch, never inline in the deploy.

## Mobile

The mobile driver application ships on a weekly release train that cuts every
Wednesday. Hotfixes outside the train require sign-off from the mobile lead and
the Director of Engineering.
