---
name: apptest-monetization
description: "In-app purchase and subscription audit: guidelines 3.1.1 / 3.1.2, Restore Purchases, product not found, paywall disclosures, external payment, hardcoded prices, ads, sandbox testing."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-monetization — purchases, subscriptions, ads

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.10 · report
`../apptest/shared/report.md` · rejection index `../apptest/shared/rejections.md`
(R-05, R-20 … R-27, T-06). Rule text comes from the official site EVERY TIME
(principle 7); the regional link and payment rules in 3.1.1(a) / 3.1.3 in
particular change often: https://developer.apple.com/app-store/review/guidelines/#payments ·
https://developer.apple.com/in-app-purchase/ ·
https://developer.apple.com/help/app-store-connect/manage-in-app-purchases/
Talking with the user: `../apptest/shared/CONVENTIONS.md` §11 (when to ask, status lines, one next step).

**Default contract:** Reports; does not write to code or App Store Connect.
Creating / submitting a purchase product is the user's job (principle 16); the
member prepares the steps and texts.

## When

- An in-app purchase, subscription, Pro / premium lock or ads are being added.
- "Product not found", price not showing, restore not working.
- A purchase product is about to be created in App Store Connect / submitted
  for review.
- A 3.1.x rejection arrived. Before release (the family head's Release mode).

## Out of scope

- Price, packaging, trial length, business model decisions (MO-P2).
- The tracking side of ads (ATT, privacy label) → privacy-permissions
  (PP-20). Ads in the kids category → content-safety.
- The flow of paying for physical goods / services itself (only asks "is this
  the right route").

## Step 0

CONVENTIONS §5. The static scan only reads. StoreKit / sandbox trials run on a
temporary simulator or the user's test device; real Apple accounts and real
money are NOT used (MO-P1).

## Member-specific principles

- **MO-P1** Makes no real purchases; only a StoreKit configuration file
  (local) or sandbox / TestFlight.
  *Why:* risk to real money, refunds and the user's account.
- **MO-P2** Stays out of price, packaging and business model; only rule
  compliance and consistency: promised on screen = gate in code = product in
  App Store Connect.
  *Why:* the business decision is the user's; but a mismatch between promise
  and gate is a 2.3 / 3.1 rejection (e.g. a budgeting app's paywall bullets
  were made to match its code gates one to one).
- **MO-P3** Reports a gate that exists only in the UI (not checked in the
  service / server layer) as a SUGGESTION, not an error.
  *Why:* it is an architecture decision (principle 2); but a bypassable gate is
  lost revenue, and the user should know.

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`purchases` (purchases), `subscriptions` (subscription), `ads` (ads); from the
dependencies, an intermediary such as RevenueCat / Adapty (then product
configuration also lives in their dashboard).

## Setup (good to know from the start)

1. **Product type clear from the start:** consumable (coins), non-consumable
   (permanent unlock), auto-renewable subscription, non-renewing subscription.
   Restore, refund and subscription rules vary by type.
2. **Product ID from one source** (code, StoreKit file, App Store
   Connect, RevenueCat if used): it cannot be changed later.
3. **Price always comes from the store** (localized); never hardcoded in code
   or text.
4. **Restore** is a visible button; a purchased entitlement comes back after
   changing devices or reinstalling.
5. **Where the entitlement is checked:** only in the UI, or also in the
   service / server (MO-P3). A refund / subscription end removes the entitlement;
   the user's data must not be locked (e.g. in a budgeting app, a user who
   drops from Pro still sees their data but cannot start new Pro actions).
6. **Subscription screen (3.1.2(c)):** name, length, price and unit price,
   auto-renewal and cancellation, terms of use (EULA) and privacy links are
   visible BEFORE purchase. Apple's `SubscriptionStoreView` /
   `StoreView` show most of these themselves.
7. **Digital ≠ physical:** digital content / features through in-app purchase
   (3.1.1); physical goods / person-to-person services through outside payment
   (3.1.3); regional exceptions from the current text.
8. **StoreKit configuration file** from day one: try purchase, refund, renewal
   and interruption on the simulator without money.

## Test (during development)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-monetization/scripts/monetization_scan.py" <root> [--json]
```

| ID | Topic | Severity |
|---|---|---|
| MO-10 | Product IDs in code (compare exactly with ASC) | INFO |
| MO-11 | Product in code but not in the StoreKit file | USER BUG |
| MO-12 | No StoreKit configuration file | SUGGESTION |
| MO-13 | Purchases exist, with no "Restore" call, or with a call but no visible Restore text | REJECTION RISK (3.1.1) |
| MO-14 | No terms / privacy / renewal info on the subscription screen | REJECTION RISK (3.1.2(c)) |
| MO-15 | Price hardcoded in code or text | USER BUG |
| MO-16 | Outside payment / web checkout link (if purchases exist) | REJECTION RISK / SUGGESTION |
| MO-17 | Unlocking with a code (license / coupon), not an Apple offer code | SUGGESTION (3.1.1) |
| MO-18 | Reward in exchange for a review / rating | REJECTION RISK (3.2.2, 5.6.1) |
| MO-19 | Random rewards, odds not shown | REJECTION RISK (3.1.1) |
| MO-20 | Ad SDK (rules reminder) | INFO |

The output is CANDIDATES (principle 6). When verifying: MO-13, are only
consumables sold; MO-14, does the info come from a server / image; MO-16, is
what's sold digital or physical (a donation to an approved organization?).

### 2. StoreKit trial (simulator; principle 13)

- Select **StoreKit Configuration** in the Xcode scheme (Flutter / RN use it too
  when run from Xcode). Try: buy · cancel · interrupted · pending approval
  (Ask to Buy) · refund · subscription renewal and expiry · delete and reinstall
  → Restore.
- Automated test: `SKTestSession` in XCTest (refund, accelerated renewal,
  interruption): suggested if the project uses XCTest, not added.
- Look at: does the price come from the store and is it right in another region;
  are error and cancel messages clear; does Restore report its result; on refund /
  expiry does the entitlement go while the data stays unlocked.

### 3. Sandbox / TestFlight (device; done by the user)

TestFlight purchases are sandbox, no money is charged. If "product not found"
appears, in order: does the product exist in ASC and does the ID match exactly ·
is the product "Ready to Submit" (name, description, price, review screenshot
complete) · Paid Apps agreement + tax + banking "Active" · is the bundle id right ·
if the product is new, a few hours of propagation.

## Release (before submitting)

1. **Check Apple (principle 7):** current 3.1.x and 3.2 text + "Last
   Updated"; regional payment link rules.
2. Static scan.
3. **Product in App Store Connect** (with the user; `references/iap-submission.md`):
   name / description limits, price, review screenshot and note; the FIRST product
   is submitted TOGETHER with a version from the version page (T-06, SR-87).
4. **Review note:** path to the purchase screen, product name, where Restore is
   (store-readiness SR-P3).
5. **Screen = gate = product** comparison (MO-P2): for every promise on the
   purchase screen, the gate in code and the product in ASC.
6. Report.

## Report

`shared/report.md`. Separate table: promise (item on screen) · gate in code
(file:line) · ASC product · difference. Environment: "Apple rules: Last Updated
<date>, read <today>"; if StoreKit / sandbox was tried, which scenarios.
