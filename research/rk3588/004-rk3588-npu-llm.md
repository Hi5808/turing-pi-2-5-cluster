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

## Consequence for the cluster — measured, and the idea is dead

**Updated 2026-11-18, same day.** The section this replaces proposed node1 as a *prefill* stage
(NPU ingests the prompt at ~220 t/s, KV cache ships to an Orin for decode) and named the
KV-transfer cost over the ~119 MB/s backplane as the go/no-go. Both the proposal and the stated
decider were wrong. Measured:

### 1. An Orin prefills ~10x faster than node1's NPU

Same model, same quantization class, `llama-bench -ngl 99` over the RPC backend to node2:

| Engine | prefill pp128 | prefill pp512 | decode |
|---|---|---|---|
| node1 NPU (3 cores, w8a8) | 219.94 t/s | — | 9.67 t/s |
| node1 CPU (8 threads, Q8_0) | 110.73 ± 3.61 | — | 16.11 ± 2.28 |
| **node2 Orin NX (CUDA, Q8_0)** | **1966.82 ± 178.43** | **2269.58 ± 41.36** | **45.31 ± 0.40** |

The NPU's 2.0x win over node1's own CPU is real but irrelevant: the Orin beats the NPU by
**8.9-10.3x at prefill** and 4.7x at decode. There is no prompt length at which routing prefill
to node1 beats simply prefilling on the node that will decode. The Orin figures are measured
*through* RPC while node2 was also running a DLA compile on one of its eight cores, so node2's
native rate is at least this high — which only widens the gap.

### 2. The NPU cannot host the models the cluster exists to run

KV geometry read from the GGUF metadata, not estimated:

| Model | n_layer | n_head_kv | n_embd_head | KV per token |
|---|---|---|---|---|
| TinyLlama-1.1B | 22 | 4 | 64 | 22,528 B (22 KiB) |
| Qwen3-32B | 64 | 8 | 128 | 262,144 B (**256 KiB**) |

Qwen3-32B — the model 002 runs split across the two Orins — would need ~32 GB of w8a8 weights
against node1's 31 GB of RAM, before any KV cache. It cannot be hosted on the NPU at all, and a
KV cache is model-specific, so prefilling a *different, smaller* model on node1 produces a cache
no Orin can consume. The idea fails on capacity before bandwidth is even consulted.

### 3. Transfer cost was never the blocker

Measured backplane node1 -> node2: **105.1 MB/s** over SSH (600 MB in 5.71 s; 001's clean
119 MB/s is line rate without encryption).

| Model | Prompt | KV size | Transfer | Prefill on Orin pipeline |
|---|---|---|---|---|
| Qwen3-32B | 512 | 134.2 MB | 1.28 s | 7.1 s |
| Qwen3-32B | 2048 | 536.9 MB | 5.11 s | 28.6 s |
| Qwen3-32B | 8192 | 2147.5 MB | 20.43 s | 114.3 s |

Transfer is ~18% of prefill time — affordable. Had capacity and prefill rate permitted the
split, the wire would **not** have stopped it. Naming the transfer as the decider was a guess,
and it was the wrong guess.

### Net

**Project 001 constraint 1 stands unmodified: node1 orchestrates and holds nothing hot.** Not
because its CPU is weak — that part of 001's reasoning was incomplete — but because every engine
on node1, NPU included, is an order of magnitude behind an Orin at both phases of inference, and
because node1 cannot hold the model. The NPU's only defensible use on this cluster is work the
Orins are not doing at all, on a model small enough to fit, at a time when the Orins are
saturated. That is a narrow enough window that it should not shape the architecture.

## Open

- Is there any model both the NPU and an Orin can host where the NPU's prefill is competitive?
  Everything measured says no, but only TinyLlama-1.1B was tested on the NPU because it is the
  one converted `.rkllm` on hand; conversion requires the x86 rknn-llm toolkit.
- Does the NPU beat the *Orins* at anything? CNN inference is its design target and was not
  measured; `yolov5s_relu_rk3588.rknn` is on node1 for exactly this.
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
