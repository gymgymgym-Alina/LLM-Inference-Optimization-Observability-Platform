# Week 1 — Docker + Linux + Cloud Warm-up

Goal: be able to go code → image → running on a cloud box. No LLM yet — this is pure plumbing practice.

## 0. Prerequisite: install Docker

Install Docker Desktop (macOS): https://docs.docker.com/desktop/install/mac-install/

Verify:
```bash
docker --version
docker compose version
```

## 1. Run locally

```bash
cd week1-docker-basics
docker compose up --build
```

Then check:
```bash
curl localhost:8000/
curl localhost:8000/health
```
Expect `{"message":"hello world"}` and `{"status":"ok"}`.

Stop with `docker compose down`.

## 2. RunPod smoke test (GPU access, no LLM yet)

1. Sign up at https://www.runpod.io/, add a small amount of credit.
2. Deploy a pod with a cheap GPU (RTX 3090/4090, ~$0.2-0.4/hr) using any base PyTorch/CUDA template.
3. SSH in (RunPod gives you the command in the console).
4. Run:
   ```bash
   nvidia-smi
   ```
   Confirm the GPU shows up.
5. **Stop the pod immediately** — this step is just to prove you can rent a GPU box and reach it, not to run anything. Billing is per-minute/hour, so don't leave it running idle.

## 3. Deploy hello-world to AWS EC2 (free tier)

1. Sign up for AWS, launch a `t2.micro` / `t3.micro` EC2 instance (free tier eligible), Ubuntu AMI, open inbound port 8000 in the security group.
2. SSH in, install Docker on the instance:
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-plugin
   sudo usermod -aG docker $USER
   # log out/in for group change to apply
   ```
3. Copy this `week1-docker-basics/` directory to the instance (`scp` or `git clone` the repo) and run:
   ```bash
   docker compose up --build -d
   ```
4. From your local machine:
   ```bash
   curl http://<EC2-PUBLIC-IP>:8000/health
   ```
5. When done, `docker compose down` on the instance. EC2 free-tier `t2.micro` can stay running (it's within the free tier), but there's no reason to leave it up once verified — stopping (not terminating) the instance costs nothing extra in compute.

## Done when

- [ ] `docker compose up --build` works locally, `/` and `/health` respond
- [ ] `nvidia-smi` confirmed on a RunPod GPU pod, pod stopped afterward
- [ ] Same Docker image reachable over the public internet from an EC2 instance
