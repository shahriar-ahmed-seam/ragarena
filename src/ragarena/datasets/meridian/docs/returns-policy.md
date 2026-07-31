# Returns and RMA Handling

## Raising a return

A return is created against a delivered shipment via
`POST /shipments/{id}/returns`. A return authorisation (RMA) is valid for 30 days
from issue. After that the RMA expires and a new one must be raised; the original
shipment reference is preserved on the new RMA so reporting stays joined up.

Returns cannot be raised against a shipment in `exception` until the exception is
cleared, because the physical location of the freight is unknown.

## Return labels

A return label expires 21 days after issue, which is deliberately shorter than
the 30 day RMA window: the label is a carrier commitment with a price attached,
and carriers reprice after three weeks. An expired label can be reissued at no
charge while the RMA is still valid.

Labels are generated asynchronously. The `return.label_ready` event fires when the
label is available; polling the return object is unnecessary.

## Refunds

Once a returned parcel is scanned at the destination warehouse, the refund is
issued within 14 days. Refunds go back to the original payment method. A partial
return refunds pro rata by line item value, not by weight.

## Restocking and fees

A restocking fee is configurable per workspace, capped at 20% of line item value.
Fees do not apply to returns caused by a carrier-confirmed damage or loss event.

## Data retention for returns

Return records, including inspection photographs, are retained for 18 months from
closure. This is shorter than the 7 year shipment record retention because
returns data is operational rather than a customs record. Inspection photographs
are stripped of location metadata on upload.

## Reporting

`GET /returns/summary` gives return rate by workspace, by carrier and by line item
category over a requested window of up to 13 months. Return rate above 8% for a
single category over 30 days raises an advisory notification to the workspace
owner, because that usually indicates a catalogue data problem rather than a
logistics problem.
