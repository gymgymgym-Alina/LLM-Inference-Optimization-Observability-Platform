# pytorch/pytorch images ship CUDA-enabled torch already built in.
# On a GPU host (with nvidia-container-toolkit + `docker run --gpus all`) it uses the GPU.
# On a CPU-only host it silently falls back to CPU — same image works for local dev and prod.
FROM pytorch/pytorch:2.4.0-cuda12.1-cudnn9-runtime

WORKDIR /app

# torch is NOT in requirements.txt on purpose: this base image already has the
# CUDA-matched build. `pip install -r requirements.txt` alone would pull the
# CPU-only wheel from PyPI and silently break GPU inference.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
