# Benchmarks

This page holds every published V.I.S.O.R. pilot. The README links here instead of quoting numbers, because each result depends on its setup and the caveats matter as much as the figures.

**Short version:** these are small pilots, mostly on synthetic fixtures. With V.I.S.O.R. context, agents finished diagnostic navigation tasks a median of about 4 seconds faster (intervals exclude zero). Patch correctness showed no measurable difference. Token differences were too noisy to support a savings claim. An adversarial pilot shows that a wrong context slice can lead an agent to edit the wrong file, so treat V.I.S.O.R. output as leads to verify.

## Overview

Three published pilots are in this repository. None is a universal token-reduction claim. All depend on the task, agent, model, cache behavior, and context. Provider token fields are not comparable across Codex and Claude Code. V.I.S.O.R. context was supplied as leads and had to be checked against the repository.

## Adversarial retrieval misses, 2–3 November 2026

Four hidden-cause fixes, three repeats, Codex and Claude Code, native and V.I.S.O.R., produced 48 cells (24 native/V.I.S.O.R. pairs). Every V.I.S.O.R. initial context omitted the declared causal file and included an obvious API decoy, so initial gold-file recall was 0%. A patch counted as correct only when its behavioral check passed and it changed the causal file. Full figures: [`benchmarks/results/v1.4.2-adversarial-retrieval-summary.json`](./benchmarks/results/v1.4.2-adversarial-retrieval-summary.json).

| Agent | Native passed | V.I.S.O.R. passed | Both passed | Native only | V.I.S.O.R. only | Both failed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex | 9/12 | 8/12 | 6 | 3 | 2 | 1 |
| Claude Code | 12/12 | 12/12 | 12 | 0 | 0 | 0 |

Claude Code recovered the omitted causal file in all 12 V.I.S.O.R. runs. Codex recovered it in 8/12 V.I.S.O.R. runs; four Codex V.I.S.O.R. runs made behaviorally plausible edits in the decoy file instead. Codex also made three wrong-location edits without V.I.S.O.R. The one-run correctness difference is not evidence of a real advantage or disadvantage: this is a small synthetic suite, and the five discordant Codex pairs split 3 native-only to 2 V.I.S.O.R.-only. The result shows the failure mode exists and must be measured; it does not establish that focused context generally helps or hurts correctness.

## Patch correctness, 31 October 2026

Three seeded fixes, three repeats, Codex and Claude Code, native and V.I.S.O.R., 36 paired cells. Every cell had its own detached worktree. A check command scored the patch after the agent. Deltas are V.I.S.O.R. minus native. Full figures: [`benchmarks/results/v1.2.1-patch-pilot-summary.json`](./benchmarks/results/v1.2.1-patch-pilot-summary.json).

| Agent | Condition | Patches passed | Median input-token delta | Median output-token delta | Median runtime delta |
| --- | --- | --- | --- | --- | --- |
| Codex | Native | 9/9 | baseline | baseline | baseline |
| Codex | V.I.S.O.R. | 9/9 | −6,352 (95% CI −55,316 to 36,583) | +78 (95% CI −324 to 192) | −0.2 s (95% CI −10.2 s to 6.6 s) |
| Claude Code | Native | 9/9 | baseline | baseline | baseline |
| Claude Code | V.I.S.O.R. | 9/9 | −2 (95% CI −2 to 0) | +50 (95% CI −219 to 303) | +0.4 s (95% CI −2.0 s to 1.3 s) |

All 36 patches passed. The token and runtime intervals are wide and, except for Claude's two-token uncached input difference, include both directions. Claude's `input_tokens` value is the uncached remainder; cache-read tokens are a separate field and that paired interval also crosses zero. Codex does not report monetary cost. This does not show that V.I.S.O.R. saves a fixed share of tokens.

## Diagnostic navigation, v1.2.0

The v1.2.0 diagnostic pilot compared native repository navigation with the same tasks plus V.I.S.O.R. context. Figures are from [`benchmarks/results/v1.2.0-diagnostic-pilot-summary.json`](./benchmarks/results/v1.2.0-diagnostic-pilot-summary.json). Paired intervals were recomputed from the preserved scored records.

| Fact | Value |
| --- | --- |
| Successful records | 144 |
| Failed records | 0 |
| Tasks | 12 diagnostic navigation tasks |
| Repeats | 3 |
| Native/V.I.S.O.R. pairs per agent | 36 |
| Codex median paired duration delta | −4.17 s (95% CI −8.22 s to −2.21 s) |
| Claude Code median paired duration delta | −3.63 s (95% CI −6.68 s to −0.91 s) |
| Median evidence recall | 100% in both native and V.I.S.O.R. conditions |

## Limitations

- The navigation pilot does not measure patch correctness, refactoring quality, or task success.
- The patch and adversarial pilots use small synthetic fixtures, not representative production repositories.
- Timing and token counts are machine-, model-, provider-, plan-, and cache-dependent.
- Evidence recall is a heuristic, not human correctness review.
- These results are not proof that V.I.S.O.R. makes coding agents universally faster, cheaper, or better.

Protocol: [`benchmarks/README.md`](./benchmarks/README.md). Published-result notes: [`benchmarks/results/README.md`](./benchmarks/results/README.md).
