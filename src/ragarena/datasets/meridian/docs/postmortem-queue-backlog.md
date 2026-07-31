# Postmortem: Webhook Delivery Backlog, 14 March 2026

Severity: SEV2. Duration: 3 hours 42 minutes (11:18 - 15:00 UTC).
Incident commander: R. Okafor. Communications lead: J. Lindqvist.
Status: resolved, action items open.

## Customer impact

214 workspaces experienced delayed webhook deliveries. The worst observed delay
was 96 minutes between the state change and the delivery attempt. No events were
lost and no shipment data was corrupted. The Shipments API itself stayed within
its latency objective throughout.

## Timeline (UTC)

- 11:18 A customer began a bulk import of 1,204,000 shipments through the batch
  endpoint.
- 11:26 Queue depth on `webhook-dispatch` crossed 800,000 messages. No alert
  fired.
- 12:05 First customer ticket reported missing status callbacks.
- 12:31 Incident declared SEV2 after a second and third report arrived.
- 12:48 Queue depth peaked at 4,100,000 messages.
- 13:10 Consumer prefetch identified as the bottleneck.
- 13:35 Prefetch cap deployed; drain rate roughly tripled.
- 15:00 Backlog fully drained, incident resolved.

## Root cause

The `webhook-dispatch` consumer was configured with an unbounded prefetch. Under
a burst it pulled far more messages into memory than it could process, hit
sustained garbage-collection pressure, and its effective throughput collapsed to
roughly a third of nominal. The queue then grew faster than it drained.

## Contributing factors

The paging threshold on queue depth was set at 5,000,000 messages, chosen when
the queue was first introduced and never revisited. The backlog peaked below that
threshold, so the on-call responder learned about the incident from a customer
ticket rather than from an alert.

The batch import endpoint had no per-tenant rate cap, so a single customer could
saturate a shared queue.

## Action items

1. Cap consumer prefetch at 500 messages. Owner: Platform Reliability. Shipped
   13:35 on the day of the incident.
2. Re-tier queue-depth alerting to warn at 250,000 and page at 1,000,000. Owner:
   Platform Reliability. Shipped 18 March 2026.
3. Add a per-tenant bulk import cap of 50,000 shipments per hour. Owner:
   Ingestion. Shipped 27 March 2026.
4. Add a saturation panel for every queue to the service RED dashboards. Owner:
   Observability. Due 30 April 2026.

## What went well

Mitigation was deployed 25 minutes after the bottleneck was identified. The
status page was updated within the SEV2 expectation and no customer data was
lost.
