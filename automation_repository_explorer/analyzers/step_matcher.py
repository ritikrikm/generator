"""Cucumber step-to-step-definition matcher."""

from __future__ import annotations

import re

from automation_repository_explorer.models.domain import JavaMethod, Step


class StepDefinitionMatcher:
    """Matches feature steps to Java Cucumber step definitions."""

    _CUCUMBER_PARAMETER_PATTERNS = {
        "string": r'(?:(?:"[^"\\]*(?:\\.[^"\\]*)*")|(?:\'[^\'\\]*(?:\\.[^\'\\]*)*\'))',
        "int": r"[-+]?\d+",
        "float": r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)",
        "double": r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)",
        "bigdecimal": r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)",
        "biginteger": r"[-+]?\d+",
        "byte": r"[-+]?\d+",
        "short": r"[-+]?\d+",
        "long": r"[-+]?\d+",
        "word": r"[^\s]+",
        "boolean": r"(?:true|false)",
        "": r".+?",
    }
    _PARAMETER_RE = re.compile(r"\{(?P<name>[^{}]*)\}")

    def matches(self, step: Step, method: JavaMethod) -> bool:
        """Return True if a Java method's Cucumber annotation matches a step."""

        if method.step_definition is None:
            return False
        regex = self._pattern_to_regex(method.step_definition.pattern)
        try:
            return re.fullmatch(regex, step.normalized_text) is not None
        except re.error:
            # A malformed/custom Java regex should not break the whole repository scan.
            return False

    def _pattern_to_regex(self, pattern: str) -> str:
        clean = pattern.strip()

        # Cucumber also accepts regular-expression step definitions. Preserve them as regex
        # when they are explicitly anchored instead of escaping them as plain text.
        if clean.startswith("^") or clean.endswith("$"):
            return clean

        parts: list[str] = []
        cursor = 0
        for match in self._PARAMETER_RE.finditer(clean):
            parts.append(re.escape(clean[cursor : match.start()]))
            parameter_name = match.group("name").strip().lower()
            parts.append(self._CUCUMBER_PARAMETER_PATTERNS.get(parameter_name, r".+?"))
            cursor = match.end()
        parts.append(re.escape(clean[cursor:]))
        return "".join(parts)
