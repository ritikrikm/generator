from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.parsers.property_parser import PropertyParser


class PropertyParserTest(unittest.TestCase):
    def test_extracts_key_value_and_line_number(self) -> None:
        file_path = Path(
            "sample_repo/huntress_MMSRB/src/test/resources/mfa/ObjectRepository.Selenium/"
            "SeleniumObjectRepo.properties"
        )

        result = PropertyParser().parse(file_path)

        keys = {entry.key: entry for entry in result.items}
        self.assertEqual(
            keys["MMSRB.Notification.NewUncalledGICMaturityLeads"].value,
            "//a[normalize-space()='New, Uncalled GIC Maturity Leads']",
        )
        self.assertEqual(keys["MMSRB.Notification.NewUncalledGICMaturityLeads"].location.line, 7)
