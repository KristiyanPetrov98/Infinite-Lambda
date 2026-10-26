import tempfile
import unittest
from pathlib import Path

from classifier import Result
from corrections import CorrectionStore, corrected_policy, dataset_id


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "review.sqlite3"
        self.store = CorrectionStore(self.path)
        self.result = Result("example", "Hourly", "In scope", 24, 24, None, None)
        self.dataset = dataset_id(b"example dataset")
        self.addCleanup(self.temp.cleanup)

    def append(self, **kwargs):
        args = dict(dataset=self.dataset, result=self.result, frequency="Fixed interval (minutes)",
                    minutes="30", reason="Scheduler shows updated cadence", source="Ticket FLOW-123", reviewer="Reviewer")
        args.update(kwargs)
        return self.store.append(**args)

    def test_restart_preserves_original_and_every_correction(self):
        first = self.append()
        second = self.append(minutes="60", reason="Ticket confirms hourly")
        reopened = CorrectionStore(self.path)
        review = reopened.review(self.dataset, self.result)
        self.assertEqual(review["original"]["decision"], "In scope")
        self.assertEqual([c["decision"] for c in review["corrections"]], ["Too frequent", "In scope"])
        self.assertEqual(review["effective"]["id"], second["id"])
        self.assertGreater(second["id"], first["id"])
        self.assertEqual(review["effective"]["provenance"], "reviewer-supplied")
        self.assertEqual(review["effective"]["source"], "Ticket FLOW-123")
        self.assertIn("+00:00", review["effective"]["timestamp"])

    def test_same_policy_on_original_fast_and_corrected_fast(self):
        self.result.decision = "Too frequent"
        self.assertEqual(self.append(minutes="59.9999999999999999999")["decision"], "Too frequent")
        self.assertEqual(self.append(minutes="60")["decision"], "In scope")

    def test_requires_reason_and_supporting_source(self):
        for kwargs in ({"reason": " "}, {"source": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.append(**kwargs)
        self.assertEqual(self.store.history(self.dataset, self.result), [])

    def test_corrections_never_leak_between_datasets(self):
        self.append()
        self.assertEqual(self.store.history(dataset_id(b"other"), self.result), [])

    def test_original_never_overwritten(self):
        self.append()
        self.result.decision = "Unknown"
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            self.append()
        self.assertEqual(self.store.original(self.dataset, self.result)["decision"], "In scope")

    def test_reviewer_optional_and_unknown_supported(self):
        correction = self.append(frequency="Unknown", reviewer="")
        self.assertEqual(correction["decision"], "Unknown")
        self.assertIsNone(correction["reviewer"])

    def test_all_named_calendar_frequencies_follow_policy(self):
        for f in ("Daily", "Weekdays (Mon–Fri)", "Weekly", "Fortnightly", "Twice monthly", "Monthly", "Quarterly"):
            self.assertEqual(corrected_policy(f)[1], "In scope")

    def test_invalid_intervals_rejected(self):
        for value in ("", "nonsense", "0", "-30", "NaN", "Infinity", "-Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                corrected_policy("Fixed interval (minutes)", value)

    def test_engine_version_scopes_history(self):
        self.append()
        self.result.engine_version = "next"
        self.assertEqual(self.store.history(self.dataset, self.result), [])


if __name__ == "__main__":
    unittest.main()
