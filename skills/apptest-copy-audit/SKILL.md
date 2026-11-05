---
name: apptest-copy-audit
description: "Copy audit: does the text match what the code does, then tone, clutter (shorten text), and meaning reversed between languages. Reports only, does not change code. Copy review, UX writing."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
metadata:
  version: "2.4.0"
---

# App Tests: Copy-Behaviour and Language Audit (Copy Audit)

This skill is the copy/language member of the **apptest** family. The family
head and shared rules: `../apptest/SKILL.md` and
`../apptest/shared/CONVENTIONS.md` (≥ 1.3 — priority, safety, report, suppressed
items). Siblings: store-readiness, layout-a11y, locale-time,
privacy-permissions, monetization, network, data-integrity … (current list in
the family head). Boundary: missing translations, broken format (date / number
/ plural / direction) → locale-time; the MEANING, tone and clutter of text →
this skill. Whether privacy / legal text describes what the app does → together
with privacy-permissions (that member covers the code ↔ policy gap, this skill
the text itself).

**v2 note:** v1 looked only at the TEXT ITSELF (politeness, consistency, logic),
which is an IMPORTANT but LESS CRITICAL layer. In a real audit (an independent
team scanning the same app), the vast majority of problems came from another
layer: **what the text claims does not match what the code actually does** —
even with flawless tone, it leads the user to the wrong action or a wrong
expectation. So Step 0 and Step 4-D are now this skill's **primary** job; the
tone scan (Step 4 A/B/C) is secondary but is not skipped.

**v2.2 note — Clutter layer (F):** On a real tour the user also asked, "is
something that two words can say written in five?" Text with flawless tone and
meaning can still be needlessly long: questions saying the same thing three
times in one sentence ("**Apart from** your spending money, do you have
**extra** money **set aside**…?"), one idea written at four different lengths,
VoiceOver hints longer than iOS's own language. Step 4-F reports this by
measuring (word count) with a before/after suggestion. Clutter ranks LOWER than
a meaning error; but it is not skipped when the user asks, and shortening must
never break the MEANING (see "Shortening safety" in F).

**Default contract:** Produce a report only. Do not write to or delete any file
— source code, translation files — unless the user explicitly says "fix it" /
"suggest a diff". Writing a temporary VERIFICATION file (a mini test) is
allowed, BUT following the safety rule in Step 0: outside the project or leaving
no trace.

## When it applies

When the user wants a "fresh eyes" review of an app's user-facing text: language
problems, confusion, rudeness, inconsistency — but the valuable part is
answering **is what the text says actually true** with "yes, I read the code /
tested it". Code review / bug hunting is NOT this skill's main purpose, but
Step 4-D requires exactly that — without the bridge between text and code, the
most valuable part of this skill does not work.

Also when the user says "is there needless clutter", "is something two words
can say written in five", "shorten the text": then Step 4-F (clutter) becomes
the main section of the report; D is still done briefly, because a shortening
suggestion must keep verified claims.

## Out of scope (on purpose, with narrow exceptions)

- Full translation fidelity (word-by-word equivalence from source to target) —
  heavy work, not this skill's. **EXCEPTION:** if two language versions say the
  **OPPOSITE** of each other (meaning reversed, see Step 4-E) this MUST be
  reported — this is a "logic error", not "translation quality".
- Legal adequacy (whether a privacy text is legally valid under GDPR, KVKK or
  similar) — a separate audit. **EXCEPTION:** whether legal/privacy text
  correctly describes **WHAT THE APP ACTUALLY DOES** is fully in this skill's
  scope (see Step 4-D; legal/privacy text also counts as a "behaviour claim").
- Perfect grammar — only problems that truly hurt readability.

---

## Step 0 — Safety: conflict with another agent/process

The family's shared rule: `../apptest/shared/CONVENTIONS.md` §5 (working tree,
persistent lock, process management, device and data, writing to the project).
Reminders specific to this skill are below.

This audit usually requires reading code AND writing short verification tests.
Another agent (Codex, another Claude session) may be working in the same project
at the same time. Rule:

