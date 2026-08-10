# Experiment Log

Every load test / optimization run gets a row. Change one variable at a time (see [CLAUDE.md](CLAUDE.md) 工作要求 #2). Numbers must come from real runs — never fabricated (工作要求 #2/#4).

| Date | Week | Config (model / batching / quant) | Concurrency | P50 (ms) | P99 (ms) | QPS | GPU util (%) | Notes |
|---|---|---|---|---|---|---|---|---|
| 2026-07-28 | Phase 1 | Qwen2.5-1.5B-Instruct, fp32, CPU, no batching, greedy decode | 1 | - | - | - | - | Single manual smoke test, not a load test: `/generate` on "What is the capital of France?" → "Paris" in 2531ms (16 max_new_tokens). Real P50/P99/QPS under concurrency come from the Locust baseline in phase 2. |
