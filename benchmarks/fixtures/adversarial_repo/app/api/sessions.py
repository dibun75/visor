"""Session-facing API."""

from app.kernel.projection import project


def session_permissions(previous: list[str], current: list[str]) -> list[str]:
    return project(previous, current)
