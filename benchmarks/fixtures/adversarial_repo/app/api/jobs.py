"""Background-job API."""

from app.kernel.timing import span


def job_retry_schedule(base_seconds: float, attempts: int) -> list[float]:
    return span(base_seconds, attempts)
