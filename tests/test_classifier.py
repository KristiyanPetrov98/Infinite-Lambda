import csv
import io
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from classifier import (DEFAULT_POLICY, SPEC_POLICY, classify, eligibility, read_history)


def history(starts, statuses=None, name="workflow"):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["workflow_name", "start_time", "end_time", "status"])
    for i, t in enumerate(starts):
        writer.writerow([name, str(t), "", statuses[i] if statuses else "Succeeded"])
    return read_history(buf.getvalue())


def result(starts, statuses=None, policy=DEFAULT_POLICY):
    return classify(history(starts, statuses), policy)[0]


def sequence(period, count=12, days=2, jitter=None):
    base = datetime(2026, 9, 24, 7)
    return [base + timedelta(days=d, minutes=i * period + (jitter[i] if jitter else 0))
            for d in range(days) for i in range(count)]


class BoundaryTests(unittest.TestCase):
    def test_exact_periods_below_boundary_never_approve(self):
        for p in (15, 30, 54, 55, 57, 59, 59.5, 59.8, 59.9, 59.99, 59.999):
            with self.subTest(minutes=p):
                self.assertEqual(result(sequence(p)).decision, "Too frequent")

    def test_policy_boundary_has_no_rounding(self):
        for p in (59.999999, 59.9, 30):
            self.assertEqual(eligibility(p), "Too frequent")
        for p in (60, 60.000001, 1440):
            self.assertEqual(eligibility(p), "In scope")
        for p in (None, 0, -1, float("nan"), float("inf")):
            self.assertEqual(eligibility(p), "Unknown")

    def test_hourly_with_52_to_67_minute_gaps(self):
        jitter = [0, -8, -1, 4, -2, 3, 0, 1, -3, 2, 1, -2]
        r = result(sequence(60, jitter=jitter))
        self.assertEqual((r.cadence, r.decision), ("Hourly", "In scope"))

    def test_unresolved_drift_is_reviewed(self):
        # A small consistent negative slope obscured by noise is not proof of hourly jitter.
        jitter = [0, 2, -2, 1, -1, 0, 0, -1, 1, -2, 2, 0]
        self.assertEqual(result(sequence(59.9, jitter=jitter)).decision, "Unknown")

    def test_proven_fast_day_is_not_hidden_by_hourly_day(self):
        starts = sequence(59, days=1) + [x + timedelta(days=1) for x in sequence(60, days=1)]
        self.assertEqual(result(starts).decision, "Too frequent")

    def test_short_conflicting_daily_periods_are_unknown(self):
        starts = sequence(59, count=6, days=1) + [x + timedelta(days=1) for x in sequence(60, count=6, days=1)]
        self.assertEqual(result(starts).decision, "Unknown")

    def test_overnight_does_not_hide_fast_schedule(self):
        self.assertEqual(result(sequence(30, count=6)).decision, "Too frequent")

    def test_extra_independent_fast_pattern_blocks_daily(self):
        daily = [datetime(2026, 9, 1, 3) + timedelta(days=d) for d in range(30)]
        self.assertEqual(result(daily + sequence(15, count=6)).decision, "Too frequent")

    def test_unknown_hourly_conflicting_start(self):
        self.assertEqual(result(sequence(60) + [datetime(2026, 9, 24, 8, 30)]).decision, "Unknown")

    def test_hourly_missing_days_fail_coverage(self):
        starts = sequence(60, days=1) + [x + timedelta(days=9) for x in sequence(60, days=1)]
        self.assertEqual(result(starts).decision, "Unknown")

    def test_hourly_business_window_excludes_weekend(self):
        base = datetime(2026, 9, 21, 7)
        starts = [base + timedelta(days=d, hours=h) for d in range(12)
                  if (base + timedelta(days=d)).weekday() < 5 for h in range(8)]
        self.assertEqual(result(starts).decision, "In scope")
        self.assertIn("Mon–Fri", " ".join(result(starts).evidence))


