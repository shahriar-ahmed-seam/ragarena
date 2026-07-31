# Security and Access Control Policy

Applies to all employees, contractors and third-party integrators.

## Identity

Access to production requires SAML single sign-on through the corporate identity
provider. Local passwords for production systems are not issued under any
circumstances.

Multi-factor authentication is mandatory for every account. Administrators and
anyone holding a production elevation role must use a hardware security key;
TOTP applications are not accepted for those roles.

## Production access

Standing production access is not granted. Engineers request just-in-time
elevation, which is approved by the owning service team and expires
automatically after a maximum of 4 hours. Every elevation records the requester,
the approver, the justification and the commands executed.

Break-glass credentials exist for total identity provider failure. They are held
in a sealed offline safe, and any use triggers an automatic SEV1 and a mandatory
review within one business day.

Access reviews run quarterly. Service owners confirm every active grant; unclaimed
grants are revoked at the end of the review window.

## Secrets

Application secrets live in HashiCorp Vault and are injected at runtime. Secrets
must never be committed to a repository, pasted into a ticket, or stored in a
plaintext environment file on a workstation.

Secret scanning runs on every push and blocks the merge on a positive match. A
leaked credential is rotated immediately and the exposure window is documented.

## Data protection

Customer data is encrypted at rest with AES-256 and in transit with TLS 1.3.
Workstation disks must be fully encrypted; an unencrypted device is denied
network access by the posture check.

## Vulnerability management

Remediation targets, measured from the moment a finding is triaged:

- Critical: 7 days
- High: 30 days
- Medium: 90 days
- Low: next scheduled maintenance window

A target that will be missed requires a documented exception approved by the
Head of Security, with a compensating control in place.

## Third parties

Any vendor processing customer data requires a security review and a signed data
processing agreement before integration. Vendor reviews are repeated annually,
and a vendor holding production data access is also subject to the quarterly
access review.
