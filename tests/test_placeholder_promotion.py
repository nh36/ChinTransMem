import unittest
from scripts.qc_corpus import run_source_traceability_checks


class PlaceholderPromotionTests(unittest.TestCase):
    def test_placeholder_keys_exist_and_are_lists(self):
        issues = run_source_traceability_checks('shiji')
        self.assertIn('placeholder_sources_in_active_sections', issues)
        self.assertIn('placeholder_sources_in_blocked_sections', issues)
        self.assertIsInstance(issues['placeholder_sources_in_active_sections'], list)
        self.assertIsInstance(issues['placeholder_sources_in_blocked_sections'], list)


if __name__ == '__main__':
    unittest.main()