class EvidenceTests(unittest.TestCase):
    def test_original_near_hourly_counts_are_stricter(self):
        starts = sequence(59, count=6)
        self.assertEqual(result(starts).decision, "Too frequent")
        self.assertEqual(result(starts, policy=SPEC_POLICY).decision, "Unknown")
        self.assertEqual(result(sequence(59, count=10), policy=SPEC_POLICY).decision, "Too frequent")

    def test_short_clear_fast_history_single_day(self):
        starts = sequence(30, count=6, days=1)
        self.assertEqual(result(starts).decision, "Too frequent")
        self.assertEqual(result(starts, policy=SPEC_POLICY).decision, "Unknown")

    def test_short_fast_history_two_days(self):
        starts = sequence(30, count=4)
        self.assertEqual(result(starts).decision, "Too frequent")
        self.assertEqual(result(starts, policy=SPEC_POLICY).decision, "Unknown")

    def test_single_day_hourly_evidence(self):
        starts = sequence(60, count=12, days=1)
        self.assertEqual(result(starts).decision, "In scope")
        self.assertEqual(result(starts, policy=SPEC_POLICY).decision, "Unknown")

    def test_three_daily_dates(self):
        starts = [datetime(2026, 9, 1, 3) + timedelta(days=d) for d in range(3)]
        self.assertEqual(result(starts).decision, "In scope")
        self.assertEqual(result(starts, policy=SPEC_POLICY).decision, "Unknown")

    def test_three_weekly_dates(self):
        starts = [datetime(2026, 9, 1, 3) + timedelta(days=7*d) for d in range(3)]
        self.assertEqual(result(starts).decision, "In scope")
        self.assertEqual(result(starts, policy=SPEC_POLICY).decision, "Unknown")

    def test_too_little_evidence_remains_unknown(self):
        for starts in [sequence(30, count=3, days=1), sequence(60, count=5, days=1),
                       [datetime(2026, 9, 1), datetime(2026, 9, 2)]]:
            with self.subTest(starts=starts):
                self.assertEqual(result(starts).decision, "Unknown")


class CalendarTests(unittest.TestCase):
    def test_weekdays_expected_calendar(self):
        base = datetime(2026, 6, 29, 7)
        starts = [base + timedelta(days=d) for d in range(90)
                  if (base + timedelta(days=d)).weekday() < 5]
        r = result(starts)
        self.assertEqual((r.cadence, r.decision), ("Weekdays (Mon–Fri)", "In scope"))
        self.assertIn("100.0%", r.evidence[0])

    def test_weekday_missing_dates_use_weekdays_denominator(self):
        base = datetime(2026, 6, 29, 7)
        starts = [base + timedelta(days=d) for d in range(26)
                  if (base + timedelta(days=d)).weekday() < 5 and d != 2]
        r = result(starts)
        self.assertEqual(r.decision, "In scope")
        self.assertIn("95.0%", r.evidence[0])
        self.assertTrue(any("Gaps" in w for w in r.warnings))

    def test_missing_majority_does_not_approve(self):
        starts = [datetime(2026, 9, 1, 3) + timedelta(days=d) for d in (0, 1, 8, 9, 15)]
        self.assertEqual(result(starts).decision, "Unknown")

    def test_monthly_rules(self):
        examples = [
            (["2026-06-30", "2026-07-31", "2026-08-31"], "month-end"),
            (["2026-07-01", "2026-08-03", "2026-09-01"], "first weekday"),
            (["2026-07-03", "2026-08-05", "2026-09-03"], "business day 3"),
            (["2026-07-24", "2026-08-25", "2026-09-25"], "previous weekday"),
            (["2026-07-05", "2026-08-02", "2026-09-06"], "1 Sunday"),
            (["2026-07-31", "2026-08-28", "2026-09-25"], "last Friday"),
        ]
        for dates, label in examples:
            with self.subTest(dates=dates):
                r = result([datetime.fromisoformat(d + " 03:00") for d in dates])
                self.assertEqual(r.decision, "In scope")
                self.assertIn(label, r.cadence)

    def test_no_invented_month_end_or_holidays(self):
        dates = [datetime.fromisoformat(d + " 03:00") for d in ("2026-06-30", "2026-07-31", "2026-08-28")]
        self.assertEqual(result(dates).decision, "Unknown")

    def test_twice_monthly(self):
        starts = [datetime(2026, m, d, 22) for m in (7, 8, 9) for d in (1, 15)]
        self.assertTrue(result(starts).cadence.startswith("Twice monthly"))
        self.assertEqual(result(starts).decision, "In scope")

    def test_quarterly_needs_three_quarters(self):
        starts = [datetime(2026, m, 10, 21) for m in (1, 4, 7)]
        self.assertEqual(result(starts).decision, "In scope")
        self.assertTrue(result(starts).cadence.startswith("Quarterly"))
        self.assertEqual(result(starts[:1]).decision, "Unknown")

    def test_no_about_monthly_matching(self):
        starts = [datetime(2026, m, d, h) for m, d, h in [(7, 3, 3), (8, 4, 11), (9, 5, 6)]]
        self.assertEqual(result(starts).decision, "Unknown")

    def test_skipped_month_is_unknown(self):
        starts = [datetime(2026, m, 15, 3) for m in (5, 7, 8)]
        self.assertEqual(result(starts).decision, "Unknown")


