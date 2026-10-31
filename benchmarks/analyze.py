#!/usr/bin/env python3
"""Summarize reproducible V.I.S.O.R. benchmark records."""

from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20261031


def _json_lines(value: str) -> list[dict[str, Any]]:
    events = []
    for line in value.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def extract_answer(record: dict[str, Any]) -> str:
    stdout = record.get("stdout", "")
    if record["agent"] == "codex":
        answers = [
            event["item"].get("text", "")
            for event in _json_lines(stdout)
            if event.get("type") == "item.completed"
            and event.get("item", {}).get("type") == "agent_message"
        ]
        return answers[-1] if answers else ""
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return ""
    return payload.get("result", "") if isinstance(payload, dict) else ""


def extract_usage(record: dict[str, Any]) -> dict[str, int | float]:
    stdout = record.get("stdout", "")
    if record["agent"] == "codex":
        usages = [
            event.get("usage", {})
            for event in _json_lines(stdout)
            if event.get("type") == "turn.completed"
        ]
        usage = usages[-1] if usages else {}
        return {
            "input_tokens": int(usage.get("input_tokens", 0)),
            "cached_input_tokens": int(usage.get("cached_input_tokens", 0)),
            "cache_creation_input_tokens": int(
                usage.get("cache_write_input_tokens", 0)
            ),
            "output_tokens": int(usage.get("output_tokens", 0)),
            "cost_usd": 0.0,
        }
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {}
    usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0)),
        "cached_input_tokens": int(usage.get("cache_read_input_tokens", 0)),
        "cache_creation_input_tokens": int(usage.get("cache_creation_input_tokens", 0)),
        "output_tokens": int(usage.get("output_tokens", 0)),
        "cost_usd": float(payload.get("total_cost_usd", 0.0)),
    }


def score_record(record: dict[str, Any], source: Path) -> dict[str, Any]:
    answer = extract_answer(record)
    lowered = answer.casefold()
    evidence = record["task"].get("evidence", [])
    hits = [item for item in evidence if item.casefold() in lowered]
    usage = extract_usage(record)
    evaluation = record.get("evaluation") or {}
    patch_success = record.get("patch_success", evaluation.get("passed"))
    return {
        "source": source.name,
        "task": record["task"]["id"],
        "agent": record["agent"],
        "condition": record["condition"],
        "run_id": record["run_id"],
        "exit_code": record["exit_code"],
        "duration_seconds": record["duration_seconds"],
        "answer_characters": len(answer),
        "evidence_hits": hits,
        "evidence_total": len(evidence),
        "evidence_recall": len(hits) / len(evidence) if evidence else None,
        "patch_success": patch_success,
        "changed_files": evaluation.get("changed_files", []),
        **usage,
    }


def _median(rows: list[dict[str, Any]], key: str) -> float:
    return statistics.median(float(row[key]) for row in rows)


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _bootstrap_ci(
    values: list[float],
    statistic: Callable[[list[float]], float] = statistics.median,
) -> list[float]:
    if not values:
        return []
    if len(values) == 1:
        return [values[0], values[0]]
    rng = random.Random(BOOTSTRAP_SEED)
    estimates = [
        float(statistic(rng.choices(values, k=len(values))))
        for _ in range(BOOTSTRAP_SAMPLES)
    ]
    return [_percentile(estimates, 0.025), _percentile(estimates, 0.975)]


