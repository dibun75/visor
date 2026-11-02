"""Numeric normalization primitives."""


def settle(value: float) -> float:
    return int(value * 100) / 100
