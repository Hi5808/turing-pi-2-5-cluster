# 002 — Pipeline-parallel LLM inference: measured behaviour

**Platform:** Turing Pi 2.5; node1 Turing RK1 (RK3588, orchestrator, CPU-only), node2 Jetson Orin
NX 16GB, node3 Jetson Orin Nano 8GB.
**Software stack:** Ubuntu 24.04.5; JetPack 7.2 / L4T R39.2 / CUDA 13.2 on nodes 2–3;
llama.cpp @ `704485942ab54bbbbf1f241b3550ffba35f5f37e` (ggml 0.19.0) built identically on all three
nodes; RPC backend (`ggml-rpc-server`) with CUDA on both Jetsons.
**Date:** 2026-11-17/18. **Status:** Phases 2–5b complete; optimization sweep in progress.

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

## 7. The impossible models run

Both targets exceed what either node can allocate individually, at constant Q3_K_M quantisation.

| | Dense Qwen3-32B | MoE Qwen3-30B-A3B |
|---|---|---|
| File size | 14.87 GiB (32.76B params) | 13.70 GiB (30.53B params, ~3B active) |
| node2 alone | **OOM, NvMap error 12** | **loads and runs at 18.63 t/s** (see correction, §9) |
| node3 alone (5.39 GiB) | **OOM, NvMap error 12** | exceeds by 8.3 GiB |
| **node2+node3, pp128** | **82.22 t/s** | **129.21 t/s** |
| **node2+node3, tg64** | **2.44 t/s** | **14.20 t/s** |
| tg256 | — | 14.88 t/s |
| Peak mem node2 | 11678 / 15599 MiB | 11585 / 15599 MiB |
| Peak mem node3 | 6450 / 7547 MiB | 5304 / 7547 MiB |
| Swap caused by run | **none** | **none** |
| Weights shipped from node1 | 15.67 GB | 14.62 GB |

Both produce coherent text. Dense:

> Hello my name is Ashlee and I live in Missouri. I was diagnosed with breast cancer in October
> 2006. I was 32 at the time. I had a lump in my left breast that was found during my self exam.
> It was stage 2B. It had already spread to the

MoE:

> Hello my name is Maria I am from Mexico City and I am a 23 year old woman who is very active on
> the internet and social media I'm a digital marketer and I am currently working as a freelance
> for the company of my ex boyfriend

**Primary result:** a 32.76B-parameter dense model runs at 2.44 t/s on a chassis where it cannot be
loaded on any single node, beating node1's CPU inference (~2 t/s) on a model 2.3× smaller. The
combined-memory thesis holds — **for the dense model only**; see the correction in §9.

### Swap validity check

node3 reported 105 MiB of swap in use during the dense run. Measuring at idle *before* the next run
showed the same 105 MiB, and it was unchanged after — so it is pre-existing from earlier activity
and **no run caused any spill**. Had this not been checked, the headline result would have rested on
an unexamined confound.

### Finding: MoE is 5.8× faster, and the prediction held

The prediction recorded before the run was that MoE would be faster in absolute terms but pay a
larger *relative* pipeline penalty, since it does far less compute per token for the same number of
round-trips and the same logit return.

| | Dense 32B | MoE 30B-A3B |
|---|---|---|
| Decode | 2.44 t/s | **14.20–14.88 t/s (5.8–6.1×)** |
| ms per token | ~410 ms | ~67 ms |
| Measured inbound per token | ~666 KB | ~617 KB |
| Transfer time at line rate | ~5.9 ms | ~5.5 ms |
| **Link as share of token budget** | **~1.4%** | **~8.2%** |

Both halves confirmed. MoE decodes 5.8× faster because only ~3B of 30B parameters are active, and
the link's share of its per-token budget is ~6× larger — the same absolute transfer cost against a
6× shorter token. Extrapolating, a pipeline fast enough to reach ~170 tok/s would be bandwidth-bound
on logits alone; MoE gets meaningfully closer to that wall than dense does.

Per-token traffic is near-identical between the two models despite the architectural difference,
which independently confirms section 4: the cost is the logit return, set by the shared 151,936
vocabulary, not by parameter count or activation sparsity.

