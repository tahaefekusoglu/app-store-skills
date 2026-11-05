# Copy audit: scan layers

The full method for Step 4 of `../SKILL.md`.

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
