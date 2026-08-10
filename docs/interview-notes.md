# Interview prep notes

Likely questions per phase, with answer points grounded in this project's actual decisions/data. Update as later phases land.

## Phase 1 — baseline service

**Q: Why build a "bad" baseline on purpose instead of starting with vLLM/optimized serving?**
A: Without a measured baseline, every later optimization claim ("N× faster") is unfalsifiable — you need a fixed reference point. The baseline also has to be *representative* of the naive-but-common mistake (one request at a time, no batching), because that's exactly the bottleneck the project sets out to demonstrate and fix.

**Q: Your `/generate` endpoint is `def`, not `async def` — doesn't that hurt concurrency?**
A: `model.generate()` is blocking (CPU/GPU-bound), so a plain `async def` handler would block FastAPI's single event loop entirely — every request stalls, even unrelated ones like `/health`. Using `def` lets FastAPI dispatch it to a threadpool, which keeps the event loop responsive, but doesn't give real parallel compute: all threads still contend for the same model object and the same GPU, so throughput under concurrency is still ~serial. That's the actual bottleneck phase 2's Locust test is designed to surface and phase 3's batching is designed to fix.

**Q: Why greedy decoding instead of sampling?**
A: Determinism. If output length/content varies run to run, you can't tell whether a latency change came from your optimization or from randomness in generation length. Locking decoding to greedy keeps that one variable out of the comparison — consistent with the project's "change one variable per round" rule.

**Q: How would you know if batching is actually helping, versus just seeming faster?**
A: Compare against the logged baseline numbers in `experiments.md` under matched concurrency, holding decoding strategy and prompt length fixed. A real result needs the same load-test methodology (Locust, same concurrency levels) run before and after — a single manual `curl` timing (like the phase 1 smoke test) isn't sufficient evidence, it only proves correctness, not performance.