### Finding: an explicitly specified split can fail outright

`llama-bench --tensor-split 69,31` — the capacity-derived ratio from section 2 — **failed to load
the dense model entirely**, with only 18 KB leaving node1 (i.e. it aborted before weight transfer,
not an OOM mid-load). The identical run without `--tensor-split`, letting llama.cpp allocate by free
memory, loaded and ran.

The likely mechanism is that large indivisible tensors (token embeddings, output head) are placed
whole on one device and do not obey the ratio, so a hand-tuned split that looks feasible on
aggregate numbers can leave one device unable to satisfy an allocation. **Practical consequence:
prefer the automatic allocator.** This inverts the plan's intent to hand-tune the split from
measured capacity — the measurement was useful for understanding the constraint, and actively
harmful as a configuration.


## 8. Batched decoding: the real throughput lever

Every measurement above says the pipeline is compute-bound with idle headroom everywhere else —
link at 4–8%, orchestrator CPU at 7.4%, and the logit return costing the same per *token* no matter
how many sequences produced it. Single-stream decode leaves the GPUs idle between round-trips.

`llama-batched-bench`, MoE, `-npp 128 -ntg 32`, KV q8_0, clocks locked:

| Streams (B) | N_KV | Prompt t/s | Decode t/s | Total t/s |
|---|---|---|---|---|
| 1 | 160 | 100.82 | 12.64 | 42.10 |
| 2 | 320 | 163.29 | 19.91 (1.58×) | 66.92 |
| 4 | 640 | 238.30 | 23.58 (1.87×) | 84.46 |
| 8 | 1280 | 254.36 | **35.30 (2.79×)** | **113.50** |

**2.79× aggregate decode throughput at 8 streams, 2.5× on prompt processing.** Each weight read from
memory serves all streams at once, so per-stream latency barely moves while aggregate throughput
climbs. This is how the idle headroom gets spent, and it is the answer to "more tokens" on this
hardware — not single-stream tuning.

### KV quantisation is only justified in combination

`-ctk q8_0 -ctv q8_0` *lost* 2.9% single-stream (§8a below), but 8 streams require 8× the KV cache
(N_KV reached 1280). The quantisation is what buys the stream count. Testing it one-factor-at-a-time
marked it useless; in combination it is an enabler. A caution against trusting isolated A/B results.

## 8a. Single-stream optimisation sweep

| Lever | MoE pp128 / tg64 | Dense pp128 / tg64 | Verdict |
|---|---|---|---|
| Baseline | 129.21 / 14.20 | 82.22 / 2.44 | — |
| `jetson_clocks` locked | **137.85 / 15.18 (+6.9%)** | 83.62 / **2.46 (+0.8%)** | **only real win** |
| + `-fa on` | 137.92 / 15.16 | 82.90 / 2.44 | neutral — `auto` already enabled it |
| + KV `q8_0` | 136.54 / 14.74 (−2.9%) | 82.90 / 2.44 | regression single-stream |
| + `-ub 1024` | 136.60 / 14.77 | — | neutral |

### Finding: clock-ramp loss scales inversely with per-token work

Locking clocks gained **6.9% on the MoE but only 0.8% on the dense model**. node2's GPU idles at
306 MHz of 1173 MHz under `schedutil`. Dense tokens take ~410 ms of sustained GPU work, so DVFS has
ample time to ramp within a single token; the MoE's ~67 ms tokens are short enough that ramp latency
is a material fraction of the work. **The faster a pipeline gets, the more clock locking matters** —
and this is invisible in single-node benchmarking, where sustained load keeps clocks high anyway.

Nothing else moved the needle, which is what compute-bound means in practice: levers that trade
compute for memory (KV quantisation) or amortise round-trips (`-ub`) have nothing to buy when the
link runs at 8% and memory is not short.

## 9. Correction: the MoE is not single-node-impossible

**Sections 7's MoE column as originally published was wrong.** It stated the MoE exceeded node2's
allocatable memory by 1.5 GiB. That was *inferred* from a 12.21 GiB reading, not measured — only the
dense model's single-node controls were actually run. Measured directly afterwards:

