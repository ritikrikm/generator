"""Cucumber step matching backed by the official cucumber-expressions package."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import Any

from cucumber_expressions.expression import CucumberExpression
from cucumber_expressions.parameter_type_registry import ParameterTypeRegistry
from cucumber_expressions.regular_expression import RegularExpression

from automation_repository_explorer.models.domain import JavaMethod, Step


class StepMatchStatus(StrEnum):
    MATCH = "match"
    NO_MATCH = "no_match"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class StepMatchResult:
    status: StepMatchStatus
    reason: str = ""


class StepDefinitionMatcher:
    """Match Cucumber steps using Cucumber's own expression implementation."""

    _PARAMETER_RE = re.compile(r"\{[^{}]*\}")
    _TOKEN_RE = re.compile(r"\w+", re.UNICODE)
    _MIN_ANCHOR_LENGTH = 3

    def matches(self, step: Step, method: JavaMethod) -> bool:
        return (
            self.match_result_text(step.normalized_text, method).status
            == StepMatchStatus.MATCH
        )

    def matches_text(self, step_text: str, method: JavaMethod) -> bool:
        return self.match_result_text(step_text, method).status == StepMatchStatus.MATCH

    def match_result_text(
        self,
        step_text: str,
        method: JavaMethod,
    ) -> StepMatchResult:
        if method.step_definition is None:
            return StepMatchResult(StepMatchStatus.NO_MATCH)
        return self._match_pattern(method.step_definition.pattern, step_text)

    @classmethod
    @lru_cache(maxsize=262_144)
    def _match_pattern(cls, pattern: str, step_text: str) -> StepMatchResult:
        try:
            expression = cls._expression(pattern)
            if expression is None:
                return StepMatchResult(
                    StepMatchStatus.UNRESOLVED,
                    "Cucumber expression could not be constructed.",
                )
            status = (
                StepMatchStatus.MATCH
                if expression.match(step_text) is not None
                else StepMatchStatus.NO_MATCH
            )
            return StepMatchResult(status)
        except Exception as exc:
            return StepMatchResult(
                StepMatchStatus.UNRESOLVED,
                f"{exc.__class__.__name__}: {exc}",
            )

    @classmethod
    @lru_cache(maxsize=4096)
    def _expression(cls, pattern: str) -> Any | None:
        clean = pattern.strip()
        if not clean:
            return None
        registry = ParameterTypeRegistry()
        if clean.startswith("^") or clean.endswith("$"):
            return RegularExpression(clean, registry)
        return CucumberExpression(clean, registry)

    @classmethod
    @lru_cache(maxsize=4096)
    def anchor_token(cls, pattern: str) -> str | None:
        """Return only anchors that are guaranteed under Cucumber semantics."""

        clean = pattern.strip()
        if not clean:
            return None
        if clean.startswith("^") or clean.endswith("$"):
            return None

        # Alternatives, optionals and escapes can make an apparent literal token optional.
        # Keep these expressions in the full-match fallback bucket rather than risk false negatives.
        if any(symbol in clean for symbol in ("/", "(", ")", "\\")):
            return None

        literal_only = cls._PARAMETER_RE.sub(" ", clean)
        tokens = [
            token.lower()
            for token in cls._TOKEN_RE.findall(literal_only)
            if len(token) >= cls._MIN_ANCHOR_LENGTH
        ]
        return max(tokens, key=len) if tokens else None

    @classmethod
    @lru_cache(maxsize=262_144)
    def text_tokens(cls, step_text: str) -> frozenset[str]:
        return frozenset(
            token.lower() for token in cls._TOKEN_RE.findall(step_text)
        )
