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
  --run-id r1 \
  --workspace /absolute/worktree \
  --context-file /absolute/visor-context.json \
  --command 'codex exec "{prompt} Use this V.I.S.O.R. context as leads: {context}"' \
  --timeout 1800 \
  --output benchmarks/results/p01-codex-visor.json --dry-run
```

`--dry-run` writes the exact reproducibility record without invoking an agent.
For the complete randomized matrix, use `run_pilot.py`. It writes `plan.json`
before execution and supports `--resume`, which reruns only missing or nonzero
cells while preserving successful records and their original run IDs. This is
important for provider quotas and transient failures.

Run the live matrix only in an environment authorized to send prompts to the agent providers. The command template
is split into an argument vector before placeholders are expanded, so task
prompts are never evaluated by a shell. Shell operators such as redirection and
pipes are intentionally unsupported; configure provider context through its
CLI flags or a wrapper with a reviewed, fixed argument interface.

The diagnostic manifest contains navigation prompts. It does not by itself measure bug-fix performance. The patch pilot below is a separate three-task fixture with executable checks.

## Patch pilot

`benchmarks/prepare_patch_pilot.py` copies `benchmarks/fixtures/patch_repo` into an empty directory, makes one git commit, and can write V.I.S.O.R. context files. The published run used fixture revision `36715f0ea3ae0d32694a42c275fe030dc29bf86c`. Its parent, `aa898b304916081417afe0e361dc7387e91e1988`, is the same tree before the check scripts added the repository root to `sys.path`. A fresh prepare commits the current fixture once, so that new hash will not equal the published revision; the file contents should match `36715f0`.

The published matrix is 3 tasks, 2 agents, 2 conditions, and 3 repeats (36 cells). Random seed `20261031`. Bootstrap: 10,000 resamples, seed `20261031`, 95% interval. Timeout 600 seconds. Concurrency 2. Codex model `gpt-5.6-sol`, CLI `0.152.0`. Claude Code canonical model `claude-sonnet-5-5`, CLI `2.1.316`, invoked with `--model sonnet`.

Evaluators, run after the agent in the cell worktree:

```bash
python checks/check_discounts.py
python checks/check_retry.py
python checks/check_paths.py
```

Prepare and run from the repository root. This calls the configured agent CLIs and sends prompts to those providers. Do not commit raw stdout, stderr, session IDs, or absolute home paths.

```bash
python benchmarks/prepare_patch_pilot.py \
  --workspace /tmp/visor-patch-pilot/workspace \
  --manifest /tmp/visor-patch-pilot/manifest.json \
  --contexts /tmp/visor-patch-pilot/contexts

python benchmarks/run_pilot.py \
  --manifest /tmp/visor-patch-pilot/manifest.json \
  --workspace /tmp/visor-patch-pilot/workspace \
  --worktrees /tmp/visor-patch-pilot/worktrees \
  --contexts /tmp/visor-patch-pilot/contexts \
  --results /tmp/visor-patch-pilot/results \
  --repeats 3 \
  --seed 20261031 \
  --concurrency 2 \
  --timeout 600 \
  --codex-model gpt-5.6-sol \
  --codex-client-version 0.152.0 \
  --claude-model claude-sonnet-5-5 \
  --claude-client-version 2.1.316 \
  --codex-native-command 'codex exec --json --ephemeral --approve-for-me --ignore-user-config --ignore-rules -m gpt-5.6-sol "{prompt} Work only in this repository. Implement the fix, run the requested check, and do not commit."' \
  --codex-visor-command 'codex exec --json --ephemeral --approve-for-me --ignore-user-config --ignore-rules -m gpt-5.6-sol "{prompt} Work only in this repository. Implement the fix, run the requested check, and do not commit. Use the following V.I.S.O.R. context only as leads; verify it against the repository before editing: {context}"' \
  --claude-native-command 'claude --safe-mode --print --output-format json --permission-mode bypassPermissions --dangerously-skip-permissions --no-session-persistence --model sonnet "{prompt} Work only in this repository. Implement the fix, run the requested check, and do not commit."' \
  --claude-visor-command 'claude --safe-mode --print --output-format json --permission-mode bypassPermissions --dangerously-skip-permissions --no-session-persistence --model sonnet "{prompt} Work only in this repository. Implement the fix, run the requested check, and do not commit. Use the following V.I.S.O.R. context only as leads; verify it against the repository before editing: {context}"'

python benchmarks/analyze.py /tmp/visor-patch-pilot/results/patch-*.json \
  --output benchmarks/results/v1.2.1-patch-pilot-summary.json
```

`--resume` skips result files whose `exit_code` is 0 and leaves those files in place. An interrupt stops the agent process group. Seven cells in the published run were re-scored after the import-path fix without rerunning the agents; that is recorded in the summary.

The sanitized published aggregate is `benchmarks/results/v1.2.1-patch-pilot-summary.json`. To recompute intervals for the older diagnostic summary without raw logs:

```bash
python benchmarks/analyze.py \
  --refresh-summary benchmarks/results/v1.2.0-diagnostic-pilot-summary.json \
  --output benchmarks/results/v1.2.0-diagnostic-pilot-summary.json
```

## Scoring

Each diagnostic task declares concrete file and symbol evidence. Summarize one or
more completed records with:

```bash
python benchmarks/analyze.py benchmarks/results/*.json \
  --output benchmarks/results/summary.json
```

The analyzer extracts provider-reported usage where available, computes evidence
recall, and reports paired native-versus-V.I.S.O.R. deltas by task and run ID.
Evidence recall checks whether an answer cites the predeclared implementation
anchors; it is not a substitute for human correctness review. Codex traces do
not currently expose monetary cost, so their cost remains zero/unknown rather
than estimated.

## Outcomes and analysis

Record task pass/fail, test results, elapsed wall time, changed files, and any
human-review score using a predeclared rubric. Keep raw stdout/stderr only when
they have been reviewed for credentials and private source. Analyze each paired
task with paired deltas; report medians and bootstrap confidence intervals, not
single aggregate claims. Publish exclusions, retries, failures, and raw
configuration alongside any public conclusion.

The harness is measurement infrastructure, not evidence of a context or token
improvement by itself.
