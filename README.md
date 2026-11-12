# Cron-expression explainer

A small command-line tool that explains a standard 5-field cron expression
in plain English.

## Usage

```text
cron-explainer "<minute> <hour> <day-of-month> <month> <day-of-week>"
cron-explainer --help
```

### Input mode

The tool has exactly one input mode: a single cron expression supplied as
one command-line argument (quoted so the shell passes all five fields as one
value).

Tokenization: trim leading and trailing ASCII whitespace (space U+0020 and
horizontal tab U+0009), then split on runs of one or more ASCII whitespace
characters (space/tab). The resulting token count MUST equal 5. An empty
string or whitespace-only string tokenizes to 0 fields and fails with
`error: expected 5 fields, got 0`. Multiple spaces, tabs, or mixed runs
between fields are equivalent to a single separator. Whitespace can never
appear inside a field: any inner whitespace splits fields and changes the
count.

The five fields, in order, are:

| Position | Field        | Allowed values                          |
|----------|--------------|-----------------------------------------|
| 1        | Minute       | `0`–`59`                                |
| 2        | Hour         | `0`–`23`                                |
| 3        | Day of month | `1`–`31`                                |
| 4        | Month        | `1`–`12`                                |
| 5        | Day of week  | `0`–`7` (`0` and `7` both mean Sunday)  |

Each field is a comma-separated list of one or more items. Empty items are
invalid (`1,,2`, a leading comma, or a trailing comma are malformed). Each
item MUST be exactly one of:

- `*`
- `V` (one or more ASCII digits)
- `A-B`
- `*/N`
- `A-B/N`

where `V`, `A`, `B` are ASCII digit strings (leading zeros allowed, value is
the decimal value; no signs, spaces, or other characters) and `N` is an
ASCII digit string. A bare value with a step (`60/5`) is malformed: the step
base MUST be `*` or `A-B`. Anything else — month or weekday names, a sixth
field, non-numeric tokens, reversed ranges such as `5-2` (`A > B`), or a zero
step such as `*/0` (`N < 1`) — is invalid.

Validity: every integer literal `V`/`A`/`B` appearing in a field MUST lie
within that field's allowed range, and the step divisor MUST satisfy
`N >= 1` (no upper bound). `*/N` means `min-max/N` for that field.
Expansion starts at `A` (or the field minimum for `*`), steps by `N` while
the value stays at or below `B` (or the field maximum), and collects each
visited value. A literal outside the field range is an out-of-range error;
any other shape violation is a malformed error (see Errors).

Normalization: expand each field to its integer set, sort ascending, and
deduplicate. Day-of-week `7` normalizes to `0` (Sunday) before deduplication,
so `0`, `7`, `0,7`, `1-5`, `1,2,3,4,5`, and `5,4,3,2,1` render identically to
their normalized forms. Full ranges are minute `0`–`59`, hour `0`–`23`,
day-of-month `1`–`31`, month `1`–`12`, and day-of-week `0`–`6` after
normalization. A field whose normalized set equals its full range is
unrestricted (`*`-equivalent) regardless of syntax: `*`, `*/1`, `0-59`, and
`0,0-59` are identical.

### Output mode

The tool has exactly one output mode: one human-readable plain-English
sentence written to standard output as UTF-8 text terminated by exactly one
newline (`\n`), with no other stdout bytes.

Mention rule: each restricted field (normalized set not equal to its full
range) MUST be described by its clause below; each unrestricted field MUST
be omitted. The single exception is the all-unrestricted expression
`* * * * *`, whose output is exactly `Every minute.` followed by `\n`.

Name maps (fixed):

- Weekday numbers render as `0` Sunday, `1` Monday, `2` Tuesday,
  `3` Wednesday, `4` Thursday, `5` Friday, `6` Saturday.
- Month numbers render as `1` January, `2` February, `3` March, `4` April,
  `5` May, `6` June, `7` July, `8` August, `9` September, `10` October,
  `11` November, `12` December.
- Minute, hour, and day-of-month values render as decimal numbers with no
  leading zeros.

Clause templates (each a function of the normalized set only, so
reordered/duplicate/`0`-vs-`7` spellings produce byte-identical output).
Let `S` be the normalized set with `a = min(S)` and `b = max(S)`:

