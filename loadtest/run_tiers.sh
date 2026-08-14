#!/usr/bin/env bash
# Run the full concurrency ladder against a target host, one tier at a time.
# Usage: ./loadtest/run_tiers.sh http://<HOST>:8000 <tag> [duration]
#   tag      — label for this configuration, e.g. "baseline-gpu-3090"
#   duration — per-tier run time, default 5m (use 1m for local pipeline checks)
set -euo pipefail

HOST="${1:?usage: run_tiers.sh <host-url> <tag> [duration]}"
TAG="${2:?usage: run_tiers.sh <host-url> <tag> [duration]}"
DURATION="${3:-5m}"
TIERS=(1 10 50 100)

mkdir -p loadtest/results

for U in "${TIERS[@]}"; do
    echo "=== tier: ${U} concurrent users, ${DURATION} ==="
    locust -f loadtest/locustfile.py --host "$HOST" \
        --headless -u "$U" -r "$U" -t "$DURATION" \
        --csv "loadtest/results/${TAG}_u${U}" \
        --only-summary
    echo "=== tier ${U} done; cooling down 30s so runs don't bleed into each other ==="
    sleep 30
done

echo "All tiers done. Percentiles are in loadtest/results/${TAG}_u*_stats.csv"
echo "Copy P50/P99/QPS into experiments.md — one row per tier."
