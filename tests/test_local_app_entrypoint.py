"""Regression checks for the stable local ARE entrypoint."""

from automation_repository_explorer.local_app import ARELocalApp
from automation_repository_explorer.local_app_base import ARELocalApp as BaseARELocalApp


def test_public_local_app_keeps_base_behavior_and_adds_enhancements() -> None:
    assert issubclass(ARELocalApp, BaseARELocalApp)
    assert ARELocalApp is not BaseARELocalApp