- A set is contiguous when `size > 1` and `b - a + 1 == size`.
- A set is a uniform step when `size >= 2` and there exists `N > 1` such
  that `S` exactly equals the `a-b/N` expansion (start at `a`, step by `N`
  while `<= b`).
- A set is a full-span step when `size >= 2` and there exists `N > 1` such
  that `S` exactly equals the field-minimum to field-maximum `*/N`
  expansion for that field, whether or not the field maximum is visited
  (for example `*/7` in minute expands to `{0, 7, ..., 56}` and is
  full-span, rendering the short form `every 7 minutes`).

Precedence: full range (omitted) first, then single value (`size == 1`),
then contiguous range, then full-span step, then other uniform step with
`N > 1`, then value list. (For day of week, the two exact grouping sets
below take precedence over single/contiguous/step/list.) For example
`{2, 4, 6, 8, 10}` (as from `2-10/2`) is an other-uniform step rendering
`every 2 minutes from 2 through 10`, never a value list.

- Minute: single `v` renders `at minute v`; contiguous `a`–`b`
  renders `minutes a through b`;
  full-span step renders `every N minutes` (with the `N` from the matched
  `*/N` expansion); other uniform steps
  render `every N minutes from a through b`; any other set renders
  `minutes ` followed by the ascending list (`v1 and v2` for two values,
  `v1, v2 and v3` for three or more, `, ` separators except ` and ` before
  the last).
- Hour: single `v` renders `at hour v`; contiguous `a`–`b` renders
  `during hours a through b`; full-span step renders `every N hours`; other
  uniform steps render `every N hours from a through b`; any other set
  renders `at hours ` followed by the ascending list in the same
  comma/`and` format.
- Day of month: single `v` renders `on day-of-month v`; contiguous renders
  `on days-of-month a through b`; full-span step renders
  `every N days-of-month`; other uniform steps render
  `every N days-of-month from a through b`; any other set renders
  `on days-of-month ` followed by the ascending list.
- Month: single renders `in <Name>`; contiguous `a`–`b` renders
  `in <First> through <Last>`; full-span step renders `every N months`;
  other uniform steps render `every N months from <First> through <Last>`;
  any other set renders `in ` followed by the ascending month names in the
  same comma/`and` format.
- Day of week: the exact normalized set `{1,2,3,4,5}` renders
  `on weekdays (Monday to Friday)`; the exact normalized set `{0,6}`
  renders `on weekends (Saturday and Sunday)`; otherwise single renders
  `on <Name>`; contiguous renders `on <First> through <Last>`; full-span
  step renders `every N days-of-week`; other uniform steps render
  `every N days-of-week from <First> through <Last>`; any other set renders
  `on ` followed by the ascending weekday names in the same comma/`and`
  format. No other grouping phrases exist.

Sentence assembly: join the present clauses in field order (minute, hour,
day-of-month, month, day-of-week) with single spaces, with one override:
when both day-of-month and day-of-week clauses are present (both fields
restricted), the separator immediately before the day-of-week clause MUST
be ` or ` instead of a space, stating standard cron OR semantics (the
schedule fires when either date condition matches). Clauses stay in field
order, so when a month clause sits between them the day-of-month/month
separator stays a single space and only the month/day-of-week separator
becomes ` or `. No `and` joins the day-of-month and day-of-week clauses.
Uppercase the first letter of the assembled sentence and append `.`. For
example `0 0 1 * 0` MUST render exactly
`At minute 0 at hour 0 on day-of-month 1 or on Sunday.`, and `0 0 1 6 0`
MUST render exactly
`At minute 0 at hour 0 on day-of-month 1 in June or on Sunday.`.

Example (exact, not illustrative):

```text
$ cron-explainer "*/15 9-17 * * 1-5"
Every 15 minutes during hours 9 through 17 on weekdays (Monday to Friday).
```

Determinism: the same argument bytes always produce byte-identical stdout
bytes, independent of the current time, time zone, locale, or network.
Normalized equivalents (reordered lists, duplicates, `0` vs `7`) MUST
produce byte-identical output. Check procedure: run the same expression
twice and byte-compare stdout; run each normalized-equivalent pair
(`1-5` vs `1,2,3,4,5` vs `5,4,3,2,1`; `0 * * * *` vs `7 * * * *`) and
byte-compare stdout.

