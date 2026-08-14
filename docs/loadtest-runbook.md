# GPU load-test runbook (baseline data collection)

Goal: real P50/P99/QPS/GPU-util numbers for the **unoptimized baseline** at 1/10/50/100 concurrency. These numbers anchor every later comparison — collect them carefully once, don't improvise mid-run.

**Cost estimate**: 4 tiers × 5 min + cooldowns + setup ≈ 1–1.5 hr of GPU time (~$0.3–0.6 on a 3090/4090). Everything below assumes you already verified the whole pipeline locally (see README) — the GPU box is for measurement, not debugging.

## Before you start (local, free)

- [ ] `docker compose up` works locally: Grafana dashboard at `localhost:3000` shows data during a short local Locust run
- [ ] Repo pushed to GitHub so the pod can `git clone`

## 1. Rent the pod and set up

Same as [gpu-deployment.md](gpu-deployment.md) steps 1–3: rent RTX 3090/4090 pod, `nvidia-smi` sanity check, clone the repo.

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
```

Wait for model load, then verify — **do not skip**:

```bash
curl localhost:8000/health          # must say "device": "cuda"
curl -s localhost:9090/api/v1/targets | grep -o '"health":"[a-z]*"'
```

- If `"device"` is `"cpu"`: the GPU didn't reach the container — fix before testing, or every number you collect is garbage.
- Prometheus targets: `llm-api` must be `up`. `dcgm` should be `up` too; if dcgm-exporter won't start on this pod (some container-based pods disallow it), fall back to:
  ```bash
  ./scripts/gpu_util_log.sh loadtest/results/gpu_util_u<N>.csv   # run alongside each tier, Ctrl-C after
  ```

## 2. Warm-up (not recorded)

First requests hit model download + CUDA kernel compilation. Send ~5 requests and discard:

```bash
for i in 1 2 3 4 5; do
  curl -s -X POST localhost:8000/generate -H "Content-Type: application/json" \
    -d '{"prompt": "warmup", "max_new_tokens": 64}' > /dev/null && echo "warmup $i ok"
done
```

## 3. Run the ladder

Install Locust on the pod (outside the container): `pip install -r loadtest/requirements.txt`

```bash
./loadtest/run_tiers.sh http://localhost:8000 baseline-<gpu-name> 5m
```

What it does: for each of 1/10/50/100 users → 5-minute run → CSV stats → 30s cooldown. **5 minutes per tier** is enough for hundreds of samples at low concurrency and stable percentiles, while keeping total GPU cost bounded; the 30s cooldown drains the queue so tiers don't contaminate each other.

Rules while it runs:
- Don't touch the pod (no other workloads — they'd pollute GPU util numbers)
- Keep Grafana open (`<pod-ip>:3000`) and screenshot each tier's steady state — these go in the README's technical report
- If a tier errors out en masse, note it and keep the data — "baseline falls over at N users" is a result, not a failure

## 4. Record results

For each tier, take from `loadtest/results/baseline-<gpu>_u<N>_stats.csv` (the `Aggregated` row): P50 (`50%` column), P99 (`99%`), QPS (`Requests/s`), failure count. GPU util: average `DCGM_FI_DEV_GPU_UTIL` over the tier window in Prometheus/Grafana, or average the CSV from `gpu_util_log.sh`.

Add one row per tier to `experiments.md`:

| Date | Week | Config | Concurrency | P50 (ms) | P99 (ms) | QPS | GPU util (%) | Notes |
|---|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | Phase 2 | baseline fp16, RTX 3090, greedy, 64 tok | 10 | … | … | … | … | locust 5m, prompt fixed |

Also save: Grafana screenshots to `docs/img/`, the raw CSVs (commit them — they're the evidence).

## 5. Shut down

```bash
docker compose down
```
Then **stop the pod in the RunPod console immediately**. Check the billing page confirms it stopped.

## Done when

- [ ] 4 rows (u=1/10/50/100) in `experiments.md` with real numbers
- [ ] Grafana screenshots saved for the technical report
- [ ] A one-paragraph bottleneck analysis written (expected shape: QPS flat as concurrency grows, P99 exploding ~linearly with queue depth, GPU util NOT the bottleneck — that's the case for batching)
- [ ] Pod stopped
