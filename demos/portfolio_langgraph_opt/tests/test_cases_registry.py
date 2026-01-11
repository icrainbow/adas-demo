import unittest
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent  # demos/portfolio_langgraph_opt
sys.path.insert(0, str(PROJECT_ROOT))

from service.case_service import discover_cases, get_default_case_id, validate_case_id
from service.agent_service import list_agents


class TestCaseRegistry(unittest.TestCase):
    def test_discover_cases_contains_kyc_and_legal(self):
        cases = discover_cases()
        self.assertIn("kyc_case", cases)
        self.assertIn("legal_case", cases)

    def test_default_case_is_kyc(self):
        self.assertEqual(get_default_case_id(), "kyc_case")

    def test_list_agents_kyc_returns_dict(self):
        data = list_agents("kyc_case")
        self.assertIsInstance(data, dict)
        self.assertIn("agents", data)
        self.assertIn("errors", data)

    def test_case_id_validation(self):
        self.assertTrue(validate_case_id("kyc_case"))
        self.assertFalse(validate_case_id("../evil"))
    
    def test_config_js_calls_render_case_selector(self):
        """Ensure config.js contains renderCaseSelector and calls it during init."""
        js_path = PROJECT_ROOT / "ui" / "config.js"
        text = js_path.read_text(encoding="utf-8")
        self.assertIn("function renderCaseSelector", text)
        # Must be called at init:
        self.assertTrue(
            "renderCaseSelector();" in text or "await renderCaseSelector()" in text,
            "config.js must call renderCaseSelector() during DOMContentLoaded init"
        )
        self.assertIn("loadCases", text)


if __name__ == "__main__":
    unittest.main()
