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
python3 -I ~/.claude/skills/apptest-copy-audit/scripts/copy_inventory.py <project_root> \
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

### D. Meaning/behaviour match — PRIORITY, the most critical layer

For every string in categories 5, 7 and 8 (notification, rule/calculation,
legal), ask: **"Is this sentence a CLAIM (a rule, reason, frequency, calculation,
or a 'will / won't' statement)?"** If yes, do not trust it without verifying
against the code. The 7 common error patterns (distilled from a real audit):

**D1. Describing two SEPARATE concepts with the same word**
If the app's data model deliberately separates two states (e.g. "actual income"
vs "expected/uncollected income"; "draft" vs "published"), a text may conflate
them with a single word ("add as income") and steer the user to the WRONG one.
**Check:** are there two paths in the domain model, one that "increments this
money/state" and one that does not? Which does the text recommend — the RIGHT
path?

**D2. A setting/state description is fixed instead of following the current STATE**
If a "this X is Y" description actually depends on a setting being ON/OFF or a
threshold being under/over, and the text says it UNCONDITIONALLY → it may show
the same claim while the setting is off / the threshold not crossed. **Check:**
does the code calling this text really read the current setting/state and CHANGE
the text, or is the text fixed?

**D3. The same (general) message is shown from several different TRIGGER paths,
but the text explains the reason for only ONE**
If an error/info message is called from several `if`s/states in code, while the
text says "the reason is X", the real reason in some calls may be Y/Z.
**Check:** find ALL callers of this string (grep); is the stated reason valid in
each?

**D4. TWO SEPARATE time/date fields in the model are mixed up**
If the domain model has two separate fields such as "actual due/target date" and
"reminder/snooze date", a notification/label may show ONE of them ("today") while
reading as if it means the other. **Check:** WHICH field does the code producing
the text read; WHICH field will the user THINK they are reading?

**D5. Describing something the system DOES NOT KNOW as if it knew**
A sentence like "your payment is due soon" claims false certainty if the system
knows only a REMINDER DAY chosen by the user (not the real external due date).
**Check:** is the claimed information REALLY in the system, or an APPROXIMATION
derived from user input? If so, lower the word to a more honest frame like
"reminder" / "check" — note it as a suggestion, do not change it.

**D6. A short summary misstates or omits the calculation's BASE**
A short label like "N% of every X" is misleading if the engine actually applies
N% not to ALL of X but to what remains AFTER SOME DEDUCTIONS from X (gross/net
difference, before/after order) — even if the long explanation is correct.
**Check:** read the relevant calculation function (engine); does the short label
describe the function's REAL input?

**D7. An "X happens automatically" claim conflicts with an actual
THRESHOLD/LIMIT/INTERVAL constant in the code**
A sentence like "backed up automatically when going to the background" is
MISLEADING if the code has a throttle/cooldown/limit constant (e.g. "at least 4
hours between consecutive backups"). **Check:** is there a constant (duration,
count, rate limit) in the service/function next to the behaviour this text
describes; if so, does the text IGNORE it?

**How to verify (by importance):**
1. First by READING CODE: grep the string's key/text, find where it is called,
   read the REAL condition of that code path.
2. If possible, verify EMPIRICALLY: write a short, disposable probe test calling
   the relevant service/engine function with the project's OWN test
   infrastructure (if any) — TEST a concrete claim like "is this text still shown
   while this setting is off", "does this calculation really give the stated
   rate". Follow the safety rule in Step 0 (separate copy, or write-run-delete).
   This lets you say "verified, here is the evidence" instead of "probably" — it
   definitely raises the report's quality.
3. If you could not verify, mark it honestly ("probably", "should be checked") —
   do not report with fake certainty.

### A/B/C. Tone layer — secondary but not skipped

