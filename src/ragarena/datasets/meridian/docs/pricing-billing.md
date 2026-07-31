# Pricing, Metering and Billing

## Plans

- Standard: $499 per month, includes 50,000 shipments
- Business: $1,900 per month, includes 250,000 shipments
- Enterprise: custom pricing, negotiated per contract

An annual commitment paid up front receives a 15% discount on the platform fee.
The discount does not apply to overage charges.

## Overage

Shipments beyond the plan allowance are billed per shipment:

- Standard: $0.012 per shipment
- Business: $0.008 per shipment
- Enterprise: set in the contract

Overage is calculated on the calendar month and appears as a separate line on the
invoice.

## What counts as a billable shipment

A shipment is metered once, at its first transition into the `booked` status. A
shipment that stays in `draft` is never billed. A shipment that is cancelled after
being booked remains billable, because the carrier booking has already been made.

Re-bookings of the same shipment after a cancellation count as a new billable
shipment.

## Invoicing

Invoices finalise on the first day of each month for the preceding month and are
issued on net 30 terms. The `invoice.finalized` webhook fires at finalisation, so
billing integrations do not need to poll.

Failed payment triggers a dunning sequence at 3, 7 and 14 days. API write access
is suspended 21 days after a failed payment; read access and data export remain
available so a customer is never locked out of their own records.

## Sandbox

The sandbox environment is free and allows 1,000 shipments per month. Sandbox data
is purged every 30 days and carries no uptime commitment or service credits.

Sandbox and production use separate API keys. A production key used against the
sandbox host returns `401 invalid_environment`.

## Taxes and currency

Prices are quoted in USD and exclude applicable taxes. Invoices are issued in USD
regardless of billing country. VAT or sales tax is added where required by the
customer's registered address.
