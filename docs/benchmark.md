# P1 Benchmark Report

Validated on 2026-05-10 against benchmark version `m2.7-agt29-v3` and baseline artifact `manual-reviewed-standalone-web-search (2026-05-10-v1)`.

## Conclusion

- The benchmark is functioning as intended. The primary failure mode is retrieval recall on must-find anchor papers, not broken evaluator logic.
- The baseline artifact is not the dominant problem. The default run fell below baseline on 9 of 22 queries, and every regression was a recall metric.
- Hard-filter contract preservation, post-merge result filtering, topic coverage, alternate coverage, and source coverage all held at 1.000 in the validated default run.
- One benchmark-surface cleanup was applied during validation: the Temporal Fusion Transformer anchor now uses the 2021 journal DOI instead of the 2019 arXiv preprint DOI so the must-find target matches the query's 2020+ framing more directly.

## Default Scenario

Command used:

```bash
uv run python examples/m2_7_benchmark.py --output-json /tmp/p1-benchmark-current.json
```

| Metric                    | Result       |
| ------------------------- | ------------ |
| Queries                   | 22           |
| Passed all checks         | 13 / 22      |
| Hard-filter contract rate | 1.000        |
| Result hard-filter rate   | 1.000        |
| Topic coverage rate       | 1.000        |
| Alternate coverage rate   | 1.000        |
| Source coverage rate      | 1.000        |
| Must-find recall@10       | 0.231        |
| Must-find recall@20       | 0.231        |
| Average latency           | 15.36 s      |
| Estimated cost            | 0.000000 USD |

Queries below the reviewed manual baseline:

- AI-01
- AI-04
- TS-02
- TS-05
- BIO-01
- BIO-02
- BIO-04
- BIO-05
- INTER-01

Representative evidence from the validated run:

- AI-04 returned transformer and attention surveys, but not _Attention Is All You Need_ in the top 20.
- BIO-02 returned AlphaFold-adjacent papers, including AlphaFold 3 and AlphaFold-Multimer, but not the AlphaFold 2 anchor.
- TS-04 passed on the exact Temporal Fusion Transformer anchor, which shows the evaluator matches anchor papers correctly when retrieval returns them.

## Feature-Flag Measurement

Command used:

```bash
uv run python examples/m2_7_benchmark.py --measure-flags --output-json /tmp/p1-benchmark-flags.json
```

| Scenario              | Passed  | Recall@20 | Avg latency | Delta vs default                 |
| --------------------- | ------- | --------- | ----------- | -------------------------------- |
| default               | 13 / 22 | 0.231     | 15.36 s     | baseline                         |
| `AGT_USE_KEYBERT`     | 12 / 22 | 0.154     | 32.60 s     | worse recall, much slower        |
| `AGT_USE_SPELL_CHECK` | 13 / 22 | 0.231     | 14.47 s     | no material change on this panel |
| `AGT_USE_RERANKER`    | 14 / 22 | 0.308     | 14.74 s     | modest recall improvement        |

Per-flag query movement versus default:

- `AGT_USE_KEYBERT` regressed INTER-03 and improved no queries.
- `AGT_USE_SPELL_CHECK` changed no pass/fail outcomes on the current panel.
- `AGT_USE_RERANKER` improved TS-05 and introduced no pass/fail regressions.

Interpretation:

- `AGT_USE_KEYBERT` is retired from the active tuning surface and should remain disabled. The current measurement shows lower recall and materially worse latency, so there is no evidence case for promotion.
- `AGT_USE_SPELL_CHECK` stays disabled and explicitly experimental. The current panel contains no typo-focused acceptance queries, so the honest disposition is to defer promotion or removal until a dedicated typo benchmark exists rather than pretend this panel answered the question.
- `AGT_USE_RERANKER` is retained as a supported opt-in experiment. It is the only flag with a positive benchmark signal, but the improvement is not large enough to declare P1 retrieval competitive or to treat the flag as a full milestone exit by itself.

Decision summary:

- `AGT_USE_KEYBERT`: do not promote; keep disabled and treat as retired pending future cleanup.
- `AGT_USE_SPELL_CHECK`: do not promote; keep disabled and defer final keep/remove judgment to a typo-focused benchmark slice.
- `AGT_USE_RERANKER`: keep as a positive opt-in experiment; do not claim it closes the retrieval gap on its own.

## Status

- SCI-0101 is complete: the benchmark panel, baseline comparison, and published report now exist and are validated.
- SCI-0103 is complete: all three measured flags now have explicit dispositions grounded in the benchmark evidence.
- P1 remains open: [docs/core.md](core.md) requires SciAgent to match or exceed the reviewed manual baseline on must-find recall before release promotion, and the validated default run still trails that baseline on 9 of 22 queries.
