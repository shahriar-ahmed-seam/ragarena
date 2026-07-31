# On-Call and Incident Response Runbook

Owner: Platform Reliability. Applies to every service in the Meridian Freight
Systems production estate.

## Rotation

The on-call rotation is one week long and hands over every Monday at 10:00 UTC.
Each rotation has a primary and a secondary responder. Handover requires a
written summary of open incidents posted in `#platform-oncall`.

Paging runs through PagerDuty. Every alert rule must link to a runbook section;
an alert without a runbook link fails review and is disabled at the next
observability audit.

If the primary responder does not acknowledge a page within 10 minutes, the
secondary responder is paged automatically. If neither acknowledges within a
further 10 minutes, the entire Platform Reliability group is paged.

## Severity levels

SEV1 is a customer-wide outage or confirmed data loss. Acknowledge within 5
minutes.

SEV2 is significant degradation affecting a subset of workspaces, or any
delivery delay longer than 30 minutes. Acknowledge within 15 minutes.

SEV3 is a minor defect with a viable workaround. It is picked up on the next
business day and does not page.

## SEV1 protocol

1. Open a dedicated incident channel named `#inc-<incident-id>`.
2. Name an incident commander and a separate communications lead. One person
   must not hold both roles.
3. Publish an initial status page entry within 20 minutes of declaration, then
   update it at least every 30 minutes until resolution.
4. If a SEV1 is still unresolved after 45 minutes, escalate to the Director of
   Engineering. Escalation is mandatory and is not a judgement call.
5. Mitigate first, diagnose second. Rolling back a release is always an
   acceptable first action and never requires approval.

## Postmortems

Every SEV1 and SEV2 requires a written postmortem published within 5 business
days of resolution. SEV3 incidents do not require one.

Postmortems are blameless and must contain: a timeline in UTC, the customer
impact expressed in affected workspaces, the root cause, the contributing
factors, and action items with named owners and due dates.

Action items from a SEV1 postmortem are tracked as blocking work in the next
sprint. Unclosed action items are reviewed in the monthly reliability review.

## Communication rules

Customer-facing language is written by the communications lead, never by the
responder holding the pager. Internal speculation stays in the incident
channel. Status page entries state impact and mitigation only, never root cause
before the postmortem is published.
