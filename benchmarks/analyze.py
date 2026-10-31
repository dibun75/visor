#!/usr/bin/env python3
"""Summarize reproducible V.I.S.O.R. benchmark records."""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


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
        "output_tokens": int(usage.get("output_tokens", 0)),
        "cost_usd": float(payload.get("total_cost_usd", 0.0)),
    }


def score_record(record: dict[str, Any], source: Path) -> dict[str, Any]:
    answer = extract_answer(record)
    lowered = answer.casefold()
    evidence = record["task"].get("evidence", [])
    hits = [item for item in evidence if item.casefold() in lowered]
    usage = extract_usage(record)
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
        **usage,
    }


def _median(rows: list[dict[str, Any]], key: str) -> float:
    return statistics.median(float(row[key]) for row in rows)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = [row for row in rows if row["exit_code"] != 0]
    rows = [row for row in rows if row["exit_code"] == 0]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["agent"], row["condition"])].append(row)

    cells = {}
    for (agent, condition), items in sorted(groups.items()):
        cells[f"{agent}:{condition}"] = {
            "runs": len(items),
            "successful_runs": sum(item["exit_code"] == 0 for item in items),
            "median_duration_seconds": _median(items, "duration_seconds"),
            "median_evidence_recall": _median(items, "evidence_recall"),
            "input_tokens": sum(item["input_tokens"] for item in items),
            "cached_input_tokens": sum(item["cached_input_tokens"] for item in items),
            "output_tokens": sum(item["output_tokens"] for item in items),
            "cost_usd": sum(item["cost_usd"] for item in items),
        }

    by_pair: dict[tuple[str, str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        by_pair[(row["agent"], row["task"], row["run_id"])][row["condition"]] = row
    deltas: dict[str, list[dict[str, float]]] = defaultdict(list)
    for (agent, _task, _run_id), pair in by_pair.items():
        if {"native", "visor"} <= pair.keys():
            deltas[agent].append(
                {
                    "duration_seconds": pair["visor"]["duration_seconds"]
                    - pair["native"]["duration_seconds"],
                    "evidence_recall": pair["visor"]["evidence_recall"]
                    - pair["native"]["evidence_recall"],
                }
            )
    paired = {
        agent: {
            "pairs": len(items),
            "median_duration_delta_seconds": _median(items, "duration_seconds"),
            "median_evidence_recall_delta": _median(items, "evidence_recall"),
        }
        for agent, items in sorted(deltas.items())
    }
    return {
        "successful_records": len(rows),
        "failed_records": len(failures),
        "cells": cells,
        "paired": paired,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

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
        "schema_version": 1,
        "records": rows,
        "skipped_inputs": skipped_inputs,
        "aggregate": aggregate(rows),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
