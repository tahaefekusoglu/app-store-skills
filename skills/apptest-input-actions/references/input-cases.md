# Input field try list

Each row applies to one field; rows that do not fit are "not applicable".
Limits are read from code / configuration (IA-P1). Expected: no data loss, no
wrong save, a clear message.

| ID | Case | Sample value | Look for |
|---|---|---|---|
| IN-01 | Empty | `` | save disabled or a clear error |
| IN-02 | Whitespace only | `   ` | counted as empty? |
| IN-03 | At the limit | (the maximum found in code) | accepted |
| IN-04 | Limit + 1 | | rejected; if not truncated, a warning |
| IN-05 | Very long paste | 10,000 characters | no freeze, limit applied |
| IN-06 | Emoji and skin tone | `👍🏽 👨‍👩‍👧` | counted as one character (IA-14) |
| IN-07 | Combining letter | `é` (e + U+0301) | one character, search / matching correct |
| IN-08 | Right-to-left text | `مرحبا` | display and save correct |
| IN-09 | Comma decimal | `12,5` | as 12.5 (IA-12) |
| IN-10 | Thousands separator | `1.250,50` / `1,250.50` | correct for the language |
| IN-11 | Minus / zero | `-5`, `0` | accepted / rejected per the rule |
| IN-12 | Very large number | `99999999999` | no overflow, limit |
| IN-13 | Leading / trailing space | ` name ` | trimmed? matching correct? |
| IN-14 | Line break | `a⏎b` | as expected in a single-line field |
| IN-15 | Rich text paste | (formatted text) | reduced to plain text |
| IN-16 | Case and Turkish I | `İSTANBUL` / `istanbul` | matching per language (I/ı/İ/i) |
| IN-17 | Double tap (save / pay) | two quick taps | one save (IA-10) |
| IN-18 | Back / background while working | | no half save |
