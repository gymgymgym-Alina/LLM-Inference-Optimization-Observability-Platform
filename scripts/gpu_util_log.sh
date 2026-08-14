#!/usr/bin/env bash
# Fallback GPU utilization logger for hosts where dcgm-exporter can't run
# (e.g. container-based GPU pods without full docker privileges).
# Samples nvidia-smi once per second into a CSV; run it alongside each
# load-test tier, then average the util column for experiments.md.
#
# Usage: ./scripts/gpu_util_log.sh <output.csv>   (Ctrl-C to stop)
set -euo pipefail

OUT="${1:?usage: gpu_util_log.sh <output.csv>}"

nvidia-smi \
    --query-gpu=timestamp,utilization.gpu,utilization.memory,memory.used,power.draw \
    --format=csv -l 1 | tee "$OUT"
