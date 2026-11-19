# 004 — The RK3588 NPU as an inference engine: prefill yes, decode no

**Platform:** node1, Turing RK1 (RK3588), 4x Cortex-A76 + 4x Cortex-A55, 31 GB, Mali-G610,
3-core 6 TOPS NPU. Kernel 6.1.0-1025-rockchip.
**Date:** 2026-11-18. **Status:** measured.

## Abstract

Project 001's first design constraint asserted that node1 "cannot be a pipeline stage" because
its A76 cores are far slower at inference than either Orin GPU, and recorded the NPU as unusable
("driver present, no userland"). Both claims are revised here. The NPU driver *and* its userland
runtime are present and working, and the NPU is **2.0x faster than node1's own CPU at prefill**
while being **1.7x slower at decode**. The constraint holds for decode and fails for prefill,
which makes node1 a candidate prefill stage rather than an orchestrator-only node.

## Correction to the recorded state

Previously noted as "RK3588 NPU driver present, no userland". Measured state on node1:

| Component | State |
|---|---|
| NPU DRM node | `/dev/dri/renderD129`, `DRIVER=RKNPU`, `OF_NAME=npu` |
| Device tree | `npu@fdab0000` `status=okay`; driver built in, not a module |
| devfreq | `/sys/class/devfreq/fdab0000.npu` @ 1.0 GHz |
| Runtime | `/usr/lib/librknnrt.so` 2.3.2 (429f97ae6b, 2025-04-09) |
| LLM runtime | `librkllmrt.so` via `rkllama` 0.0.75 |
| Toolkit | `rknn-toolkit-lite2` 2.3.2 |

The userland was already installed. Nothing had been measured, which is a different problem from
nothing being available.

## Method

Same architecture and parameter count on both engines, 8-bit weights on both:

- **NPU:** `TinyLlama-1.1B-plain-w8a8-maxctx16384` (`.rkllm`, 1.26 GB) via the `rkllama` server
  (`--processor rk3588`), Ollama-compatible `/api/generate`, `stream: false`.
- **CPU:** `tinyllama-1.1b-chat-v1.0.Q8_0.gguf` (1.09 GiB) via `llama-bench`, `-t 8 -r 2`.

Prefill and decode are reported separately because they behave oppositely.

## Results

| Workload | NPU (3 cores, w8a8) | node1 CPU (8 threads, Q8_0) | Winner |
|---|---|---|---|
| **Prefill** | **219.94 t/s** (75 tok / 341 ms) | 110.73 ± 3.61 t/s (pp128) | **NPU 1.99x** |
| **Decode** | 9.67 t/s (127 tok / 13127 ms) | **16.11 ± 2.28 t/s** (tg64) | **CPU 1.67x** |

Decode was stable across runs: 9.76, 9.75, 9.74, 9.67 t/s.

### All three NPU cores are used, and none is saturated

Sampled `/sys/kernel/debug/rknpu/load` during decode (requires root):

```
idle:  Core0:  0%, Core1:  0%, Core2:  0%
decode: Core0: 64%, Core1: 62%, Core2: 60%   (steady, ~14 s)
```

This rules out the obvious objection that rkllm uses one of three cores. The load is distributed
evenly — and it plateaus near 62%, so decode is **not** NPU-compute-bound. At 9.67 t/s against
1.26 GB of weights the NPU moves ~12.2 GB/s, well under the RK3588's LPDDR5 ceiling, so it is not
DRAM-bound either. The limit is per-token launch and dispatch overhead on a batch-1 GEMV: the
NPU is a throughput engine being asked to do a latency-bound job.

## Why this mirrors project 003

003 found the Orin's DLA loses to its GPU at decode and will not even compile at prefill. The
RK3588 NPU shows the *same* fixed-function signature with the opposite prefill outcome:

| | decode (batch-1 GEMV) | prefill (batched GEMM) |
|---|---|---|
| Orin DLA vs Orin GPU | loses 2.1–33.7x | will not compile |
| RK3588 NPU vs RK3588 CPU | loses 1.67x | **wins 1.99x** |

Both accelerators are poor at decode for the same structural reason — no arithmetic intensity to
exploit. The difference is the baseline they are measured against: the Orin GPU already saturates
memory bandwidth, so the DLA has nothing to add, whereas node1's A76 cores are weak enough that
its NPU has real headroom to beat them at prefill.

## Consequence for the cluster

Project 001 constraint 1 said node1 cannot be a pipeline stage because pipeline throughput equals
the slowest stage. That reasoning is about **decode**, and it stands — 9.67 t/s on the NPU is
still slower than node1's own CPU and far slower than either Orin GPU.

But prefill is a separate stage with separate economics. A prefill-only role for node1 — NPU
ingests the prompt at ~220 t/s, KV cache ships to an Orin for decode — is not ruled out by
anything measured here, and it uses the one engine in the chassis that is otherwise completely
idle. Whether the KV-cache transfer cost eats the gain is the open question, and on this
interconnect that is the question that decides it: 001 measured ~119 MB/s between nodes, and a
1.1B-class KV cache for a long prompt is far larger than the ~10 KB/token of activations that
made pipeline parallelism viable in the first place.

## Open

- KV-cache size and transfer time for a realistic prompt vs the prefill time saved. This is the
  go/no-go for a prefill stage and has not been measured.
- Does the NPU win at prefill for a *larger* model, or does the 2x shrink as weights stop fitting
  the NPU's SRAM?
- `rknn-toolkit-lite2` is installed and a `yolov5s_relu_rk3588.rknn` model exists on node1; CNN
  throughput was not measured here and is the NPU's actual design target.
- The Mali-G610 was not considered. It is a third idle engine on node1.

## Reproduction

```bash
# NPU
/mnt/nvme/npu-bench/.venv/bin/rkllama_server --processor rk3588 --port 8080 \
  --models /mnt/nvme/npu-bench/models
curl -s http://127.0.0.1:8080/api/generate -H 'Content-Type: application/json' \
  -d '{"model":"TinyLlama-1.1B-plain-w8a8-maxctx16384","prompt":"...","stream":false,
       "options":{"num_predict":128}}'
# CPU
/mnt/nvme/llama.cpp/build-rpc/bin/llama-bench -m /mnt/nvme/tinyllama-1.1b-chat-v1.0.Q8_0.gguf \
  -p 128 -n 64 -t 8 -r 2
# core load
sudo cat /sys/kernel/debug/rknpu/load
```

**Instrumentation caveat:** rkllama's `/api/generate` reports `total_duration` in **nanoseconds**
but `prompt_eval_duration` and `eval_duration` in **milliseconds**. Treating them uniformly as ns
yields rates inflated by 1e6 (9.7 million t/s). All figures above divide the eval durations by
1e3.

**Model caveat:** the NPU model is the TinyLlama base ("plain"), the CPU model the chat
fine-tune. Same architecture and parameter count; fine-tuning does not change per-token cost.
Prefill token counts differ between the two measurements (75 vs 128) because the NPU figure comes
from a served request rather than a fixed harness.
