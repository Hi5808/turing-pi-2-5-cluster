# 011 — One slow core taxes the whole inference: the big.LITTLE thread barrier on RK3588

**Platform:** Turing Pi 2.5; node1 Turing RK1 (Rockchip RK3588), 4x Cortex-A55 @ 1800 MHz
(`CPU part 0xd05`, cpu0-3) + 4x Cortex-A76 @ 2256 MHz (`0xd0b`, cpu4-7), 31 GB.
Kernel 6.1.0-1025-rockchip.
**Software:** llama.cpp `llama-completion` from `/mnt/nvme/llama-rpc-build`, Qwen3-0.6B Q4_K_M
(378 MiB), CPU-only via `-ngl 0 -dev none`.
**Date:** 2026-11-26. **Status:** complete. Measurements in `selfmodel.db` runs `5feecf2bb458`
(placement sweep) and `b3077a17ba4a` (process recovery). Harnesses:
[`suite/e2_big_little.sh`](../../capability-matrix/scripts/bench/suite/e2_big_little.sh),
[`suite/e7_a55_as_worker.sh`](../../capability-matrix/scripts/bench/suite/e7_a55_as_worker.sh).

> **Platform identification note.** Core types are read from `/proc/cpuinfo` CPU part IDs and
> confirmed by `cpufreq/cpuinfo_max_freq` (1800 vs 2256 MHz). Every arm is confined to named cores
> with `taskset`, and the thread count the binary actually used is read back from its own
> `system_info: n_threads = N` line rather than assumed from the flag.

## Abstract

Adding a single Cortex-A55 core to a four-thread A76 decode costs **26–32 % of throughput**, and
adding four A55 cores costs no more than adding one. That step shape identifies the mechanism:
llama.cpp splits work evenly per thread, so the slowest thread gates every token at a barrier and
one little core is enough to set the pace. The A55 cluster is not weak — four of them decode
**12.32 tok/s** alone — so this is a scheduling loss, not a hardware limit. The capability is
**fully recoverable as a separate process**: one process per cluster reaches **97.2 % of ideal
separability** and **+27 % over the big cluster alone**, where threads spanning both clusters
*lose* 23 %. The practical rule is therefore the opposite of the default: never give one inference
threads from both clusters; run one process per cluster instead.

## Question

`llama.cpp` defaults to using all available threads, and on an 8-core part that means all 8. On a
homogeneous CPU that is right. On big.LITTLE it is a question, and the usual framing — that slow
cores drag down an average — predicts that the penalty should grow with how many little cores you
add. A barrier predicts something different: a step, with no further cost after the first.

This matters beyond one chip. If the loss is a barrier, it is recoverable by changing the unit of
parallelism rather than the hardware, and the fix is free.

## Prior work, and what is new here

The closest published result is a Turing Pi write-up that found four-thread runs beating
configurations spread across both clusters, attributing it to keeping work on the A76 cluster. That
is an explanation offered, not a measured breakdown, and it reports a single figure (5.462 tok/s on
Qwen2.5-7B Q4_K_M). A TVM forum result on *different* big.LITTLE silicon found four small cores
**beating** four big ones, with both clusters together faster still — which cuts against any
blanket "fewer cores is faster" rule and is why this is measured per placement rather than asserted.

What is new: the per-placement sweep, the step shape that identifies the barrier, the measured cost
of the *first* little core, and the demonstration that process-level separation recovers it.

## Method

Qwen3-0.6B Q4_K_M, 96 tokens, `--ignore-eos --no-warmup`, decode rate taken from the binary's own
`eval time` line — never `prompt eval time`, which also ends in "tokens per second" and silently
yields prefill rates. Three repetitions for the placement sweep, five for the process arms.

**CPU-only on this build requires both `-ngl 0` and `-dev none`.** `-ngl 0` alone still loads the
Vulkan backend and produces non-monotonic nonsense; without either flag every layer is offloaded to
Mali and the sweep measures the GPU while appearing to measure the CPU.

## Results

### Placement sweep

| placement | threads | decode | sd |
|---|--:|--:|--:|
| 1x A76 | 1 | 17.13 tok/s | 0.10 |
| 2x A76 | 2 | 31.33 | 0.10 |
| 3x A76 | 3 | 41.60 | 2.57 |
| 4x A76 | 4 | **46.81** | 2.37 |
| 1x A55 | 1 | 3.37 | 0.05 |
| 2x A55 | 2 | 6.79 | 0.01 |
| 4x A55 | 4 | **12.39** | 0.02 |
| 4x A76 + 1x A55 | 5 | 31.83 (**−32.0 %**) | 6.32 |
| 4x A76 + 2x A55 | 6 | 34.89 (−25.5 %) | 4.65 |
| 4x A76 + 4x A55 | 8 | 34.41 (−26.5 %) | 0.85 |
| 2x A76 + 2x A55 | 4 | 28.82 | 0.23 |

