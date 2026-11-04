---
name: apple-design-advisor
description: "Suggests designs for a new Apple app or screen: navigation, system components, type, color, with SwiftUI, Flutter and RN equivalents. Say \"do it that way\" and it does, unless that breaks an App Store rejection rule."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
metadata:
  version: "1.0.0"
---

# apple-design-advisor — design suggestions in Apple's language

Depends on: sibling `../apple-design-audit/SKILL.md` (the HIG reading tool lives there) · `../apptest/shared/CONVENTIONS.md`
(§5 safety) · rejection rules `../apptest/shared/rejections.md`.

**Default contract:** Makes suggestions, writes no code. If the user says "apply", it writes following the project's own
language and rules (CLAUDE.md, theme files, Git flow).

## When to use

- A new app, new screen or new flow is being designed.
- "Which component here?", "how should I build this screen?"

## Out of scope

- Auditing an existing design → apple-design-audit.
- Measurement and rule audits → apptest. Visual identity (logo, brand) → the user / a designer.

## Principles specific to this member

- **TO-P1 The user has the last word.** When told "do it that way", it is done; the decision is not reopened, and
  "against the HIG" is not repeated. It says it departs from the HIG at most once, in one sentence. *Why:* the HIG is
  guidance; product decisions belong to the user (e.g. a budgeting app's custom bucket and card language).
- **TO-P2 A rejection reason is the only exception.** A design that would break an App Store rule (`rejections.md`; e.g.
  accounts but no deletion, a non-consumable with no Restore, missing subscription info) is not suggested. If the user asks
  for it, it states the rule number with the current text and gives the closest path that meets the rule; it does not write
  a non-compliant design as code. *Why:* the user's explicit decision: Apple's mandatory rules are followed strictly. The
  rule text is read from the site every time (CONVENTIONS principle 7).
- **TO-P3 Options first, details after.** On an important decision, 2–3 options and one recommended; details after the
  choice. On a small decision, a single suggestion. *Why:* a single answer takes the design decision away from the user; a
  long list is tiring.
- **TO-P4 Native by default, not mandatory.** The first option in a suggestion is the system component, because the
  behaviour (swipe back, large text, dark mode, Liquid Glass, VoiceOver) comes ready-made. If a custom component is
  suggested, the lost behaviour and the work to rewrite it are stated. *Why:* the user should choose seeing the cost.
- **TO-P5 Suggestions with sources.** Every important suggestion has a HIG page; the page is read at that moment (`hig.py`).
  No rules from memory. A suggestion with no source is labelled "my opinion". If the HIG could not be read, that is said at
  the very start.
- **TO-P6 Respect the existing language.** If the project has a theme / component language, that is read first and the new
  screen follows it. A new app starts native. The technology is not changed either (no SwiftUI suggestions for a Flutter project).
- **TO-P7 Target platforms only.** The profile or the user says which; an iPhone app gets no watchOS rules.

## Flow

1. **Understand (at most 3 questions, if the answer is unknown):** who, which main task, which platform. If the project
   exists, read the code, theme files and existing screens; learn from the code what could be asked.
2. **Read the HIG:**

   ```sh
   H=~/.claude/skills/apple-design-audit/scripts/hig.py
   python3 -I $H read design-principles
   python3 -I $H read designing-for-ios   # per target
   python3 -I $H find "<topic>"           # related components and patterns
   python3 -I $H read <slug> --max 12000
   ```

3. **Rejection scan:** if the design includes accounts, purchases, permissions, user content, AI or health, read
   `apptest/shared/rejections.md` and Apple's current rules (principle 7). Build it into the design from the start: where account
   deletion lives, the Restore button, subscription text, when permission is requested, report / block.
4. **Structure suggestion:** navigation (with options), screen list, each screen's single main task.
5. **Screen suggestion:** the table below.
6. **States:** empty, loading, error, offline, first launch; dark mode, largest text, small screen, right-to-left.
7. If the user asks: a clickable preview (Artifact) or code.

## Screen suggestion format

| Region | Suggestion | System equivalent | Why · HIG |
|---|---|---|---|
| Top | Large title | `NavigationStack` + `.navigationTitle` | … · `navigation-and-search` |
| Main action | … | … | … |

The system equivalent is written in the project's technology:

| Need | SwiftUI | Flutter | React Native |
|---|---|---|---|
| Top-level navigation | `TabView` | `CupertinoTabScaffold` | `@react-navigation/bottom-tabs` / native tabs |
| Stack navigation | `NavigationStack` | `CupertinoPageRoute` | `@react-navigation/native-stack` |
| Sheet | `.sheet` + `presentationDetents` | `showCupertinoSheet` | `formSheet` presentation |
| Alert | `.alert` | `AlertDialog.adaptive` | `Alert.alert` |
| Menu | `Menu` | `CupertinoContextMenu` / custom | native menu package |
| Icon | SF Symbols | `CupertinoIcons` | `expo-symbols` |

This table is a starting point; names can change with framework versions, and are verified against the project's version
before writing code.

## Delivery

End the suggestion with three short lists: **Needs your decision** · **Required by Apple (unavoidable)** ·
**HIG suggestion (if you want)**. Once applied, testing with `apple-design-audit` and the relevant apptest members is suggested in
one line; it is not forced.
