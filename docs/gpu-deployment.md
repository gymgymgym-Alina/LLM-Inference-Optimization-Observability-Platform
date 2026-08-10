# Deploying the baseline service to a rented GPU box

Goal: one real inference request served by the actual GPU, proving the container runs end-to-end outside your laptop. Do this only once you've verified `/generate` works locally on CPU — don't debug on the clock.

**Cost discipline**: RTX 3090/4090 pods run ~$0.2-0.4/hr. Everything below should take well under an hour. Stop the pod the moment you've confirmed it works (last step).

## 1. Rent a GPU pod

1. Go to https://www.runpod.io/ (or vast.ai), add a small amount of credit.
2. Deploy a pod: pick a template that already includes CUDA + Docker (RunPod's "RunPod PyTorch" template works — it has `nvidia-container-toolkit` preinstalled, which most templates do by default since the pod itself runs in a GPU container).
3. SSH into the pod (RunPod gives you the exact `ssh` command in its console).

## 2. Confirm the GPU is visible

```bash
nvidia-smi
```
You should see the GPU listed. If this fails, nothing below will work — stop and check the pod's GPU allocation in the RunPod console before spending more time.

## 3. Get the code onto the pod

```bash
git clone <your-repo-url>
cd LLM-Inference-Optimization-Observability-Platform
```
(If you haven't pushed to GitHub yet, `scp -r` the directory instead.)

## 4. Build and run with GPU access

```bash
docker build -t llm-baseline .
docker run --rm --gpus all -p 8000:8000 llm-baseline
```

What each flag does:
- `--gpus all` — passes all host GPUs into the container (requires `nvidia-container-toolkit` on the host, which RunPod's templates ship with)
- `-p 8000:8000` — maps the container's port to the pod's port so you can reach it
- `--rm` — removes the container when it exits, so you don't leave stopped containers lying around

First request downloads the ~3GB model — same as local, just faster on the pod's network.

## 5. Verify it's actually using the GPU

From another terminal on the pod (or via RunPod's exposed HTTP port if you set one up):
```bash
curl localhost:8000/health
```
Confirm `"device": "cuda"` in the response — if it says `"cpu"`, the `--gpus all` flag didn't take effect and you're not actually testing what you think you're testing.

```bash
curl -X POST localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is the capital of France?", "max_new_tokens": 32}'
```

Compare `latency_ms` here against your CPU run — this is your first real GPU vs. CPU data point, worth a line in `experiments.md`.

## 6. Shut down

```bash
docker stop $(docker ps -q)   # if you ran without --rm and didn't Ctrl-C
```
Then, in the RunPod console: **stop or terminate the pod**. Don't leave it running — billing is per-minute.

## Done when

- [ ] `nvidia-smi` on the pod shows the GPU
- [ ] `curl .../health` from the pod returns `"device": "cuda"`
- [ ] One real `/generate` response recorded, pod stopped afterward
