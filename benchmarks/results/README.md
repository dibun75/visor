# Published benchmark results

## v1.2.0 diagnostic pilot

`v1.2.0-diagnostic-pilot-summary.json` contains the sanitized aggregate for the
12-task, three-repeat, paired Codex/Claude pilot against release commit
`b7699ed4919b9fb5aab54ec89b71f7788f7e4553`.

The tasks measure repository navigation and recall of predeclared file/symbol
evidence. They do not measure patch correctness, test success, or refactoring
quality. Raw model answers, stderr, session identifiers, absolute workspace
paths, and supplied repository context are intentionally not published.

Codex traces report tokens but no monetary cost, so Codex `cost_usd` values are
zero placeholders and must be interpreted as unknown. Claude cost values are
provider-reported. Timings include provider latency and repository inspection on
the recorded local machine; do not generalize them across machines or plans.

## Adversarial retrieval benchmark

`v1.4.2-adversarial-retrieval-summary.json` contains the sanitized 48-cell
run from 2–3 November 2026: four tasks, two agents, two conditions, and three
repeats. Random seed `20261102`. Codex `gpt-5.6-sol`, CLI `0.152.0`; Claude
Code canonical model `claude-sonnet-5-5`, CLI `2.1.316`, invoked with `--model
sonnet`.

Every V.I.S.O.R. initial context had zero gold-file recall and included a
declared decoy. Claude Code passed 12/12 in each condition. Codex passed 9/12
native and 8/12 with V.I.S.O.R.; its paired transitions were six both-pass,
three native-only, two V.I.S.O.R.-only, and one both-fail. Codex made three
wrong-location edits natively and four with V.I.S.O.R. No agent process failed.

The scored records contain metrics, causal and changed paths, and outcome labels,
but not raw provider stdout, stderr, session identifiers, prompts, or absolute
paths. The sample is too small and synthetic to establish a correctness effect.
It demonstrates that retrieval misses and plausible wrong-location patches need
to be measured separately from token and runtime deltas.

## v1.2.1 patch pilot

`v1.2.1-patch-pilot-summary.json` is the sanitized aggregate for the 3-task
patch pilot run on 31 October 2026. Fixture revision
`36715f0ea3ae0d32694a42c275fe030dc29bf86c`. Random seed `20261031`. Bootstrap
10,000 samples, seed `20261031`.

Codex `gpt-5.6-sol`, CLI `0.152.0`. Claude Code canonical model
`claude-sonnet-5-5`, CLI `2.1.316`, command flag `--model sonnet`.

All 36 evaluated patches passed. Paired token and runtime intervals are wide.
Claude `input_tokens` is uncached input, not the full prompt. Raw stdout,
stderr, session identifiers, and absolute paths are not published.

Reproduce from `benchmarks/README.md`.
