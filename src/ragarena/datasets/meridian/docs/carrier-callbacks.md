# Carrier Callback Ingestion

Carriers push tracking milestones to Meridian. This is the inbound mirror of the
outbound webhooks we send to customers, and the two systems deliberately do not
share configuration.

## Endpoint

Carriers post to `https://ingest.meridianfreight.com/carrier/{carrier_code}`.
Each carrier has its own path and its own credential; there is no shared
endpoint.

## Signature verification

Carrier callbacks are verified with **HMAC-SHA1** over the concatenation of the
timestamp and the raw body, supplied in the `X-Carrier-Sign` header. The
timestamp tolerance is 10 minutes.

SHA-1 is a legacy requirement: three of the seven integrated carriers cannot
sign with anything stronger. The migration to SHA-256 is tracked as a compliance
action item with a target of Q4 2026. Do not copy this scheme for new
integrations; outbound customer webhooks use HMAC-SHA256 with a 5 minute
tolerance and that is the pattern to follow.

## Retry behaviour on our side

If our ingest endpoint returns a non-2xx, most carriers retry, but the policy
belongs to them and we cannot rely on it. Our own internal reprocessing of a
callback that failed downstream is attempted 5 times, with backoff starting at
30 seconds and a total window of 12 hours.

A carrier integration that produces 50 consecutive signature failures is
suspended and an alert pages the Integrations team. Suspension is at the carrier
level, not the shipment level.

## Deduplication

Carriers routinely send the same milestone more than once. Callbacks are
deduplicated on the tuple of carrier code, tracking number, milestone code and
milestone timestamp, with a 72 hour deduplication window.

Duplicate suppression is logged but not surfaced to customers, so a customer
seeing one `shipment.status_changed` event for a milestone the carrier sent three
times is the system working correctly.

## Unknown milestones

A milestone code we do not recognise is stored raw, mapped to the generic
`in_transit` status, and reported in the weekly integrations digest. Unknown
codes are never dropped silently, because a carrier adding a code without notice
is the most common cause of a tracking gap.

## Latency expectation

Callbacks are processed within 60 seconds of receipt at p95. Processing slower
than 5 minutes at p95 for 15 minutes raises a warning, not a page, because
tracking freshness degrades gracefully.
