# 010 — The per-submit serial cost, measured on a CPU: fit it from width, test it on concurrency

**Platform:** Turing Pi 2.5; node1 Turing RK1 (Rockchip RK3588, 4x Cortex-A55 @ 1800 MHz +
4x Cortex-A76 @ 2256 MHz), kernel 6.1.0-1025-rockchip.
**Software:** llama.cpp `llama-completion` from `/mnt/nvme/llama-rpc-build`, Qwen3-0.6B Q4_K_M
(378 MiB), CPU-only via `-ngl 0 -dev none`.
**Date:** 2026-11-25. **Status:** complete. Measurements in `selfmodel.db` run `bb4ba8ff8a53`.

> **Platform identification note.** Core types are read from `/proc/cpuinfo` CPU part IDs —
> `0xd05` (A55) on cpu0-3, `0xd0b` (A76) on cpu4-7 — and confirmed by
> `cpufreq/cpuinfo_max_freq` (1800 vs 2256 MHz). Every arm is confined to named cores with
> `taskset`, and the thread count the binary actually used is read back from its own
> `system_info: n_threads = N` line rather than assumed from the flag.

## Abstract

[007 §3b](../jetson-orin/007-dla-concurrency-fragmentation.md) isolated a fixed **per-submit**
serial cost on the Orin NX's DLA by varying DLA-resident depth at a submit count of exactly one.
That method needs a depth knob and so cannot be applied to a general-purpose engine. A CPU admits
a stronger test, because thread width is continuous: **fit the serial cost from a width sweep, then
predict the concurrency curve the fit never saw.** On three homogeneous A76 cores, least squares on
width alone gives a serial segment of **S = 5.485 ms/token** (R² = 1.0000, 23.7% of per-token time)
and predicts aggregate throughput within **+0.2%** at one stream and **+5.7%** at three. The same
functional form therefore holds on two engines of entirely different design, measured by two
independent methods. Two corrections fall out: width scales at **84% efficiency** here, not "not at
all", and the **1.64x** concurrency advantage published for this CPU is **withdrawn in favour of
1.126x** — the original baseline was handicapped by the A55 cores.

## Question

A fixed cost paid once per submission, rather than per unit of work, predicts two things at once:
widening a single inference cannot amortise it, and running several concurrent inferences can. That
is a strong claim, and until now it rested on one engine (the DLA) plus convergent circumstantial
headroom on three others. The question here is whether it survives on an engine with no
fixed-function submit path at all, and whether a cost measured one way predicts behaviour measured
another way — the difference between a fitted curve and an isolated mechanism.

## Method

```
one stream, n threads, per-token time   t(n) = S + W/n
k streams, 3/k threads each, aggregate  T(k) = k / (S + W*k/3)
```

S and W are fitted by least squares on the **width sweep only**. T(k) is then a prediction, not a
fit. The model is falsifiable in the direction that matters: if S ≈ 0, T(k) is flat and concurrency
cannot help — which the measured curve would contradict.

96 tokens per request, `--ignore-eos --no-warmup`, 5 repetitions per arm, decode rate taken from
the binary's own `eval time` line (never `prompt eval time`). Streams are disjointly pinned: one
core each at k=3, so no two processes share a core.

**The budget is three A76 cores (cpu4,5,6), not four, and not eight.** Eight threads would span
both core types, making `W/n` meaningless. Four would claim the entire big cluster; see
§Corrections for why that regime is unusable.

## Results

| arm | threads | aggregate decode | sd |
|---|--:|--:|--:|
| width, 1 stream | 1 | 17.100 tok/s | 0.3% |
| width, 1 stream | 2 | 31.398 tok/s | 0.2% |
| width, 1 stream | 3 | 43.050 tok/s | 0.6% |
| concurrency, 1 stream | 3 | 43.122 tok/s | 0.7% |
| concurrency, 3 streams | 1 each | **48.538 tok/s** | 0.2% |

Fit on the width sweep alone:

```
S = 5.485 ms/token (serial)    W = 52.965 ms/token (parallel)    R² = 1.0000
serial share at 3 cores = 23.7%        width 1->3 scaling = 2.518x  (84% of ideal)
```

Out-of-sample prediction of the concurrency curve:

| | predicted from width | measured | error |
|---|--:|--:|--:|
| k=1, 3 threads | 43.215 | 43.122 | **+0.2%** |
| k=3, 1 thread each | 51.326 | 48.538 | **+5.7%** |

Concurrency gain at a constant homogeneous budget: **1.126x** (48.538 / 43.122).

### DVFS and temperature excluded

