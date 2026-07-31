# Finance Operations

## Carrier invoice reconciliation

Carrier invoices are reconciled with a three-way match: the booked shipment, the
carrier's rated charge, and the carrier's invoice line. All three must agree
within tolerance before the invoice line is approved for payment.

The match tolerance is the greater of $2.50 or 1.5% of the line value. Anything
outside tolerance is routed to the disputes queue rather than paid and corrected
later, because recovering an overpayment from a carrier is materially harder than
withholding it.

## Disputes

A carrier invoice line can be disputed within 45 days of the invoice date. After
that the line is deemed accepted regardless of the underlying error, which is why
the reconciliation run is a blocking part of month-end rather than a best-effort
job.

Disputes are tracked to closure with an ageing report; anything open beyond 60
days escalates to the Head of Finance.

## Month-end close

The books close by the fifth business day of the following month. The sequence is
fixed: carrier invoice reconciliation, then customer overage calculation, then
revenue recognition, then the close package.

Customer invoices finalise on the first of the month, before reconciliation
completes. The two are deliberately decoupled: customer billing must not wait on
carrier paperwork.

## Revenue recognition

Platform fees are recognised rateably across the subscription month. Shipment
overage is recognised in the month the shipment was booked, which is the same
event that meters it, so billing and revenue never disagree about which month a
shipment belongs to.

Freight charges passed through to the customer are recognised gross with the
carrier cost as an offsetting expense, not netted.

## Credits and write-offs

Service credits under the SLA are recorded as a reduction of revenue in the month
the credit is applied, not the month of the incident. Write-offs above $5,000
require sign-off from the Head of Finance and the account owner.

## Currency

The platform bills exclusively in USD. Carrier invoices arriving in other
currencies are translated at the rate on the invoice date, and the translation
difference at payment is booked to FX gain or loss rather than adjusted against
the shipment margin.
