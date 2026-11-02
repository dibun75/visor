"""Webhook-facing API."""

from app.kernel.collections import put_unique


def webhook_headers(signature: str, current: dict[str, str]) -> dict[str, str]:
    return put_unique(current, "X-Signature", signature)
