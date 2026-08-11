from pathlib import Path

from automation_repository_explorer.analyzers.step_matcher import StepDefinitionMatcher, StepMatchStatus
from automation_repository_explorer.models.domain import JavaMethod, SourceLocation, StepDefinition


def _method(pattern: str) -> JavaMethod:
    path = Path("Steps.java")
    return JavaMethod(
        name="step", return_type="void", parameters=(), location=SourceLocation(path, 10),
        end_line=12, body="", calls=(), string_literals=(),
        step_definition=StepDefinition(keyword="Then", pattern=pattern, location=SourceLocation(path, 9)),
    )


def test_cucumber_alternative_matches_each_official_alternative() -> None:
    matcher = StepDefinitionMatcher()
    method = _method("{string} Should be redirected to Lead/Opportunity details page")
    assert matcher.match_result_text('"User" Should be redirected to Lead details page', method).status == StepMatchStatus.MATCH
    assert matcher.match_result_text('"User" Should be redirected to Opportunity details page', method).status == StepMatchStatus.MATCH
    assert matcher.anchor_token(method.step_definition.pattern) is None


def test_cucumber_optional_text_uses_official_semantics() -> None:
    matcher = StepDefinitionMatcher()
    method = _method("I have cucumber(s)")
    assert matcher.matches_text("I have cucumber", method)
    assert matcher.matches_text("I have cucumbers", method)
