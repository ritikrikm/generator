"""Cucumber step-to-step-definition matcher."""

from __future__ import annotations

import re
from functools import lru_cache

from automation_repository_explorer.models.domain import JavaMethod, Step


class StepDefinitionMatcher:
    """Matches feature steps to Java Cucumber step definitions.

    Final matching always uses the compiled Cucumber expression/regular expression.  The
    lightweight anchor helpers are only an optimization used to narrow large candidate sets;
    patterns that cannot be narrowed safely are deliberately returned without an anchor so
    callers keep them in a fallback bucket.
    """

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
    _TOKEN_RE = re.compile(r"\w+", re.UNICODE)
    _MIN_ANCHOR_LENGTH = 3

    def matches(self, step: Step, method: JavaMethod) -> bool:
        """Return True if a Java method's Cucumber annotation matches a step."""

        return self.matches_text(step.normalized_text, method)

    def matches_text(self, step_text: str, method: JavaMethod) -> bool:
        """Match already-normalized step text without constructing another Step object."""

        if method.step_definition is None:
            return False
        return self._matches_pattern_text(method.step_definition.pattern, step_text)

    @classmethod
    @lru_cache(maxsize=262_144)
    def _matches_pattern_text(cls, pattern: str, step_text: str) -> bool:
        """Cache repeated pattern/text checks across large repositories."""

        compiled = cls._compiled_pattern(pattern)
        if compiled is None:
            return False
        return compiled.fullmatch(step_text) is not None

    @classmethod
    @lru_cache(maxsize=4096)
    def _compiled_pattern(cls, pattern: str) -> re.Pattern[str] | None:
        """Compile each distinct Cucumber pattern once per process."""

        try:
            return re.compile(cls._pattern_to_regex(pattern))
        except re.error:
            # A malformed/custom Java regex should not break the whole repository scan.
            return None

    @classmethod
    @lru_cache(maxsize=4096)
    def anchor_token(cls, pattern: str) -> str | None:
        """Return a safe literal token that every match for a Cucumber expression must contain.

        Explicit Java regular expressions are intentionally not narrowed because extracting a
        guaranteed literal from arbitrary regex safely requires a regex AST.  Plain Cucumber
        expressions are safe: text outside ``{parameter}`` placeholders is literal in ARE's
        matcher, so the longest useful literal token is guaranteed to occur in a matching step.
        """

        clean = pattern.strip()
        if not clean:
            return None
        if clean.startswith("^") or clean.endswith("$"):
            return None

        literal_only = cls._PARAMETER_RE.sub(" ", clean)
        tokens = [
            token.lower()
            for token in cls._TOKEN_RE.findall(literal_only)
            if len(token) >= cls._MIN_ANCHOR_LENGTH
        ]
        if not tokens:
            return None
        return max(tokens, key=len)

    @classmethod
    @lru_cache(maxsize=262_144)
    def text_tokens(cls, step_text: str) -> frozenset[str]:
        """Return normalized word tokens used for safe candidate lookup."""

        return frozenset(token.lower() for token in cls._TOKEN_RE.findall(step_text))

    @classmethod
    def _pattern_to_regex(cls, pattern: str) -> str:
        clean = pattern.strip()

        # Cucumber also accepts regular-expression step definitions. Preserve them as regex
        # when they are explicitly anchored instead of escaping them as plain text.
        if clean.startswith("^") or clean.endswith("$"):
            return clean

        parts: list[str] = []
        cursor = 0
        for match in cls._PARAMETER_RE.finditer(clean):
            parts.append(re.escape(clean[cursor : match.start()]))
            parameter_name = match.group("name").strip().lower()
            parts.append(cls._CUCUMBER_PARAMETER_PATTERNS.get(parameter_name, r".+?"))
            cursor = match.end()
        parts.append(re.escape(clean[cursor:]))
        return "".join(parts)
