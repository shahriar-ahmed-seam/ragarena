# Capacity Planning and Peak Season

## Seasonality

Traffic is strongly seasonal. November and December run at roughly 4x the annual
baseline, peaking in the ten days after the last Thursday in November. January
drops back below baseline.

## Pre-scaling

Production is pre-scaled to 3x baseline capacity by 1 November and held there
through 5 January. Autoscaling covers the gap between 3x and peak, but is not
relied on to absorb the initial step: cold-start latency on the ingestion workers
is around 90 seconds, which is too slow when volume steps up inside a minute.

A change freeze applies to infrastructure topology from 1 November to 5 January.
Application deploys continue normally under the usual canary rules.

## Load testing

A full load test runs quarterly at 5x baseline, plus a mandatory peak-readiness
test in the second week of October. The October test must sustain 5x for 60
minutes with p95 API latency under 500 ms and zero queue growth.

Load tests run against staging at production topology, which is why staging is
maintained at one quarter of production capacity rather than something smaller:
scaling a quarter-size environment by 4x is a credible extrapolation, scaling a
toy environment is not.

## Component sizing

- RabbitMQ runs as a 3 node cluster with quorum queues; a single node loss is
  survivable with no message loss.
- Postgres runs one primary and 2 read replicas. Reporting queries are pinned to
  replicas; anything in the booking path reads the primary.
- Connection pools are sized at 25 per API replica, with PgBouncer in transaction
  pooling mode in front. Raising the pool size is almost never the right fix for
  saturation and requires a written justification.
- Redis is used for rate limiting and idempotency keys only, never as a system of
  record.

## Error budget interaction

Peak season does not relax the 99.9% availability objective. It does change the
response: during the freeze window, burning half the monthly error budget in a
week triggers an immediate capacity review rather than a feature-deploy freeze,
because there are no feature deploys to freeze.

## Forecasting

Capacity forecasts are refreshed monthly from the previous 13 months of shipment
volume plus signed contract commitments for the coming quarter. A new Enterprise
contract above 500,000 shipments per month triggers an out-of-cycle capacity
review before the go-live date.
