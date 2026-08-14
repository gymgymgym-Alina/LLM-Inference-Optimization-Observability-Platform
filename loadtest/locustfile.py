"""Locust load test for the /generate endpoint.

Reproducibility rules (change one variable at a time — see CLAUDE.md):
- Fixed prompt and fixed max_new_tokens for every request, so generation
  length is identical across runs and across optimization rounds.
- Greedy decoding on the server side makes output deterministic.
- Concurrency is the ONLY knob turned between tiers, via -u on the CLI.

Usage (headless, one tier per run):
    locust -f loadtest/locustfile.py --host http://<HOST>:8000 \
        --headless -u <CONCURRENCY> -r <CONCURRENCY> -t 5m \
        --csv results/<tag>_u<CONCURRENCY>

-u = number of concurrent users, -r = spawn rate (spawn all users at once so
the whole run is at target concurrency), -t = duration, --csv writes
percentile stats to CSV for experiments.md.
"""

import os

from locust import HttpUser, constant, task

PROMPT = os.environ.get(
    "LOADTEST_PROMPT",
    "Explain the difference between a process and a thread in one paragraph.",
)
MAX_NEW_TOKENS = int(os.environ.get("LOADTEST_MAX_NEW_TOKENS", "64"))

# Under the serial baseline at 100 users, a request can wait many minutes in
# the queue. A short client timeout would kill those requests and silently
# understate P99 — so the timeout is generous on purpose.
REQUEST_TIMEOUT_S = int(os.environ.get("LOADTEST_TIMEOUT_S", "600"))


class GenerateUser(HttpUser):
    # Closed-loop load: each user waits for its response, then immediately
    # sends the next request. Offered load adapts to what the server can
    # sustain, which is the right model for measuring capacity (QPS at a
    # given concurrency) without overload collapse hiding the signal.
    wait_time = constant(0)

    @task
    def generate(self):
        with self.client.post(
            "/generate",
            json={"prompt": PROMPT, "max_new_tokens": MAX_NEW_TOKENS},
            timeout=REQUEST_TIMEOUT_S,
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
                return
            body = resp.json()
            # Guard against silently measuring truncated/empty generations.
            if body.get("generated_tokens", 0) <= 0:
                resp.failure("empty generation")
            else:
                resp.success()
