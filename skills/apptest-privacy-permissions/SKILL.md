---
name: apptest-privacy-permissions
description: "iOS privacy and permissions audit: usage descriptions (ITMS-90683), App Tracking Transparency, privacy manifest (ITMS-91053), privacy label, policy vs actual behaviour, consent for sending data to AI, health data."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - WebFetch
metadata:
  version: "1.0.0"
---

# apptest-privacy-permissions — privacy and permissions

Depends on: `../apptest/shared/CONVENTIONS.md` ≥ 1.2 · report
`../apptest/shared/report.md` · rejection index `../apptest/shared/rejections.md`
(R-37 … R-48). Rule text comes from the official site every time (principle 7):
https://developer.apple.com/app-store/review/guidelines/#privacy ·
https://developer.apple.com/documentation/bundleresources/privacy-manifest-files ·
https://developer.apple.com/app-store/user-privacy-and-data-use/

**Default contract:** Reports; does not touch code or App Store Connect.
Sends user data nowhere. `--policy-url` only reads the public policy page.

## When

- A new permission (camera, location, microphone, contacts, health …), a new SDK
  (analytics, ads, crash reporting, sign-in) or an AI feature was added.
- The App Store Connect privacy label or the privacy policy is being
  written / updated.
- An ITMS-90683 / ITMS-91053 / ITMS-91061 email arrived after upload.
- Before release (the family head's Release mode).

## Out of scope

- Legal sufficiency (KVKK / GDPR compliance): this member checks whether the
  policy text describes what the app DOES; it gives no legal opinion.
- Account deletion and sign-in methods (5.1.1(v), 4.8) → network.
- Kids category details → content-safety.

## Step 0

CONVENTIONS §5. Read-only; no build or simulator needed (except trying the
permission flow by hand, below).

## Member-specific principles

- **PP-P1** Does not guess what an SDK collects; relies on the SDK's docs or
  privacy manifest, otherwise says "not verified".
  *Why:* a wrongly filled privacy label leads to a 5.1 rejection and a false
  statement to users; a guess can be wrong in either direction.
- **PP-P2** Treats every difference between the privacy label, policy text,
  privacy manifest and code as a finding; the user decides which one is right.
  *Why:* each of the four can look "reasonable" alone while contradicting the
  others (e.g. a budgeting app's privacy text had stale backup and notification details).

## Profile

`python3 -I "${CLAUDE_SKILL_DIR}/../apptest/shared/profile.py" <root>` →
`permissions` (permissions), `tracking` (tracking), `ads` (ads), `ai` (AI),
`account` (account), `extensions` (extensions: each has its own Info.plist and
privacy manifest), technology (Expo / Unity / MAUI: Info.plist is generated at
build time; descriptions may come from a plugin / app.json / csproj).

The scripts read Info.plist **as it ships to the store**: custom-named files
(`App-Info.plist`), Xcode's generated `INFOPLIST_KEY_*` build settings and
`.xcconfig`, the Release configuration; excluding variants such as Alpha / Debug /
Experimental, and framework and test bundles (`profile.shipping_info_plists`).

## Setup (good to know from the start)

1. **Data inventory from the start:** what data, from where, to whom (your own
   server, SDKs, AI provider), for how long. The privacy label, policy and
   privacy manifest are filled from this; reconstructing it later is hard.
2. **Each SDK's data behaviour and privacy manifest** are read before adding it;
   an ad / attribution SDK means tracking → ATT and label.
3. **Ask for a permission when it is needed,** in a context where the user
   understands what it is for; after a denial the app keeps working.
4. **Concrete usage descriptions:** "To photograph your receipt and read the
   total", not "Camera access required". If the app is multi-language, the
   description is translated too.
5. **AI:** if personal data goes to a third-party model, say which data goes to
   whom and get explicit permission BEFORE sending (5.1.2(i)). A model running
   on the device is outside this rule.
6. **Required-reason APIs** (UserDefaults, file timestamps, boot time, disk space,
   keyboard list) go in the privacy manifest with a reason code, updated on every
   new use (store-readiness SR-31).
7. **Health data** is not stored in iCloud and not used for ads (5.1.3).

## Test (during development)

### 1. Static scan (seconds)

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-privacy-permissions/scripts/privacy_scan.py" <root> [--json] [--policy-url <privacy_url>]
```

| ID | Topic | Severity |
|---|---|---|
| PP-10 | No usage description for a capability used in code (SUGGESTION if only a package is present) | REJECTION RISK (ITMS-90683) |
| PP-11 | Usage description present, no use found | SUGGESTION (5.1.1(iii)) |
| PP-12 | Usage description vague or too short | REJECTION RISK (5.1.1(ii)) |
| PP-13 | Usage descriptions not translated in a multi-language app | SUGGESTION |
| PP-14 | Permission may be requested at the app entry point, without context | SUGGESTION (HIG) |
| PP-20 | Ad / attribution SDK present, ATT not requested | REJECTION RISK (5.1.2, ATT) |
| PP-21 | Privacy manifest tracking declaration ↔ SDK mismatch | SUGGESTION |
| PP-22 | No collected data types in the manifest, but analytics / account / crash reporting exist | SUGGESTION (R-43) |
| PP-30 | Third-party AI present, no consent / disclosure found | REJECTION RISK (5.1.2(i)) |
| PP-40 | Health data + iCloud | REJECTION RISK (5.1.3) |
| PP-41 | Background / always-on location | SUGGESTION (5.1.5, 2.5.4) |
| PP-50 | Inventory of third-party components that may collect data | INFO |
| PP-60 / 61 | Privacy policy does not open · does not mention something the app does | REJECTION RISK (5.1.1(i)) |

The output is CANDIDATES (principle 6). When verifying: PP-10, is the capability
really used and does the description come from another source (Expo plugin, MAUI
csproj, Unity setting); PP-11, is a package using it; PP-20, has the SDK been
configured out of tracking; PP-30, is the model on the device.

### 2. Permission flow (simulator, by hand; principle 13)

Your own temporary simulator (CONVENTIONS §5.4). Reset permissions and try every
path:

```sh
xcrun simctl privacy <UDID> reset all <bundle>
xcrun simctl privacy <UDID> revoke photos <bundle>       # denied-permission path
xcrun simctl privacy <UDID> revoke location <bundle>
```

Services: `photos`, `photos-add`, `location`, `location-always`,
`contacts`, `calendar`, `reminders`, `microphone`, `motion`,
`media-library`, `siri` (current list: `xcrun simctl help privacy`).
The simulator has no camera: try the camera permission and its denial on a real device.

Look at: when the permission is asked (at launch, or on tapping the feature),
what the description says, whether the app works after denial and shows the user
the path to Settings, whether the ATT prompt comes BEFORE tracking starts.

## Release (before submitting)

1. **Check Apple (principle 7):** current 5.1.x text + "Last Updated";
   privacy manifest reason codes and the "commonly used SDK" list from the
   current page (the list changes).
2. Static scan + `--policy-url` (the privacy link in the app).
3. **Privacy label (App Store Connect › App Privacy) ↔ code ↔ manifest
   ↔ policy** comparison (PP-P2): ask the user for a screenshot of the label or
   its answers; for each data type "is it collected, is it linked to identity,
   is it used for tracking". Give the differences as a table.
4. **Extensions:** each extension's Info.plist and privacy manifest separately
   (R-44).
5. If an ITMS warning email arrived after upload: match the code to the relevant
   API or SDK and the missing reason in the manifest.
6. Report.

## Report

`shared/report.md`. The privacy label comparison is a separate table:
data type · code / SDK evidence · manifest · label · policy · difference.
Environment: "Apple rules: Last Updated <date>, read <today>"; if the policy was
read, its address and date.
