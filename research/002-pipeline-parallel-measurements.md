# 002 — Pipeline-parallel LLM inference: measured behaviour

**Platform:** Turing Pi 2.5; node1 Turing RK1 (RK3588, orchestrator, CPU-only), node2 Jetson Orin
NX 16GB, node3 Jetson Orin Nano 8GB.
**Software stack:** Ubuntu 24.04.5; JetPack 7.2 / L4T R39.2 / CUDA 13.2 on nodes 2–3;
llama.cpp @ `704485942ab54bbbbf1f241b3550ffba35f5f37e` (ggml 0.19.0) built identically on all three
nodes; RPC backend (`ggml-rpc-server`) with CUDA on both Jetsons.
**Date:** 2026-11-17. **Status:** in progress — Phases 2–4 complete, Phase 5 running.

## Abstract

Measures a two-stage pipeline-parallel (layer-split) LLM deployment across two different Jetson
modules, orchestrated by an ARM CPU node, over a 1GbE backplane. Three results contradict the
assumptions the experiment was designed around. The decode penalty for splitting a model across
two machines is **4%**, not the substantial slowdown the literature predicts. The compute
asymmetry between the two modules (2.3× in INT8 TOPS) **does not appear in decode throughput at
all**, because decode is memory-bandwidth-bound. And the dominant network traffic is not layer
activations but **logits returning to the orchestrator**, which scale with vocabulary size and
exceeded the predicted per-token volume by roughly 70×.

## 1. Single-node baselines

`llama-bench`, same model and settings on both nodes, 2 repetitions, `-ngl 99`.

| Node | Module | INT8 TOPS | Model | pp512 (t/s) | tg128 (t/s) |
|---|---|---|---|---|---|
| node2 | Orin NX 16GB | ~157 | Qwen3-4B Q4_K_M | 744.61 ± 18.24 | **20.00 ± 0.02** |
| node3 | Orin Nano 8GB | ~67 | Qwen3-4B Q4_K_M | 671.38 ± 7.16 | **18.16 ± 0.01** |
| node2 | Orin NX 16GB | — | Qwen3-14B Q4_K_M | 239.94 ± 2.24 | 7.49 ± 0.01 |

### Finding: the TOPS ratio does not predict decode throughput

node2 has **2.3× the INT8 TOPS of node3 and delivers 9% more decode throughput** on an identical
model. Both modules have the same 102 GB/s memory bandwidth, and single-stream token generation is
bandwidth-bound rather than compute-bound, so the compute advantage never materialises at batch
size 1. Prompt eval — which processes 512 tokens in parallel and is compute-bound — differs by
only 11%, also far less than the spec ratio implies.

**Consequence for stage balancing:** a throughput-weighted layer split would be ~52/48, not the
~70/30 a spec-sheet reading suggests. Deriving the split from TOPS would have been wrong.

## 2. What the nodes can actually allocate

The RPC workers report available unified memory at startup, and it is materially less than the
"VRAM" figure:

| Node | Reported total | **Actually allocatable** |
|---|---|---|
| node2 | 15599 MiB | 12806944 KB = **12.21 GiB** |
| node3 | 7547 MiB | 5651168 KB = **5.39 GiB** |
| combined | 23.1 GiB | **17.60 GiB** |

Jetson memory is unified CPU+GPU, so weights, KV cache, activations and the OS all draw from one
pool. **Capacity, not compute, is what forces the split proportions** (~69/31 by available memory),
which is the inverse of how distributed inference is usually reasoned about.

## 3. Pipeline overhead on a model that fits one node

Qwen3-14B Q4_K_M (8.38 GiB), which fits node2 alone, run both ways:

| Configuration | pp512 (t/s) | tg128 (t/s) |
|---|---|---|
| node2 alone (CUDA) | 239.94 ± 2.24 | 7.49 ± 0.01 |
| node2 + node3 (RPC layer split) | 200.57 ± 1.68 | **7.19 ± 0.00** |
| Pipeline cost | **−16.4%** | **−4.0%** |

### Finding: splitting costs ~4% of decode, not a large penalty

Community guidance states that adding RPC workers to a model that already fits one node makes
inference meaningfully slower. Measured here, decode loses 4.0%. The capacity gained by splitting
is therefore close to free — not the usual throughput-for-capacity trade.

The asymmetry between the two columns is the mechanism: prompt eval moves 512 tokens' worth of
activation data and loses 16.4%, while decode moves one token per round-trip and loses 4.0%. The
link penalises the parallel phase, not the sequential one.

## 4. Per-token network traffic