def _paired_metric(items: list[dict[str, float]], key: str) -> dict[str, Any]:
    deltas = [item[key] for item in items]
    percentages = [
        item[f"{key}_percent"]
        for item in items
        if item.get(f"{key}_percent") is not None
    ]
    result: dict[str, Any] = {
        f"median_{key}_delta": statistics.median(deltas),
        f"{key}_delta_ci95": _bootstrap_ci(deltas),
    }
    if percentages:
        result[f"median_{key}_delta_percent"] = statistics.median(percentages)
        result[f"{key}_delta_percent_ci95"] = _bootstrap_ci(percentages)
    return result


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in rows if row["exit_code"] != 0]
    rows = [row for row in rows if row["exit_code"] == 0]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["agent"], row["condition"])].append(row)

    cells = {}
    for (agent, condition), items in sorted(groups.items()):
        patch_rows = [item for item in items if item.get("patch_success") is not None]
        cells[f"{agent}:{condition}"] = {
            "runs": len(items),
            "successful_runs": sum(item["exit_code"] == 0 for item in items),
            "median_duration_seconds": _median(items, "duration_seconds"),
            "median_evidence_recall": (
                _median(items, "evidence_recall")
                if all(item.get("evidence_recall") is not None for item in items)
                else None
            ),
            "patch_successes": sum(bool(item["patch_success"]) for item in patch_rows),
            "patch_evaluated_runs": len(patch_rows),
            "patch_success_rate": (
                sum(bool(item["patch_success"]) for item in patch_rows)
                / len(patch_rows)
                if patch_rows
                else None
            ),
            "input_tokens": sum(item.get("input_tokens", 0) for item in items),
            "cached_input_tokens": sum(
                item.get("cached_input_tokens", 0) for item in items
            ),
            "cache_creation_input_tokens": sum(
                item.get("cache_creation_input_tokens", 0) for item in items
            ),
            "output_tokens": sum(item.get("output_tokens", 0) for item in items),
            "cost_usd": sum(item.get("cost_usd", 0.0) for item in items),
        }

    by_pair: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_pair[(row["agent"], row["task"], row["run_id"])][row["condition"]] = row
    deltas: dict[str, list[dict[str, float]]] = defaultdict(list)
    metrics = (
        "duration_seconds",
        "evidence_recall",
        "input_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
        "output_tokens",
        "cost_usd",
    )
    for (agent, _task, _run_id), pair in by_pair.items():
        if not {"native", "visor"} <= pair.keys():
            continue
        item: dict[str, float] = {}
        for key in metrics:
            native = pair["native"].get(key)
            visor = pair["visor"].get(key)
            if native is None or visor is None:
                continue
            item[key] = float(visor) - float(native)
            item[f"{key}_percent"] = (
                (float(visor) / float(native) - 1) * 100 if float(native) else None
            )
        native_patch = pair["native"].get("patch_success")
        visor_patch = pair["visor"].get("patch_success")
        if native_patch is not None and visor_patch is not None:
            item["patch_success"] = float(bool(visor_patch)) - float(bool(native_patch))
        deltas[agent].append(item)

    paired = {}
    for agent, items in sorted(deltas.items()):
        result: dict[str, Any] = {"pairs": len(items)}
        for key in metrics:
            present = [item for item in items if key in item]
            if present:
                result.update(_paired_metric(present, key))
        result["median_duration_delta_seconds"] = result.pop(
            "median_duration_seconds_delta"
        )
        result["duration_delta_seconds_ci95"] = result.pop(
            "duration_seconds_delta_ci95"
        )
        if "median_duration_seconds_delta_percent" in result:
            result["median_duration_delta_percent"] = result.pop(
                "median_duration_seconds_delta_percent"
            )
            result["duration_delta_percent_ci95"] = result.pop(
                "duration_seconds_delta_percent_ci95"
            )
        patch_deltas = [
            item["patch_success"] for item in items if "patch_success" in item
        ]
        if patch_deltas:
            result["patch_pairs"] = len(patch_deltas)
            result["median_patch_success_delta"] = statistics.median(patch_deltas)
            result["patch_success_delta_ci95"] = _bootstrap_ci(patch_deltas)
        paired[agent] = result

    return {
        "successful_records": len(rows),
        "failed_records": len(failures),
        "cells": cells,
        "paired": paired,
    }


def refresh_published_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Recompute paired intervals from preserved scored records.

    Historical summaries do not include raw provider logs. This keeps those
    records and replaces only the aggregate.
    """
    rows = []
    for record in summary.get("records", []):
        if not isinstance(record, dict):
            continue
        row = dict(record)
        row.setdefault("cache_creation_input_tokens", 0)
        row.setdefault("cached_input_tokens", 0)
        row.setdefault("patch_success", None)
        rows.append(row)
    refreshed = dict(summary)
    refreshed["schema_version"] = 2
    refreshed["bootstrap"] = {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "confidence": 0.95,
        "source": "preserved scored records; raw provider logs were not republished",
    }
    refreshed["aggregate"] = aggregate(rows)
    return refreshed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--refresh-summary",
        type=Path,
        help="recompute aggregate and intervals from a sanitized summary",
    )
    args = parser.parse_args()
    if not args.refresh_summary and not args.inputs:
        parser.error("provide result files or --refresh-summary")

    if args.refresh_summary:
        summary = json.loads(args.refresh_summary.read_text(encoding="utf-8"))
        report = refresh_published_summary(summary)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0

    required = {"agent", "task", "condition", "run_id", "exit_code"}
    rows = []
    skipped_inputs = []
    for path in args.inputs:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not required <= payload.keys():
            skipped_inputs.append(path.name)
            continue
        rows.append(score_record(payload, path))
    report = {
        "schema_version": 2,
        "bootstrap": {
            "samples": BOOTSTRAP_SAMPLES,
            "seed": BOOTSTRAP_SEED,
            "confidence": 0.95,
        },
        "records": rows,
        "skipped_inputs": skipped_inputs,
        "aggregate": aggregate(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
