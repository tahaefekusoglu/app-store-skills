# persona — behaviour catalogue, goal and measurement

A persona is not a HUMAN TYPE but a **bundle of behaviours** (PE-P1). Each dimension
exposes a separate class of bugs in the app; the persona's name is a short form of its
dimensions: "returning · largest text · smallest screen · de".

## Dimensions

| Dimension | Levels | What it catches | How to set up |
|---|---|---|---|
| experience | first launch · returning | empty state text, forced setup, list slowing with months of data, old period screens | in-memory / temporary data: empty or seeded rich data; past-dated records via the clock hook |
| pace | careful · hurried | hurried: result of accepting defaults, half-finished form, loss of unsaved changes | agent probabilities: hurried taps the first visible primary button, 15% back / cancel, does not read text |
| reading | normal text · largest accessibility text · VoiceOver | truncated / overlapping text, button pushed off screen; unlabelled element, wrong reading order | text scale (test framework or `-UIPreferredContentSizeCategoryName`); the VoiceOver persona sees ONLY elements with a label |
| screen | smallest supported · largest | overflow, field covered by the keyboard, one-handed reach | surface size or temporary simulator model |
| language | development language · long-text language · (if any) right-to-left | button truncated by a long translation, wrong-way arrow / scroll in reversed layout | app language setting or `-AppleLanguages (de) -AppleLocale de_DE` |
| account (if purchases) | free · paid · (subscription) expired | dead end at the lock screen, data vanishing after dropping from Pro, basic job unreachable on free | purchase fake / StoreKit test session (NO real purchase, T2) |
| session (if accounts) | signed out · signed in | job forced to sign in that could work without it, draft lost when the session drops | test account / faked identity; NO production account (T1) |
| network (if networking) | good · slow / dropping | endless loading, second submit, error text | delay / error in the app's network fake; the Mac's network is NOT TOUCHED (T4) |
| permission (if permissions / notifications) | denies · grants | dead end after denial, screen not directing to settings, job that should work without permission | `xcrun simctl privacy <UDID> revoke <service> <bundle>` or a permission fake |

**Plan rule (every level at least once, risky pairs together):**
`pe_plan.py` suggests four personas:

- **A:** first launch · careful · smallest screen · free · denies permission.
- **B:** returning · hurried · largest screen · paid · slow network.
- **C:** returning · **largest text + smallest screen** · long-text language.
- **D:** first launch · **VoiceOver** · (if any) right-to-left language · subscription expired.

The full product (2×2×3×2×3×…) means hundreds of tours and opens no new bug
class; it is enough for each level to appear once and for the two riskiest pairs to be
tried together. The user can remove or add a persona:
the plan is a suggestion.

Naming to avoid: age ("elderly", "young"), gender, occupation, income,
"not tech-savvy". Why: a 30-year-old uses large text too;
a stereotype hides the behaviour that should really be tried (text scale,
slow reading, VoiceOver) and hurts whoever reads the report.

## Goal

5–8 goals per persona: the app's MAIN jobs. Where they come from:
tab bar / main menu, primary action button, setup steps,
the first three promises of the store description, the promise of the paid feature.

Each goal has three parts:

1. **Name** — in the user's words: "add an expense", "find last month's total".
2. **Word sequence** — words the user will look for on screen IN ORDER,
   in the persona's language: `["add", "expense", "save"]`. NOT code names / ids:
   the user does not see ids. If the word is not on screen, that too is a finding
   (the user will not find it either).
3. **Success measure** — DATA or SCREEN state (PE-P3): "expense count
   went up", "cycle day is 15 in settings", "screen X is VISIBLE and tappable"
   (a screen sitting in a back tab does not count). "Save was tapped" is not a measure.

Goals drop out by persona: a first-launch persona has no past period, so the
"find last month" goal is not given to it; a free persona's paid goal is
measured as "reached the lock screen".

## Agent (each step)

```
budget: 40 steps per goal; a time limit per tour (T7)
1. goal done? → yes: record, return to the main screen (with real back, one at a time)
2. if there is an empty field for the goal to type in, type
3. take tappable elements from the accessibility tree (VoiceOver persona: labelled only)
4. score: next word +6, later word +2, in the last 3 taps −4
5. if no element carries a goal word and fewer than 3 scrolls on this screen: SCROLL DOWN (a real user
   scrolls too; with large text content moves below the screen. e.g. in a budgeting app's tour an agent without scrolling
   could not see the Tax card on the Buckets screen and took the goal as "not reached")
6. seeded die: 8% back (hurried 15%); if best score > 0, 82% best; otherwise random
7. tap → wait (condition, T6) → did the screen signature and data count change? if not, dead tap
```

Randomness is seeded; every persona runs with at least **2 seeds**. A finding
that does not appear in both seeds is written separately as "flaky" (T5).

## Measurement and finding ids

| Id | What | Severity |
|---|---|---|
| PE-20 | Goal not reached within budget (≥2 seeds). If there is a concrete cause (element unlabelled, off-screen, truncated, locked, no path after permission denial) | USER BUG |
| PE-20 | Same, but no concrete cause (just a long path) | SUGGESTION |
| PE-21 | Goal reached but step count more than 2× the shortest path (median of the two seeds) | SUGGESTION |
| PE-22 | Dead tap: an element that looks tappable changes nothing (≥2 seeds, same element) | SUGGESTION; USER BUG if the element promises an action |
| PE-23 | Loop: going back and forth between the same two or three screens ≥3 times | SUGGESTION |
| PE-24 | Dead end: no back / close, no way out without closing the app | USER BUG |
| PE-25 | Uncaught error / crash during the journey | USER BUG |

Measurement issues seen on the path (truncated text, target under 44 pt, unlabelled
button, contrast) are written under **layout-a11y**'s ids, with the note
"(on persona C's path)" (§2: the same finding once, under the rule
member's name). A permission dialog appearing without context →
privacy-permissions; a free persona unable to reach a basic job →
monetization.

## Agent error ≠ app error (PE-P6)

Rule these out first (from a budgeting app's tours):

- The agent says "nothing to tap" but the screen has a button → the accessibility
  tree is not on by itself on a device (Flutter: `ensureSemantics`).
- A record is rejected as "before the start of use" → the test clock differs from
  the real today and the app takes the date from elsewhere: a setup
  error. Set the clock from one place in persona setup.
- The tour hangs → an external link opened Safari; the tour does not start without an external link fake
  (`pe_plan.py` PE-10).
- Truncated text only in a widget test → the test font draws letters as squares,
  making text wider than it really is: verify on a simulator (PE-P5).
- The goal is on screen but not reached → is the agent scrolling? An agent without scrolling never sees an element
  below the screen with large text (e.g. in a budgeting app's ×2.0 / SE tour "how much was set aside for tax?" was not
  reached in 40 steps in both seeds; the cause was the agent not scrolling, not the app).
- The agent circles on the same button → the word list does not match the
  actual on-screen text (translation differs). Fix the word first; if the user would not look for that
  word either, it is not a finding.

## App language

The agent goes by on-screen labels: goal words (`Goal.words`) are written in the app's language for that run
(`["löschen"]` for a German persona, `["elimina"]` for Italian). A word in the wrong language produces "goal not reached",
which is not an app bug. Set the language with `-AppleLanguages`.
