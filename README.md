# LLM Inference Optimization & Observability Platform

Deploying Qwen2.5-1.5B-Instruct as a production-style API service, then driving latency/throughput improvements through a measure → optimize → re-measure loop: load testing, hand-written dynamic batching (benchmarked against vLLM), quantization, and full observability with Prometheus/Grafana. Every optimization claim is backed by a real load-test run logged in [experiments.md](experiments.md) — see [CLAUDE.md](CLAUDE.md) for the full project context and timeline.

## Status: Phase 2 (load testing + observability)

The service is still the deliberately-serial baseline (one request on the model at a time, enforced by an explicit lock), now instrumented: Prometheus metrics, Grafana dashboard, and a Locust concurrency ladder. Next step is collecting baseline P50/P99/QPS/GPU-util data on a GPU box — see [docs/loadtest-runbook.md](docs/loadtest-runbook.md).

## Layout

- `app/` — the inference service (`main.py`: FastAPI + transformers, `/generate` + `/health` + `/metrics`)
- `loadtest/` — Locust script (fixed prompt/length for reproducibility) + `run_tiers.sh` concurrency ladder
- `monitoring/` — Prometheus scrape config, Grafana provisioning + dashboard
- `Dockerfile`, `docker-compose.yml`, `docker-compose.gpu.yml` — containerized deployment (CPU locally, GPU on a rented box)
- `scripts/gpu_util_log.sh` — nvidia-smi fallback GPU-util logger for pods where dcgm-exporter can't run
- `experiments.md` — every load test / optimization run, with real measured numbers
- `week1-docker-basics/` — a standalone Docker/FastAPI warm-up exercise, not part of the actual service

## Run locally (CPU)

You don't need a GPU to verify correctness — it'll just be slow (expect tens of seconds per response on a laptop CPU).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only wheel, ~200MB
pip install -r requirements.txt
uvicorn app.main:app --reload
```

First request triggers a ~3GB model download from Hugging Face (cached under `~/.cache/huggingface` after that).

```bash
curl localhost:8000/health

curl -X POST localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?", "max_new_tokens": 32}'
```

## Run in Docker (API + Prometheus + Grafana)

```bash
docker compose up --build
```

- API: `localhost:8000` (same `curl` commands as above; metrics at `localhost:8000/metrics/`)
- Prometheus: `localhost:9090` (Status → Targets should show `llm-api` up; `dcgm` is down on CPU hosts, that's expected)
- Grafana: `localhost:3000` — the "LLM Inference Service" dashboard is auto-provisioned (anonymous access enabled, no login)

This uses CPU unless you're on a GPU host — see [docs/gpu-deployment.md](docs/gpu-deployment.md) / [docs/loadtest-runbook.md](docs/loadtest-runbook.md) for the GPU box.

## Load testing

```bash
pip install -r loadtest/requirements.txt
./loadtest/run_tiers.sh http://localhost:8000 local-check 1m   # local pipeline check (numbers don't count)
```

For real measurements on a GPU box, follow [docs/loadtest-runbook.md](docs/loadtest-runbook.md) — 5 minutes per tier, results recorded in [experiments.md](experiments.md).

## API

- `GET /health` → `{"status": "ok", "model_loaded": bool, "device": "cuda"|"cpu"}`
- `POST /generate` → body `{"prompt": str, "max_new_tokens": int}`, returns `{"response": str, "latency_ms": float}`

## Phase 1 design decisions

| Decision | Motivation | Trade-off / what it sets up |
|---|---|---|
| Model loaded once at FastAPI startup (`lifespan`), not per-request | Reloading ~3GB of weights per request would dominate latency and make every other measurement meaningless | Means the process holds the model in memory for its whole lifetime — fine here, becomes a real constraint once we add batching/queueing state in phase 3 |
| `POST /generate` is a sync `def`, not `async def` | `model.generate()` is blocking CPU/GPU work; FastAPI runs sync handlers in a threadpool so the event loop doesn't freeze | Concurrent requests still queue up on the *same* model/GPU — no real parallel compute happens. This is intentional: it's the exact bottleneck phase 2's load test is designed to surface |
| Greedy decoding (`do_sample=False`) | Deterministic output means two runs of the same prompt give the same token count/latency — required to isolate one variable at a time across optimization rounds | Slightly worse output diversity than sampling, irrelevant for a latency/throughput benchmark |
| `apply_chat_template` before tokenizing | Qwen2.5-1.5B-**Instruct** was fine-tuned on chat-formatted input; skipping the template gets base-model-style completions instead of instruction-following behavior | One more place a bug can hide (wrong template = technically-working but silently worse quality) |
| `torch` excluded from `requirements.txt`, baked into the Docker base image instead | `pytorch/pytorch:*-cuda*` ships a CUDA-matched torch build; `pip install torch` from PyPI defaults to a CPU-only wheel that would silently disable GPU inference inside the container | Local (non-Docker) dev needs an explicit separate `pip install torch --index-url .../cpu` step — documented above |
| `latency_ms` returned in the response body | Cheap way to eyeball baseline latency via `curl` before Locust/Prometheus exist (phase 2) | Not a substitute for a real load test — single-request timing isn't a percentile, see `experiments.md` |

Verified 2026-07-28: real `/generate` call on CPU (fp32, Qwen2.5-1.5B-Instruct) — prompt "What is the capital of France?" → `"Paris"` in 2531ms. Logged in [experiments.md](experiments.md).
