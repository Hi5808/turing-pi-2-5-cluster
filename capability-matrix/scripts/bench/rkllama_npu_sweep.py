#!/usr/bin/env python3
"""Benchmark decode tok/s at a single fixed NPU devfreq step. Called once per
step by sweep_npu.sh, which handles pinning the frequency (needs root) before
invoking this. Appends its result to npu_sweep_results.json.
"""
import sys
sys.path.insert(0, "/mnt/nvme/npu-bench")
from bench import run_trial, npu_temp_c
import json
import os
import statistics

MODEL = "TinyLlama-1.1B-plain-w8a8-core3"
PROMPTS = [
    "List five random fruits and describe each one in one sentence, focusing on taste and texture.",
    "Explain how photosynthesis works in simple terms for a curious child.",
    "Write a short story opening about a lighthouse keeper discovering something strange.",
]
TRIALS = 4
RESULTS_PATH = "/mnt/nvme/npu-bench/out/npu_sweep_results.json"

npu_freq_hz = int(sys.argv[1])

trials = []
print(f"--- NPU pinned @ {npu_freq_hz} Hz ---")
for i in range(TRIALS):
    prompt = PROMPTS[i % len(PROMPTS)]
    r = run_trial(MODEL, prompt)
    trials.append(r)
    if "error" in r:
        print(f"  trial {i+1}/{TRIALS} ERROR: {r['error'][:150]}")
    else:
        print(f"  trial {i+1}/{TRIALS} decode={r['decode_tok_s']} tok/s n_tok={r['eval_count']} temp_after={r['npu_temp_after_c']}C")

valid = [t for t in trials if "error" not in t and t.get("decode_tok_s")]
mean = round(statistics.mean(t["decode_tok_s"] for t in valid), 2) if valid else None
stdev = round(statistics.stdev(t["decode_tok_s"] for t in valid), 2) if len(valid) > 1 else 0
print(f"  -> mean decode: {mean} +/- {stdev} tok/s ({len(valid)}/{TRIALS} valid)\n")

all_results = {}
if os.path.exists(RESULTS_PATH):
    with open(RESULTS_PATH) as f:
        all_results = json.load(f)
all_results[str(npu_freq_hz)] = {"trials": trials, "mean_decode_tok_s": mean, "stdev": stdev, "n_valid": len(valid)}
with open(RESULTS_PATH, "w") as f:
    json.dump(all_results, f, indent=2)
