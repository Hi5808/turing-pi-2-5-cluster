# 012 — A module that served on CPU for three months: `-ngl 99` as a silent no-op, and what it cost

**Platform:** Turing Pi 2.5; node3 Jetson Orin Nano 8GB (1024 CUDA cores, sm_87, no DLA),
CUDA 13.2, driver present, `/dev/nvgpu` and `/dev/nvhost-gpu` present throughout.
**Software:** before — `llama-server` from the release build `dc64a1620` (b10533, dated
**2026-08-20**); after — a local build of `074f1f3` with `GGML_CUDA=ON`,
`CMAKE_CUDA_ARCHITECTURES=87`. Qwen3-4B Q4_K_M staged on local NVMe.
**Date:** 2026-11-26. **Status:** complete. Measurements in `selfmodel.db` run `d58cab4922db`.
Harness: [`suite/e3_cpu_vs_gpu_energy.sh`](../../capability-matrix/scripts/bench/suite/e3_cpu_vs_gpu_energy.sh).

> **Platform identification note.** The absence of GPU execution is established from the binary
> rather than inferred from performance: the shipped directory contains `libggml-cpu-armv8.*.so`,
> `libggml-cpu-armv9.*.so` and `libggml-rpc.so` and **no `libggml-cuda.so` at all**, and
> `~/llama.cpp/build/bin/llama-server` did not exist on this node. GPU execution after the change
> is established by `gpu_load` rising from 0 to 968 during a request, not by throughput alone.

## Abstract

This module's `llama-server` had **no CUDA backend compiled in**, so the `-ngl 99` in its start
script was accepted and silently ignored, and every `llama-server` measurement taken on it since
2026-08-20 was a CPU measurement. Nothing failed, nothing warned, and the figures looked plausible
because a six-core Cortex-A78AE is not slow. Building the same source with CUDA and measuring both
paths with **one binary, one model and identical flags** gives the cost: at four concurrent streams
the GPU delivers **4.29x the throughput at slightly lower package power, so 4.35x the energy
efficiency**. At one stream it is 2.18x. The failure mode is the finding: a flag that does nothing
is indistinguishable from a flag that works, unless you check the backend or the rails.

## Question

`-ngl N` offloads N layers to the GPU. On a build without a GPU backend there is nothing to offload
to, and llama.cpp does not treat that as an error — the flag parses, the server starts, requests
succeed. The only symptoms are a throughput figure with nothing to compare it against and a
`gpu_load` nobody is reading.

The question is what that cost, measured properly, and how it could have been caught.

## How it was found

Not by looking for it. While upgrading llama.cpp to chase an unrelated shutdown bug
([matrix A44](../../capability-matrix/MATRIX.md)), a check of which binary each node ran turned up
`-ngl 99` in a start script pointing at a directory with no CUDA backend. The confirming details:

- the release directory listing contains seven `libggml-cpu-*.so` variants and no `libggml-cuda.so`
- `~/llama.cpp/build/bin/llama-server`, which would have been a local CUDA build, did not exist
- the only `llama-server` on the box was dated **2026-08-20**
- a CUDA backend built for the right architecture *did* exist in `~/llama-rpc-build`
  (`libggml-cuda.so`, `sm_87`) — but that build has no `llama-server`, only the RPC server

So the module had the toolkit, the driver, the GPU and a correctly-targeted backend on disk, and
still served every request on its CPU.

## Method

Both arms use the **same binary** (`074f1f3`, built locally with CUDA), the **same model**, and
identical `-c 2048 --parallel 4`. The only difference is `-ngl 0 -dev none` versus `-ngl 99`.

Power is read from the module's INA3221 at 1 Hz across the request window, with a 10-sample idle
baseline taken with the managed service stopped.

> **Instrumentation limit, stated rather than worked around.** Rail 2 on this module is
> `CPU_GPU_CV` — CPU, GPU and CV share one INA3221 channel — so there is **no clean iGPU-only power
> reading**, and per NVIDIA's own documentation the SoC rail excludes those blocks. Every tok/J
> figure here is therefore total-module `VDD_IN` (rail 1), which is the honest quantity for a
> deployed box and cannot be decomposed further with this hardware.

## Results

Idle baseline: **6.731 W**.

| arm | streams | aggregate | VDD_IN | tok/J | tok/J net of idle |
|---|--:|--:|--:|--:|--:|
| CPU (`-ngl 0 -dev none`) | 1 | 9.34 tok/s | 13.33 W | 0.701 | 1.417 |
| GPU (`-ngl 99`) | 1 | 20.38 tok/s | 12.57 W | 1.621 | 3.488 |
| CPU | 4 | 21.47 tok/s | 12.72 W | 1.688 | 3.584 |
| GPU | 4 | **92.12 tok/s** | **12.55 W** | **7.340** | **15.831** |