- If the project is a git repository, first see the current state with
  `git status`; do not add extra mess to a dirty tree. Without git (plain folder,
  files uploaded to Desktop) apply the same care by hand: note which files you
  touch, return them to the same state when done.
- If possible, run verification tests in **an independent copy** (`git worktree`
  if git exists, or a plain copy) — without touching the main project at all. If
  not possible: create the temporary test file in the main tree, run it, and
  **delete it when done**; with git, verify `git status` is clean again, without
  git compare the file list by hand.
- Watch out for running build/test commands (`flutter test`, `npm test` etc.) AT
  THE SAME TIME as another build/test (resource/cache lock conflicts can look
  like a false "hang").
- Under no circumstances CHANGE main project files (text files included) — this
  is a report-focused audit.

## Step 1 — Find the text sources

Framework-independent search (continue with the first pattern that matches):

- Flutter/Dart: `**/*.arb`, `lib/l10n/**`
- iOS/macOS: `**/*.strings`, `**/*.stringsdict`, `**/*.lproj/**`
- Android: `**/res/values*/strings.xml`
- Web: `**/locales/**/*.json`, `**/i18n/**/*.json`,
  `**/translations/**/*.{json,yaml,yml}`
- gettext: `**/*.po`, `**/*.pot`
- Rails/general YAML: `**/locale/**/*.yml`, `**/config/locales/**/*.yml`
- **Legal/privacy text** (`**/legal/**`, `**/privacy*`, `**/terms*`, `**/*.md`
  mentioning "privacy"/"terms" or the equivalent in the app's language) — these
  may not be normal i18n files but fall under Step 4-D; do not skip them.
- If there is no i18n system: search source code for hardcoded user text.
  Framework-independent hint: user-facing text almost always sits in UI
  COMPONENT/VIEW/TEMPLATE/WIDGET files, as a quoted literal inside text-display
  calls (e.g. a string literal given to a text component, label, or alert call).
  EXCLUDE text the user never sees: logs, comments, variable names.

If there are several languages, read ALL of them (needed for the Step 4-E cross
check).

## Step 2 — Extract and clean

**Run the ready script first** (standard Python only; does not write to the
project):

```sh
python3 -I "${CLAUDE_SKILL_DIR}/../apptest-copy-audit/scripts/copy_inventory.py" <project_root> \
  --out <temp folder outside the project> [--source en] [--files a.arb b.arb] [--max 40]
```

What it gives: it finds translation files (Flutter `.arb`, web/RN locale `.json`
— nested keys are flattened, i18next `_one/_other` recognized —, iOS `.strings`,
`.stringsdict`, String Catalog `.xcstrings`, Android `strings.xml` + `plurals`,
gettext `.po`, Java `.properties`, YAML [if PyYAML is present]; it cannot read
translations kept as a code module — `languages/en.ts` — but says "NOT READ");
it groups language versions of the same text set into a **family** (e.g.
`public/locales/*/common.json`, `res/values*/strings.xml`) and compares each
family with its own source language. Output: a
`key<TAB>length<TAB>category<TAB>text` dump for each language + a markdown
candidate list: missing/untranslated keys, placeholder mismatch (C), number +
noun with no plural form (C), long text over a category threshold (F), the same
sentence in ≥3 keys (F4/F5), the same idea written at different lengths (F4),
stem repetition within a text (F1), filler patterns (F3; starter list for
EN/TR/DE/FR/ES — if the project's language is missing, add it to `FILLERS`).

**The script's result is a CANDIDATE, not a verdict.** Verify each item by
reading the text; the stem repetition and threshold lists are deliberately broad
(especially English, which runs ~20% more words than Turkish). The script does
NOT do the meaning/behaviour (D) check. If the script does not recognize a file
format, or text is hardcoded in components, return to the manual method below.

Manual method:

Extract key → text value pairs, drop metadata. In large files (1000+ lines),
proceed without bloating context: writing an intermediate copy of the filtered
value lines to a temporary location OUTSIDE the project (e.g. `/tmp`) is a good
method.

Also write each text's **length** to the intermediate copy
(`key<TAB>length<TAB>text`) — Step 4-F sorts by this column. In space-separated
languages count words; in languages written without spaces (JA, ZH, TH) count
characters and roughly double the thresholds. A placeholder in any format
(`{amount}`, `%s`, `%@`, `{{name}}`, `:count`, `%1$d`) counts as one word; in
ICU/plural/select bodies and text containing HTML/markdown (with the tags
stripped), count the longest branch.

## Step 3 — Sort by functional category

Categories: (1) error/validation, (2) destructive confirmation, (3) button/CTA,
(4) hint/help, (5) **notification** (title+body), (6) onboarding/marketing,
(7) **text explaining a rule/calculation** (describing a condition, a rate, a
frequency — the main target of Step 4-D), (8) **legal/privacy**.

---

## Step 4 — Scan layers (D: meaning/behaviour, A/B/C: tone, E: language pair, F: clutter)

Read `references/scan-layers.md` before scanning, and work through its layers in this order:

1. **D, meaning and behaviour (first).** Does each claim match what the code does? Verify in the code, and with a short probe where you can.
2. **E, reversed meaning between languages.** Compare the two versions of legal, permission and safety text.
3. **A, B and C, tone.** Politeness, terms and style, and plain logic errors in the text.
4. **F, clutter.** Only by measuring, and never at the cost of a verified claim.

## Step 5 — Which text gets a deep look (scaling)

In an app with 900+ strings, verifying them all by code tracing is not possible. Set
priority with this filter (deep look from high to low):

1. Text carrying a money/duration/frequency/threshold/permission/security claim
   (binding words, or their equivalents in the audited language: "automatically",
   "every", "always/never", "when", "because/for", "soon", "set aside / not set
   aside", "safely").
2. Notification text (shown later; the moment it is produced and the moment it is seen
   can differ — D4 risk is especially high here).
3. Text whose key is used from SEVERAL call sites (D3 risk).
4. Behaviour claims in legal/privacy text.
5. Everything else → tone layer only (A/B/C), no deep code tracing; at large scope, tell
   the user this explicitly.

The clutter layer (F) is NOT subject to this filter: it needs no code tracing and
applies to all text through the threshold + pattern scan in Step 4-F.

## Step 6 — Importance ranking

1. **Meaning/behaviour mismatch** (D1-D7) in a highly visible flow.
2. Meaning/behaviour mismatch in a low-visibility/corner case.
3. Meaning reversal (E) — always high in legal/permission text.
4. Tone (A/B/C) in a highly visible flow.
5. Clutter (F) in a highly visible flow (onboarding, frequently opened window, today /
   home screen) and F4-type multi-key repetition.
6. Tone (A/B/C) low visibility/cosmetic; clutter (F) on a rarely seen screen.

## Step 7 — Report format

```
## Overall impression
[is the tone consistent, is anything rude; ALSO: in text-behaviour match, how many
items are "proven" (code read/test written) and how many "suspect"]

## Meaning/behaviour findings (D1-D7, E) — these first
### [N]. [short title] — [D code]
- Where: key/file:line + the code file:line CALLING the text
- Text: full quote (ALL relevant languages in the project, not just two)
- Actual behaviour: what the relevant code/engine DOES (briefly, with evidence)
- Evidence: "read the code" / "wrote and ran this probe test: [result]"
- Why it is a problem: 1 sentence
- (if requested) Suggestion: alternative text — a suggestion ONLY

## Tone findings (A/B/C)
[v1 format: where/what/why/suggestion]

## Clutter findings (F)
| Text (key) | Now | Suggestion | Words | Pattern |
|---|---|---|---|---|
| openingFundQuestion | "…" | "…" | 14 → 9 | F1 |
[for F4: idea + affected keys + the ONE suggested pattern]
[for F5: pattern + how many places]

## Count
[language]: N keys scanned; M checked deep (code traced);
X over-threshold texts read; K meaning, L tone, Y clutter findings.
```

Do not present an uncertain finding as certain. If there are no findings, say so
plainly; do not force findings.
