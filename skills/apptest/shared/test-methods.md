# apptest: group principles for test method members

Version: 1.0.0 (2026-10-28). Applies to: crawl, state-sim, time-travel,
upgrade, device-tour, persona, rapid-input, lifecycle, visual,
network-chaos, test-health. Added ON TOP of `CONVENTIONS.md`; cannot loosen it
(principle 0).

T1. **Runs in a sandbox.** A test drives the app only in a disposable environment:
    in-memory or temporary database, temporary simulator, fake or staging server.
    Real user data, real accounts, production servers NEVER.

T2. **Destructive and outward-facing actions are mocked.** Real purchases, account
    deletion, sending email/SMS/notifications, sharing, payment, writing to a server,
    opening an external app, writing to contacts/calendar: in a test tour these are
    either mocked (stub/mock) or done in a sandbox. If they cannot be mocked the
    element is not touched and the report says "not touched: <reason>".

T3. **Adds no hooks to app code without saying so.** Hooks a test needs (clock
    override, fake network, test ids) are first looked for in existing code. If
    absent, either (a) solve it in test code alone or (b) suggest the smallest change
    to the user; never write to app code without approval (principles 2, 8).

T4. **Does not touch the Mac itself.** The system clock, time zone, language and
    network settings are NOT CHANGED on the Mac; only inside the test process (TZ=,
    app clock, simulator setting) and reverted.

T5. **Failures come reproducible.** For each failure: seed, step sequence (shortened
    as far as possible), clock, device, language and a one-command way to rerun.
    "It happens sometimes" is not a finding; a result that cannot be repeated is
    reported separately as "flaky".

T6. **Waits for conditions, not for time.** Instead of a fixed `sleep`: "until this
    element appears / this state holds, at most N s". A timeout is classified as an
    infrastructure error or an app error (principle 15).

T7. **Runs on a budget.** Each tour starts with a step / time / tap budget; when it
    runs out it stops and reports the partial result (principle 13). Quick tour by
    default; full tour on request.

T8. **Suggests leaving what it found as a test.** For a bug found, it suggests a small
    regression test in the project's own test tool; writing it needs the user's approval.

T9. **Does not delete, loosen or skip tests.** Disabling an existing test, weakening
    its expectation or adding `skip` happens only with a stated reason and the user's
    approval (principle 11).

T10. **Picks the method by technology, or falls back.** For UIs that expose an
     accessibility tree (UIKit/SwiftUI, Flutter semantics, RN
     testID/accessibilityLabel), go through the tree; for those that do not (game
     engine, canvas, some web wrappers), screenshots + coordinates or the engine's own
     test tool; failing that, a manual scenario list (principle 9).
