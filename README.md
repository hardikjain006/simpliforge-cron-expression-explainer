# Cron-expression explainer

## Purpose

Explain a standard 5-field cron expression in plain English.

This document is the requirements contract. It defines the complete public,
testable behavior. It does not define implementation internals.

## Commands

The repository root MUST provide an executable file:

- `./cron-explainer`

It MUST support exactly two command forms (one input mode plus help):

1. `./cron-explainer EXPRESSION`
2. `./cron-explainer --help`

No other input modes are required (no stdin mode, no file mode, no extra
subcommands, no JSON/XML output mode).

## Input contract

### Explain form

- Form: `./cron-explainer EXPRESSION`
- `EXPRESSION` is exactly one argument: the full 5-field cron expression as a
  single shell-quoted string, e.g. `"*/15 9-17 * * 1-5"`.
- Field order: `MINUTE HOUR DAY-OF-MONTH MONTH DAY-OF-WEEK`.
- Fields are separated by one or more ASCII spaces or tabs. Leading and
  trailing ASCII whitespace around the whole expression MUST be accepted and
  ignored.
- Each field MUST be a comma-separated list of one or more items. Each item is
  one of:
  - `*` (all values)
  - `*/n` (every nth value)
  - `a-b` (inclusive range)
  - `a-b/n` (every nth value inside an inclusive range)
  - `a` (single value)
- Only ASCII digits and the characters `*`, `,`, `-`, `/` are allowed inside a
  field. Month/day names (e.g. `JAN`, `MON`) are NOT accepted.
- Allowed numeric ranges:
  - minute: `0-59`
  - hour: `0-23`
  - day-of-month: `1-31`
  - month: `1-12`
  - day-of-week: numeric literals `0-7` accepted in any value position (a
    singleton `a`, either endpoint of `a-b` and `a-b/n`, and any comma-separated
    list element); each `7` MUST be treated as Sunday, identical to `0`. Step
    counts (`n`) are not value positions. Literals `8` and above in
    day-of-week value positions are out-of-range and invalid.
- Leading zeros are accepted (e.g. `09` equals `9`).
- Step values MUST be positive integers (`>= 1`). A step of `0`, an empty list
  element (e.g. `1,,2`), an empty field, a reversed range (e.g. `10-2`), or any
  value outside the field's allowed range is invalid.
- Only `*/n` and `a-b/n` are valid step forms. A bare `a/n` (e.g. `5/2`) is NOT
  accepted and MUST be rejected as invalid syntax.
- Equal endpoints (e.g. `5-5`) are valid and mean that single value. Only a
  strictly reversed range, where the numeric start is greater than the numeric
  end (e.g. `10-2`), is invalid. For day-of-week, the comparison uses literal
  values, so `5-7` is valid.

## Output contract (the one output mode)

On valid input:

- Exit code MUST be `0`.
-_stdout_ MUST contain a plain-text, human-readable explanation. _stderr_ MUST
  be empty.
- The explanation MUST contain, in this relative order, six `\n`-terminated
  lines: first a schedule line whose stripped content starts with the
  case-insensitive label `Schedule:` followed by the canonical expression
  defined below, then five field lines whose stripped contents start with the
  case-insensitive labels `Minute:`, `Hour:`, `Day of month:`, `Month:`, and
  `Day of week:` respectively, each describing that field.
- Canonical expression form: leading and trailing ASCII whitespace trimmed,
  with each interior run of ASCII spaces/tabs collapsed to one ASCII space.
  The `Schedule:` line MUST state exactly this canonical form, not the raw
  untrimmed argument.
- The explanation MUST be deterministic: the same argument bytes always
  produce byte-identical stdout. Spellings that canonicalize to the same
  string (e.g. extra-spacing variants) MUST produce byte-identical stdout.
  Semantically equal spellings that canonicalize differently (e.g. `09` vs
  `9`, `7` vs `0`) are both valid but are NOT required to produce
  byte-identical stdout. Output MUST NOT depend on the current time,
  timezone, locale, network, or run-to-run state.
- Output MUST be UTF-8 plain text and MUST end with a single trailing newline.

Example (labels, order, and `Schedule:` form are normative; descriptive phrasing after each field label is illustrative but MUST describe that field):

```sh
$ ./cron-explainer "*/15 9-17 * * 1-5"
Schedule: */15 9-17 * * 1-5
Minute: every 15 minutes
Hour: every hour from 9 through 17
Day of month: every day
Month: every month
Day of week: Monday through Friday
```

## Help contract

- Form: `./cron-explainer --help`
- MUST exit `0` with the help text on stdout and nothing on stderr.
- Help text MUST document: the two command forms, the 5-field order with
  allowed ranges, the supported `* , - /` syntax, at least one quoted example,
  and the error behavior below.
- `--help` is recognized ONLY as the sole argument (exactly
  `./cron-explainer --help`). It MUST print help and exit `0` without
  validating any expression.
- Any other combination involving `--help` MUST NOT print help and MUST fail
  under the error contract above (e.g. `./cron-explainer --help extra`,
  `./cron-explainer "a b c d e" --help`, and `./cron-explainer --json --help`
  are all errors). Only the two command forms succeed; every other
  arity/flag combination MUST fail with the one-line `error: ...` shape.

## Error contract (predictable errors)

All errors share one predictable shape:

- Exit code MUST be non-zero (`1`).
- stdout MUST be empty.
- stderr MUST contain exactly one line starting with `error: ` followed by a
  human-readable reason, ending with a newline.

The program MUST fail this way for each of these cases:

| Case | Example |
|---|---|
| No arguments | `./cron-explainer` |
| More than one expression argument | `./cron-explainer "a b c d e" extra` |
| Empty expression | `./cron-explainer ""` |
| Wrong field count (not exactly 5) | `./cron-explainer "*/5 * * *"` |
| Unknown flag | `./cron-explainer --json` |
| Illegal character or empty list element | `./cron-explainer "1,,2 * * * *"` |
| Out-of-range value | `./cron-explainer "99 * * * *"` |
| Zero step | `./cron-explainer "*/0 * * * *"` |
| Reversed range | `./cron-explainer "10-2 * * * *"` |

## Boundary cases

- `"  */15  9-17 * * 1-5  "` (extra spacing) is valid; its stdout MUST be
  byte-identical to the compact `"*/15 9-17 * * 1-5"` form, with the
  `Schedule:` line stating the canonical single-space form.
- `"09 09 * * *"` is valid (same schedule as `"9 9 * * *"`); the two spellings
  are NOT required to produce byte-identical stdout.
- `"0 0 * * 7"` is valid and means Sunday (same schedule as `0`); the two
  spellings are NOT required to produce byte-identical stdout. `7` is also
  valid in any day-of-week value position (e.g. `5-7`, `7-7`, `0,7` are
  valid); `8` is invalid.
- `"5-5 * * * *"` is valid (single value); `"5/2 * * * *"` is invalid (bare
  `a/n` not accepted).
- `"MON * * * *"` is invalid (names not accepted).
- An expression with 6 fields (seconds form) is invalid (wrong field count).

## Non-goals

- No schedule computation (no "next run" output), no editing or installing
  crontabs, no daemon/service behavior.
- No second input or output mode beyond what is defined above.

## Acceptance summary

The goal is met when `./cron-explainer --help` prints useful help, valid
5-field expressions produce the one deterministic plain-text explanation on
stdout with exit `0`, and every error case above produces the predictable
`error: ...` stderr line with a non-zero exit.