**A. Politeness consistency:** find the audited LANGUAGE'S OWN politeness/formality
marker — it looks different in each language: a separate word (TR "Lütfen", EN
"Please", DE "Bitte"), a pronoun/conjugation choice (TR siz/sen, DE Sie/du, FR
vous/tu, ES usted/tú, the politeness level in JP/KR verb conjugation) or another
marker. These are examples; look for the equivalent in the language you are
checking. Then: is the marker consistent within a category; is the SAME formality
level kept throughout (formal on one screen and casual on another is always a tone
error — whatever the language); is there accusatory language; is destructive action
text more playful than it should be.

**B. Term/style consistency:** is one name used for one concept; are capitalization
and punctuation rules consistent; are button labels always imperative; is the error
message format (CAPITAL + period + problem+action) consistent.

**C. Pure text illogic (read without looking at code):** ambiguous multi-condition
error messages (which field is wrong is not said); pronoun/reference ambiguity;
placeholder/interpolation health:
- do languages have the same `{variable}` names; raw template/`TODO`/"coming soon"
  leaks.
- a grammatical suffix stuck directly (no space) to a variable — VARIES BY LANGUAGE,
  scan them all: Turkish vowel harmony (`{isim}'e`, "to {name}"), the gendered
  article before a variable in German/French (der/die/das, le/la), case endings in
  Russian/Polish/Finnish, gender agreement in Hebrew/Arabic — all the same class: a
  suffix/word that should change with the variable's REAL VALUE, hardcoded in code,
  silently breaks at runtime.
- a missing PLURAL CATEGORY in number placeholders like `{count}`: each language has
  its own plural rule (EN: one/other; RU/PL: one/few/many/other; AR:
  zero/one/two/few/many/other; JP/ZH/KO: no plural distinction). A template written
  only by "singular/plural" may be wrong or incomplete in the target language (e.g.
  Russian/Arabic). **Empirical check:** actually render/compile each number
  placeholder with at least 0, 1, 2 and a large number (e.g. 5, 100) and read the
  output — a concrete test step that is language-independent and works in any
  project.

### E. Meaning REVERSED between languages (narrow exception)

Do not assess full translation quality, BUT for every key pair (especially legal/
permission/security text) ask: **if I roughly translated one of these sentences into
the other, do they FORBID/ALLOW/PROMISE THE SAME THING?** Method (works for any
language pair): COUNT THE NEGATION MARKERS in both versions — depending on the
language these may be a separate word (EN "not"/"without"/"no", TR
"değil"/"olmayan"/"-sız"), an affix (TR -ma/-me, DE "un-"), or a verb conjugation
(JP ...ません); the form varies by language, the COUNT matters. If one version's
count DIFFERS from the other's (a double negative on one side but not the other can
reverse the meaning), read the sentence again, slowly: what is actually
FORBIDDEN/ALLOWED? If you find one, report it as HIGH importance — it is a logic
error, not translation quality.

### F. Clutter / needless words — by measuring

Question: **can this text become clearly shorter without losing any meaning?** Not
"keep it short" — report WITH EVIDENCE (word count).

**Method (independent of language and platform — mobile, desktop, web):**
1. Start from the "Over threshold", "Same sentence", "Same idea", "Stem repetition"
   and "Filler" sections of the Step 2 script (without the script, sort the
   word-counted dump yourself). Thresholds (by category, rough): button/label > 4,
   error > 12, hint/help > 15, confirmation body > 15, notification body > 12,
   onboarding description > 15 words → READ.
   Text under the threshold is scanned not one by one but by pattern (grep for
   F1–F6 below).
2. READ ALL of those over the threshold (usually hundreds in a large app; reading is
   cheap in this layer, no code tracing needed). For short text, the pattern scan
   alone is enough.
3. Write before/after and word count on each finding: "14 → 9".

**Clutter patterns:**

(The examples below are from a real audit — a budgeting app, TR/EN; the patterns are
the same for every app and website.)

