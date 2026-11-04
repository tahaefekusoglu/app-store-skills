# App Store rejection list

Last checked: **2026-10-28** · Apple's rules page "Last Updated: October
16, 2026". Sources: https://developer.apple.com/app-store/review/guidelines/
and https://developer.apple.com/distribute/app-review/ ("Avoiding common
issues").

**Freshness rule (CONVENTIONS principle 7), on EVERY use:** this file is only an
INDEX, not a source. For any job based on a rule, first read the official page:
compare its closing "Last Updated" date with the one above and read the current text
of the relevant rule. However recent the date is, this step is not skipped. If there
is a difference, say so in the report under the heading "Rules changed" and suggest
updating this file (number, title, condition, date). Without a network, the top of
the report says "Apple's current rules could not be read; assessment is based on the
list dated 2026-10-28".

Update checklist (when refreshing this file):
- Rules page: numbers and titles (new / removed / moved)
- "Avoiding common issues" page: new common problems
- Developer news (developer.apple.com/news): new requirements, minimum SDK date,
  privacy manifest / SDK list changes
- App Store Connect help: screenshot sizes, age rating questionnaire, privacy label
  questions

Apple's own data: **more than 40%** of unresolved issues are **2.1 (App
Completeness)**. 50% of reviews finish within 24 hours, 90% within 48.

Columns: **ID** (used in reports) · **Rule** · **What it catches** ·
**Profile** (when it applies; "always" = every app) · **Member**.

## 1. Completeness and performance (most common)

| ID | Rule | What it catches | Profile | Member |
|---|---|---|---|---|
| R-01 | 2.1 | Crash, freeze, failure to open on the review device; not tried on the latest iOS | always | test-strategy, device-tour, store-readiness |
| R-02 | 2.1 | Placeholder text/images ("Lorem", "TODO", "Coming soon", empty screen) | always | store-readiness, copy-audit |
| R-03 | 2.1 / 5.1 | Broken links; support link without current contact info; no privacy policy link | always | store-readiness, privacy-permissions |
| R-04 | 2.1 | Missing review info: demo account, special setup steps, required hardware or video | account / special setup / hardware | store-readiness |
| R-05 | 2.1(b) | Purchase product does not load for the reviewer, product not submitted, empty purchase screen | purchases | monetization |
| R-06 | 2.2 | Beta / demo / trial version submitted to the App Store (the word "beta") | always | store-readiness |
| R-07 | 2.3.1 | Hidden, undocumented or remotely enabled features | network | network, product-fit |
| R-08 | 2.3 / 2.3.3 / 2.3.4 | Screenshots or previews do not show the app accurately; splash or sign-in screen only | always | store-assets |
| R-09 | 2.3 / 2.3.2 | Description, subtitle or keywords promise features not in the app; paid features not indicated | always | product-fit, copy-audit |
| R-10 | 2.3.7 / 2.3.8 | Other brands, prices or irrelevant terms in the name or keywords; icon and name unsuitable for the age rating | always | store-readiness |
| R-11 | 2.3.6 | Age rating questionnaire answered incorrectly | always | content-safety |
| R-12 | 2.3.12 | "What's New" text is vague or does not describe the change | update | store-readiness |
| R-13 | 2.4.1 | Broken or unusable on iPad (iPhone apps also run on iPad) | always | layout-a11y |
| R-14 | 2.4.5 / 2.5.x | iPhone apps publish on Mac (Apple silicon) and Vision Pro automatically; if broken there, turn it off | always | store-readiness, layout-a11y |
| R-15 | 2.5.1 | Private APIs, public APIs used for an unintended purpose | native code | store-readiness |
| R-16 | 2.5.2 | Changing app behaviour with downloaded code | network | network |
| R-17 | 2.5.4 | Unjustified background modes (location, audio, VoIP) | background | privacy-permissions |
| R-18 | 2.5.9 | Altering system buttons, volume keys or system behaviour | always | layout-a11y |
| R-19 | 2.5.14 | Recording, camera or microphone use without explicit consent and a visible indicator | camera / microphone / screen recording | privacy-permissions |

## 2. Business model

| ID | Rule | What it catches | Profile | Member |
|---|---|---|---|---|
| R-20 | 3.1.1 | Digital content / feature unlocks sold other than through in-app purchase (regional exceptions: read the official text) | purchases | monetization |
| R-21 | 3.1.1 | No "Restore" for purchases | purchases (permanent / subscription) | monetization |
| R-22 | 3.1.1 | Codes, QR, crypto or external keys that unlock things | purchases | monetization |
| R-23 | 3.1.2 / 3.1.2(c) | Subscription name, length, price, unit price, auto-renewal, terms of use (EULA) and privacy links missing on the purchase screen and in metadata | subscription | monetization |
| R-24 | 3.1.2(a) | Subscription gives no ongoing value; one-off content sold as a subscription | subscription | monetization |
| R-25 | 3.1.3 | Physical goods/services sold through in-app purchase (the reverse case) | payment | monetization |
| R-26 | 3.2.2 / 5.6.1 | Rewarding or forcing users to rate, download or take other actions; review prompt outside Apple's own API (custom review dialog) | always | monetization, product-fit |
| R-27 | 3.1.5 | Crypto mining, unauthorized exchange/ICO | crypto | product-fit |

