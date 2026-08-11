from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_repository_explorer.parsers.feature_parser import FeatureParser


class FeatureParserTest(unittest.TestCase):
    def test_parses_feature_scenarios_steps_examples_and_tags(self) -> None:
        file_path = Path("sample_repo/huntress_MMSRB/src/test/resources/features/MMSRBHome.feature")

        result = FeatureParser().parse(file_path)

        feature = result.items[0]
        self.assertTrue(feature.name)
        self.assertGreater(len(feature.scenarios), 0)
        self.assertGreater(sum(len(scenario.steps) for scenario in feature.scenarios), 0)

    def test_background_is_applied_without_folder_or_file_naming_assumptions(self) -> None:
        source = """
            Feature: Generic layout

              Background:
                Given a user is authenticated

              Scenario: First flow
                When the user opens a lead
                Then the lead is visible

              Scenario: Second flow
                When the user opens an account
                Then the account is visible
        """
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "anything.feature"
            file_path.write_text(source, encoding="utf-8")

            feature = FeatureParser().parse(file_path).items[0]

        self.assertEqual(len(feature.scenarios), 2)
        self.assertEqual(feature.scenarios[0].steps[0].text, "a user is authenticated")
        self.assertEqual(feature.scenarios[1].steps[0].text, "a user is authenticated")

    def test_rule_background_is_applied_only_inside_current_rule(self) -> None:
        source = """
            Feature: Rules
              Background:
                Given global setup

              Rule: Retail
                Background:
                  Given retail setup

                Scenario: Retail flow
                  When retail action
                  Then retail result

              Rule: Mortgage
                Scenario: Mortgage flow
                  When mortgage action
                  Then mortgage result
        """
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "rules.feature"
            file_path.write_text(source, encoding="utf-8")

            feature = FeatureParser().parse(file_path).items[0]

        retail_steps = [step.text for step in feature.scenarios[0].steps]
        mortgage_steps = [step.text for step in feature.scenarios[1].steps]
        self.assertEqual(retail_steps[:2], ["global setup", "retail setup"])
        self.assertEqual(mortgage_steps[0], "global setup")
        self.assertNotIn("retail setup", mortgage_steps)
