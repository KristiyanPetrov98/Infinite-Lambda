"""Actual Streamlit interactions; requires the optional interface dependency."""
import importlib.util
import os
import tempfile
import unittest
from unittest.mock import patch


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit not installed; engine tests remain available")
class AppTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {"FLOWLINE_DB": self.temp.name + "/review.sqlite3"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.AppTest = AppTest
        self.app = AppTest.from_file("app.py", default_timeout=30).run()

    def test_initial_table_contains_every_workflow(self):
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)
        self.assertEqual(len(self.app.dataframe[0].value), 40)
        self.assertEqual(sum(int(m.value) for m in self.app.metric), 40)

    def test_required_fields_reject_empty_correction(self):
        self.app.button[0].click().run()
        self.assertIn("reason and supporting source", self.app.error[0].value)

    def test_correction_persists_in_new_app_and_preserves_original(self):
        self.app.selectbox[0].select("wf_PAY_AUTH_HOURLY").run()
        self.app.selectbox[1].select("Fixed interval (minutes)")
        self.app.text_input[0].set_value("59.9")
        self.app.text_area[0].set_value("Confirmed in scheduler")
        self.app.text_input[1].set_value("Scheduler job PAY_AUTH")
        self.app.text_input[2].set_value("Test reviewer")
        self.app.button[0].click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)
        reopened = self.AppTest.from_file("app.py", default_timeout=30).run()
        row = reopened.dataframe[0].value.set_index("Workflow").loc["wf_PAY_AUTH_HOURLY"]
        self.assertEqual(row["Frequency"], "Every 59.9 minutes")
        self.assertEqual(row["Decision"], "Too frequent")
        self.assertEqual(row["Original decision"], "Too frequent")
        self.assertEqual(row["Provenance"], "reviewer-supplied")
        reopened.selectbox[0].select("wf_PAY_AUTH_HOURLY").run()
        reopened.selectbox[1].select("Fixed interval (minutes)")
        reopened.text_input[0].set_value("60")
        reopened.text_area[0].set_value("Corrected scheduler setting")
        reopened.text_input[1].set_value("Ticket PAY-2")
        reopened.button[0].click().run()
        row = reopened.dataframe[0].value.set_index("Workflow").loc["wf_PAY_AUTH_HOURLY"]
        self.assertEqual((row["Decision"], row["Original decision"]), ("In scope", "Too frequent"))
        audit = reopened.dataframe[-1].value
        self.assertEqual(len(audit), 2)
        self.assertEqual(list(audit["decision"]), ["Too frequent", "In scope"])

    def test_engineer_filter(self):
        self.app.radio[0].set_value("Engineer review").run()
        self.assertFalse(self.app.exception)
        self.assertTrue(all(self.app.dataframe[0].value["Decision"] != "In scope"))


if __name__ == "__main__":
    unittest.main()
