# Postmortem: Total API Outage from Expired Intermediate Certificate, 2 May 2026

Severity: SEV1. Duration: 41 minutes (06:14 - 06:55 UTC).
Incident commander: A. Bergström. Communications lead: R. Okafor.
Status: resolved, all action items closed.

## Customer impact

100% of API traffic failed TLS negotiation for 41 minutes. Every customer
integration was affected. No data was lost or corrupted; requests failed before
reaching application code. 1,180 workspaces attempted at least one request during
the window.

Because the outage was total, service credits were issued proactively rather than
on claim.

## Timeline (UTC)

- 06:14 The intermediate certificate in the edge chain expired. All TLS
  handshakes began failing.
- 06:15 Synthetic external probes failed. The page routed to a Slack channel that
  had been archived in March.
- 06:22 An on-call engineer noticed the synthetic dashboard while working an
  unrelated ticket.
- 06:24 Incident declared SEV1.
- 06:31 Root cause identified from the edge terminator logs.
- 06:44 Replacement chain deployed to the first edge region.
- 06:55 All regions serving, incident resolved.

## Root cause

The certificate renewal automation had been failing silently for 9 days. A
credential it used to talk to the certificate authority had been rotated as part
of an unrelated quarterly access review, and the job treated the resulting
authentication failure as a soft error: it logged at `warn` level and exited
zero, so nothing alerted and the scheduler recorded nine consecutive successes.

## Contributing factors

The 14 day certificate expiry warning did fire, on schedule, nine days before the
outage. It was routed to `#alerts-platform-legacy`, which had been archived during
a channel cleanup in March. Archiving a channel silently discards messages
delivered to it.

Certificate expiry was monitored only for leaf certificates. The intermediate in
the chain was not covered by any check.

## Action items

1. Alert on any scheduled job exiting zero with warnings, and fail the renewal
   job loudly instead. Owner: Platform Reliability. Shipped 4 May 2026.
2. Monitor expiry for every certificate in the chain, not just leaves. Owner:
   Platform Reliability. Shipped 6 May 2026.
3. Validate every alert destination weekly and fail the observability audit on an
   archived or unreachable channel. Owner: Observability. Shipped 11 May 2026.
4. Add an external, third-party-hosted TLS probe independent of our own
   monitoring stack. Owner: Observability. Shipped 19 May 2026.

## Lesson

Two independent controls existed and both were defeated by the same class of
failure: a signal that was generated correctly and then delivered nowhere. An
alert nobody receives is indistinguishable from an alert that never fired.
