# Engineering Onboarding

Welcome to Meridian Freight Systems. This page covers your first ninety days.

## Day one

You receive a laptop with the posture agent pre-installed, an SSO account, and
Vault access scoped to the `dev` environment. Production access is not granted on
day one and is never granted by default; see the security and access control
policy for how just-in-time elevation works.

Every new engineer is assigned an onboarding buddy from a different team. The
buddy is your default question channel for the first month and is explicitly not
your reviewer, so asking a naive question carries no cost.

## Local development

Run `make bootstrap`. It installs toolchain dependencies, starts the Docker
Compose stack (Postgres, Redis, RabbitMQ, the API and the dispatcher), applies
migrations and seeds the database with 500 synthetic shipments spread across
three fictional workspaces.

If `make bootstrap` fails, that is a bug in the bootstrap script rather than a
problem with your machine. File it; do not work around it silently.

## Expectations

You are expected to open your first pull request within week one. It can be a
documentation fix, and most people's first PR is. You should have code running in
production by the end of week two.

The 30/60/90 plan is written jointly by you and your manager in week one: at 30
days you can ship a small change unaided, at 60 days you can take a rotation
shadow shift, at 90 days you join the on-call rotation as secondary.

## Required reading

Read these in your first week: this onboarding page, the on-call and incident
response runbook, the observability standards, and the deployment and release
process.

## Meetings

The engineering all-hands runs every Thursday at 14:00 UTC and is recorded.
Standups are asynchronous and written. There is no daily synchronous status
meeting anywhere in the engineering organisation.

## Culture notes

Written proposals beat meetings. Any change affecting more than one team starts as
a short design document circulated for comment, not as a calendar invite.

Blameless postmortems are taken literally. Naming a person as a root cause is
treated as a defect in the postmortem itself.
