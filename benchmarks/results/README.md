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
