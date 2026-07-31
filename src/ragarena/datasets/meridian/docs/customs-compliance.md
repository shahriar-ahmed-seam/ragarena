# Customs and Trade Compliance

Applies to every cross-border shipment moved through the platform.

## Classification

Every line item on an international shipment requires a Harmonised System code
of at least 6 digits. Shipments to the United States and the European Union
require 10 and 8 digits respectively. A shipment submitted without a valid code
for its destination is rejected at booking with `422 hs_code_required`.

Classification suggestions are generated automatically but are advisory. The
shipper of record remains legally responsible for the declared code.

## Denied party screening

Every consignee and consignor is screened against sanctions and denied party
lists before a shipment can move to `booked`. Screening runs synchronously and
carries a p95 latency objective of 200 ms; a screening call that exceeds 2
seconds fails open into a manual review queue rather than blocking the booking
indefinitely.

Watch lists are refreshed daily at 03:00 UTC. A refresh that fails twice in a row
pages the Compliance Engineering on-call.

A positive match places the shipment in `exception` and notifies the compliance
queue. Only a compliance officer can clear a match; engineers cannot override a
screening result, and attempting to do so is a reportable control failure.

## Document retention

Customs declarations, commercial invoices and certificates of origin are retained
for 10 years from the date of entry. This is longer than the general 7 year
shipment record retention and is driven by customs audit rules in the largest
trading jurisdictions we operate in.

Retention here is absolute: these documents are excluded from workspace deletion
purges and from data subject erasure requests, and the exclusion is stated in the
data processing agreement.

## Duties and taxes

Landed cost quotes are estimates. Delivered Duty Paid shipments reconcile against
the actual carrier duty invoice, and a variance above 15% is flagged to Finance
Operations for review.

## Restricted goods

Lithium batteries, aerosols and perishables require a hazardous goods
declaration and a carrier that accepts the class. The platform blocks booking
with an unaccepting carrier rather than letting the carrier reject it later,
because a late rejection strands freight at origin.
