"""Repository-native tests for the cron-expression explainer.

Covers the public requirements contract from README.md: input tokenization,
field shapes and ranges, clause rendering, sentence assembly, help text, and
the closed error-message set with deterministic exit statuses.
"""

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
WRAPPER = os.path.join(REPO_ROOT, "cron-explainer")

sys.path.insert(0, REPO_ROOT)

import cron_explainer


def run_cli(*args):
    """Run the user-facing wrapper; return (status, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, WRAPPER, *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestGoldenOutputs(unittest.TestCase):
    def test_spec_example(self):
        status, out, err = run_cli("*/15 9-17 * * 1-5")
        self.assertEqual(status, 0)
        self.assertEqual(
            out,
            "Every 15 minutes during hours 9 through 17 "
            "on weekdays (Monday to Friday).\n",
        )
        self.assertEqual(err, "")

    def test_day_of_month_or_day_of_week(self):
        status, out, err = run_cli("0 0 1 * 0")
        self.assertEqual(status, 0)
        self.assertEqual(
            out, "At minute 0 at hour 0 on day-of-month 1 or on Sunday.\n"
        )
        self.assertEqual(err, "")

    def test_month_between_date_clauses(self):
        status, out, err = run_cli("0 0 1 6 0")
        self.assertEqual(status, 0)
        self.assertEqual(
            out,
            "At minute 0 at hour 0 on day-of-month 1 in June or on Sunday.\n",
        )
        self.assertEqual(err, "")

    def test_all_unrestricted(self):
        status, out, err = run_cli("* * * * *")
        self.assertEqual(status, 0)
        self.assertEqual(out, "Every minute.\n")
        self.assertEqual(err, "")

    def test_stdout_is_single_newline_terminated_line(self):
        status, out, _ = run_cli("*/15 9-17 * * 1-5")
        self.assertEqual(status, 0)
        self.assertTrue(out.endswith("\n"))
        self.assertFalse(out.endswith("\n\n"))
        self.assertEqual(out.count("\n"), 1)


class TestClauses(unittest.TestCase):
    def check(self, expression, sentence):
        status, out, err = run_cli(expression)
        self.assertEqual(status, 0, msg=err)
        self.assertEqual(out, sentence + "\n")
        self.assertEqual(err, "")

    def test_single_values(self):
        self.check(
            "5 3 15 4 *",
            "At minute 5 at hour 3 on day-of-month 15 in April.",
        )
        self.check("* * * * 2", "On Tuesday.")

    def test_no_leading_zeros(self):
        self.check(
            "007 03 07 04 *",
            "At minute 7 at hour 3 on day-of-month 7 in April.",
        )
        self.check("* * * * 07", "On Sunday.")

    def test_contiguous_ranges(self):
        self.check(
            "1-3 9-17 1-5 1-3 *",
            "Minutes 1 through 3 during hours 9 through 17 "
            "on days-of-month 1 through 5 in January through March.",
        )
        self.check(
            "1-3 9-17 1-5 1-3 1-3",
            "Minutes 1 through 3 during hours 9 through 17 "
            "on days-of-month 1 through 5 in January through March "
            "or on Monday through Wednesday.",
        )

    def test_full_span_steps(self):
        self.check("*/7 * * * *", "Every 7 minutes.")
        self.check("* */6 * * *", "Every 6 hours.")
        self.check("* * */10 * *", "Every 10 days-of-month.")
        self.check("* * * */3 *", "Every 3 months.")
        self.check("* * * * */2", "Every 2 days-of-week.")

    def test_other_uniform_steps(self):
        self.check("2-10/2 * * * *", "Every 2 minutes from 2 through 10.")
        self.check("* 9-17/2 * * *", "Every 2 hours from 9 through 17.")
        self.check(
            "* * 1-10/2 * *",
            "Every 2 days-of-month from 1 through 9.",
        )
        self.check(
            "* * * 2-10/2 *",
            "Every 2 months from February through October.",
        )
        self.check(
            "* * * * 1-5/2",
            "Every 2 days-of-week from Monday through Friday.",
        )

    def test_full_span_without_visiting_maximum(self):
        # */2 over month 1-12 visits {1,3,5,7,9,11}: the maximum 12 is
        # never visited, yet the set is still a full-span step.
        self.check("* * * 1-11/2 *", "Every 2 months.")

    def test_value_lists(self):
        # {1,2} and {1,2,3} are contiguous, and any 2-value set with a
        # gap is a uniform step, so lists need 3+ non-uniform values.
        self.check("1,3 * * * *", "Every 2 minutes from 1 through 3.")
        self.check("1,2,4 * * * *", "Minutes 1, 2 and 4.")
        self.check(
            "5,15,26,35 * * * *", "Minutes 5, 15, 26 and 35."
        )
        self.check(
            "* * * 1,6,12 *", "In January, June and December."
        )

    def test_weekday_grouping(self):
        self.check("* * * * 1-5", "On weekdays (Monday to Friday).")

    def test_weekend_grouping(self):
        self.check("* * * * 0,6", "On weekends (Saturday and Sunday).")

    def test_day_of_week_names(self):
        # {1,3,5} is a uniform 1-5/2 step; use a non-uniform set.
        self.check(
            "* * * * 1,3,6", "On Monday, Wednesday and Saturday."
        )

    def test_unrestricted_spellings_omit_clause(self):
        self.check("0-59 * * * *", "Every minute.")
        self.check("*/1 * * * *", "Every minute.")
        self.check("0 * * * *", "At minute 0.")

    def test_day_of_month_and_day_of_week_join(self):
        status, out, _ = run_cli("0 0 1 * 6")
        self.assertEqual(
            out, "At minute 0 at hour 0 on day-of-month 1 or on Saturday.\n"
        )
        self.assertNotIn(" and ", out)

    def test_day_of_week_without_day_of_month_uses_space(self):
        status, out, err = run_cli("5 3 * 4 2")
        self.assertEqual(status, 0)
        self.assertEqual(
            out, "At minute 5 at hour 3 in April on Tuesday.\n"
        )
        self.assertEqual(err, "")
        self.assertNotIn(" or ", out)


class TestNormalization(unittest.TestCase):
    def output(self, expression):
        status, out, err = run_cli(expression)
        self.assertEqual(status, 0, msg=err)
        return out

    def test_reordered_lists_identical(self):
        self.assertEqual(
            self.output("5,4,3,2,1 * * * *"), self.output("1-5 * * * *")
        )
        self.assertEqual(
            self.output("1,2,3,4,5 * * * *"), self.output("1-5 * * * *")
        )

    def test_duplicates_identical(self):
        self.assertEqual(
            self.output("1,1,2,2,3 * * * *"), self.output("1-3 * * * *")
        )

    def test_sunday_zero_and_seven_identical(self):
        self.assertEqual(
            self.output("* * * * 0"), self.output("* * * * 7")
        )
        self.assertEqual(
            self.output("* * * * 0,7"), self.output("* * * * 0")
        )

    def test_determinism(self):
        first = self.output("*/15 9-17 * * 1-5")
        second = self.output("*/15 9-17 * * 1-5")
        self.assertEqual(first, second)


class TestTokenization(unittest.TestCase):
    def check_error(self, args, message):
        status, out, err = run_cli(*args)
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, message + "\n")

    def test_empty_string(self):
        self.check_error([""], "error: expected 5 fields, got 0")

    def test_whitespace_only(self):
        self.check_error(["   "], "error: expected 5 fields, got 0")

    def test_trimmed_expression_valid(self):
        status, out, _ = run_cli("  */15 9-17 * * 1-5 ")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("Every 15 minutes"))

    def test_tabs_valid(self):
        status, out, _ = run_cli("*/15\t9-17\t*\t*\t1-5")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("Every 15 minutes"))

    def test_mixed_runs_valid(self):
        status, out, _ = run_cli("*/15  \t 9-17\t * *   1-5")
        self.assertEqual(status, 0)
        self.assertTrue(out.startswith("Every 15 minutes"))

    def test_four_fields(self):
        self.check_error(["* * * *"], "error: expected 5 fields, got 4")

    def test_six_fields(self):
        self.check_error(["* * * * * *"], "error: expected 5 fields, got 6")


class TestArgumentsAndHelp(unittest.TestCase):
    def test_missing_expression(self):
        status, out, err = run_cli()
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, "error: missing cron expression\n")

    def test_extra_argument(self):
        status, out, err = run_cli("*/15 9-17 * * 1-5", "extra")
        self.assertEqual(status, 2)
        self.assertEqual(out, "")
        self.assertEqual(err, "error: expected 1 expression argument, got 2\n")

    def test_help_flag(self):
        for flag in ("--help", "-h"):
            status, out, err = run_cli(flag)
            self.assertEqual(status, 0, msg=flag)
            self.assertEqual(err, "", msg=flag)
            self.assertIn("Usage:", out, msg=flag)
            self.assertIn("minute", out, msg=flag)
            self.assertIn("0-59", out, msg=flag)
            self.assertIn("day-of-week", out, msg=flag)
            self.assertIn("*/15 9-17 * * 1-5", out, msg=flag)
            self.assertIn(
                "Every 15 minutes during hours 9 through 17 "
                "on weekdays (Monday to Friday).",
                out,
                msg=flag,
            )
            self.assertIn("error:", out, msg=flag)

    def test_help_takes_precedence(self):
        status, out, err = run_cli("not a cron", "--help")
        self.assertEqual(status, 0)
        self.assertIn("Usage:", out)
        self.assertEqual(err, "")
        status, out, err = run_cli("* * *", "-h", "extra")
        self.assertEqual(status, 0)
        self.assertIn("Usage:", out)
        self.assertEqual(err, "")


class TestFieldValidity(unittest.TestCase):
    def check_error(self, expression, message):
        status, out, err = run_cli(expression)
        self.assertEqual(status, 2, msg=expression)
        self.assertEqual(out, "", msg=expression)
        self.assertEqual(err, message + "\n", msg=expression)

    def test_out_of_range_literals(self):
        self.check_error("61 * * * *", "error: minute field out of range: 61")
        self.check_error(
            "1-70 * * * *", "error: minute field out of range: 1-70"
        )
        self.check_error("* 24 * * *", "error: hour field out of range: 24")
        self.check_error(
            "* * 0 * *", "error: day-of-month field out of range: 0"
        )
        self.check_error("* * * 0 *", "error: month field out of range: 0")
        self.check_error(
            "* * * * 8", "error: day-of-week field out of range: 8"
        )

    def test_malformed_shapes(self):
        self.check_error(
            "60/5 * * * *", "error: minute field malformed: 60/5"
        )
        self.check_error("* 5-2 * * *", "error: hour field malformed: 5-2")
        self.check_error("* * */0 * *", "error: day-of-month field malformed: */0")
        self.check_error("* * * JAN *", "error: month field malformed: JAN")
        self.check_error(
            "* * * * MON", "error: day-of-week field malformed: MON"
        )
        self.check_error(
            "1,,2 * * * *", "error: minute field malformed: 1,,2"
        )
        self.check_error(
            ",1 * * * *", "error: minute field malformed: ,1"
        )
        self.check_error(
            "1, * * * *", "error: minute field malformed: 1,"
        )

    def test_large_steps_valid(self):
        status, out, err = run_cli("*/100 * * * *")
        self.assertEqual(status, 0)
        self.assertEqual(out, "At minute 0.\n")
        self.assertEqual(err, "")
        status, out, _ = run_cli("0-59/100 * * * *")
        self.assertEqual(status, 0)
        self.assertEqual(out, "At minute 0.\n")

    def test_leftmost_field_wins(self):
        self.check_error(
            "61 25 * * *", "error: minute field out of range: 61"
        )

    def test_malformed_beats_out_of_range(self):
        self.check_error(
            "70-80/0 * * * *", "error: minute field malformed: 70-80/0"
        )


class TestModuleApi(unittest.TestCase):
    def test_explain_is_deterministic(self):
        tokens = cron_explainer.tokenize("*/15 9-17 * * 1-5")
        self.assertEqual(cron_explainer.explain(tokens), cron_explainer.explain(tokens))

    def test_sunday_normalization(self):
        self.assertEqual(
            cron_explainer.normalize_day_of_week({0, 7}), {0}
        )


if __name__ == "__main__":
    unittest.main()
