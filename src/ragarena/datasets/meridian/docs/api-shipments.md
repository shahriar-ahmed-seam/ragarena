# Shipments API Reference (v2)

Base URL: `https://api.meridianfreight.com/v2`

## Authentication

All requests use a bearer token in the `Authorization` header. Tokens are scoped;
the shipments endpoints require `shipments:read` for reads and `shipments:write`
for writes. A token missing the required scope returns `403 scope_insufficient`.

Tokens do not expire on a schedule but are revoked immediately when the issuing
workspace member is deactivated.

## Rate limits

Each API key is limited to 600 requests per minute with a burst allowance of
100 requests. Exceeding the limit returns `429 rate_limited` with a
`Retry-After` header in seconds. Rate limits are per key, not per workspace, so
splitting traffic across keys raises effective throughput.

The server-side request timeout is 30 seconds. A request still executing at that
point is terminated and returns `504 upstream_timeout`.

## Creating a shipment

`POST /shipments`

Supply an `Idempotency-Key` header on every create. Keys are retained for 24
hours; replaying the same key inside that window returns the original response
instead of creating a duplicate shipment.

A single shipment accepts at most 250 line items. Larger manifests must be split
across multiple shipments.

Required fields: `origin`, `destination`, `service_level`, `line_items`.
Optional: `reference`, `incoterms`, `requested_pickup_at`, `metadata`.

## Shipment lifecycle

A shipment moves through these statuses:

- `draft` - created but not submitted to a carrier
- `booked` - accepted by a carrier, billing has been triggered
- `in_transit` - picked up
- `delivered` - terminal success state
- `cancelled` - terminal state after an explicit cancellation
- `exception` - carrier reported a problem; requires manual resolution

`POST /shipments/{id}/cancel` succeeds only while the shipment is in `draft` or
`booked`. Once a shipment reaches `in_transit` the cancel endpoint returns
`409 not_cancellable` and the shipment must be handled as a return.

## Listing and pagination

`GET /shipments` uses cursor pagination. The `limit` parameter defaults to 50
and accepts a maximum of 200. The response includes `next_cursor`, which is
`null` on the final page. Offset pagination is not supported.

Filters: `status`, `created_after`, `created_before`, `reference`,
`service_level`.

## Errors

Errors return a JSON body with `code`, `message` and `request_id`. Always log
`request_id`: support cannot trace a failed call without it. Codes in the `4xx`
range are permanent and must not be retried unmodified, with the single
exception of `429`.