## 3. Design

| ID | Rule | What it catches | Profile | Member |
|---|---|---|---|---|
| R-28 | 4.1 | Copy of another app or an Apple product, similar icon/name | always | product-fit |
| R-29 | 4.2 | Minimal functionality, repackaged website, no lasting value (the "low quality" emphasis hardened in 2026) | always; especially web wrappers | product-fit |
| R-30 | 4.2.3 | Requiring another app to be installed in order to work | always | product-fit |
| R-31 | 4.3 | Spam: copies of the same app, the same as a common one | always | product-fit |
| R-32 | 4.4 | Extension breaks its own rules (widget, keyboard, Safari, notification) | extension | store-readiness |
| R-33 | 4.5.x | Abuse of Apple services (Push, Game Center, Apple Music); push for ads | remote notifications | privacy-permissions |
| R-34 | 4.7 | Mini app, chatbot, streaming game, plug-in rules | AI / mini app | content-safety, product-fit |
| R-35 | 4.8 | Third-party sign-in (Google, Facebook, X ...) but no equivalent option meeting the privacy conditions (name + email only, hide email, no ad tracking; Sign in with Apple meets them). Exceptions (own account system only, education / enterprise accounts, client of a specific third-party service, government services needing authentication, etc.): read the official text | third-party sign-in | network |
| R-36 | 4.0 / HIG | Bad UI, unreadable text, imitation of system elements | always | layout-a11y |

## 4. Legal and privacy

| ID | Rule | What it catches | Profile | Member |
|---|---|---|---|---|
| R-37 | 5.1.1(i) | No privacy policy, or it does not describe collected data, its use, third parties, retention and deletion | always | privacy-permissions |
| R-38 | 5.1.1(ii) | Permission explanation (purpose string) vague or missing; permission unnecessary or requested at launch | permissions | privacy-permissions |
| R-39 | 5.1.1(iii) | Asking for more data than needed; data not required for a feature is mandatory | always | privacy-permissions |
| R-40 | 5.1.1(v) | Sign-in required when the feature needs no account; an account can be created but not deleted from inside the app | account | network |
| R-41 | 5.1.2(i) | Personal data shared with third parties, INCLUDING third-party AI, without clear disclosure and explicit consent | network / AI / analytics | privacy-permissions |
| R-42 | 5.1.2 / ATT | No App Tracking Transparency consent before tracking; tracking despite denial | tracking / ads | privacy-permissions |
| R-43 | App Privacy | Privacy label in App Store Connect does not match real behaviour (SDKs included) | always | privacy-permissions |
| R-44 | ITMS-91053 / 91061 | Missing privacy manifest: no "required reason" API declaration; a listed third-party SDK has no manifest or signature (extensions included) | always | privacy-permissions, store-readiness |
| R-45 | ITMS-90683 | Missing Info.plist explanation for a used permission (an SDK may be using it) | always | privacy-permissions |
| R-46 | 5.1.3 | Health data used for ads/marketing or stored in iCloud | health | privacy-permissions |
| R-47 | 5.1.4 / 1.3 | Third-party ads/analytics in the Kids category, no parental gate | kids | content-safety |
| R-48 | 5.1.5 | Location, especially "always", without justification | location | privacy-permissions |
| R-49 | 5.2 | Copyright, trademark, unauthorized third-party content | always | product-fit |
| R-50 | 5.3 / 5.4 / 5.5 / 3 | Regulated service (gambling, VPN, MDM, banking, crypto, health, airline) submitted by someone other than the authorized legal entity, no license | regulated | product-fit |

## 5. Safety and content

| ID | Rule | What it catches | Profile | Member |
|---|---|---|---|---|
| R-51 | 1.1 | Objectionable content | always | content-safety |
| R-52 | 1.2 | User content without report, block, filtering and published contact info | user content / AI output | content-safety |
| R-53 | 1.4 | Physical harm: medical accuracy claims, dangerous activity | health | content-safety |
| R-54 | 1.5 | Developer contact info and support link do not work | always | store-readiness |
| R-55 | 1.6 | User data security (unencrypted transmission, unjustified ATS exception) | network | network |

## 6. Technical submission (automatic rejection or warning email)

| ID | Topic | What it catches | Member |
|---|---|---|---|
| T-01 | Minimum SDK | Apple raises the minimum Xcode / iOS SDK version every year (usually April); read the current announcement | store-readiness |
| T-02 | Icon | Alpha channel or wrong size (rejection / upload error). Dark and tinted variants are optional: if missing, SUGGESTION only | store-readiness |
| T-03 | Screenshot | Outside accepted sizes, has an alpha channel | store-assets |
| T-04 | Encryption | No `ITSAppUsesNonExemptEncryption` declaration → question on every build | store-readiness |
| T-05 | Version / build | Same build number, version does not match the ASC version | store-readiness |
| T-06 | Purchases | First purchase product not submitted with the version; review screenshot or note missing | monetization |
| T-07 | Name / language | Name, subtitle and languages in ASC do not match the app's real languages | store-readiness |
