from pathlib import Path

from automation_repository_explorer.parsers.csv_parser import CsvParser
from automation_repository_explorer.parsers.ini_parser import IniParser
from automation_repository_explorer.parsers.json_parser import JsonParser
from automation_repository_explorer.parsers.property_parser import PropertyParser
from automation_repository_explorer.parsers.toml_parser import TomlParser
from automation_repository_explorer.parsers.xml_parser import XmlParser
from automation_repository_explorer.parsers.yaml_parser import YamlParser


def test_properties_uses_java_escaping(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.properties"
    file_path.write_bytes(b"hello\\ world=some\\ value\n")
    entry = PropertyParser().parse(file_path).items[0]
    assert entry.key == "hello world"
    assert entry.value == "some value"


def test_structured_parsers_emit_semantic_entries(tmp_path: Path) -> None:
    json_file = tmp_path / "a.json"
    json_file.write_text('{"user":{"name":"R"}}', encoding="utf-8")
    assert JsonParser().parse(json_file).items[0].key == "$.user.name"

    yaml_file = tmp_path / "a.yaml"
    yaml_file.write_text("user:\n  name: R\n", encoding="utf-8")
    assert YamlParser().parse(yaml_file).items[0].key == "$.user.name"

    xml_file = tmp_path / "a.xml"
    xml_file.write_text("<root><name>R</name></root>", encoding="utf-8")
    assert XmlParser().parse(xml_file).items[0].key.endswith("/name[1]")

    csv_file = tmp_path / "a.csv"
    csv_file.write_text("name\nR\n", encoding="utf-8")
    assert CsvParser().parse(csv_file).items[0].key == "$row[0].name"

    toml_file = tmp_path / "a.toml"
    toml_file.write_text("[user]\nname='R'\n", encoding="utf-8")
    assert TomlParser().parse(toml_file).items[0].key == "$.user.name"

    ini_file = tmp_path / "a.ini"
    ini_file.write_text("[user]\nname=R\n", encoding="utf-8")
    assert IniParser().parse(ini_file).items[0].key == "user.name"
