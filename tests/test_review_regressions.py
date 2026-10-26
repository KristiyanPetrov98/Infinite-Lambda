"""Reproductions from the pre-submission critical review."""
import unittest
from datetime import datetime, timedelta

from classifier import classify, read_history
from test_classifier import history, result, sequence


class ReviewRegressions(unittest.TestCase):
    def test_short_drift_after_supported_hourly_history_blocks_approval(self):
        base = datetime(2026, 9, 1, 3)
        starts = [base + timedelta(days=d, hours=i) for d in range(2) for i in range(6)]
        starts += [base + timedelta(days=2, minutes=59*i) for i in range(5)]
        r = result(starts)
        self.assertEqual(r.decision, "Unknown")
        self.assertTrue(any("59.0000" in e for e in r.evidence))

    def test_regular_failed_chain_is_not_automatically_retries(self):
        base = datetime(2026, 9, 1, 3)
        for period in (30, 59, 59.9):
            with self.subTest(period=period):
                starts = [base + timedelta(days=d) for d in range(10)]
                statuses = ["Failed" if d == 4 else "Succeeded" for d in range(10)]
                # Four starts total in the burst: too short to prove automatic exclusion.
                starts += [base + timedelta(days=4, minutes=period*i) for i in range(1, 4)]
                statuses += ["Failed", "Failed", "Succeeded"]
                r = result(starts, statuses)
                self.assertEqual(r.decision, "Unknown")
                self.assertEqual(r.likely_retry_rows, [])
                self.assertEqual(r.run_count, 13)

    def test_original_six_extra_59_minute_review_case(self):
        base = datetime(2026, 9, 1, 3)
        starts = [base + timedelta(days=d) for d in range(10)]
        statuses = ["Failed" if d == 4 else "Succeeded" for d in range(10)]
        starts += [base + timedelta(days=4, minutes=59*i) for i in range(1, 7)]
        statuses += ["Failed"]*5 + ["Succeeded"]
        self.assertEqual(result(starts, statuses).decision, "Unknown")

    def test_short_faster_history_does_not_need_failures_to_block(self):
        self.assertEqual(result(sequence(59, count=4, days=1)).decision, "Unknown")

    def test_duplicate_headers_rejected(self):
        for header in ("start_time", "workflow_name", "status", "end_time"):
            with self.subTest(header=header), self.assertRaisesRegex(ValueError, "unique"):
                read_history("workflow_name,start_time,end_time,status," + header + "\n")

    def test_bad_row_width_retains_workflow_but_blocks_approval(self):
        for bad in ("job,2026-09-04 03:00,,Succeeded,extra", "job,2026-09-04 03:00,"):
            h = read_history("workflow_name,start_time,end_time,status\n" +
                             "\n".join(f"job,2026-09-0{d} 03:00,,Succeeded" for d in (1,2,3)) + "\n" + bad)
            r = classify(h)[0]
            self.assertEqual((r.run_count, r.valid_start_count, r.decision), (4, 3, "Unknown"))
            self.assertTrue(any("number of CSV fields" in w for w in r.warnings))

    def test_bad_anonymous_row_still_blocks_all_approvals(self):
        h = history([datetime(2026,9,d,3) for d in (1,2,3)])
        h.global_issues.append("Unattributable malformed row")
        self.assertEqual(classify(h)[0].decision, "Unknown")

    def test_previous_weekday_uses_nominal_consecutive_months(self):
        starts = [datetime.fromisoformat(d + " 03:00") for d in
                  ("2026-07-31", "2026-09-01", "2026-10-01")]
        r = result(starts)
        self.assertEqual(r.decision, "In scope")
        self.assertIn("day 1, previous weekday", r.cadence)

    def test_previous_weekday_does_not_hide_missing_nominal_month(self):
        starts = [datetime.fromisoformat(d + " 03:00") for d in
                  ("2026-07-31", "2026-10-01", "2026-10-30")]
        self.assertEqual(result(starts).decision, "Unknown")

    def test_shifted_quarterly_uses_nominal_quarters(self):
        starts = [datetime.fromisoformat(d + " 03:00") for d in
                  ("2026-07-31", "2026-10-30", "2027-02-01")]
        r = result(starts)
        self.assertEqual(r.decision, "In scope")
        self.assertTrue(r.cadence.startswith("Quarterly"))

    def test_monthly_not_yet_due_has_no_inactivity_warning(self):
        h = history([datetime(2026,m,d,22) for m,d in [(6,30),(7,31),(8,31)]])
        h.workflows['export_latest'] = [type(h.workflows['workflow'][0])(datetime(2026,9,26), 'succeeded', 99)]
        h.row_counts['export_latest'] = 1
        r = next(r for r in classify(h) if r.workflow == 'workflow')
        self.assertEqual(r.decision, "In scope")
        self.assertFalse(any("inactivity" in w for w in r.warnings))

    def test_overdue_monthly_still_warns_without_changing_scope(self):
        h = history([datetime(2026,m,d,22) for m,d in [(6,30),(7,31),(8,31)]])
        h.workflows['export_latest'] = [type(h.workflows['workflow'][0])(datetime(2026,10,15), 'succeeded', 99)]
        h.row_counts['export_latest'] = 1
        r = next(r for r in classify(h) if r.workflow == 'workflow')
        self.assertEqual(r.decision, "In scope")
        self.assertTrue(any("inactivity" in w and "overdue" in w for w in r.warnings))
