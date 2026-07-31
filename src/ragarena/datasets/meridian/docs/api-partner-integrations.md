# Partner Integration API (v1)

A separate surface from the customer-facing Shipments API, used by carrier and
marketplace partners. It is versioned, rate limited and authenticated
independently.

Base URL: `https://api.meridianfreight.com/partner/v1`

## Authentication

Partner traffic uses mutual TLS plus the OAuth 2.0 client credentials grant.
Certificates are issued per partner and per environment, and are valid for 13
months. There are no long-lived bearer tokens on this surface: access tokens
expire after 15 minutes and must be refreshed.

A partner certificate approaching expiry raises a warning 30 days out. Expiry
takes the integration down, so renewal is tracked as scheduled work rather than
handled reactively.

## Rate limits

The Partner API is limited to 120 requests per minute per partner credential,
with a burst allowance of 20 requests. This is intentionally lower than the
customer Shipments API, because partner calls fan out into carrier systems that
we do not control.

Exceeding the limit returns `429 partner_rate_limited`. Unlike the customer API,
partner rate limits are enforced per credential *and* per partner organisation,
so issuing extra credentials does not raise the ceiling.

The server-side request timeout on this surface is 45 seconds, longer than the
customer API because carrier lookups are slow and frequently synchronous.

## Idempotency

Write calls accept an `Idempotency-Key` header. Partner keys are retained for 6
hours, shorter than the customer API window, because partner replays are
operational retries rather than user-initiated resubmissions.

## Pagination

Cursor pagination with a `limit` that defaults to 25 and caps at 100. The
customer API allows larger pages; the partner cap is lower because responses
embed full carrier payloads.

## Sandbox and certification

Every partner completes a certification suite in sandbox before production
credentials are issued: 40 scripted scenarios covering happy path, carrier
rejection, partial pickup and cancellation. Certification results are valid for
12 months, after which the suite must be re-run.

## Deprecation

Breaking changes on the Partner API get 90 days notice, and a deprecated
endpoint keeps serving for 180 days after the announcement. Both windows are
shorter than the notice period offered to Enterprise customers on the
customer-facing API.
