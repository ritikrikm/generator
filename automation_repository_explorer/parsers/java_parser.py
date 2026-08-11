"""Static parser for Java automation code."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from automation_repository_explorer.core.exceptions import ParserError
from automation_repository_explorer.models.domain import (
    JavaClass,
    JavaMethod,
    SourceLocation,
    StepDefinition,
)
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser

LOGGER = logging.getLogger(__name__)


class JavaParser(RepositoryParser[JavaClass]):
    """Parse Java classes, methods, annotations, calls, and string literals.

    The parser is intentionally deterministic and dependency-light. It uses stable static
    heuristics and exposes the same output model that a future tree-sitter adapter can fill.
    """

    _PACKAGE_RE = re.compile(r"^\s*package\s+(?P<package>[\w.]+)\s*;", re.MULTILINE)
    _IMPORT_RE = re.compile(r"^\s*import\s+(?P<import>[\w.*]+)\s*;", re.MULTILINE)
    _CLASS_RE = re.compile(
        r"\b(?P<kind>class|interface|enum)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
    )
    _ANNOTATION_RE = re.compile(
        r"@(?P<keyword>Given|When|Then|And|But)\s*\(\s*(?P<quote>\"|')(?P<pattern>.*?)(?P=quote)\s*\)",
        re.DOTALL,
    )
    _METHOD_RE = re.compile(
        r"(?P<prefix>(?:public|private|protected)\s+"
        r"(?:(?:static|final|synchronized)\s+)*)"
        r"(?P<return>[A-Za-z_][\w<>\[\].?,\s]*?)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
        r"\((?P<params>[^)]*)\)\s*(?:throws\s+[^{]+)?\{",
        re.MULTILINE,
    )
    _CALL_RE = re.compile(r"(?<!new\s)\b(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
    _STRING_RE = re.compile(r'"(?P<value>(?:\\.|[^"\\])*)"')
    _CONTROL_WORDS = frozenset(
        {
            "if",
            "for",
            "while",
            "switch",
            "catch",
            "return",
            "throw",
            "new",
            "super",
            "this",
            "try",
            "synchronized",
        }
    )

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".java"})

    def parse(self, file_path: Path) -> ParseResult[JavaClass]:
        LOGGER.debug("Parsing Java file %s", file_path)
        try:
            source = file_path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise ParserError(f"Unable to read Java file {file_path}") from exc

        package_match = self._PACKAGE_RE.search(source)
        package_name = package_match.group("package") if package_match else ""
        imports = tuple(match.group("import") for match in self._IMPORT_RE.finditer(source))

        class_match = self._CLASS_RE.search(source)
        if not class_match:
            return ParseResult(file_path=file_path, items=tuple())

        class_name = class_match.group("name")
        class_line = self._line_for_offset(source, class_match.start())
        methods = tuple(self._parse_methods(source, file_path))

        return ParseResult(
            file_path=file_path,
            items=(
                JavaClass(
                    name=class_name,
                    package=package_name,
                    imports=imports,
                    location=SourceLocation(file_path, class_line),
                    methods=methods,
                ),
            ),
        )

    def _parse_methods(self, source: str, file_path: Path) -> list[JavaMethod]:
        methods: list[JavaMethod] = []

        for match in self._METHOD_RE.finditer(source):
            body_start = match.end()
            body_end = self._find_matching_brace(source, body_start - 1)
            if body_end is None:
                continue

            method_source_start = self._annotation_start(source, match.start())
            annotation_text = source[method_source_start : match.start()]
            step_definition = self._parse_step_definition(annotation_text, source, file_path)
            method_body = source[body_start:body_end]
            method_line = self._line_for_offset(source, match.start())
            end_line = self._line_for_offset(source, body_end)
            method_name = match.group("name")

            calls = tuple(
                call.group("name")
                for call in self._CALL_RE.finditer(method_body)
                if call.group("name") not in self._CONTROL_WORDS and call.group("name") != method_name
            )
            string_literals = tuple(
                bytes(literal.group("value"), "utf-8").decode("unicode_escape")
                for literal in self._STRING_RE.finditer(method_body)
            )

            methods.append(
                JavaMethod(
                    name=method_name,
                    return_type=" ".join(match.group("return").split()),
                    parameters=tuple(self._parse_parameters(match.group("params"))),
                    location=SourceLocation(file_path, method_line),
                    end_line=end_line,
                    body=method_body,
                    calls=calls,
                    string_literals=string_literals,
                    step_definition=step_definition,
                )
            )

        return methods

    def _parse_step_definition(
        self,
        annotation_text: str,
        source: str,
        file_path: Path,
    ) -> StepDefinition | None:
        annotation_match = None
        for annotation_match in self._ANNOTATION_RE.finditer(annotation_text):
            pass
        if annotation_match is None:
            return None

        absolute_offset = source.find(annotation_match.group(0))
        line = self._line_for_offset(source, absolute_offset) if absolute_offset >= 0 else 1
        return StepDefinition(
            keyword=annotation_match.group("keyword"),
            pattern=annotation_match.group("pattern"),
            location=SourceLocation(file_path, line),
        )

    @staticmethod
    def _annotation_start(source: str, method_start: int) -> int:
        index = method_start
        while index > 0:
            previous_line_start = source.rfind("\n", 0, index - 1)
            line_start = previous_line_start + 1
            line = source[line_start:index].strip()
            if not line or line.startswith("@"):
                index = line_start
                continue
            return index
        return index

    @staticmethod
    def _find_matching_brace(source: str, open_brace_index: int) -> int | None:
        depth = 0
        in_string = False
        escaped = False
        for index in range(open_brace_index, len(source)):
            char = source[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        return None

    @staticmethod
    def _parse_parameters(params: str) -> list[str]:
        if not params.strip():
            return []
        result: list[str] = []
        for param in params.split(","):
            clean_param = " ".join(param.strip().split())
            if clean_param:
                result.append(clean_param)
        return result

    @staticmethod
    def _line_for_offset(source: str, offset: int) -> int:
        return source.count("\n", 0, offset) + 1
