"""Subprocess-only black-box tests for ./cron-explainer.

No product code is imported or dynamically loaded. Every check runs the
repository-root executable as a subprocess and asserts on exit codes,
stdout bytes, and stderr bytes.
"""
import os
import re
import subprocess
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(REPO_ROOT, "cron-explainer")

LABELS = ["schedule:", "minute:", "hour:", "day of month:", "month:", "day of week:"]


def run(*args):
    return subprocess.run(
        [BIN, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def assert_valid_shape(test, proc, canonical=None):
    test.assertEqual(proc.returncode, 0, msg="stderr: %r" % (proc.stderr,))
    test.assertEqual(proc.stderr, b"", msg="stderr must be empty on success")
    text = proc.stdout.decode("utf-8")
    test.assertTrue(proc.stdout.endswith(b"\n"), msg="must end with newline")
    test.assertFalse(proc.stdout.endswith(b"\n\n"), msg="single trailing newline only")
    lines = text.split("\n")
    test.assertEqual(len(lines), 7, msg="expected 6 newline-terminated lines, got: %r" % (text,))
    test.assertEqual(lines[6], "")
    stripped = [ln.strip() for ln in lines[:6]]
    for got, want in zip(stripped, LABELS):
        test.assertTrue(
            got.lower().startswith(want),
            msg="line %r must start with label %r" % (got, want),
        )
    if canonical is not None:
        test.assertTrue(
            stripped[0].lower().startswith("schedule:"),
            msg="first line must be Schedule",
        )
        schedule_value = stripped[0].split(":", 1)[1].strip()
        test.assertEqual(schedule_value, canonical)
    return [ln.strip() for ln in lines[:6]]


def assert_error_shape(test, proc):
    test.assertEqual(proc.returncode, 1, msg="error exit must be 1, got %r" % (proc.returncode,))
    test.assertEqual(proc.stdout, b"", msg="stdout must be empty on error")
    test.assertTrue(proc.stderr.startswith(b"error: "), msg="stderr must start with 'error: ', got %r" % (proc.stderr,))
    test.assertTrue(proc.stderr.endswith(b"\n"), msg="stderr must end with newline")
    test.assertEqual(proc.stderr.count(b"\n"), 1, msg="stderr must be exactly one line, got %r" % (proc.stderr,))


class TestHelp(unittest.TestCase):
    def test_help_succeeds(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")
        text = proc.stdout.decode("utf-8")
        self.assertTrue(len(text) > 0)

    def test_help_documents_two_forms(self):
        text = run("--help").stdout.decode("utf-8")
        self.assertIn("./cron-explainer EXPRESSION", text)
        self.assertIn("./cron-explainer --help", text)

    def test_help_documents_field_order_and_ranges(self):
        text = run("--help").stdout.decode("utf-8")
        lower = text.lower()
        for token in ["minute", "hour", "day-of-month", "month", "day-of-week"]:
            self.assertIn(token, lower)
        for token in ["0-59", "0-23", "1-31", "1-12", "0-7"]:
            self.assertIn(token, text)

    def test_help_documents_syntax_characters(self):
        text = run("--help").stdout.decode("utf-8")
        for token in ["*", ",", "-", "/"]:
            self.assertIn(token, text)

    def test_help_has_quoted_example(self):
        text = run("--help").stdout.decode("utf-8")
        self.assertRegex(text, r'"[^"\n]*\*[^"\n]*"')

    def test_help_documents_errors(self):
        text = run("--help").stdout.decode("utf-8").lower()
        self.assertIn("error", text)

    def test_help_with_extra_arg_fails(self):
        assert_error_shape(self, run("--help", "extra"))

    def test_expression_then_help_flag_fails(self):
        assert_error_shape(self, run("1 2 3 4 5", "--help"))

    def test_unknown_flag_then_help_fails(self):
        assert_error_shape(self, run("--json", "--help"))


class TestValidOutput(unittest.TestCase):
    def test_readme_example(self):
        proc = run("*/15 9-17 * * 1-5")
        lines = assert_valid_shape(self, proc, canonical="*/15 9-17 * * 1-5")
        self.assertIn("15", lines[1])
        self.assertIn("9", lines[2])
        self.assertIn("17", lines[2])
        low = lines[5].lower()
        self.assertIn("monday", low)
        self.assertIn("friday", low)

    def test_all_stars(self):
        proc = run("* * * * *")
        assert_valid_shape(self, proc, canonical="* * * * *")

    def test_valid_edges(self):
        assert_valid_shape(self, run("0 0 1 1 0"), canonical="0 0 1 1 0")
        assert_valid_shape(self, run("59 23 31 12 6"), canonical="59 23 31 12 6")

    def test_leading_zeros_valid(self):
        assert_valid_shape(self, run("09 09 * * *"))

    def test_step_forms_valid(self):
        assert_valid_shape(self, run("*/15 * * * *"))
        assert_valid_shape(self, run("0-30/5 * * * *"))
        assert_valid_shape(self, run("2-10/3 * * * *"))

    def test_equal_endpoints_valid(self):
        proc = run("5-5 * * * *")
        lines = assert_valid_shape(self, proc, canonical="5-5 * * * *")
        self.assertIn("5", lines[1])

    def test_tabs_separate_fields(self):
        proc = run("*/15\t9-17 * * 1-5")
        assert_valid_shape(self, proc, canonical="*/15 9-17 * * 1-5")

    def test_leading_trailing_whitespace(self):
        proc = run("  * * * * *  ")
        assert_valid_shape(self, proc, canonical="* * * * *")

    def test_determinism_same_bytes(self):
        a = run("*/15 9-17 * * 1-5")
        b = run("*/15 9-17 * * 1-5")
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(a.returncode, 0)
        self.assertEqual(b.returncode, 0)

    def test_unordered_list_canonical_order(self):
        proc = run("5,3,1 * * * *")
        lines = assert_valid_shape(self, proc, canonical="5,3,1 * * * *")
        self.assertIn("1, 3 and 5", lines[1])
        self.assertNotIn("5, 3 and 1", lines[1])

    def test_month_names_in_output(self):
        proc = run("* * * 3 *")
        lines = assert_valid_shape(self, proc)
        self.assertIn("march", lines[4].lower())


class TestBoundaries(unittest.TestCase):
    def test_extra_spacing_byte_identical(self):
        compact = run("*/15 9-17 * * 1-5")
        spaced = run("  */15  9-17 * * 1-5  ")
        self.assertEqual(compact.returncode, 0)
        self.assertEqual(spaced.returncode, 0)
        self.assertEqual(spaced.stdout, compact.stdout)
        lines = spaced.stdout.decode("utf-8").split("\n")
        self.assertEqual(lines[0].strip(), "Schedule: */15 9-17 * * 1-5")

    def test_leading_zeros_same_schedule(self):
        proc = run("09 09 * * *")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, b"")

    def test_sunday_alias_zero(self):
        proc = run("0 0 * * 0")
        lines = assert_valid_shape(self, proc, canonical="0 0 * * 0")
        self.assertIn("sunday", lines[5].lower())

    def test_sunday_alias_seven(self):
        proc = run("0 0 * * 7")
        lines = assert_valid_shape(self, proc, canonical="0 0 * * 7")
        self.assertIn("sunday", lines[5].lower())

    def test_seven_in_every_value_position(self):
        for expr in ["0 0 * * 5-7", "0 0 * * 7-7", "0 0 * * 0,7"]:
            with self.subTest(expr=expr):
                proc = run(expr)
                lines = assert_valid_shape(self, proc, canonical=expr)
                self.assertIn("sunday", lines[5].lower())

    def test_step_count_not_value_position(self):
        proc = run("0 0 * * */8")
        lines = assert_valid_shape(self, proc)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("day of week", lines[5].lower())

    def test_eight_invalid(self):
        assert_error_shape(self, run("0 0 * * 8"))
        assert_error_shape(self, run("0 0 * * 1,8"))
        assert_error_shape(self, run("0 0 * * 8-8"))

    def test_single_value_range_valid(self):
        assert_valid_shape(self, run("5-5 * * * *"))

    def test_bare_step_invalid(self):
        assert_error_shape(self, run("5/2 * * * *"))
        assert_error_shape(self, run("5/2 0 1 1 1"))

    def test_names_invalid(self):
        assert_error_shape(self, run("MON * * * *"))
        assert_error_shape(self, run("* * * JAN *"))
        assert_error_shape(self, run("* * * * MON"))

    def test_six_fields_invalid(self):
        assert_error_shape(self, run("0 0 0 * * *"))
        assert_error_shape(self, run("* * * * * *"))


class TestErrors(unittest.TestCase):
    def test_no_args(self):
        assert_error_shape(self, run())

    def test_too_many_args(self):
        assert_error_shape(self, run("* * * * *", "extra"))

    def test_empty_expression(self):
        assert_error_shape(self, run(""))

    def test_whitespace_only(self):
        assert_error_shape(self, run("   "))

    def test_wrong_field_count(self):
        assert_error_shape(self, run("*/5 * * *"))
        assert_error_shape(self, run("* * * *"))
        assert_error_shape(self, run("* * * * * *"))
        assert_error_shape(self, run("*"))

    def test_unknown_flag(self):
        assert_error_shape(self, run("--json"))
        assert_error_shape(self, run("-h"))

    def test_empty_list_element(self):
        assert_error_shape(self, run("1,,2 * * * *"))
        assert_error_shape(self, run(",1 * * * *"))
        assert_error_shape(self, run("1, * * * *"))

    def test_out_of_range_each_field(self):
        assert_error_shape(self, run("60 * * * *"))
        assert_error_shape(self, run("99 * * * *"))
        assert_error_shape(self, run("* 24 * * *"))
        assert_error_shape(self, run("* * 0 * *"))
        assert_error_shape(self, run("* * 32 * *"))
        assert_error_shape(self, run("* * * 0 *"))
        assert_error_shape(self, run("* * * 13 *"))
        assert_error_shape(self, run("* * * * 8"))

    def test_zero_step(self):
        assert_error_shape(self, run("*/0 * * * *"))
        assert_error_shape(self, run("* */0 * * *"))
        assert_error_shape(self, run("0-10/0 * * * *"))

    def test_reversed_range(self):
        assert_error_shape(self, run("10-2 * * * *"))
        assert_error_shape(self, run("* 20-5 * * *"))
        assert_error_shape(self, run("* * * * 5-1"))

    def test_reversed_dow_literal(self):
        assert_error_shape(self, run("0 0 * * 7-5"))

    def test_illegal_characters(self):
        assert_error_shape(self, run("a * * * *"))
        assert_error_shape(self, run("* * * * SUN"))
        assert_error_shape(self, run("1.5 * * * *"))

    def test_error_line_shape(self):
        proc = run("99 * * * *")
        assert_error_shape(self, proc)
        self.assertRegex(proc.stderr.decode("utf-8"), r"^error: .+\n$")


if __name__ == "__main__":
    unittest.main()
