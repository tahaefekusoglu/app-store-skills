# App Store Connect — manual checklist

App Store Connect is not visible in the repo (SR-P1): these items are asked
of the user or verified by screenshot, never guessed. Apple can change field
names and limits: during Release, compare against the App Store Connect help
page (CONVENTIONS principle 7):
https://developer.apple.com/help/app-store-connect/

Grade: **Required** = Apple requires it (if missing, cannot submit or rejected) ·
**Conditional** = required depending on the profile · **Optional** = optional / nice to have.

## Agreements and account (Business)

| ID | Item | Grade |
|---|---|---|
| SR-70 | Free apps agreement active | Required |
| SR-71 | If paid app / purchases: Paid Apps agreement + tax + banking "Active" | Conditional (purchases) |
| SR-72 | DSA "trader" status declared for EU distribution | Conditional (EU countries) |

## App Information

| ID | Item | Grade |
|---|---|---|
| SR-73 | Name (30 characters) and subtitle (30): no other brands, prices or "best" claims (2.3.7) | Required |
| SR-74 | Primary / secondary category fit the app | Required |
| SR-75 | Age rating questionnaire answered honestly in its CURRENT version (2.3.6), including Social Media, Shared Location and Dating and Relationships (`shared/rejections.md` has the dates), and the AI / user content / web access questions | Required |
| SR-76 | Content rights (third-party content) declaration | Required |
| SR-77 | Privacy policy URL opens and describes what the app does (5.1.1(i)) | Required |

## Pricing and Availability

| ID | Item | Grade |
|---|---|---|
| SR-78 | Price and countries chosen deliberately | Required |
| SR-79 | Availability as an iPhone/iPad app on **Mac (Apple silicon)** and **Apple Vision Pro** chosen deliberately: ON by default; switched off if untested or broken there (R-14). E.g. a budgeting app switched the Mac option off before submitting | Required |

## App Privacy

| ID | Item | Grade |
|---|---|---|
| SR-80 | Privacy label PUBLISHED and matches real behaviour, SDKs included (details: privacy-permissions) | Required |

## Version page (iOS App › version)

| ID | Item | Grade |
|---|---|---|
| SR-81 | Screenshots: at least one accepted size set for iPhone (current list in ASC help); iPad set if iPad is supported; real screens (2.3.3) — store-assets | Required |
| SR-82 | Description (4000), keywords (100), promotional text (170): no features the app lacks (2.3) | Required (description, keywords) |
| SR-83 | Support URL opens, with current contact details (1.5) | Required |
| SR-84 | Copyright line | Required |
| SR-85 | **Build**: the RIGHT build selected for review (the intended one, not the latest upload). E.g. a budgeting app needed build 4 selected, not build 3 | Required |
| SR-86 | On updates, "What's New" describes the change concretely (2.3.12) | Conditional (update) |
| SR-87 | First purchase product / subscription added with this version from the "In-App Purchases and Subscriptions" section (T-06) — monetization | Conditional (purchases) |
| SR-88 | App Review Information: name, phone, email; a working demo account if there are accounts; a step-by-step note for special setup, hardware or hidden flows (2.1) | Required |
| SR-89 | Version release option (manual / automatic after approval / scheduled) chosen deliberately | Optional |
| SR-90 | If the Accessibility Nutrition Label is filled in, every declared feature really works — layout-a11y. Check the current page for whether it is mandatory | Conditional |

## Build

| ID | Item | Grade |
|---|---|---|
| SR-91 | Build is not "Missing Compliance": encryption question answered (or declared in Info.plist) | Required |
| SR-92 | Build compiled to Apple's current minimum Xcode / SDK requirement (developer.apple.com/news/upcoming-requirements) | Required |
| SR-93 | Version number matches the ASC version; build number greater than previous ones | Required |
| SR-94 | No ITMS warnings in the post-upload email (privacy manifest, usage description, SDK signature) | Required |

## Review note draft (SR-P3)

Write from this app's REAL flow, no boilerplate:

1. Is sign-in needed? If so, a demo account (provided by the user; Claude does
   not ask for passwords, the user types them into the field).
2. What the reviewer should do on first launch (setup steps, how many taps).
3. How to reach the main features (menu path).
4. Purchases: product name, where it is, where "Restore" is; sandbox note.
5. Hidden or conditional features (location, hardware, a certain time):
   how to trigger them.
6. Where data is stored (device only / server), matching the privacy label.

Keep it short; write it in English (the review team reads English).
