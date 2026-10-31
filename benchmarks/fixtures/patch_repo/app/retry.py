"""Retry scheduling."""


def retry_delays(base_seconds: float, attempts: int) -> list[float]:
    if base_seconds <= 0:
        raise ValueError("base_seconds must be positive")
    if attempts < 0:
        raise ValueError("attempts must be non-negative")
    return [base_seconds * (2**attempt) for attempt in range(1, attempts + 1)]