**F1. The same information repeated in one text.** The same constraint/relation is
said in two or three different words: EN "**Apart from** your spending money, do you
have **extra** money **set aside**…?"; the Turkish original "Harcanabilir paranızdan
**ayrı**, … için **kenara ayırdığınız ekstra** bir para var mı?" repeats it the same
way (ayrı "separate" = kenara "aside" = ekstra "extra"). The same verb appearing
twice is also a sign (TR "**kapatılamaz** … **kapatın**", EN "can't be **closed** …
**close** the gap").

**F2. Repeating what the screen/context already says.** "… shown on the home screen"
while the user is on the home screen; a title of "Close X" with a body of "To close
X …"; "Continue?" in a confirmation window + a separate question; on the web, a first
paragraph repeating the page title, or a `title`/tooltip repeating the button text.

**F3. Filler and politeness add-ons.** Look for the filler patterns of the LANGUAGE
you are auditing; examples: TR "İsterseniz" ("if you like"), "daha sonra … içinden"
("later … from within"), "Lütfen" ("please"), "…-ebilirsiniz. İsterseniz
…-ebilirsiniz." ("you can … if you like you can …"); EN "please", "in order to", "you
will be able to", "at this time", "simply", "just"; DE "bitte", "gerne", "um … zu
können". Two permission/possibility modals in the same sentence ("you can … if you
wish") are a typical sign. (If politeness is CONSISTENT and part of the brand voice,
that is a layer A decision; here count only the length impact.)

**F4. The same idea written at different lengths across keys.** E.g. the idea "a rate
change applies only to new income" in four separate texts of 4, 6, 13 and 18 words.
Common candidates are similar in every product: "try again", paid tier limits
("upgrade for more"), "the change applies only to new ones", "saved", empty states
("no … yet"). Method: grep with a distinctive word pair; suggest ONE pattern for each
idea. This overlaps with B (term consistency); it is reported in F because the
suggestion is shortening.

**F5. Accessibility text longer than the platform's language.** iOS VoiceOver hints
(`accessibilityHint`) and Android TalkBack (`contentDescription`, action label)
describe the RESULT ("Opens the purchase page."), not the action ("Tap to …") — the
screen reader already says "button" and how to use it. On the web, `aria-label`,
`alt`, `title`: do not repeat the role ("button to …", "image of …"), do not rewrite
the visible text. If the same long hint repeats in 5+ places, count it as one finding.

**F6. Empty state / hint text repeating another text.** If the second sentence of
empty-page text is the same as a button description or form hint on the same screen,
the second is unnecessary.

**Shortening safety (MANDATORY):** A shortening suggestion must not delete or blur a
CLAIM verified by Step 4-D (limit, frequency, "will / won't", who it applies to).
When writing a suggestion, check that every condition in the original ("only", "at
most 3", "if iCloud is on", "at least 4 hours") is also in the suggestion; if you drop
one, say so explicitly. In legal/privacy and destructive confirmation text, clarity
comes before length; there, suggest only obvious F1/F3 repetitions. The suggested text
must keep the SAME brevity for English (and other languages); shortening only one
language can create a meaning gap between languages (E).

Also follow the project's OWN text rules: before writing a suggestion, look for —
(a) tests that read text files (in test folders, those mentioning a translation file
name or the i18n library: `test/`, `__tests__/`, `spec/`, `*.test.*`, `*_test.*`),
(b) i18n lint/style configuration, (c) a style guide / glossary (`docs/`,
`CONTRIBUTING`, `STYLE*`, `glossary*`), (d) agent instruction files (`CLAUDE.md`,
`AGENTS.md` etc.). A real example: shortening "The Savings Account
has $X…" → "The account's $X…" broke a project's test "the account uses its full name when
mentioned alone"; the right suggestion was "The Savings Account's $X…". Brand/product
names, legal terms, terms locked in a glossary and keywords deliberately repeated for
SEO (web) are outside shortening.

**Web-specific notes:** Look only at user-visible text (component/template text, form
validation, toast, empty state, email template); meta description and page title
length are SEO decisions, not this layer's job — only note obvious F1/F2-type
repetition. If hardcoded text sits in a component instead of a translation file (Step
1), the same thresholds apply.

**Scale:** Do not inflate the finding count. If a text gets 1–2 words shorter, do not
report it; the "clearly" threshold is roughly 30% or 4+ words. If the same pattern is
in many places, one finding + a list of affected keys.

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
