import os
import threading
import time
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
DEFAULT_MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "256"))

# Under heavy queueing, end-to-end latency can reach minutes while pure
# inference stays in the seconds range — one shared bucket ladder covers both
# so the three histograms stay directly comparable.
LATENCY_BUCKETS = (0.1, 0.25, 0.5, 1, 2, 4, 8, 15, 30, 60, 120, 240, 480)

REQUESTS = Counter(
    "llm_requests_total",
    "Total /generate requests",
    ["status"],  # "success" | "error"
)
REQUEST_LATENCY = Histogram(
    "llm_request_latency_seconds",
    "End-to-end /generate latency (queue wait + inference + overhead)",
    buckets=LATENCY_BUCKETS,
)
QUEUE_WAIT = Histogram(
    "llm_queue_wait_seconds",
    "Time spent waiting for the model lock before inference starts",
    buckets=LATENCY_BUCKETS,
)
INFERENCE_TIME = Histogram(
    "llm_inference_seconds",
    "Time spent inside model.generate()",
    buckets=LATENCY_BUCKETS,
)
IN_FLIGHT = Gauge(
    "llm_requests_in_flight",
    "Requests currently inside /generate (queued + running)",
)
GENERATED_TOKENS = Counter(
    "llm_generated_tokens_total",
    "Total tokens generated (for tokens/sec throughput)",
)

state: dict = {"model": None, "tokenizer": None, "device": None}

# The baseline is deliberately serial: one request on the model at a time.
# Without this lock, concurrent threads would interleave ops on the same
# model and thrash each other — still ~serial throughput, but with noisy,
# unattributable latency. The lock makes the serialization explicit and
# lets us measure queue wait as a first-class metric.
model_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, torch_dtype=dtype)
    model.to(device)
    model.eval()

    state["model"] = model
    state["tokenizer"] = tokenizer
    state["device"] = device
    yield
    state.clear()


app = FastAPI(title="llm-inference-baseline", lifespan=lifespan)
app.mount("/metrics", make_asgi_app())


class GenerateRequest(BaseModel):
    prompt: str
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS


class GenerateResponse(BaseModel):
    response: str
    latency_ms: float
    queue_wait_ms: float
    inference_ms: float
    generated_tokens: int


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": state["model"] is not None,
        "device": state["device"],
    }


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    tokenizer = state["tokenizer"]
    model = state["model"]
    device = state["device"]

    IN_FLIGHT.inc()
    request_start = time.perf_counter()
    try:
        messages = [{"role": "user", "content": req.prompt}]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt").to(device)

        with model_lock:
            inference_start = time.perf_counter()
            queue_wait = inference_start - request_start
            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    max_new_tokens=req.max_new_tokens,
                    do_sample=False,
                    temperature=None,
                    top_p=None,
                    top_k=None,
                )
            inference_time = time.perf_counter() - inference_start

        generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
        response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

        latency = time.perf_counter() - request_start
        REQUESTS.labels(status="success").inc()
        REQUEST_LATENCY.observe(latency)
        QUEUE_WAIT.observe(queue_wait)
        INFERENCE_TIME.observe(inference_time)
        GENERATED_TOKENS.inc(len(generated_ids))

        return GenerateResponse(
            response=response_text,
            latency_ms=latency * 1000,
            queue_wait_ms=queue_wait * 1000,
            inference_ms=inference_time * 1000,
            generated_tokens=len(generated_ids),
        )
    except Exception as exc:
        REQUESTS.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        IN_FLIGHT.dec()
