# Agent benchmark protocol

This harness measures a paired 2×2 comparison: Codex native, Codex with
V.I.S.O.R., Claude Code native, and Claude Code with V.I.S.O.R. It intentionally
does not contain provider credentials or claim a winner.

## Reproducible pilot

The 12-task pilot manifest is in `tasks/pilot.json`. Every task names the
immutable release commit under test. The harness refuses a different worktree
revision. Record the agent client version, model identifier, prompt, command,
time budget, and machine characteristics alongside the results.

For every task, create four fresh worktrees at the same revision. Randomize the
order of the four cells. Give every cell the same task prompt, timeout, and
test command. The V.I.S.O.R. cells may run `visor index` and use the documented
Skill; native cells must not. Do not carry conversation state between cells.
Repeat every cell at least three times before drawing comparative conclusions.

```bash
python benchmarks/run.py \
  --manifest benchmarks/tasks/pilot.json --task p01 \
  --agent codex --condition visor --model MODEL_ID \
  --client-version "codex 0.152.0" \
  --workspace /absolute/worktree \
  --context-file /absolute/visor-context.json \
  --command 'codex exec "{prompt} Use this V.I.S.O.R. context as leads: {context}"' \
  --timeout 1800 \
  --output benchmarks/results/p01-codex-visor.json --dry-run
```

`--dry-run` writes the exact reproducibility record without invoking an agent.
Remove it only in an intentionally authorized environment. The command template
is split into an argument vector before placeholders are expanded, so task
prompts are never evaluated by a shell. Shell operators such as redirection and
pipes are intentionally unsupported; configure provider context through its
CLI flags or a wrapper with a reviewed, fixed argument interface.

The pilot manifest currently contains diagnostic prompts, not seeded coding
fixtures. It validates navigation and explanation behavior only. Do not report
it as evidence for bug-fix or refactoring performance until immutable fixture
patches and machine-verifiable evaluators are added.

## Outcomes and analysis

Record task pass/fail, test results, elapsed wall time, changed files, and any
human-review score using a predeclared rubric. Keep raw stdout/stderr only when
they have been reviewed for credentials and private source. Analyze each paired
task with paired deltas; report medians and bootstrap confidence intervals, not
single aggregate claims. Publish exclusions, retries, failures, and raw
configuration alongside any public conclusion.

The harness is measurement infrastructure, not evidence of a context or token
improvement by itself.
