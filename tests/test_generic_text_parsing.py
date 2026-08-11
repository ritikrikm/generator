from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from automation_repository_explorer.parsers.feature_parser import FeatureParser
from automation_repository_explorer.parsers.property_parser import PropertyParser


class GenericTextParsingTests(unittest.TestCase):
    def test_properties_fall_back_from_utf8_to_windows_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "language_strings.properties"
            path.write_bytes("Greeting=Échéance\n".encode("cp1252"))

            result = PropertyParser().parse(path)

            self.assertEqual(result.items[0].key, "Greeting")
            self.assertEqual(result.items[0].value, "Échéance")
            self.assertTrue(result.warnings)
            self.assertIn("cp1252", result.warnings[0])

    def test_feature_skips_only_malformed_example_row(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.feature"
            path.write_text(
                """Feature: Generic parsing\n"
                "Scenario Outline: Example table\n"
                "  Given value <a>\n"
                "Examples:\n"
                "  | a | b |\n"
                "  | 1 |\n"
                "  | 2 | 3 |\n",
                encoding="utf-8",
            )

            result = FeatureParser().parse(path)

            self.assertEqual(len(result.items), 1)
            table = result.items[0].scenarios[0].examples[0]
            self.assertEqual(len(table.rows), 1)
            self.assertEqual(table.rows[0], {"a": "2", "b": "3"})
            self.assertTrue(result.warnings)
            self.assertIn("row skipped", result.warnings[0])

    def test_feature_table_preserves_escaped_pipe(self) -> None:
        row = r"| name | A\|B |"
        self.assertEqual(FeatureParser._split_table_row(row), ["name", "A|B"])


if __name__ == "__main__":
    unittest.main()
