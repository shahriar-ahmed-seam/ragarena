# Data Retention and Deletion Policy

Owner: Data Governance. Reviewed annually.

## Retention periods

Shipment records are retained for 7 years after the shipment reaches a terminal
status. This period is set by customs and freight-forwarding record-keeping
obligations and cannot be shortened by customer request.

API request logs are retained for 90 days in the primary log store. After 90
days they are aggregated into daily rollups, which are kept for 400 days for
capacity planning. Rollups contain counts and latency histograms only, never
request bodies.

Webhook delivery logs, including response codes and bodies, are retained for 30
days.

Support ticket contents are retained for 3 years after the ticket is closed.

## Workspace deletion

Deleting a workspace starts a 30-day soft-delete window during which an
administrator can restore it in full. After the window closes, purge jobs remove
all workspace data within a further 14 days, except records under the 7-year
shipment retention obligation, which are anonymised in place instead of deleted.

A deletion certificate is issued on request once the purge completes.

## Backups

Full backups run daily and are retained for 35 days. Point-in-time recovery is
available for the most recent 7 days. Backups are encrypted with a separate key
hierarchy from the primary datastore, and restore drills are performed quarterly.

## Personal data

The following fields are tokenised at ingest and stored only in the vault-backed
token service: consignee name, consignee phone number, and the second address
line. Application databases hold tokens, so a database compromise alone does not
expose these fields.

Data subject access requests are fulfilled within 30 days of a verified request.
A request that spans data under the 7-year retention obligation is answered with
the data plus a statement of the legal basis for continued retention.

## Customer exports

Customers may export their own data at any time through
`GET /exports/shipments`, which produces newline-delimited JSON. Exports are
generated asynchronously and the download link expires after 72 hours.
