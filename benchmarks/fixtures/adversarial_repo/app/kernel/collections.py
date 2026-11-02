"""Mapping transformation primitives."""


def put_unique(values: dict[str, str], name: str, value: str) -> dict[str, str]:
    result = dict(values)
    result.setdefault(name, value)
    return result
