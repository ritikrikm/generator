from __future__ import annotations

import unittest
from pathlib import Path

from automation_repository_explorer.parsers.java_parser import JavaParser


class JavaParserTest(unittest.TestCase):
    def test_extracts_class_methods_step_annotations_and_calls(self) -> None:
        file_path = Path(
            "sample_repo/huntress_MMSRB/src/test/stepDefs/com/td/stepdefs/MMSRB/home/"
            "MMSRBHomePageStepDefs.java"
        )

        result = JavaParser().parse(file_path)

        java_class = result.items[0]
        self.assertEqual(java_class.name, "MMSRBHomePageStepDefs")
        self.assertEqual(java_class.package, "com.td.stepdefs.MMSRB.home")
        self.assertEqual(len(java_class.methods), 7)

        then_method = next(method for method in java_class.methods if method.name == "clicksOnNotification")
        self.assertIsNotNone(then_method.step_definition)
        assert then_method.step_definition is not None
        self.assertEqual(then_method.step_definition.keyword, "Then")
        self.assertEqual(
            then_method.step_definition.pattern,
            "{string} clicks on {string} notification",
        )
        self.assertIn("clickOnSpecificNotification", then_method.calls)
        self.assertEqual(then_method.parameters, ("String group", "String notification"))
