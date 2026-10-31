# Agent benchmark protocol

This harness measures a paired 2×2 comparison: Codex native, Codex with
V.I.S.O.R., Claude Code native, and Claude Code with V.I.S.O.R. It intentionally
does not contain provider credentials or claim a winner.

## Reproducible pilot

The 12-task pilot manifest is in `tasks/pilot.json`. Before each run, replace
every `PINNED_REVISION` with the immutable commit under test and record the
agent client version, model identifier, prompt, command, time budget, and
machine characteristics in the results directory.

For every task, create four fresh worktrees at the same revision. Randomize the
order of the four cells. Give every cell the same task prompt, timeout, and
test command. The V.I.S.O.R. cells may run `visor index` and use the documented
Skill; native cells must not. Do not carry conversation state between cells.

```bash
python benchmarks/run.py \
  --manifest benchmarks/tasks/pilot.json --task p01 \
  --agent codex --condition visor --model MODEL_ID \
  --workspace /absolute/worktree \
  --command 'codex exec "{prompt}"' \
  --output benchmarks/results/p01-codex-visor.json --dry-run
```

`--dry-run` writes the exact reproducibility record without invoking an agent.
Remove it only in an intentionally authorized environment. The command template
is captured verbatim in the result so reviewers can reproduce the invocation.

## Outcomes and analysis

Record task pass/fail, test results, elapsed wall time, changed files, and any
human-review score using a predeclared rubric. Keep raw stdout/stderr only when
they have been reviewed for credentials and private source. Analyze each paired
task with paired deltas; report medians and bootstrap confidence intervals, not
single aggregate claims. Publish exclusions, retries, failures, and raw
configuration alongside any public conclusion.

The harness is measurement infrastructure, not evidence of a context or token
improvement by itself.