A76/A55 ratio at equal core count: **3.78x**.

### Process recovery

Same model and flags, five repetitions, disjointly pinned:

| arm | decode | sd |
|---|--:|--:|
| A — one process, 4x A76 | 40.18 tok/s | 7.30 |
| B — one process, 4x A55 | 12.32 | 0.04 |
| C — **two processes, A76 + A55** | **51.02** | 5.77 |
| D — one process, 8 threads | 31.11 | 3.26 |

Inside arm C: the A76 process delivers 38.68 tok/s and the A55 process 12.33 tok/s.

```
A + B (if fully separable)  52.50
C measured                  51.02   = 97.2% of separable, 1.270x over A alone
D (threads span clusters)   31.11   = 0.774x of A
```

## Findings

1. **One A55 core costs 26–32 % of a four-thread A76 decode.** The first little core carries
   essentially the whole penalty.
2. **The penalty is a step, not a slope.** Four little cores cost no more than one (−26.5 % vs
   −32.0 %). An averaging mechanism cannot produce that; a per-token barrier can, because the
   slowest thread sets the pace regardless of how many slow threads there are.
3. **The A55 cluster is not weak.** It decodes 12.32–12.39 tok/s on its own, reproducibly, with the
   tightest variance of any arm here (sd 0.02–0.04).
4. **Thread parallelism cannot reach that capability.** Ideal 4+4 partitioning would give ~59
   tok/s; eight threads give 34.41, *worse than the four big cores alone*.
5. **Process separation recovers 97.2 % of it.** Two processes, one per cluster, reach 51.02 of a
   separable 52.50, and beat the big cluster alone by 27 %. Inside that arm the little-cluster
   process delivers 12.33 against its 12.32 solo rate — essentially zero interference — while the
   big-cluster process gives up only 3.7 %.
6. **So the loss is in the unit of parallelism, not the silicon.** Same cores, same model, same
   total hardware: 31.11 tok/s as one process with eight threads, 51.02 tok/s as two processes.
   A **1.64x** difference, free.
7. **The practical rule inverts the default.** `llama.cpp` uses all threads by default. On this
   part that is the worst of the three options measured. Pin one process per cluster.

## Corrections and limitations

**Arm A is the least trustworthy number here** (sd 7.30, per-rep 48.3 → 29.8), and it reads 40.18
in the process experiment against 46.81 in the placement sweep. Arms that occupy all four A76 cores
are bimodal on this node — established separately in
[010](010-cpu-per-submit-serial-cost.md): per-rep aggregates 48.56, 48.98, then 33.16, 35.51,
38.55. That instability is **not** thermal and **not** DVFS (clocks held 2256 MHz, min = max = mean,
at 44–60 °C); the remaining candidate is OS starvation when every big core is claimed, since
`k3s-server` alone takes ~8 % of a core. Findings 1–5 rest on arms with sd under 1 %; finding 6's
1.64x inherits arm A's noise and should be read as "large", not as three significant figures.

The mixed-placement arms are also the noisy ones (sd 6.32 and 4.65), so **−26 % is solid but the
ordering of −32.0 / −25.5 / −26.5 is within noise** — this paper does not claim that adding one
little core is *worse* than adding four, only that it is not better.

One model at one quantisation on one part. A 378 MiB model at ~50 tok/s moves ~19 GB/s, close to
this platform's practical DRAM ceiling, so a larger model may hit bandwidth before the barrier and
show a different balance. Prefill was measured in the placement sweep but is not analysed here.
The barrier is inferred from the step shape and from process recovery, not observed directly in
`llama.cpp`'s threadpool — confirming it in code would need instrumentation of the per-token
synchronisation point.

## Reproduction

[`suite/e2_big_little.sh`](../../capability-matrix/scripts/bench/suite/e2_big_little.sh) and
[`suite/e7_a55_as_worker.sh`](../../capability-matrix/scripts/bench/suite/e7_a55_as_worker.sh),
run via [`suite/run_all.sh`](../../capability-matrix/scripts/bench/suite/run_all.sh) which records
both into `selfmodel.db` automatically. Read
[`suite/PITFALLS.md`](../../capability-matrix/scripts/bench/suite/PITFALLS.md) first: the flag trap
in §Method and the decode-vs-prefill parsing trap each produced published-looking wrong numbers on
this cluster before being caught.
