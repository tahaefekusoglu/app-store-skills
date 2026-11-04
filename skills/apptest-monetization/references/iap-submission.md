# Preparing and submitting a purchase product in App Store Connect

Done by the user; the member prepares the steps and texts (principle 16). Field
limits and requirements can change: compare against the current help page before
relying on them (principle 7):
https://developer.apple.com/help/app-store-connect/manage-in-app-purchases/

## Prerequisites

- Paid Apps agreement, tax and banking details "Active" (Business).
- App record and bundle id ready.

## Product (MO-30 … MO-37)

| ID | Field | Note |
|---|---|---|
| MO-30 | Type | Consumable / non-consumable / auto-renewable / non-renewing; cannot change later |
| MO-31 | Reference Name | Visible only in ASC; make it descriptive |
| MO-32 | Product ID | EXACTLY as in code; cannot change later and cannot be reused even after deletion |
| MO-33 | Price | Price tier; regions |
| MO-34 | Localization: Display Name + Description | The user sees these in the purchase sheet; CHECK THE FIELD LIMITS in ASC (e.g. the description is short). Says what the app really provides (2.3); concrete rather than a vague term such as "history" (e.g. a budgeting app rewrote its description for the 55-character limit and concrete wording) |
| MO-35 | Review Screenshot | REAL image of the purchase screen; one of the accepted sizes and with NO ALPHA CHANNEL (e.g. a budgeting app's PNG with alpha was rejected; JPEG / RGB PNG passed) |
| MO-36 | Review Notes | Path to the purchase screen; what is seen in sandbox |
| MO-37 | Status | Without "Ready to Submit", "product not found" can appear in TestFlight too |

## Submission

- The FIRST purchase product / first subscription is ADDED to the version from
  the "In-App Purchases and Subscriptions" section of the app version page and
  submitted with the version; not submitted separately (T-06).
- Later products can be submitted on their own.
- Subscriptions: subscription group, ordering within the group (upgrade /
  downgrade), introductory offers; group localization.
