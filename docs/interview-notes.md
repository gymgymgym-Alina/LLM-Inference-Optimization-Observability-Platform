# Interview prep notes

Likely questions per phase, with answer points grounded in this project's actual decisions/data. Update as later phases land.

## Phase 1 — baseline service

**Q: Why build a "bad" baseline on purpose instead of starting with vLLM/optimized serving?**
A: Without a measured baseline, every later optimization claim ("N× faster") is unfalsifiable — you need a fixed reference point. The baseline also has to be *representative* of the naive-but-common mistake (one request at a time, no batching), because that's exactly the bottleneck the project sets out to demonstrate and fix.

**Q: Your `/generate` endpoint is `def`, not `async def` — doesn't that hurt concurrency?**
A: `model.generate()` is blocking (CPU/GPU-bound), so a plain `async def` handler would block FastAPI's single event loop entirely — every request stalls, even unrelated ones like `/health`. Using `def` lets FastAPI dispatch it to a threadpool, which keeps the event loop responsive, but doesn't give real parallel compute: all threads still contend for the same model object and the same GPU, so throughput under concurrency is still ~serial. That's the actual bottleneck phase 2's Locust test is designed to surface and phase 3's batching is designed to fix.

**Q: Why greedy decoding instead of sampling?**
A: Determinism. If output length/content varies run to run, you can't tell whether a latency change came from your optimization or from randomness in generation length. Locking decoding to greedy keeps that one variable out of the comparison — consistent with the project's "change one variable per round" rule.

## Phase 2 — load testing + observability

**Q: Why did you add an explicit lock around `model.generate()`? Isn't that making the service worse?**
A: Without the lock, concurrent threadpool requests interleave torch ops on the same model — throughput is still ~serial (the compute device is the bottleneck), but latency becomes noisy and unattributable: every request is slowed by every other request, and you can't decompose latency into "waiting" vs "computing". The lock makes the baseline's serialization *explicit and measurable*: queue wait becomes a first-class metric (`llm_queue_wait_seconds`), and the P99 story becomes precise — "requests spend X% of their time queued, not computing; GPU util is low while users wait". That's exactly the evidence that motivates batching in phase 3. Trade-off: it's a slightly idealized model of the naive service, but a well-defined baseline beats a noisy one for controlled comparisons.

**Q: Why P99 and not just average latency?**
A: Averages hide the tail, and under queueing the tail is the story: with a serial server, the unlucky request that arrives behind a deep queue waits for everyone ahead of it, so P99 grows roughly linearly with queue depth while the average moves much less. Users experience the tail (in production, one slow page load out of 100 is a complaint), and SLOs are defined on percentiles for that reason. Histograms in Prometheus let us compute P50/P99 from bucket counts (`histogram_quantile` over `_bucket` rates) — the trade-off being bucket-resolution error, which is why the bucket ladder spans 0.1s→480s tuned to the latency range we actually expect.

**Q: Why closed-loop load (Locust users waiting for responses) instead of fixed request rate (open-loop)?**
A: Closed-loop with N users measures "what does the system deliver at concurrency N" — offered load adapts to what the server sustains, so you get a stable capacity number (QPS at N users) instead of an unbounded queue explosion. Open-loop (fixed arrival rate) is better for modeling "traffic doesn't care that you're slow" and finding the collapse point — it's the honest model of public internet traffic, and the classic pitfall of closed-loop testing is *coordinated omission* (slow responses throttle the load generator, flattering your percentiles). For this project the comparison across optimization rounds is the goal, so a stable closed-loop measurement at matched concurrency levels is the right tool; I can name the limitation and how I'd complement it (constant-rate open-loop run at the measured capacity).

**Q: How do you know your measured QPS isn't limited by the load generator?**
A: Sanity checks: Locust worker CPU stays low during runs; at 100 users QPS should be ~100/latency_per_request for a serial server; and the server-side metrics (Prometheus QPS, in-flight gauge) agree with Locust's client-side view. If client and server numbers diverge, the harness is suspect.

**Q: How would you know if batching is actually helping, versus just seeming faster?**
A: Compare against the logged baseline numbers in `experiments.md` under matched concurrency, holding decoding strategy and prompt length fixed. A real result needs the same load-test methodology (Locust, same concurrency levels) run before and after — a single manual `curl` timing (like the phase 1 smoke test) isn't sufficient evidence, it only proves correctness, not performance.
