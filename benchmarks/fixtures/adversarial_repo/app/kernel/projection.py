"""Snapshot projection primitives."""


def project(previous: list[str], current: list[str]) -> list[str]:
    merged = set(previous)
    merged.update(current)
    return sorted(merged)
