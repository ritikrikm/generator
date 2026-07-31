"""Cucumber step-to-step-definition matcher."""

from __future__ import annotations

import re

from automation_repository_explorer.models.domain import JavaMethod, Step


class StepDefinitionMatcher:
    """Matches feature steps to Java Cucumber step definitions."""

    def matches(self, step: Step, method: JavaMethod) -> bool:
        """Return True if a Java method's Cucumber annotation matches a step."""

        if method.step_definition is None:
            return False
        regex = self._pattern_to_regex(method.step_definition.pattern)
        return re.fullmatch(regex, step.normalized_text) is not None

    def _pattern_to_regex(self, pattern: str) -> str:
        clean = pattern.strip()
        if clean.startswith("^") or clean.endswith("$") or "(" in clean:
            return clean.strip("^$")

        regex = re.escape(clean)
        regex = regex.replace(r"\{string\}", r'"[^"]*"')
        regex = regex.replace(r"\{int\}", r"\d+")
        regex = regex.replace(r"\{float\}", r"\d+(?:\.\d+)?")
        return regex