```
GPU advantage, 1 stream:   2.18x throughput   2.31x tok/J
GPU advantage, 4 streams:  4.29x throughput   4.35x tok/J   (4.42x net of idle)
```

The GPU arms draw **less** package power than the CPU arms at both concurrencies.

Post-change verification on the live service: `gpu_load` 968 during a request, decode 20.42 tok/s,
prefill 74.60 tok/s — reproducing the `gpu_k1` arm's 20.38 to within 0.2 %.

## Findings

1. **A missing backend is silent.** `-ngl 99` on a build without `libggml-cuda.so` is accepted,
   logged without complaint, and ignored. There is no error, no warning, and no degraded-mode
   notice.
2. **The cost here was 4.29x throughput and 4.35x energy efficiency** at four streams, and 2.18x at
   one. For three months this module ran at roughly a quarter of its capability and a quarter of
   its efficiency.
3. **Throughput alone would not have caught it.** 9.34 tok/s for a 4B model at Q4 is a believable
   number. What catches it is `gpu_load` reading 0 during a request, or a binary with no CUDA
   backend, or a rail that does not move when work starts.
4. **Higher concurrency widens the gap, it does not narrow it.** 2.18x at one stream to 4.29x at
   four: the GPU converts added concurrency into throughput far better than the CPU does, which is
   consistent with [006](006-batching-power-inversion.md) and with the serial-fraction result in
   [010](../rk3588/010-cpu-per-submit-serial-cost.md).
5. **Generic arm64 CUDA release builds are not a shortcut here.** Upstream ships
   `ubuntu-cuda-13.5-arm64` binaries, but generic arm64 CUDA builds target datacenter parts; Orin
   is `sm_87`. The local build sets `CMAKE_CUDA_ARCHITECTURES=87` explicitly. `nvcc` is also not on
   `PATH` on these JetPack images, so `CMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc` must be passed
   or CMake finds the toolkit, reports "CUDA compiler identification is unknown", and fails.

## What this invalidates

Any `llama-server` figure attributed to **node3's GPU** before 2026-11-26 was a CPU figure. That
includes node3's half of [008](../cluster/008-serving-capacity-knee.md) (the serving-capacity knee)
and node3's rows in [006](006-batching-power-inversion.md) (the batching power inversion). The
*mechanisms* in both may survive — 006's finding is about power versus concurrency, which holds on
a CPU too — but the engine label does not, and the magnitudes need re-measuring on the GPU.

Not affected: work that used the **RPC backend** rather than `llama-server`, where node3's
`ggml-rpc-server` could legitimately have been CUDA. That covers
[001](../cluster/001-heterogeneous-llm-pipeline.md) and
[002](../cluster/002-pipeline-parallel-measurements.md). This has not been verified and is stated
as a scope limit, not a clearance.

## Corrections and limitations

**The `gpu_load=0` values in this experiment's raw output are a sampling artifact, not evidence.**
The sampler reads that counter after the 14-second power window, by which time a 160-token request
at 92 tok/s has finished. GPU execution is established by the 4.29x and by the live-service check
at 968, not by those zeros.

**An earlier revision of this experiment produced void GPU arms.** Its backgrounded rail sampler
was a subshell that inherited the `EXIT` trap; when it finished it ran the cleanup, restarted the
managed service mid-test, and the service then held the GPU memory the next arm needed — which
failed as `failed to create context with model`. The CPU arms from that revision were valid and
agree with the final run (9.35 vs 9.34 tok/s).

One module, one model, one quantisation, no repetitions per arm — these are single measurements,
not means with variance, and the CPU rate's reproducibility across three independent runs
(9.34 / 9.35 / 9.44) is the only stability evidence offered. Rail 2's `CPU_GPU_CV` grouping means
the per-engine power split that would make this a true efficiency comparison is **not obtainable**
on this hardware; an inline 12 V meter would not help, since the limitation is on the module.

## Reproduction

[`suite/e3_cpu_vs_gpu_energy.sh`](../../capability-matrix/scripts/bench/suite/e3_cpu_vs_gpu_energy.sh).
[`suite/preflight.sh`](../../capability-matrix/scripts/bench/suite/preflight.sh) now warns when
`libggml-cuda.so` is absent and fails when a `-ngl 0 -dev none` run's decode rate does **not**
change with thread count — the two checks that would have caught this in August.
