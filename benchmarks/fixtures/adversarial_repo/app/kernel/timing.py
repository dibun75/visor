"""Time-series primitives."""


def span(base: float, count: int) -> list[float]:
    return [base * (2**offset) for offset in range(1, count + 1)]
