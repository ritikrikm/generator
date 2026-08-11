"""Static parser for Java automation code."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from automation_repository_explorer.core.exceptions import ParserError
from automation_repository_explorer.core.text_reader import read_repository_text
from automation_repository_explorer.models.domain import (
    JavaClass,
    JavaMethod,
    SourceLocation,
    StepDefinition,
)
from automation_repository_explorer.parsers.base import ParseResult, RepositoryParser

LOGGER = logging.getLogger(__name__)


class JavaParser(RepositoryParser[JavaClass]):
    """Parse Java automation classes without relying on folder or class naming conventions.

    The parser is deterministic and dependency-light. Discovery is based on Java syntax and
    content, so files can live at any directory depth and classes do not need names such as
    ``Page``, ``Steps`` or ``Wrapper`` to be indexed.
    """

    _PACKAGE_RE = re.compile(r"^\s*package\s+(?P<package>[\w.]+)\s*;", re.MULTILINE)
    _IMPORT_RE = re.compile(
        r"^\s*import\s+(?:static\s+)?(?P<import>[\w.*]+)\s*;",
        re.MULTILINE,
    )
    _CLASS_RE = re.compile(
        r"\b(?P<kind>class|interface|enum|record)\s+"
        r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b"
    )
    _ANNOTATION_RE = re.compile(
        r'@(?:[A-Za-z_][\w$]*\.)*'
        r'(?P<keyword>Given|When|Then|And|But)\s*\(\s*"'
        r'(?P<pattern>(?:\\.|[^"\\])*)"\s*\)',
        re.DOTALL,
    )
    _METHOD_RE = re.compile(
        r"(?<![\w$.])"
        r"(?P<prefix>(?:(?:public|protected|private|static|final|abstract|synchronized|native|"
        r"strictfp|default)\s+)*)"
        r"(?:<[^>{};]+>\s+)?"
        r"(?P<return>[A-Za-z_$][\w$<>\[\].?,\s&]*)\s+"
        r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*"
        r"\((?P<params>[^()]*)\)\s*"
        r"(?:throws\s+[^{;]+)?\{",
        re.MULTILINE,
    )
    _CALL_RE = re.compile(
        r"(?<!\bnew\s)"
        r"(?:(?P<receiver>[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*\.)?"
        r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*\("
    )
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
            "assert",
        }
    )
    _NON_CLASS_JAVA_FILES = frozenset({"package-info.java", "module-info.java"})

    @property
    def supported_extensions(self) -> frozenset[str]:
        return frozenset({".java"})

    def parse(self, file_path: Path) -> ParseResult[JavaClass]:
        LOGGER.debug("Parsing Java file %s", file_path)
        read_result = read_repository_text(file_path)
        source = read_result.text
        warnings: tuple[str, ...] = ()
        if read_result.used_fallback:
            warnings = (
                f"UTF-8 decoding failed; parsed successfully using {read_result.encoding}.",
            )

        package_match = self._PACKAGE_RE.search(source)
        package_name = package_match.group("package") if package_match else ""
        imports = tuple(match.group("import") for match in self._IMPORT_RE.finditer(source))

        class_match = self._CLASS_RE.search(source)
        if not class_match:
            if file_path.name.lower() in self._NON_CLASS_JAVA_FILES:
                return ParseResult(file_path=file_path, items=tuple(), warnings=warnings)
            raise ParserError(f"No Java class/interface/enum/record declaration found in {file_path}")

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
            warnings=warnings,
        )

    def _parse_methods(self, source: str, file_path: Path) -> list[JavaMethod]:
        methods: list[JavaMethod] = []

        for match in self._METHOD_RE.finditer(source):
            if not self._looks_like_method_declaration(source, match.start()):
                continue

            body_start = match.end()
            body_end = self._find_matching_brace(source, body_start - 1)
            if body_end is None:
                LOGGER.warning(
                    "Unable to match method body in %s near line %s",
                    file_path,
                    self._line_for_offset(source, match.start()),
                )
                continue

            method_source_start = self._annotation_start(source, match.start())
            annotation_text = source[method_source_start : match.start()]
            step_definition = self._parse_step_definition(
                annotation_text,
                source,
                file_path,
                annotation_base_offset=method_source_start,
            )
            method_body = source[body_start:body_end]
            method_line = self._line_for_offset(source, match.start())
            end_line = self._line_for_offset(source, body_end)
            method_name = match.group("name")

            call_matches = tuple(
                call
                for call in self._CALL_RE.finditer(method_body)
                if call.group("name") not in self._CONTROL_WORDS
                and not (
                    call.group("name") == method_name
                    and call.group("receiver") in {None, "this"}
                )
            )
            calls = tuple(call.group("name") for call in call_matches)
            call_expressions = tuple(self._format_call(call) for call in call_matches)
            string_literals = tuple(
                self._decode_java_string(literal.group("value"))
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
                    call_expressions=call_expressions,
                )
            )

        return methods

    def _parse_step_definition(
        self,
        annotation_text: str,
        source: str,
        file_path: Path,
        annotation_base_offset: int,
    ) -> StepDefinition | None:
        annotation_match = None
        for annotation_match in self._ANNOTATION_RE.finditer(annotation_text):
            pass
        if annotation_match is None:
            return None

        absolute_offset = annotation_base_offset + annotation_match.start()
        line = self._line_for_offset(source, absolute_offset)
        return StepDefinition(
            keyword=annotation_match.group("keyword"),
            pattern=self._decode_java_string(annotation_match.group("pattern")),
            location=SourceLocation(file_path, line),
        )

    @staticmethod
    def _format_call(match: re.Match[str]) -> str:
        receiver = match.group("receiver")
        name = match.group("name")
        return f"{receiver}.{name}" if receiver else name

    @staticmethod
    def _looks_like_method_declaration(source: str, start: int) -> bool:
        line_start = source.rfind("\n", 0, start) + 1
        prefix = source[line_start:start].strip()
        if not prefix:
            return True
        if prefix.startswith("@"):
            return True
        return prefix.endswith(("{", "}", ";"))

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
        in_char = False
        in_line_comment = False
        in_block_comment = False
        escaped = False
        index = open_brace_index

        while index < len(source):
            char = source[index]
            next_char = source[index + 1] if index + 1 < len(source) else ""

            if in_line_comment:
                if char == "\n":
                    in_line_comment = False
                index += 1
                continue
            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    index += 2
                    continue
                index += 1
                continue
            if in_string or in_char:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif in_string and char == '"':
                    in_string = False
                elif in_char and char == "'":
                    in_char = False
                index += 1
                continue

            if char == "/" and next_char == "/":
                in_line_comment = True
                index += 2
                continue
            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue
            if char == '"':
                in_string = True
                index += 1
                continue
            if char == "'":
                in_char = True
                index += 1
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
            index += 1
        return None

    @staticmethod
    def _parse_parameters(params: str) -> list[str]:
        if not params.strip():
            return []
        result: list[str] = []
        current: list[str] = []
        generic_depth = 0
        annotation_depth = 0
        for char in params:
            if char == "<":
                generic_depth += 1
            elif char == ">" and generic_depth:
                generic_depth -= 1
            elif char == "(":
                annotation_depth += 1
            elif char == ")" and annotation_depth:
                annotation_depth -= 1
            if char == "," and generic_depth == 0 and annotation_depth == 0:
                clean_param = " ".join("".join(current).strip().split())
                if clean_param:
                    result.append(clean_param)
                current = []
                continue
            current.append(char)
        clean_param = " ".join("".join(current).strip().split())
        if clean_param:
            result.append(clean_param)
        return result

    @staticmethod
    def _decode_java_string(value: str) -> str:
        try:
            return bytes(value, "utf-8").decode("unicode_escape")
        except UnicodeDecodeError:
            return value

    @staticmethod
    def _line_for_offset(source: str, offset: int) -> int:
        return source.count("\n", 0, offset) + 1
