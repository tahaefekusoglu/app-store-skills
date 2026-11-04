# apptest: shared rules

Version: 1.8.0 (2026-11-03; 1.4: portability · 1.5: live app audit · 1.6: honest status, §10 · 1.7: templates are proven by running them · 1.8: English sources, user-language output). All members of the family follow this file;
each member states the lowest version it is compatible with in its SKILL.md ("≥ 1.2").
When this file changes the version goes up: additions / clarifications only → MINOR
version (1.2 → 1.3, members stay compatible); a change that alters or removes a rule
→ MAJOR version (2.0), and all members are reviewed.

**Language.** Skills and scripts are written in English. Claude always talks to the
user and writes reports in the user's own language. Scanners still detect app text
in the languages listed in `shared/terms.py`.

Contents: §1 Principles · §2 Severities · §3 Stages · §4 Profile ·
§5 Step 0 (safety and conflicts) · §6 Long jobs · §7 Environment and cleanup ·
§8 Report · §9 Suppressed items · §10 Member writing rules

---

## §1 Principles

0. **Precedence.** The user's current word > the project's own instructions
   (CLAUDE.md, AGENTS.md, CONTRIBUTING etc.) > this file > group principles
   (`shared/test-methods.md`) > member-specific principles. A lower layer can only
   TIGHTEN an upper one, never loosen it; on conflict the upper one wins.
1. **Universal.** Every kind of app on the Apple App Store (iPhone first;
   iPad, Mac, Watch, TV, Vision targets through the profile): games, tools, social,
   offline, server-backed, kids, health, subscription, AI; every technology
   (SwiftUI/UIKit, Flutter, React Native, KMP, MAUI, web wrapper, game engine).
   Knowledge from a particular project becomes an EXAMPLE, not a rule.
