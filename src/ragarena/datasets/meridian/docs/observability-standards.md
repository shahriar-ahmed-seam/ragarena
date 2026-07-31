# Observability Standards

Every service in production must meet this baseline before it takes customer
traffic.

## Golden signals

Each service instruments latency, traffic, errors and saturation, and exposes a
RED dashboard (rate, errors, duration) with p50, p95 and p99 latency. A service
without a saturation panel is not considered production ready.

## Alert thresholds

- API 5xx error rate above 1% sustained for 5 minutes: page
- p95 endpoint latency above 800 ms sustained for 10 minutes: page
- Queue depth above 250,000 messages: warn
- Queue depth above 1,000,000 messages: page
- Consumer lag growing for 15 consecutive minutes: warn
- Certificate expiry within 14 days: warn

Every alert carries a runbook link and an owning team. Alerts that fire more than
five times a week without action are either fixed or deleted; a noisy alert is
treated as an incident of its own kind.

## Tracing

Distributed tracing uses OpenTelemetry. The head-based sample rate is 10% for
successful requests and 100% for requests that end in an error or exceed one
second. Trace context propagates across the queue boundary, so a webhook delivery
can be traced back to the API call that produced it.

## Logging

Logs are structured JSON, one event per line, always including `request_id`,
`workspace_id` and `service`. Personal data must never be written to logs; the
consignee fields are tokenised before they reach any log sink.

Application logs are retained for 90 days in hot storage and a further 400 days
in cold archive.

## Service level objectives

The `/shipments` endpoints carry a 99.9% availability objective measured over a
rolling 30-day window, which allows an error budget of roughly 43 minutes per
month. Burning more than half the monthly error budget in a single week freezes
feature deploys for that service until a reliability review is held.

Latency objective for `/shipments` reads is p95 under 300 ms and p99 under 900 ms.

## Dashboards

Each team maintains one service overview dashboard and one on-call triage
dashboard. The triage dashboard must answer three questions without navigation:
is the service up, is it slow, and is it saturated.
