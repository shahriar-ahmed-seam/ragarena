# Mobile Driver Application

The driver app is offline-first. Drivers work in warehouses, lorries and rural
delivery areas where connectivity is unreliable, so every operation must succeed
without a network and reconcile later.

## Sync model

The app syncs its outbound queue every 90 seconds when connectivity is available,
and immediately on regaining a connection. Up to 500 scan events can be queued
offline; beyond that the oldest non-critical telemetry is dropped first, and
delivery-critical events are never dropped.

Conflicts are resolved server-side by event timestamp, with the device clock
corrected against the server's clock on every successful sync. A device whose
clock is more than 10 minutes out is flagged in the fleet dashboard.

## Location reporting

GPS position is reported every 30 seconds while a route is active, and not at all
when no route is active. Position reporting stops entirely when battery falls
below 15%, at which point the app enters a low-power mode that keeps scanning and
proof-of-delivery capture working.

## Proof of delivery

Signature capture and photographs are stored locally at full resolution and
uploaded downsampled, with the original retained on device for 7 days as a
fallback. A delivery is never blocked on a successful upload.

## Supported platforms

The app supports iOS 16 and later and Android 11 and later. Support for an OS
version is dropped one release after it falls below 2% of the active device
fleet, announced 60 days ahead.

## Release cadence

The app ships on the weekly release train that cuts every Wednesday, the same
cadence described in the deployment and release process. Hotfixes outside the
train need sign-off from the mobile lead and the Director of Engineering.

Forced upgrades are used sparingly: the app refuses to run only when its API
contract version is no longer served, and drivers get an in-app warning for 14
days before that point.

## Diagnostics

Drivers can attach a diagnostic bundle to a support ticket from inside the app.
The bundle contains the sync queue state, the last 200 log lines and device
metadata. It never contains customer addresses or recipient names.
