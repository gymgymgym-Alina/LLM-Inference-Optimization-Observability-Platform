import os
import time
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen2.5-1.5B-Instruct")
DEFAULT_MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "256"))

state: dict = {"model": None, "tokenizer": None, "device": None}


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


class GenerateRequest(BaseModel):
    prompt: str
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS


class GenerateResponse(BaseModel):
    response: str
    latency_ms: float


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

    messages = [{"role": "user", "content": req.prompt}]
    text = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = tokenizer(text, return_tensors="pt").to(device)

    start = time.perf_counter()
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=req.max_new_tokens,
            do_sample=False,
            temperature=None,
            top_p=None,
            top_k=None,
        )
    latency_ms = (time.perf_counter() - start) * 1000

    generated_ids = output_ids[0][inputs["input_ids"].shape[1]:]
    response_text = tokenizer.decode(generated_ids, skip_special_tokens=True)

    return GenerateResponse(response=response_text, latency_ms=latency_ms)
