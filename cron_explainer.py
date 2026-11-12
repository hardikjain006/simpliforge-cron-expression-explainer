"""Cron-expression explainer.

Explains a standard 5-field cron expression in plain English, per the
requirements contract documented in README.md.
"""

import re
import sys

FIELD_SPECS = (
    ("minute", 0, 59),
    ("hour", 0, 23),
    ("day-of-month", 1, 31),
    ("month", 1, 12),
    ("day-of-week", 0, 7),
)

WEEKDAY_NAMES = (
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
)

MONTH_NAMES = (
    None,
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

_DIGITS_RE = re.compile(r"[0-9]+")
_SPLIT_RE = re.compile(r"[ \t]+")


class FieldError(ValueError):
    """A per-field validation failure.

    ``kind`` is "malformed" (shape violation) or "out-of-range".
    ``text`` is the exact offending field text.
    """

    def __init__(self, kind, field, text):
        super().__init__(kind, field, text)
        self.kind = kind
        self.field = field
        self.text = text


def _is_digits(token):
    return _DIGITS_RE.fullmatch(token) is not None


def tokenize(expression):
    """Split an expression into field texts on runs of space/tab.

    Leading/trailing spaces and tabs are trimmed first. An empty or
    whitespace-only expression tokenizes to zero fields.
    """
    stripped = expression.strip(" \t")
    if stripped == "":
        return []
    return _SPLIT_RE.split(stripped)


def _parse_range_base(base):
    """Parse the base of a stepped item; return (low, high) or None."""
    if "-" not in base:
        return None
    parts = base.split("-")
    if len(parts) != 2:
        return None
    if not _is_digits(parts[0]) or not _is_digits(parts[1]):
        return None
    low, high = int(parts[0]), int(parts[1])
    if low > high:
        return None
    return (low, high)


def _parse_item_shape(item):
    """Parse one comma-separated item's shape.

    Returns a ("star" | "value" | "range" | "starstep" | "rangestep", ...)
    tuple, or None when the item violates every allowed shape.
    """
    if "/" in item:
        parts = item.split("/")
        if len(parts) != 2:
            return None
        base, step = parts
        if not _is_digits(step) or int(step) < 1:
            return None
        divisor = int(step)
        if base == "*":
            return ("starstep", divisor)
        bounds = _parse_range_base(base)
        if bounds is None:
            return None
        return ("rangestep", bounds[0], bounds[1], divisor)
    if item == "*":
        return ("star",)
    if "-" in item:
        bounds = _parse_range_base(item)
        if bounds is None:
            return None
        return ("range", bounds[0], bounds[1])
    if _is_digits(item):
        return ("value", int(item))
    return None


def _shape_literals(shape):
    tag = shape[0]
    if tag == "value":
        return [shape[1]]
    if tag in ("range", "rangestep"):
        return [shape[1], shape[2]]
    return []


def parse_field(field, low, high, text):
    """Expand one field's text to its normalized integer set.

    Shape is validated for every item before any literal is range-checked,
    so a malformed item anywhere in the field takes precedence over an
    out-of-range literal. Raises FieldError on the first failure.
    """
    shapes = []
    for item in text.split(","):
        shape = _parse_item_shape(item)
        if shape is None:
            raise FieldError("malformed", field, text)
        shapes.append(shape)
    for shape in shapes:
        for literal in _shape_literals(shape):
            if literal < low or literal > high:
                raise FieldError("out-of-range", field, text)
    values = set()
    for shape in shapes:
        tag = shape[0]
        if tag == "star":
            values.update(range(low, high + 1))
        elif tag == "value":
            values.add(shape[1])
        elif tag == "range":
            values.update(range(shape[1], shape[2] + 1))
        elif tag == "starstep":
            values.update(range(low, high + 1, shape[1]))
        elif tag == "rangestep":
            values.update(range(shape[1], shape[2] + 1, shape[3]))
    return values


def full_range(field_index):
    """The unrestricted integer set for one field position."""
    _, low, high = FIELD_SPECS[field_index]
    if field_index == 4:
        return set(range(0, 7))
    return set(range(low, high + 1))


def normalize_day_of_week(values):
    """Map day-of-week 7 to 0 (Sunday) before deduplication."""
    return {0 if value == 7 else value for value in values}


def _uniform_step(ordered):
    if len(ordered) < 2:
        return None
    step = ordered[1] - ordered[0]
    if step <= 1:
        return None
    for first, second in zip(ordered, ordered[1:]):
        if second - first != step:
            return None
    return step


def classify(values, field_index):
    """Classify a normalized set for clause rendering.

    Returns ("single", v) | ("contiguous", a, b) | ("fullspan", n) |
    ("step", n, (a, b)) | ("list", ordered).
    """
    ordered = sorted(values)
    if len(ordered) == 1:
        return ("single", ordered[0])
    if ordered[-1] - ordered[0] + 1 == len(ordered):
        return ("contiguous", ordered[0], ordered[-1])
    step = _uniform_step(ordered)
    if step is not None:
        _, low, high = FIELD_SPECS[field_index]
        if set(range(low, high + 1, step)) == set(ordered):
            return ("fullspan", step)
        return ("step", step, (ordered[0], ordered[-1]))
    return ("list", ordered)


def _join_names(names):
    if len(names) == 2:
        return names[0] + " and " + names[1]
    return ", ".join(names[:-1]) + " and " + names[-1]


def minute_clause(values):
    kind = classify(values, 0)
    if kind[0] == "single":
        return "at minute %d" % kind[1]
    if kind[0] == "contiguous":
        return "minutes %d through %d" % (kind[1], kind[2])
    if kind[0] == "fullspan":
        return "every %d minutes" % kind[1]
    if kind[0] == "step":
        return "every %d minutes from %d through %d" % (
            kind[1],
            kind[2][0],
            kind[2][1],
        )
    return "minutes " + _join_names([str(v) for v in kind[1]])


def hour_clause(values):
    kind = classify(values, 1)
    if kind[0] == "single":
        return "at hour %d" % kind[1]
    if kind[0] == "contiguous":
        return "during hours %d through %d" % (kind[1], kind[2])
    if kind[0] == "fullspan":
        return "every %d hours" % kind[1]
    if kind[0] == "step":
        return "every %d hours from %d through %d" % (
            kind[1],
            kind[2][0],
            kind[2][1],
        )
    return "at hours " + _join_names([str(v) for v in kind[1]])


def day_of_month_clause(values):
    kind = classify(values, 2)
    if kind[0] == "single":
        return "on day-of-month %d" % kind[1]
    if kind[0] == "contiguous":
        return "on days-of-month %d through %d" % (kind[1], kind[2])
    if kind[0] == "fullspan":
        return "every %d days-of-month" % kind[1]
    if kind[0] == "step":
        return "every %d days-of-month from %d through %d" % (
            kind[1],
            kind[2][0],
            kind[2][1],
        )
    return "on days-of-month " + _join_names([str(v) for v in kind[1]])


def month_clause(values):
    kind = classify(values, 3)
    if kind[0] == "single":
        return "in %s" % MONTH_NAMES[kind[1]]
    if kind[0] == "contiguous":
        return "in %s through %s" % (MONTH_NAMES[kind[1]], MONTH_NAMES[kind[2]])
    if kind[0] == "fullspan":
        return "every %d months" % kind[1]
    if kind[0] == "step":
        return "every %d months from %s through %s" % (
            kind[1],
            MONTH_NAMES[kind[2][0]],
            MONTH_NAMES[kind[2][1]],
        )
    return "in " + _join_names([MONTH_NAMES[v] for v in kind[1]])


def day_of_week_clause(values):
    ordered = sorted(values)
    if ordered == [0, 6]:
        return "on weekends (Saturday and Sunday)"
    if ordered == [1, 2, 3, 4, 5]:
        return "on weekdays (Monday to Friday)"
    kind = classify(values, 4)
    if kind[0] == "single":
        return "on %s" % WEEKDAY_NAMES[kind[1]]
    if kind[0] == "contiguous":
        return "on %s through %s" % (
            WEEKDAY_NAMES[kind[1]],
            WEEKDAY_NAMES[kind[2]],
        )
    if kind[0] == "fullspan":
        return "every %d days-of-week" % kind[1]
    if kind[0] == "step":
        return "every %d days-of-week from %s through %s" % (
            kind[1],
            WEEKDAY_NAMES[kind[2][0]],
            WEEKDAY_NAMES[kind[2][1]],
        )
    return "on " + _join_names([WEEKDAY_NAMES[v] for v in kind[1]])


_CLAUSE_BUILDERS = (
    minute_clause,
    hour_clause,
    day_of_month_clause,
    month_clause,
    day_of_week_clause,
)


def explain(tokens):
    """Render one validated 5-token expression as a sentence (no newline)."""
    sets = []
    for index, ((field, low, high), text) in enumerate(
        zip(FIELD_SPECS, tokens)
    ):
        values = parse_field(field, low, high, text)
        if index == 4:
            values = normalize_day_of_week(values)
        sets.append(values)
    present = []
    for index, values in enumerate(sets):
        if values != full_range(index):
            present.append((FIELD_SPECS[index][0], _CLAUSE_BUILDERS[index](values)))
    if not present:
        return "Every minute."
    names = [name for name, _ in present]
    assembled = present[0][1]
    for name, clause in present[1:]:
        separator = " "
        if name == "day-of-week" and "day-of-month" in names:
            separator = " or "
        assembled += separator + clause
    return assembled[0].upper() + assembled[1:] + "."


HELP_TEXT = """Usage: cron-explainer "<minute> <hour> <day-of-month> <month> <day-of-week>"
       cron-explainer --help

Explains a standard 5-field cron expression in plain English.

Fields (in order) with allowed values:
  minute        0-59
  hour          0-23
  day-of-month  1-31
  month         1-12
  day-of-week   0-7 (0 and 7 both mean Sunday)

Each field is a comma-separated list of items. Each item is one of:
  *  V  A-B  */N  A-B/N
where V, A, B are decimal values and N is a decimal step (N >= 1).
A bare step base must be * or A-B; A must not exceed B.

Example:
  $ cron-explainer "*/15 9-17 * * 1-5"
  Every 15 minutes during hours 9 through 17 on weekdays (Monday to Friday).

Errors are reported on standard error with exit status 2 and a message
starting with "error: ". Nothing is written to standard output on error.
  error: missing cron expression
  error: expected 1 expression argument, got N
  error: expected 5 fields, got N
  error: <field> field malformed: <field-text>
  error: <field> field out of range: <field-text>
Field names are minute, hour, day-of-month, month, day-of-week.
"""


def main(argv):
    """Entry point; ``argv`` excludes the program name. Returns exit status."""
    if any(arg in ("--help", "-h") for arg in argv):
        sys.stdout.write(HELP_TEXT)
        return 0
    if len(argv) == 0:
        sys.stderr.write("error: missing cron expression\n")
        return 2
    if len(argv) > 1:
        sys.stderr.write(
            "error: expected 1 expression argument, got %d\n" % len(argv)
        )
        return 2
    tokens = tokenize(argv[0])
    if len(tokens) != 5:
        sys.stderr.write("error: expected 5 fields, got %d\n" % len(tokens))
        return 2
    try:
        sentence = explain(tokens)
    except FieldError as error:
        if error.kind == "malformed":
            sys.stderr.write(
                "error: %s field malformed: %s\n" % (error.field, error.text)
            )
        else:
            sys.stderr.write(
                "error: %s field out of range: %s\n" % (error.field, error.text)
            )
        return 2
    sys.stdout.write(sentence + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
