"""Invoice-facing API."""

from app.kernel.arithmetic import settle


def invoice_total(line_items: list[float]) -> float:
    return settle(sum(line_items))