### Help text

`cron-explainer --help` (equivalently `-h`) prints usage, the field order
with allowed ranges, at least one valid example with its exact output, and
the error-reporting rules below, then exits with status `0`. Help is
written to standard output; nothing is written to standard error. If
`--help` or `-h` appears as any argument, help takes precedence: the tool
prints help and exits `0` without validating any expression and ignores any
additional arguments (they are not errors).

### Errors

Errors are predictable:

- Any invalid invocation — missing expression, more than one expression
  argument, wrong field count, out-of-range value, or malformed field —
  exits with status `2`.
- The diagnostic goes to standard error and starts with the prefix
  `error: ` followed by a specific reason. Nothing is written to standard
  output on error.
- Closed reason classes and message patterns (field names are exactly
  `minute`, `hour`, `day-of-month`, `month`, `day-of-week`):
  - missing expression (no arguments, no help flag):
    `error: missing cron expression`
  - extra argument (two or more non-help arguments `N`):
    `error: expected 1 expression argument, got N`
  - field count (tokenized count `N`, including `0` for empty or
    whitespace-only input):
    `error: expected 5 fields, got N`
  - malformed field (shape violation in the named field; suffix is the
    exact offending field text):
    `error: <field> field malformed: <field-text>`
    (covers non-numeric tokens, names, empty items, reversed ranges such as
    `5-2`, zero step such as `*/0`, and bad step forms such as `60/5`).
  - out-of-range value (every literal parses but at least one lies outside
    the field range; suffix is the exact offending field text):
    `error: <field> field out of range: <field-text>`
    (covers `61` in minute, `1-70` in minute, `24` in hour, `0` in month).

Validation order (deterministic tie-breaking): check the help flag first,
then the argument count (missing/extra), then the tokenized field count,
then per-field validity left to right across fields (minute, hour,
day-of-month, month, day-of-week), reporting only the first invalid field.
Within a field, shape is checked before range: malformed takes precedence
over out-of-range. Tied examples (each exits `2` with nothing on stdout):
`61 25 * * *` reports only the leftmost fault,
`error: minute field out of range: 61`; `70-80/0` in the minute field
reports the shape fault, `error: minute field malformed: 70-80/0`.

Boundary decisions:

| Input | Verdict |
|-------|---------|
| `""` (empty) | invalid: `error: expected 5 fields, got 0`, exit `2` |
| `"   "` (whitespace-only) | invalid: `error: expected 5 fields, got 0`, exit `2` |
| `"  */15 9-17 * * 1-5 "` (trimmed) | valid, 5 fields |
| tab-separated fields | valid, 5 fields |
| runs of multiple spaces/tabs | valid, 5 fields |
| `* * * *` | invalid: `error: expected 5 fields, got 4`, exit `2` |
| `* * * * * *` | invalid: `error: expected 5 fields, got 6`, exit `2` |
| `*/15 9-17 * * 1-5 extra` (two args) | invalid: extra-argument error, exit `2` |
| `*/100` in minute | valid step (`N >= 1`); expansion stops at the field maximum |
| `0-59/100` in minute | valid; yields only `0` |
| `1-70` in minute | invalid: minute out of range |
| `60/5` in minute | invalid: minute malformed (step base must be `*` or `A-B`) |
| `5-2` in any field | invalid: malformed (reversed range) |
| `*/0` in any field | invalid: malformed (step `N >= 1` required) |
| `JAN` in month / `MON` in day-of-week | invalid: malformed (names not accepted) |
| `0` vs `7` Sunday | both valid; outputs byte-identical |
| `61 25 * * *` (two faulty fields) | invalid: `error: minute field out of range: 61`, exit `2` (leftmost field wins) |
| `70-80/0` in minute (out-of-range literals plus zero step) | invalid: `error: minute field malformed: 70-80/0`, exit `2` (malformed takes precedence) |
| `2-10/2` in minute | valid uniform step: `every 2 minutes from 2 through 10` |
| `*/7` in minute | valid full-span step: `every 7 minutes` |

### Non-goals

The tool does not compute next run times, install or edit crontabs, read
schedules from files or standard input, or produce any machine-readable
(JSON, YAML, CSV) output. One expression in, one plain-English explanation
out.
