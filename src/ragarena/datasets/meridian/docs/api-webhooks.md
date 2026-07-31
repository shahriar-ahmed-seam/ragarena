# Webhooks Reference

Webhooks push state changes to your endpoint so you do not have to poll the
Shipments API.

## Event types

- `shipment.created`
- `shipment.status_changed`
- `shipment.exception`
- `invoice.finalized`

Subscriptions are per workspace. One endpoint may subscribe to any combination
of event types. Event payloads carry the full current resource, not a diff.

## Signature verification

Every delivery carries two headers:

- `X-MFS-Signature` - hex-encoded HMAC-SHA256 of the raw request body, keyed
  with your endpoint's signing secret
- `X-MFS-Timestamp` - Unix seconds at which the delivery was signed

Compute the HMAC over the raw bytes of the body, before any JSON parsing or
re-serialisation. Reject a delivery whose timestamp is more than 5 minutes away
from your clock; this is the replay tolerance window.

Signing secrets are rotated from the dashboard. Both the old and the new secret
stay valid for 24 hours after a rotation so you can roll the change out without
dropping deliveries.

## Delivery timeout

Your endpoint must return a 2xx status within 10 seconds. Anything slower is
recorded as a failed delivery even if your handler eventually finishes, so do
the work asynchronously and acknowledge immediately.

## Retry policy

A failed delivery is retried up to 8 times. Backoff is exponential, starting at
10 seconds and capped at a 6 hour interval. Retries stop once the total delivery
window of 24 hours has elapsed, whichever comes first.

An endpoint that records 100 consecutive failed deliveries is disabled
automatically. All workspace owners receive an email when this happens, and the
endpoint must be re-enabled manually from the dashboard.

## Replay

`POST /webhooks/{id}/replay` re-sends historical events to a subscription. Replay
covers up to 7 days of event history and is rate limited to 10,000 events per
request. Replayed deliveries carry the header `X-MFS-Replay: true` so your
handler can distinguish them from live traffic.

## Ordering

Deliveries are not ordered. Two status changes on the same shipment may arrive
out of order, so treat the `occurred_at` field in the payload as authoritative
and discard any event older than the state you already hold.