Naively measuring one run is useless: a single `-ngl 99` run moved 8.65 GB out of node1, but the
model is 8.38 GiB, so the figure is almost entirely one-time weight distribution. Instead two
generation-only runs were differenced, cancelling the weight transfer:

| Run | tg (t/s) | rx (bytes) | tx (bytes) |
|---|---|---|---|
| `-p 0 -n 128` | 7.19 | 183,630,101 | 8,582,652,252 |
| `-p 0 -n 512` | 7.14 | 439,443,974 | 8,596,868,169 |
| **Δ over 384 tokens** | — | **255,813,873** | **14,215,917** |

Marginal per token: **666,182 bytes inbound to node1**, **37,021 bytes outbound** → **~703 KB/token
total**.

### Finding: the dominant traffic is logits, not activations

The prediction was ~10 KB/token from layer-boundary activations. The measurement is ~70× higher,
and the inbound direction dominates by 18:1. The cause is the **logit vector returning to the
orchestrator**: Qwen3's vocabulary is 151,936 tokens, so one fp32 logit vector is
151,936 × 4 = 607,744 bytes = **593.5 KiB** — accounting for essentially all of the 666 KB/token
measured inbound.

This matters because it is invisible if you reason only about activations:

- The expensive hop is the **return path to the orchestrator**, not the stage-to-stage transfer.
- It scales with **vocabulary size**, not parameter count or layer count. A large-vocab 4B model
  costs the same per token here as a large-vocab 32B one.
- It is paid **once per token regardless of how many stages** the pipeline has, so adding stages
  does not multiply it.

### Link utilisation

703 KB/token × 7.19 tok/s ≈ 5.06 MB/s ≈ **40.4 Mbit/s — about 4% of the 1GbE link.** This
independently reproduces the community-reported 30–50 Mb/s range. The bandwidth ceiling implies
~169 tok/s before the link saturates, against 7.19 measured, so **the pipeline is latency- and
compute-bound, not bandwidth-bound** — consistent with the 4% decode penalty and vindicating the
decision (research log 000) to pursue pipeline parallelism on this interconnect.

## 5. Control experiment: single-node impossibility

Dense Qwen3-32B Q3_K_M (14.87 GiB, 15,971,778,208 bytes) on node2 alone, 12.21 GiB allocatable:

```
NvMapMemAllocInternalTagged failed: error 12
NvMapMemHandleAlloc failed: error 12
llama_bench: error: failed to load model '/mnt/share/models/Qwen3-32B-Q3_K_M.gguf'
```

Error 12 is `ENOMEM`; the failure occurs in the Tegra memory allocator. Recording this is what
makes "fits on no single node" a measurement rather than an assertion.

## 6. Method notes and corrections

- **Version alignment is mandatory.** node3 was on a newer commit (ggml 0.20.2) than node1/node2
  (0.19.0); the RPC wire format changes between releases. All three were aligned to
  `704485942`. node3's clone was depth-1 shallow, so the commit had to be fetched with
  `git fetch --depth=1 origin <full 40-char SHA>` — an abbreviated SHA is rejected.
- **The RPC worker target is `ggml-rpc-server`**, not `rpc-server`.
- **`llama-cli` cannot be built on a node without a JS toolchain** at this commit: it links
  `llama-server-impl`, which pulls a web-UI asset target. `LLAMA_BUILD_UI=OFF` does not gate it,
  and the prebuilt UI bundle (checksum verified correct) lacks a `workbox*.js` asset the validator
  requires. `LLAMA_BUILD_SERVER=OFF` removes the `llama-cli` target entirely. **Workaround:**
  `llama-batched` and `llama-perplexity` use the common argument parser, support `--rpc`, and have
  no server/UI dependency.
- **Measure marginal, not total, network traffic.** Weight distribution swamps per-token cost;
  difference two runs of different lengths.
- `pkill -f ggml-rpc-server` kills the SSH session issuing it, because the binary's path appears in
  the invoking command line. The `[g]`-bracket trick does not help when the literal path is present.

## 7. Open

Phase 5 (dense 32B split across both nodes) and Phase 5b (Qwen3-30B-A3B MoE Q3_K_M, 13.70 GiB) are
pending. The MoE sits below node2's 12.21 GiB allocatable by 1.5 GiB, so both models are genuinely
single-node-impossible and the dense-vs-MoE comparison holds at constant quantisation.

**Standing prediction for 5b, recorded before the run:** MoE activates ~3B of 30B parameters per
token, so each stage does less compute for the same number of round-trips and the same ~594 KiB
logit return. MoE should therefore be faster in absolute tok/s but pay a *larger relative* pipeline
penalty, with the link a bigger share of its per-token budget.