```
MoE on node2 alone: 13.70 GiB model, loads and runs, tg16 = 18.63 t/s (CUDA)
```

### Root cause: allocatable memory on unified-memory Jetsons is a moving target

The worker reported **12.21 GiB** available mid-session and **13.90 GiB** after a restart freed
resident memory — the same hardware, a 1.7 GiB swing. The MoE sits between those two figures, so its
feasibility depended on system state at launch. **Single-node impossibility must be measured at the
time, against a freshly started worker, not derived from an earlier reading.**

The dense model at 14.87 GiB exceeds even the 13.90 GiB best case, so the primary result stands
unchanged. But **only the dense 32B demonstrates the combined-memory thesis.**

### The correction yields a better measurement

Because the MoE *does* fit one node, its split run becomes a second overhead measurement — and it
supplies the relative-penalty number §7 claimed could not be measured:

| Model | Single node | Split across 2 | **Pipeline penalty** |
|---|---|---|---|
| Dense 14B Q4 | 7.49 t/s | 7.19 t/s | **−4.0%** |
| MoE 30B-A3B Q3 | 18.63 t/s | 15.18 t/s | **−18.5%** |

**The pre-recorded Phase 5b prediction is now directly confirmed:** the MoE pays a 4.6× larger
relative pipeline penalty than the dense model, because its per-token compute is small relative to
the fixed per-token link and round-trip cost. The practical rule: **split a model only if it does not
fit — for MoE models the penalty for splitting unnecessarily is steep.**

## 10. Dense batching: the prediction failed, and the mechanism was wrong

`llama-batched-bench`, dense Qwen3-32B Q3_K_M, `-npp 128 -ntg 32`, `-c 2048`, KV q8_0, clocks locked:

| Streams (B) | N_KV | Prompt t/s | Decode t/s | Total t/s |
|---|---|---|---|---|
| 1 | 160 | 71.67 | 2.41 | 10.61 |
| 2 | 320 | 79.78 | 4.31 (1.79×) | 17.71 |
| 4 | 640 | 81.92 | **5.85 (2.43×)** | 22.76 |

**Pre-recorded prediction: dense would scale *worse* than the MoE**, on the reasoning that dense
tokens already do ~410 ms of sustained GPU work so the GPUs are not idle between round-trips, leaving
batching less slack to reclaim.

**The prediction failed.** At matched stream count dense scales *better*: **2.43× at B=4 against the
MoE's 1.87× at B=4.**

### The mechanism was misidentified

The gain is not from filling idle time between round-trips. It is **weight-read amortisation**. Dense
decode streams all 14.87 GiB of weights out of memory per token; the MoE activates only ~3B of 30B
parameters, roughly 1.4 GiB per token. The dense model therefore has ~10× more weight traffic to
spread across concurrent streams, and benefits proportionally more.

**Corrected rule: batching gain scales with how weight-read-bound the model is**, not with idle GPU
time. The corollary is visible in the prompt-eval column: dense prompt processing gains only 1.14×
(71.67 → 81.92) while the MoE gained 2.5×, because dense prompt eval is already compute-saturated and
has no spare memory bandwidth to reclaim.

### Validity caveat on B=4

node2's swap rose from 1 MiB to **263 MiB** across these runs — unlike node3's pre-existing 105 MiB
(§7), this spill *was* caused by the runs. The B=4 figure is therefore affected by memory pressure and
should be read as a soft upper bound rather than a clean measurement. N_KV 640 against a 14.87 GiB
model is at the edge of this chassis's capacity.

This also explains the earlier silent crash of this benchmark: the first attempt used `-c 4096`, and
all three levels died without an error or an OOM message on node1 while the workers retained the
model. At `-c 2048` all three levels completed with `exit=0`. **Lesson: on unified-memory devices the
failure mode for an over-large KV allocation can be a silent client death, not a diagnosable OOM** —
so per-level raw logs and recorded exit codes are necessary to tell a crash from an empty result.
