#!/usr/bin/env python3
"""NPU LLM inference benchmark harness for rkllama on RK3588 (ROCK 5B+).

Measures decode tok/s, prefill tok/s, NPU temp delta, and RAM delta across
repeated trials per model. Duration fields from rkllama's /api/chat are
inconsistently scaled (total_duration=ns, eval_duration/prompt_eval_duration=ms) —
this script accounts for that explicitly.
"""
import json
import subprocess
import time
import statistics
import requests

SERVER = "http://localhost:8080"
NPU_TEMP_PATH = "/sys/class/hwmon/hwmon6/temp1_input"
TRIALS_PER_MODEL = 6
REQUEST_TIMEOUT_S = 90

MODELS = ["TinyLlama-1.1B-plain-w8a8-maxctx16384"]

PROMPTS = [
    "List five random fruits and describe each one in one sentence, focusing on taste and texture.",
    "Explain how photosynthesis works in simple terms for a curious child.",
    "Write a short story opening about a lighthouse keeper discovering something strange.",
]


def npu_temp_c():
    with open(NPU_TEMP_PATH) as f:
        return int(f.read().strip()) / 1000.0


def mem_used_mb():
    out = subprocess.run(["free", "-m"], capture_output=True, text=True).stdout
    line = out.splitlines()[1].split()
    return int(line[2])  # used


def run_trial(model, prompt):
    t_before = npu_temp_c()
    mem_before = mem_used_mb()
    t0 = time.time()
    resp = requests.post(
        f"{SERVER}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": 100},
        },
        timeout=REQUEST_TIMEOUT_S,
    )
    wall = time.time() - t0
    t_after = npu_temp_c()
    mem_after = mem_used_mb()
    data = resp.json()
    if "error" in data:
        return {"error": data["error"], "wall_s": wall}

    eval_count = data.get("eval_count", 0)
    eval_ms = data.get("eval_duration", 0)  # milliseconds, despite the name
    prompt_eval_count = data.get("prompt_eval_count", 0)
    prompt_eval_ms = data.get("prompt_eval_duration", 0)

    decode_tps = (eval_count / (eval_ms / 1000.0)) if eval_ms else None
    prefill_tps = (prompt_eval_count / (prompt_eval_ms / 1000.0)) if prompt_eval_ms else None

    return {
        "wall_s": round(wall, 3),
        "eval_count": eval_count,
        "eval_ms": eval_ms,
        "decode_tok_s": round(decode_tps, 2) if decode_tps else None,
        "prompt_eval_count": prompt_eval_count,
        "prompt_eval_ms": prompt_eval_ms,
        "prefill_tok_s": round(prefill_tps, 2) if prefill_tps else None,
        "done_reason": data.get("done_reason"),
        "response_chars": len(data.get("message", {}).get("content", "")),
        "npu_temp_before_c": t_before,
        "npu_temp_after_c": t_after,
        "npu_temp_delta_c": round(t_after - t_before, 1),
        "mem_used_mb_before": mem_before,
        "mem_used_mb_after": mem_after,
    }


def main():
    results = {}
    for model in MODELS:
        print(f"\n=== {model} ===")
        trials = []
        for i in range(TRIALS_PER_MODEL):
            prompt = PROMPTS[i % len(PROMPTS)]
            print(f"  trial {i+1}/{TRIALS_PER_MODEL} (npu_temp={npu_temp_c()}C) ...", end=" ", flush=True)
            try:
                r = run_trial(model, prompt)
            except Exception as e:
                r = {"error": f"{type(e).__name__}: {e}"}
            trials.append(r)
            if "error" in r:
                print(f"ERROR: {r['error'][:100]}")
            else:
                print(f"decode={r['decode_tok_s']} tok/s  prefill={r['prefill_tok_s']} tok/s  "
                      f"n_tok={r['eval_count']}  temp_after={r['npu_temp_after_c']}C  delta={r['npu_temp_delta_c']}C")
            # incremental save after every trial so a late failure doesn't lose everything
            with open("/mnt/nvme/npu-bench/out/results.json", "w") as f:
                json.dump({"partial": True, "models_so_far": results | {model: {"trials": trials}}}, f, indent=2)
            time.sleep(3)

        valid = [t for t in trials if "error" not in t and t["decode_tok_s"]]
        summary = {}
        if valid:
            decode_vals = [t["decode_tok_s"] for t in valid]
            prefill_vals = [t["prefill_tok_s"] for t in valid if t["prefill_tok_s"]]
            summary = {
                "n_valid_trials": len(valid),
                "decode_tok_s_mean": round(statistics.mean(decode_vals), 2),
                "decode_tok_s_stdev": round(statistics.stdev(decode_vals), 2) if len(decode_vals) > 1 else 0,
                "prefill_tok_s_mean": round(statistics.mean(prefill_vals), 2) if prefill_vals else None,
                "npu_temp_max_delta_c": max(t["npu_temp_delta_c"] for t in valid),
                "mem_used_mb_at_load": valid[0]["mem_used_mb_after"],
            }
            print(f"  -> mean decode: {summary['decode_tok_s_mean']} +/- {summary['decode_tok_s_stdev']} tok/s")

        results[model] = {"trials": trials, "summary": summary}

    with open("/mnt/nvme/npu-bench/out/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nSaved results.json")


if __name__ == "__main__":
    main()