During a 4-thread arm, sampled 40 times at 0.5 s: `cpu4` and `cpu7` both held **2256 MHz with
min = max = mean**, soc 44-55 °C, bigcore0 45-60 °C. Neither clock reduction nor thermal
throttling occurs at any point, which matches the independent 5-minute all-core soak recorded in
matrix row F06 (RK1 2256 MHz, 62 °C, no throttling).

## Findings

1. **A fixed serial segment exists on this CPU and is 5.485 ms/token**, 23.7% of per-token time at
   three cores. It is not removed by any amount of width.
2. **A cost fitted from width predicts concurrency.** +0.2% at one stream, +5.7% at three. This is
   what distinguishes an isolated mechanism from a fitted curve: the concurrency arms were never
   used in the fit.
3. **The mechanism now holds on two engines by two methods.** DLA: a flat 0.21 ± 0.05 ms adder,
   constant across a 13.8x range of inference time ([007 §3b](../jetson-orin/007-dla-concurrency-fragmentation.md)).
   CPU: 5.485 ms/token from thread width. Different silicon, different submit paths, same form.
4. **Width scales at 84% efficiency, which the serial share predicts.** 2.518x of an ideal 3x. The
   claim that width "does not scale" is wrong as an absolute; it scales exactly as far as the
   parallel fraction permits. The NPU's 1.60x of 3x (53%) is the same statement with a larger
   serial share.
5. **Concurrency's advantage here is 12.6%, not 64%.** See Corrections.
6. **A per-submit cost is necessary but not sufficient.** The +5.7% over-prediction at three
   streams is a real residual that grows with k, so concurrent streams interfere beyond the fixed
   cost. Shared L3 and DRAM are the untested candidates.

## Corrections and retractions

**The 1.64x figure for this CPU is withdrawn and replaced by 1.126x.** The original (matrix row
A26, 2026-11-24) compared one 8-thread inference against three 2-thread processes across
**4x A55 + 4x A76**. That baseline was handicapped by the little cores: one inference on four A76
cores alone reaches 43.70 tok/s against 35.07 on eight mixed threads, so **adding the A55 cores
makes a single wide inference slower**. At a constant homogeneous budget the advantage is 1.126x.
Only the smaller factor was the per-submit effect; the remainder was core-type scheduling.

**An intermediate 1.323x, reported from two repetitions, is also withdrawn.** Arms that occupy all
four A76 cores are bimodal — per-rep aggregates 48.56, 48.98, then 33.16, 35.51, 38.55 — while
every arm at ≤3 threads per process is stable to <1% (the 3-stream arm has sd 0.03). A 2-rep
sample caught only the fast mode. **The cause is not thermal and not DVFS** (clocks held 2256 MHz,
min = max = mean, at 44-60 °C). The remaining candidate is OS starvation when every big core is
claimed: `k3s-server` alone takes ~8% of a core on this node. Any CPU concurrency claim on this
part must state whether the OS had a spare core.

**Two harness defects, both caught by implausible data rather than by an error.** First, the decode
regex matched `prompt eval time` before `eval time`, so the first figures reported were prefill
rates presented as decode. Second, the harness omitted `-ngl 0 -dev none`, so **every arm ran on
Mali rather than the CPU** — this build offloads all layers to Vulkan by default. The tell was
decode identical at 1, 4 and 8 threads (9.21 / 9.21 / 9.20), reproducing the published Mali arm to
two decimals; a knob that changes nothing is more often disconnected than saturated. Note that
`-ngl 0` alone is **not** a CPU run: the Vulkan backend still loads and yields non-monotonic
nonsense (1.32 / 4.83 / 2.62 at 1 / 4 / 8 threads).

## Limitations

One model at one quantisation on three cores of one part. A 378 MiB model at ~48 tok/s moves
~18 GB/s, close to this platform's practical DRAM ceiling, so the fitted S may absorb bandwidth
effects that a smaller model would separate — this is the most likely way finding 1's figure is
wrong. The functional form `t(n) = S + W/n` is Amdahl's law, which fits many mechanisms; its force
here comes from the out-of-sample prediction, not from R² alone.

The specific shared resource is unidentified, exactly as on the DLA. Nothing here distinguishes a
memory-ordering barrier, a runtime synchronisation point, or a kernel-launch-equivalent cost in the
threadpool. Prefill was not analysed. The A55 cluster was measured only as the handicap it imposes,
never characterised on its own.

## Reproduction

`iso3.sh` on node1 (`/tmp/iso3.sh`, also in `selfmodel.db` run `bb4ba8ff8a53` notes). Binary and
model: `/mnt/nvme/llama-rpc-build/bin/llama-completion`,
`/mnt/nvme/share/models/Qwen3-0.6B-Q4_K_M.gguf`. Always pass **both** `-ngl 0` and `-dev none` for
a CPU-only run on this build, and read back `n_threads` from the binary's `system_info` line.
