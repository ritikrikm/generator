from __future__ import annotations

import tempfile
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

    def test_parses_package_private_methods_and_fully_qualified_cucumber_annotations(self) -> None:
        source = """
            package team.any.structure;

            class CustomerJourney {
                @io.cucumber.java.en.Given("a customer with {word} status")
                void createCustomer(String status) {
                    helper.createCustomer(status);
                }
            }
        """
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "Anything.java"
            file_path.write_text(source, encoding="utf-8")

            result = JavaParser().parse(file_path)

        java_class = result.items[0]
        self.assertEqual(java_class.name, "CustomerJourney")
        self.assertEqual(len(java_class.methods), 1)
        method = java_class.methods[0]
        self.assertEqual(method.name, "createCustomer")
        self.assertEqual(method.calls, ("createCustomer",))
        self.assertEqual(method.call_expressions, ("helper.createCustomer",))
        self.assertIsNotNone(method.step_definition)
        assert method.step_definition is not None
        self.assertEqual(method.step_definition.pattern, "a customer with {word} status")

    def test_keeps_simple_calls_for_compatibility_and_richer_receiver_calls_for_resolution(self) -> None:
        source = """
            class ArbitraryName {
                public void open() {
                    ui.click();
                    BrowserActions.waitUntilReady();
                }
            }
        """
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "NoConvention.java"
            file_path.write_text(source, encoding="utf-8")

            method = JavaParser().parse(file_path).items[0].methods[0]

        self.assertEqual(method.calls, ("click", "waitUntilReady"))
        self.assertEqual(method.call_expressions, ("ui.click", "BrowserActions.waitUntilReady"))

    def test_parses_methods_even_when_team_formats_class_on_one_line(self) -> None:
        source = "class Compact { public void open() { helper.go(); } }"
        with tempfile.TemporaryDirectory() as directory:
            file_path = Path(directory) / "Compact.java"
            file_path.write_text(source, encoding="utf-8")
            java_class = JavaParser().parse(file_path).items[0]

        self.assertEqual([method.name for method in java_class.methods], ["open"])
        self.assertEqual(java_class.methods[0].calls, ("go",))
