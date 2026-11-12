# Cron-expression explainer

## Goal

Explain a standard cron expression in plain human-readable language.

The tool has one input mode (a single cron expression argument), one output
mode (a human-readable explanation on stdout), useful help text, and
predictable errors.

## Normative interfaces

All commands run from the repository root. `cron-explainer` is an executable
file at the repository root, runnable directly with no build step.

### Explain an expression

```sh
./cron-explainer EXPRESSION
```

- `EXPRESSION` is exactly one argument: a standard 5-field cron expression,
  quoted by the caller when it contains spaces, e.g.
  `./cron-explainer "*/15 9-17 * * 1-5"`.
- On success the tool prints a human-readable explanation to stdout and
  exits with status `0`. Nothing is written to stderr.
- Output is deterministic: the same expression always produces byte-identical
  stdout. Output contains no timestamps or run-varying content and ends with
  a single trailing newline.

### Help

```sh
./cron-explainer --help
```

- Prints useful help text to stdout and exits with status `0`.
- The usage line is exactly `Usage: ./cron-explainer EXPRESSION`. Help stdout
  contains this line byte-identically as one newline-terminated line.
- Help text includes: the usage line above, a one-paragraph description of
  what the tool does, the five fields with their allowed numeric ranges, the
  supported operators (`*`, lists, ranges, steps), at least two worked
  examples (each worked example is an example invocation line containing
  `./cron-explainer` followed by a quoted 5-field cron expression), and a
  note describing error behavior.
- Mechanical acceptance (alphabetic checks are case-insensitive on lowercased
  stdout): stdout contains `usage` and `./cron-explainer`; stdout contains
  each range substring `0-59`, `0-23`, `1-31`, `1-12`, and `0-7`; stdout
  contains `*`, `lists`, `ranges`, and `steps`; stdout contains at least three
  occurrences of the substring `./cron-explainer` (the usage line plus at
  least two worked-example invocations); and stdout contains `error`.
- `--help` is accepted only as the sole argument. Any other argument count or
  any other flag is a usage error (see below).

## Input contract

- The expression must contain exactly five whitespace-separated fields:

  | Position | Field        | Allowed values |
  |----------|--------------|----------------|
  | 1        | Minute       | 0-59           |
  | 2        | Hour         | 0-23           |
  | 3        | Day of month | 1-31           |
  | 4        | Month        | 1-12           |
  | 5        | Day of week  | 0-7 (0 and 7 are both Sunday) |

- Leading/trailing whitespace around the expression is tolerated. Fields may
  be separated by one or more spaces or tabs.
- Each field supports: `*` (all values), comma-separated lists (e.g. `1,15`),
  ranges (e.g. `9-17`), and steps of the form `<base>/<step>` where `<base>`
  is `*`, a range `a-b`, or a single value `a` (e.g. `*/15`, `0-30/5`,
  `5/15`), and `<step>` is a positive decimal integer (digits only, value
  >= 1). A step larger than the field span is valid and selects every
  `<step>`-th value starting from the base start (e.g. `*/45` in the minute
  field is valid). These forms may be combined (e.g. `1-10,20,*/45` where
  each list element is valid on its own). `5/15` is valid; `5/` (missing
  step digits) is invalid.
- Only numeric values and the operators above are supported. Month or weekday
  names, special strings such as `@daily`, seconds fields (six-field
  expressions), and any other token are invalid input.

## Output contract

- The explanation covers each of the five fields by name (minute, hour, day
  of month, month, day of week), stating in plain language which values each
  field selects, plus an overall summary of when the schedule runs.
  Acceptance is case-insensitive substring presence: the lowercased stdout
  must contain each of `minute`, `hour`, `day of month`, `month`, and
  `day of week`.
- `* * * * *` is explained as running every minute (acceptance:
  case-insensitive substring `every minute` in stdout).
- When both day of month and day of week are restricted (neither field is
  `*`), the schedule follows standard cron OR semantics: a calendar day
  matches when either field matches. The overall summary must be consistent
  with this rule.
- Mechanical acceptance for OR-consistency: for input `0 9 1 * 1` (09:00 on
  day-of-month 1 OR on Monday), split the lowercased stdout on `.`, `;`,
  `!`, `?`, and newline into segments; at least one segment must state the
  union with the separate word `or` between the two day references, i.e.
  match `1 ... or ... monday` or `monday ... or ... 1` (allowing `day of
  week` in place of `monday`), where `or` is matched as
  `(^|[^a-z])or([^a-z]|$)` so `for`, `before`, `more`, and `word` do not
  match. An intersection-only description (e.g. stating the schedule runs
  only when both conditions hold) fails this check because its `or`, if
  any, does not join the two day references in one segment.
- Exact prose beyond the field-name substrings, the `every minute` substring,
  and the `0 9 1 * 1` union-segment requirement above is
  implementation-defined, but for a fixed expression the output is always
  byte-identical.

## Error contract (predictable errors)

Any of the following is an error: zero arguments, more than one argument
(other than the sole `--help` form), any other flag, an empty expression,
a field count other than five, an out-of-range value (e.g. minute `60`),
a reversed range (e.g. `5-1`), a zero or negative step (e.g. `*/0`), or any
unsupported token (including `5/` with missing step digits).

- Only argument-shape errors are usage errors: zero arguments, more than one
  argument, or any flag other than the sole `--help` form. Only usage errors
  include the usage line after the reason. All other listed errors are value
  errors and must not include the usage line.
- The usage line is exactly `Usage: ./cron-explainer EXPRESSION`,
  byte-identical to the usage line in `--help` output.
- For value errors, stderr is exactly one newline-terminated line: it starts
  with the prefix `Error: `, continues with a plain-language reason, ends
  with a single trailing newline (`\n`), and contains no other newline bytes.
- For usage errors, stderr is exactly two newline-terminated lines: line 1
  starts with `Error: ` plus the reason and ends with `\n`; line 2 is exactly
  `Usage: ./cron-explainer EXPRESSION\n`. Total stderr contains exactly two
  `\n` bytes and no other output.
- The tool exits with status `1`.
- Nothing is written to stdout on error.