class RetryAndInputTests(unittest.TestCase):
    def test_daily_likely_retry(self):
        base = datetime(2026, 9, 1, 3)
        starts = [base + timedelta(days=d) for d in range(10)]
        starts.append(base + timedelta(days=4, minutes=49))
        statuses = ["Failed" if i == 4 else "Succeeded" for i in range(11)]
        r = result(starts, statuses)
        self.assertEqual(r.decision, "In scope")
        self.assertEqual(len(r.likely_retry_rows), 1)
        self.assertEqual(r.run_count, 11)

    def test_retry_crossing_midnight(self):
        base = datetime(2026, 9, 1, 23, 50)
        starts = [base + timedelta(days=d) for d in range(10)] + [base + timedelta(days=4, minutes=49)]
        statuses = ["Failed" if i == 4 else "Succeeded" for i in range(11)]
        self.assertEqual(len(result(starts, statuses).likely_retry_rows), 1)

    def test_extra_after_success_is_unknown(self):
        starts = [datetime(2026, 9, 1, 3) + timedelta(days=d) for d in range(10)]
        starts.append(starts[4] + timedelta(minutes=49))
        self.assertEqual(result(starts).decision, "Unknown")

    def test_recurrent_extra_after_failures_is_not_retry(self):
        base = datetime(2026, 9, 1, 3)
        starts, statuses = [], []
        for d in range(10):
            starts.extend([base + timedelta(days=d), base + timedelta(days=d, minutes=30)])
            statuses.extend(["Failed", "Succeeded"])
        r = result(starts, statuses)
        self.assertEqual(r.decision, "Unknown")
        self.assertEqual(r.likely_retry_rows, [])

    def test_fast_scheduled_runs_after_failure_are_preserved(self):
        starts = sequence(30)
        statuses = ["Failed" if i % 2 == 0 else "Succeeded" for i in range(len(starts))]
        self.assertEqual(result(starts, statuses).decision, "Too frequent")

    def test_all_failed_weekly_is_eligible(self):
        starts = [datetime(2026, 7, 7, 5) + timedelta(days=7*d) for d in range(8)]
        r = result(starts, ["Failed"]*8)
        self.assertEqual(r.decision, "In scope")
        self.assertTrue(any("8 failed" in w for w in r.warnings))

    def test_blank_end_time_and_aborted_status(self):
        starts = [datetime(2026, 7, 7, 5) + timedelta(days=d) for d in range(8)]
        self.assertEqual(result(starts, ["Aborted"]*8).decision, "In scope")

    def test_end_times_do_not_change_frequency(self):
        rows = [f"job,2026-09-{d:02} 03:00,{end},Succeeded" for d, end in
                [(1, "invalid end"), (2, ""), (3, "2026-10-01 12:00"), (4, "2026-08-01 01:00")]]
        h = read_history("workflow_name,start_time,end_time,status\n" + "\n".join(rows))
        self.assertEqual(classify(h)[0].decision, "In scope")

    def test_invalid_start_blocks_approval(self):
        h = history([datetime(2026, 9, d, 3) for d in range(1, 10)] + ["bad date"])
        r = classify(h)[0]
        self.assertEqual(r.decision, "Unknown")
        self.assertEqual((r.run_count, r.valid_start_count), (10, 9))

    def test_all_invalid_workflow_is_retained(self):
        r = classify(history(["bad"]))[0]
        self.assertEqual((r.run_count, r.valid_start_count, r.decision), (1, 0, "Unknown"))

    def test_duplicate_starts_unknown(self):
        starts = sequence(60)
        self.assertEqual(result(starts + starts[:1]).decision, "Unknown")

    def test_missing_workflow_name_blocks_other_approvals(self):
        buf = "workflow_name,start_time,end_time,status\n,2026-09-01 03:00,,Succeeded\n"
        buf += "\n".join(f"job,2026-09-{d:02} 03:00,,Succeeded" for d in range(1, 10))
        self.assertEqual(classify(read_history(buf))[0].decision, "Unknown")

    def test_missing_headers_and_empty_input_rejected(self):
        for text in ("bad,headers\n", "workflow_name,start_time,end_time,status\n"):
            with self.assertRaises(ValueError):
                read_history(text)

    def test_offset_timestamps_reviewed(self):
        self.assertEqual(result(["2026-09-01 03:00:00+02:00"]).decision, "Unknown")

    def test_names_and_row_order_do_not_change_inference(self):
        starts = sequence(30)
        a = classify(history(starts, name="DAILY"))[0]
        b = classify(history(list(reversed(starts)), name="HOURLY"))[0]
        self.assertEqual((a.cadence, a.decision), (b.cadence, b.decision))


class ActualCSVTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = read_history(Path("data/run_history.csv").read_text())
        cls.results = {r.workflow: r for r in classify(cls.h)}

    def test_all_source_workflows_appear_once(self):
        self.assertEqual(len(self.results), 40)
        self.assertEqual(sum(r.run_count for r in self.results.values()), 1152)
        self.assertEqual(set(self.results), set(self.h.workflows))
        self.assertTrue(all(r.evidence and r.warnings for r in self.results.values()))

    def test_customer_examples_are_explained(self):
        for name in ("wf_SLS_ORDERS_INCR", "wf_INV_STOCK_HOURLY"):
            self.assertEqual(self.results[name].decision, "In scope")
            self.assertTrue(self.results[name].likely_retry_rows)
        self.assertEqual(self.results["wf_PAY_AUTH_HOURLY"].decision, "Too frequent")
        self.assertEqual(self.results["wf_WEB_CLICKS"].cadence, "Hourly")
        self.assertEqual(self.results["wf_LEGACY_SFTP_PULL"].decision, "In scope")
        self.assertTrue(any("inactivity" in w for w in self.results["wf_MKT_CAMPAIGNS"].warnings))

    def test_no_calendar_rule_invented_for_depreciation(self):
        self.assertEqual(self.results["wf_FIN_FA_DEPRECIATION"].decision, "Unknown")

    def test_original_vs_revised_thresholds_report_actual_changes(self):
        baseline = {r.workflow: r for r in classify(self.h, SPEC_POLICY)}
        # No aggregate 30/3/7 assertion: compare policies, not desired totals.
        changes = [(name, r.decision, baseline[name].decision) for name, r in self.results.items()
                   if r.decision != baseline[name].decision]
        self.assertEqual(changes, [])


if __name__ == "__main__":
    unittest.main()
