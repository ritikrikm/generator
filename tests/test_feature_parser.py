from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.parsers.feature_parser import FeatureParser


class FeatureParserTest(unittest.TestCase):
    def test_extracts_scenario_outline_steps_examples(self) -> None:
        file_path = Path(
            "sample_repo/huntress_MMSRB/src/test/features/RetailRB/functional/home/"
            "RetailRBHomeNotification.feature"
        )

        result = FeatureParser().parse(file_path)

        feature = result.items[0]
        self.assertEqual(feature.name, "Retail RB Home Notifications")
        self.assertEqual(feature.tags, ())
        self.assertEqual(len(feature.scenarios), 2)

        scenario = feature.scenarios[0]
        self.assertEqual(
            scenario.name,
            'As "<SSOUser>" Home Page Notification for <Report> '
            "Verifying maturity notifications are linked",
        )
        self.assertEqual(scenario.tags, ())
        self.assertEqual(len(scenario.steps), 4)
        self.assertEqual(scenario.steps[2].keyword, "Then")
        self.assertEqual(
            scenario.steps[2].text,
            '"User" clicks on "<Notification>" notification',
        )
        self.assertEqual(len(scenario.examples), 1)
        self.assertEqual(
            scenario.examples[0].headers,
            ("SSOUser", "Report", "Notification", "ListView"),
        )
        self.assertEqual(
            scenario.examples[0].rows[0]["Notification"],
            "MMSRB.Notification.NewUncalledGICMaturityLeads",
        )
