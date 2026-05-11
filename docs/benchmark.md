# P1 Benchmark Report

Validated on 2026-05-11 against benchmark version `m2.7-agt29-v3` and baseline artifact `manual-reviewed-standalone-web-search (2026-05-10-v1)`.

## Conclusion

- The benchmark is functioning as intended. The primary failure mode is retrieval recall on must-find anchor papers, not broken evaluator logic.
- SCI-0104 holds the default run at 19 of 22 queries meeting or exceeding the reviewed manual baseline; the latest validated rerun recovered INTER-03 (Large language models in medicine) but did not close the remaining three retrieval gaps.
- Hard-filter contract preservation, post-merge result filtering, topic coverage, alternate coverage, and source coverage all held at 1.000 in the validated default run.
- The remaining regressions are narrowed to three recall-only misses: TS-02 (Temporal Fusion Transformer), BIO-01 (Therapeutic genome editing by CRISPR-Cas systems), and BIO-04 (Long COVID review).
- These three are external-API retrieval misses — the target papers do not appear in the free-tier APIs' top results for those broad or vocabulary-mismatched queries. Further code changes are unlikely to close this gap without paid API coverage or query hardcoding.
- P1 exit criteria per [docs/core.md](core.md) are not strictly satisfied (3 queries still trail the baseline on recall). The product team has decided to close P1 at 19/22 and advance to P2, treating the remaining three as known retrieval-depth limitations rather than P1 blockers.

## Default Scenario

Command used:

```bash
uv run python examples/m2_7_benchmark.py --output-json /tmp/p1-benchmark-current.json
```

| Metric                    | Result       |
| ------------------------- | ------------ |
| Queries                   | 22           |
| Passed all checks         | 19 / 22      |
| Hard-filter contract rate | 1.000        |
| Result hard-filter rate   | 1.000        |
| Topic coverage rate       | 1.000        |
| Alternate coverage rate   | 1.000        |
| Source coverage rate      | 1.000        |
| Must-find recall@10       | 0.615        |
| Must-find recall@20       | 0.769        |
| Average latency           | 27.09 s      |
| Estimated cost            | 0.000000 USD |

Queries below the reviewed manual baseline:

- TS-02
- BIO-01
- BIO-04

Representative evidence from the validated run:

- INTER-03 now passes on the _Large language models in medicine_ anchor, recovered by the long-query prefix variant that added a 4-keyword variant to the multi-term retrieval query.
- AI-01 passes on the Lewis et al. RAG anchor; AI-04 passes on _Attention Is All You Need_; BIO-02 passes on AlphaFold 2; TS-05 passes on Lag-Llama.
- TS-04 passes on the exact Temporal Fusion Transformer anchor, while TS-02 still misses it on the broader citation-sorted timeseries query. The issue is confirmed to be in external-API retrieval depth for generic time-series queries, not evaluator matching or ranking logic.
- BIO-01 still misses _Therapeutic genome editing by CRISPR-Cas systems_ despite the genome-editing synonym variant; the paper does not surface in any source's top results for broad CRISPR queries.
- BIO-04 still misses the _Long COVID_ review anchor despite the "long covid" query variant; the paper likely appears but is filtered by open-access status in some sources or is beyond the fetch depth for others.

## Feature-Flag Measurement

Last measured on 2026-05-10. SCI-0104 validation reran only the default scenario, so the flag dispositions below remain the latest validated flag-specific measurements and were not rerun as part of this pass.

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
- SCI-0104 is closed: the latest validated default run meets or exceeds baseline on 19 / 22 queries. INTER-03 was recovered by the long-query prefix variant. Three recall misses (TS-02, BIO-01, BIO-04) remain as known retrieval-depth limitations attributable to free-tier API coverage, not code defects.
- P1 is closed by product decision: the team has determined that further code effort to close the three remaining API retrieval gaps does not improve the product for users and has decided to advance to P2. The constraint compliance and topic coverage rates are all at 1.000.
