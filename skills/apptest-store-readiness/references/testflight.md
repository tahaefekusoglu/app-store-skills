# TestFlight — internal and external

Current details: https://developer.apple.com/testflight/ and App Store
Connect help (principle 7: limits can change, check before relying on them).

| | Internal | External |
|---|---|---|
| Who | People on the App Store Connect team (with a role) | Anyone with an email address, or a public link |
| Maximum | 100 | 10,000 |
| Apple review | None; installable once the build is processed | The FIRST build of each version goes through Beta App Review; later ones usually without waiting |
| Needed | Adding the person to the team | "Test Information" (description, feedback email, privacy URL, review contact) + "What to Test" |
| Build lifetime | 90 days | 90 days |

## Common snags (SR-95 …)

| ID | Symptom | Cause / way out |
|---|---|---|
| SR-95 | "This beta isn't accepting any new testers right now" | Build still **Waiting for Review** (first external build): wait; or no build added to the group; or the public link's tester limit is full; or the link is off. E.g. seen in a budgeting app while its first external build waited ~12+ hours |
| SR-96 | Test Information won't save: "couldn't be saved because another field is invalid" | A field NOT named in the error is the broken one, most often the phone number (with country code and no leading 0: `+44 7XXX XXX XXX`) |
| SR-97 | "Sign-in required" ticked but the app has no sign-in | Untick it; while ticked, Apple expects a username and password |
| SR-98 | Build "Missing Compliance" | The encryption question; the lasting fix is Info.plist `ITSAppUsesNonExemptEncryption` (SR-20) |
| SR-99 | Purchase says "product not found" in TestFlight | Product is not "Ready to Submit" in ASC or agreements are not active; TestFlight uses sandbox, no real money is charged — monetization |
| SR-100 | First external build passed 48 hours | Do not withdraw and resubmit (the queue resets); ask via ASC › Contact Us › App Review |

## Suggested flow

- Development team trial: internal only (no review wait).
- Outside testers: external group + public link + a **tester limit**
  (in case the link spreads). Test Information and What to Test are written
  for this app (SR-P3).
- External beta review does not replace the main App Store review; neither
  waits for the other.
