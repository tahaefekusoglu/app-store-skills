# App Store Skills

Claude Code skills that test and check iPhone and iPad apps before App Store review.

They find the problems that cost time late in a release: rejection reasons, lost data after an update, broken large text, duplicate records from a double tap, wrong dates around daylight saving. The findings are candidates. Each skill explains how to confirm one.

## Scope

- **For:** iPhone and iPad apps sold on the App Store. SwiftUI, UIKit, Flutter, React Native / Expo, Kotlin Multiplatform, .NET MAUI, Capacitor / Cordova, Unity and Godot projects are recognized.
- **Not for:** Mac-only apps (scans say "Not applicable") and Google Play.
- **Not a guarantee:** a clean scan does not mean Apple will approve the app. The final decision is Apple's.

## Install

```sh
git clone <this repo>
cd app-store-skills
python3 tools/install.py
```

Needs Python 3.8 or newer, with no other packages. Simulator tours also need macOS and Xcode.

## Use

Ask in your own words, or use the short commands:

```
/app t quick        static scan of the current project
/app k privacy      permissions and privacy manifest
/app t double       double taps and duplicate records
/app d audit        compare the design with Apple's guidelines
/app t release      the full pre-submission tour
```

`/app` alone lists every command.

| Group | Skills |
|---|---|
| **k**: rules and code | store readiness, privacy and permissions, monetization, network and accounts, content safety, product fit, store assets, layout and accessibility, locale and time, data integrity, input and actions, copy |
| **t**: run the app | crawl, state simulation, time travel, upgrade, device tour, personas, rapid input, lifecycle, visual, network chaos, test health, test strategy |
| **d**: design | design audit, design advisor |

## How it behaves

- **Reports, does not change your code**, unless you ask.
- **Leaves your things alone.** Tours use a temporary simulator and delete it afterwards. They never use your own simulator or real user data, and never write to production servers.
- **Reads Apple's rules every time.** Apple changes them often, so the rule pages are read live.
- **Apple's Human Interface Guidelines are advice.** The design skills report differences as suggestions; a deliberate design is not an error, and your decision wins. App Store rejection rules are the exception.
- **Honest results.** "Clean", "not applicable", "could not check" and "error" are different results. Scans say when they read only part of a file.

## Your language

The skills are written in English, and Claude replies and writes reports in the language you use. App text is checked in English, Turkish, German, Italian, Spanish, French and Portuguese (`skills/apptest/shared/terms.py`); add a language there.

## How it was tested

- Scans were run read-only on about 50 open-source apps, and false alarms found there became regression tests.
- `skills/apptest/shared/selftest.py` is set up to run in CI on macOS, Linux and Windows; `regressions.py` on macOS and Linux.
- `skills/apptest/shared/proof/` builds a small SwiftUI app with deliberate defects and checks that the XCUITest templates pass on the clean version and fail on the broken ones.

Known limits:

- Scans search code and text patterns and do not understand your app, so false alarms and misses remain.
- Dart, TypeScript, Detox and Maestro templates are not exercised by the proof app.
- The fault-injection proxy has been tried only with that proof app.

## License

MIT. See [LICENSE](LICENSE).