2. **Stays out of design and code.** Items are written as OUTCOMES ("at the largest
   text size text is not cut off"), not METHODS ("use this class"). Architecture,
   libraries, design language, colour, typeface and layout belong to the app. Something
   becomes a finding only if (a) it breaks an Apple rule or (b) it is a bug that
   concretely affects the user. A fix may be suggested, but as "one way", with several
   options, as not mandatory.
3. **Never pushes.** When Claude sees a member would help it suggests it in ONE LINE
   ("If you like, I can run a store-readiness scan before release."); it starts no long
   audit unless the user asks and does not repeat the suggestion in the same turn. No
   member blocks a commit, build, test or submission. Every member works on its own;
   running the family head or the full tour is not required.
4. **Three stages.** Every member has a Setup · Test · Release section (§3).
5. **Opens by profile.** The app profile comes first (§4); an unrelated item is passed
   in one line as "not applicable".
6. **Speaks with evidence.** Each finding has: file:line, test output, a screenshot or
   an Apple rule number. What cannot be verified is marked "not verified"; a guess is
   never written as if certain.
7. **Checks Apple every time.** Apple's rules change often and without notice. For
   EVERY job based on an App Store rule (assessing an item as a REJECTION RISK, the
   Release stage, a Setup decision, the user asking "does this comply") a member reads
   Apple's official page before starting. Whatever the date, it is never skipped on the
   grounds that "the list is recent":
   1. Read the "Last Updated" date at the end of the rules page and compare it with the
      date in `shared/rejections.md`.
   2. Read the CURRENT text of the relevant rule; quote or link the official text in the
      finding, not the list's summary.
   3. If the date changed or the text does not match the list, say so in the report under
      the heading "Rules changed" and suggest updating `rejections.md` to the user
      (principle 3: without pushing).
   Without a network, or if the page cannot be read, the very top of the report says:
   "Apple's current rules could not be read; assessment is based on the list dated <date>;
   verify before submitting." Rule text is not copied into the skill; `rejections.md` is
   only an index.
8. **Works safely.** Does not touch the user's real data, device or own simulator; does
   not collide with other agents (§5); writes files to the project only with permission;
   cleans up temporary files.
9. **Without an environment it falls back, never fakes.** If a simulator, Xcode, network
   or test infrastructure is missing, or the project cannot support a test, it says so and
   falls back to a manual checklist. Never writes a fake "passed".
10. **Starts cheap.** A quick tour by default. Detailed reference files (`references/`)
    are read only when needed.
11. **Does not loosen a test to pass it.** An expectation is updated only if behaviour
    really (and deliberately) changed, and it says so; otherwise the bug is looked for in
    the code. The result is verified from output: the "all passed" line and the exit code.
    The exit code is lost behind a pipe such as `| tail`; use `set -o pipefail` or write
    output to a file and search it.
12. **Leaves the environment as found** (§7).
13. **Long jobs are announced and can be split** (§6).
14. **Repeatable.** Randomness is seeded; clock, language, region and time zone are fixed;
    device and OS version are written in the report.
15. **Infrastructure errors ≠ app errors.** Environment problems such as a build lock, a
    simulator that will not boot or a network timeout are retried once; if they happen
    again they go in the report under "Environment" and do not count as findings.
16. **No outward-facing steps.** Uploading to App Store Connect, sending to TestFlight or
    review, push, opening/merging a PR, email: only with the user's explicit approval THAT
    TIME. Members only prepare these and show the exact command. Passwords, credentials and
    bank details are never requested.
17. **Reports are safe and readable.** No secrets, keys, tokens or real user data in a
    report. The report is in the user's language. Images are shrunk (≈700 px) before being
    taken into context; from many images, a sample is taken.

## §2 Severities

| Severity | When | In the report |
|---|---|---|
| **REJECTION RISK** | Based on an App Store rule (the number is written) | at the top |
| **USER BUG** | Data loss, crash, wrong result, unreachable element, security hole | second |
| **SUGGESTION** | Optional improvement | short list |
| **INFO** | Not a finding: inventory, reminder, "verify this by hand" | at the bottom; not in the summary count |

If a finding fits two severities the higher one is written. If the same finding comes
from two members it is written once in the report, under the rule member's name.

## §3 Stages

- **Setup**: when a new project or feature starts. "Good to know from the start":
  decisions that get expensive later and why. Does not impose how to solve them
  (principle 2).
- **Test**: during development. What to verify and how; with the project's own test tool
  if it has one, otherwise a manual scenario.
- **Release**: before submitting. Code and settings scan + checklist; report.

If a stage is meaningless for a member, its section says "Nothing to do at this stage."

## §4 Profile

Every member reads the profile when it starts:

```sh
python3 -I ~/.claude/skills/apptest/shared/profile.py <project_root>          # markdown
python3 -I ~/.claude/skills/apptest/shared/profile.py <project_root> --json   # for machines
```

The script only reads and never writes to the project. To run all members' static scans
at once, in one report (the same place from two members appears once):

```sh
python3 -I ~/.claude/skills/apptest/shared/run_all.py <project_root> [--only SR,PP] [--json] [--check-links] [--policy-url URL]
```

This is a STATIC scan only; it does not replace principle 7 (Apple's current page),
simulator tours and manual lists.

Members that need a simulator use the shared session tool (§5.2–5.4, §7:
temporary simulator, lock, ledger, undo):

```sh
U=$(python3 -I ~/.claude/skills/apptest/shared/sim_session.py create --project <root> [--status-bar] [--software-keyboard])
python3 -I ~/.claude/skills/apptest/shared/sim_session.py cleanup --project <root> --udid "$U"
```

It reports findings at three confidences: **certain** (explicit in configuration),
**hint** (dependency or code search), **unknown** (cannot be derived from code: Kids
category, regulated domains, target market and so on). "Unknown" items are asked of the
user in a single question, only if the relevant member really needs them.

The profile is NOT WRITTEN to the project. If the user asks, it is kept as
`.apptest/profile.md` (§9).

## §5 Step 0: safety and conflicts

Before doing anything more than reading files, each member:

1. **Working tree.** If it is a git repo, `git status`. Do not pile work on a dirty tree.
   Jobs needing tests or builds are done NOT in the main folder but in a separate worktree
   or plain copy: another agent (another session, Codex etc.) may be working in the main
   folder at the same time.
   - **What are we testing?** A worktree comes from the last commit; uncommitted changes
     are NOT IN IT. If the user wants "the current state" or the tree is dirty, ask:
     (a) last commit, (b) current state. For (b), move the changes without touching the
     main tree:
     `git -C <main> diff HEAD --binary > <temp>/wip.patch` →
     `git apply` in the worktree + copy untracked new files.
     The report says which was tested ("HEAD <short-sha>" or
     "HEAD + uncommitted changes").
   - **Reuse:** ONE worktree per project:
     `~/.cache/apptest/<project-key>/wt`. Each tour brings it to the wanted state
     (`git checkout --detach <sha>` + `git clean -fd` ONLY in this worktree; not `-x`:
     ignored dependencies and build caches are kept). Deleted if the user asks or disk is
     low (`git worktree remove`).
   - Without git, a plain copy; touched files are noted and restored when done.
2. **Lock.** Before heavy work (build, simulator tour, long test) a lock is written to the
   PERSISTENT state folder (NOT the session's temp folder: other sessions cannot see it):
   `~/.cache/apptest/<project-key>/lock`. Project key = short digest of the project root
   path (symlinks resolved). The lock is taken ATOMICALLY and carries an expiry; it is not
   tied to a PID: the shell that started the command closes right away while the session
   continues. With a live lock a second job does not start and the user is told; an expired
   one is taken over. Cleanup deletes only its own session (`--udid`); a failed step says
   "Cleanup failed" and keeps the record; no new session opens over an uncleaned old one.
   Simulators are temporary per session and not shared with other sessions. One heavy job
   per project.
3. **Process management.** Every process sent to the background is tracked with a PID file
   and stopped by PID. `pkill -f <pattern>` / `killall` are NOT used: the pattern also matches
   the member's own shell command line and cuts the job in half.
4. **Device and data.** The user's own simulator / device is not used; a tour opens its own
   temporary simulator (`xcrun simctl create`) or uses a separate simulator the user
   explicitly points to. App data is in memory or a temporary container; real user data is
   not used.
5. **Writing to the project.** Only if the user asks. A temporary verification test, if
   needed, is written in the worktree, run and deleted.
6. **Free space.** Before build / simulator / image work, check free disk (`df -h`); under
   10 GB, tell the user.

## §6 Long jobs

- Give a **time estimate** before starting. If it will exceed a few minutes, ask the user in
  one line (with a quick tour option).
- Long jobs run **in the background**; output goes to a file; wait for the completion
  notification rather than polling. If the user asks, give a short status.
- Every command has a **timeout**. If a wrapper buffers output to the end (e.g. shell tools
  that compress output) and there is silence for 60 s, stop it and rerun without the wrapper.
- Jobs are **sectioned**: after each section
  `~/.cache/apptest/<project-key>/progress.json` is updated (persistent folder: found even
  if the session changes). If interrupted, the next call resumes from there.
- An unfinished job is written in the report as "partial (N/M sections)".
- **Against silent hangs:** actions that open external apps during a test tour (Safari, share
  sheet, Settings, store) are mocked; if one opens, the tour times out and says
  "hung: <action>". The hardware keyboard is turned off on the simulator (otherwise the
  on-screen keyboard does not appear and keyboard tests mislead), and needed permissions are
  granted in advance (`xcrun simctl privacy`).

## §7 Environment and cleanup

If a tour changed the environment it reverts it at the end and lists it in the report:

| Change | How to revert |
|---|---|
| Status bar (`simctl status_bar override`) | `simctl status_bar <id> clear` (while the device is ON) |
| Language / region / appearance / permission | back to the old value |
| Simulator opened / created | shut down; if the tour created it, `simctl delete` |
| Global setting of the Simulator app (e.g. hardware keyboard: `defaults write com.apple.iphonesimulator ConnectHardwareKeyboard`) | read and save the old value BEFORE the job, then return to it |
| Background processes | stop by PID |
| Worktree, temp folder, lock | delete (`git worktree remove`, `prune`) |
| Outputs delivered to the user | NOT DELETED; location in the report |

Every change is written, the moment it is made, to the ledger
`~/.cache/apptest/<project-key>/state.json` (what, old value, how to revert); it is removed
once reverted. What could not be cleaned goes in the report under "Cleanup failed". The next
call reads this ledger first and cleans what a previous half-finished tour left behind (lock /
simulator / setting), telling the user.

Pinned during a tour for repeatability: time zone (`TZ=`), language and region, random seed,
app clock (if the project has a way). Clock- or date-dependent behaviour is also tried in at
least one zone with daylight saving (e.g. Europe/Berlin, America/Los_Angeles); in a zone without
it, day shifts are NOT VISIBLE.

## §8 Report

Template in `shared/report.md`. Required sections: Summary (one paragraph) ·
Profile (one line) · Findings (REJECTION RISK → USER BUG) · Suggestions ·
Not applicable items (one line) · Environment (device, OS, language, time zone,
seed, duration) · Environment problems · Cleanup failed.

Each finding: title · severity · evidence (file:line / output / image / rule) · effect on the
user · one or several ways to fix (not imposed) · verified or not.

Official sources (for freshness):
- https://developer.apple.com/app-store/review/guidelines/
- https://developer.apple.com/distribute/app-review/
- https://developer.apple.com/design/human-interface-guidelines/
- https://developer.apple.com/documentation/bundleresources/privacy-manifest-files
- https://developer.apple.com/help/app-store-connect/
- https://developer.apple.com/news/ (new requirements, minimum SDK, SDK list)

## §9 Suppressed items

The user may suppress an item as "I don't want this in this app". The decision is written, only
if the user asks, to the "Suppressed" list in `<project>/.apptest/profile.md` (item id + short
reason + date). Format (scripts read this, `scanlib.load_suppressed`):

```markdown
## Suppressed
- SR-25 — background mode is on deliberately (2026-10-28)
- LT-* — the app stays single-language (2026-10-28)
```

The id is a single item (`SR-25`) or a member prefix (`LT-*`). A suppressed item appears in the
report only in the "Suppressed: id ×count" line. If an item of REJECTION RISK severity is
suppressed, this line also says "(rejection risk)"; the warning is given once, without insisting.

## §10 Member writing rules

- Name `apptest-<topic>`; frontmatter has only fields Claude Code recognizes: `name`, `description`,
  `allowed-tools`, version under `metadata.version`. Unknown fields are silently ignored (there is
  no `triggers` field). Source: code.claude.com/docs/en/skills.
- `description` at most ~250 characters, key use first, in words a user would say: selection looks
  only at this text; all skills share a 1% context budget, and past it descriptions get dropped. No
  broad triggers like "on every code change" (principle 3); rules and contracts like "gives a report"
  stay in the body.
- Body order: When · Out of scope · Step 0 (reference to this file) ·
  Profile · Setup · Test · Release · Report.
- Each item has an id (`<member-code>-<no>`, e.g. `LA-07`); §9 and the report work with this id.
- If an item rests on an Apple rule, the number is written; if not, the effect on the user is
  written. With neither, the item is a SUGGESTION.
- A SKILL.md stays under 400 lines; details in `references/`; scripts under `scripts/`, standard
  Python only (`python3 -I`), never writing to the project.
- **Portability (every computer):** scripts are written for Python 3.9+ with the standard library
  only; static scans run on macOS, Linux and Windows (simulator steps are macOS-only by nature).
  Rules: `from __future__ import annotations`; no runtime `list[str]` / `X | None` / `removeprefix`
  / `match`; file paths compare with "/" (`p.rel` and `p.files` ensure this); every text file opens
  with `encoding="utf-8"`; stdout is converted to UTF-8 (automatic when importing `scanlib`; the same
  lines in a standalone script); subprocesses with `-X utf8` and `encoding="utf-8"`.
  A new script is tried on 3.9 and 3.12 (`-W error`).
- Template code that scripts provide (Swift, Dart, TS, C#) is compiled or analyzed before delivery
  (Swift: `swiftc -typecheck`, Swift 5 and 6 modes; Dart: `flutter analyze`); project-specific
  placeholders in a template are marked clearly.
- A template that compiles does not mean it works: when an XCUITest template changes, run
  `shared/proof/run.sh`; it must pass on the clean app and FAIL on the deliberately buggy build (e.g. an
  `isHittable` query compiled but crashed at run time). After a new scan rule, diff against the previous
  report; you will see your own regression there. When a script changes, `shared/selftest.py`; when a
  shared tool changes (lock, cleanup, merge, scan limit), `shared/regressions.py`. When a false alarm is
  fixed, add a test there that produces the real situation, then undo the fix in a copy and see the test
  FAIL: a test that passes first time may not be producing the bug.
- **Honest status: clean / not applicable / could not check / error are four separate results.** If a
  member did not run, "0 findings" does not count as clean. Not applicable: a network member in a
  no-network project, iOS members in a project that is not an iOS app or whose iOS project has not been
  added yet (unfinished); it says why in one sentence and produces no findings. Could not check: without
  internet a link is NOT called broken, it says "no internet" (`scanlib.online`). Error: wrong use such as
  a missing folder or an empty comparison gives exit 2 and never says "passed". A corrupt input file
  (plist, JSON) is not skipped silently. If a package exists but its code is not wired up, say "not wired
  up yet", not rejection risk. A new member is tried with all these states: empty folder, missing folder,
  non-iOS project, corrupt file, no internet.
- When reading test results the "all passed" line is not enough; read the skipped count too (`+12 ~28` =
  28 tests skipped).
- **Live app audit:** every member is also tried on apps that are live on the App Store with open source
  code. A REJECTION RISK on a live app is first suspected as a false alarm: open the evidence line; if the
  cause is a pattern, namespace, test / CI / server folder, generated file, ready-made SDK, unused
  translation key or Apple's system picker, filter it out in the script. If real, keep the severity with
  Apple's current text and note the live example (e.g. the 2026-11-03 tour across 14 projects filtered
  false alarms: REJECTION RISK 41 → 26, USER BUG 174 → 83).
- Scripts use the shared helpers: `shared/scanlib.py` (profile, code files excluding generated / test /
  tool folders, search that skips comment lines, report) and `shared/profile.py`'s
  `shipping_info_plists` / `primary_icon_names` / `release_settings` functions (the shipping Info.plist
  and main icon). The module is loaded by file path (`importlib`): the name "profile" collides with
  Python's standard module.
- Every script is tried on REAL projects (at least: one SwiftUI, one UIKit / ObjC, one Flutter or RN,
  one other technology); every candidate found is verified by opening the code, and that kind of false
  alarm is filtered in the script (e.g. "todo" inside "Mastodon", "dev" inside "developer.apple.com",
  a fixed scale used for measurement).
- Lessons from real projects are given as examples ("e.g. ..."); the rule itself is written generally.
- **Member-specific principles:** every SKILL.md has a "Principles specific to this member" section right
  after "Step 0" (3–8 items, `<CODE>-P1` ...). They concern only that member's own risk or quality; they
  do not repeat or loosen family and group principles (principle 0). Test method members also follow
  `shared/test-methods.md`.
