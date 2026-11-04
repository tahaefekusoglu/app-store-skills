# apptest report template

Per CONVENTIONS §8. The report is written in the user's language; the sample below is in English.
Empty sections are left out (e.g. no findings → the single line "No findings.").

```markdown
# <Member name>: <project name> · <date>

**Summary:** <one paragraph: how many rejection risks, how many user bugs, the two most
important things, ready to submit or not>

**Profile:** <technology · platforms · notable capabilities> (shared/profile.py)

## Rejection risk
### [R-xx | <member id>] <short title>
- **Rule:** <number + short name>
- **Evidence:** `file:line` / test output / image / setting
- **Impact:** <what happens: rejection, removal, effect on the user>
- **Ways to fix:** <one or several options; not imposed>
- **Verified:** yes (how) / no (why)

## User bug
### [<member id>] <short title>
(same fields; "Who is affected" instead of "Rule")

## Suggestions
- [<id>] <one line>

## Not applicable
<ids, one line: "LA-12, LA-13 (no iPad)">

## Suppressed
<N items; rejection risks marked "(rejection risk)">

## Environment
<device / simulator · iOS · language · region · time zone · seed · duration>
Apple rules: "Last Updated <date>", read from the official page on <today>
(if it could not be read, a warning at the VERY TOP of the report; CONVENTIONS principle 7).

## Environment problems
<infrastructure errors that do not count as findings>

## Cleanup failed
<simulator / process / file left behind and how to clean it>
```

Short report (quick tour, few findings): Summary + findings + Environment is enough.
