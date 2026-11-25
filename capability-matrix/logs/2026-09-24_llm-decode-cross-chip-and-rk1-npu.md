# One model on three chips, and the RK3588 NPU against its own CPU: decode is not faster on the NPU

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Node 1 Turing RK1 (RK3588, 32 GB; 4x A76 + 4x A55, 6-TOPS NPU), node 2 Jetson Orin NX 16GB, node 3 Jetson Orin Nano 8GB
**Software stack:** RK1: Ubuntu 24.04.1, kernel 6.1.0-1025-rockchip, RKNPU driver v0.9.7, RKLLM runtime 1.3.0 (librkllmrt build 82bf4aa8e), RKLLAMA 0.0.75, Python 3.12. Jetsons: JetPack 7.2, CUDA 13.2, kernel 6.8.12-1021-tegra, power mode MAXN_SUPER. llama.cpp builds recorded per row
**Date:** September 2026

## Question

The board carries an NPU SoC and two CUDA SoCs. With the same model file, what does each produce, and does the RK3588's NPU beat its own CPU for token generation?

## Setup and method

- **Common model:** Qwen3 1.7B Q4_K_M GGUF (1.19 GiB), copied to all three nodes; SHA-256 checked identical on all four copies.
- **Tool:** `llama-bench -p 512 -n 128`, 5 repetitions on the Jetsons (`-ngl 99`, CUDA), 3 on the RK1 (CPU build, GGML_NATIVE, no GPU offload). Output in `data/raw/llamabench-2026-09-24/README.md`.
- **Build control:** the two Jetsons had different llama.cpp builds (7044859 and 749f688). Node 3's binaries were copied to node 2 and run there.
- **NPU:** the same `bench.py` harness and TinyLlama-1.1B W8A8 RKLLM model used earlier on an Orange Pi 5 Plus (same SoC, same kernel version): 6 trials, 100 new tokens, 3 prompts, through RKLLAMA's `/api/chat`. Model file copied from the Plus and its checksum-identical runtime library used (md5 78d6d409… on both).
- **NPU sweep:** devfreq pinned to 300–1000 MHz, 4 trials per step; governors restored afterwards and verified.
- The user's triage services kept running on nodes 2 and 3. Node 3 had about 2.7 GB available; no OOM occurred and the service stayed active.

## Results

### Same model, three chips (Qwen3-1.7B Q4_K_M, llama.cpp)

| Node / backend | Prefill pp512 (t/s) | Decode tg128 (t/s) |
|---|---|---|
| Orin NX 16GB, CUDA (build 7044859) | 1748.5 ± 48.8 | 43.82 ± 0.06 |
| Orin NX 16GB, CUDA, node 3's binaries (build 749f688) | 1751.0 ± 45.2 | 43.45 ± 0.04 |
| Orin Nano 8GB, CUDA (build 749f688) | 1559.4 ± 42.9 | 39.44 ± 0.09 |
| RK1 CPU, 8 threads | 52.0 ± 0.1 | 15.53 ± 0.03 |
| RK1 CPU, 4 big cores only (`taskset -c 4-7`) | 47.7 ± 0.0 | 19.67 ± 0.01 |

### RK1: NPU vs CPU on the same chip (TinyLlama 1.1B, roughly 8-bit weights)

| Path | Prefill (t/s) | Decode (t/s) |
|---|---|---|
| NPU, RKLLM W8A8, governors default | 218–252 | 11.18 ± 0.25 (6 trials) |
| NPU, DRAM controller pinned to 2112 MHz | 226–248 | 11.44 ± 0.51 |
| NPU + DRAM controller both pinned to max | 220–254 | 11.12 ± 0.07 |
| CPU, llama.cpp Q8_0, 4 big cores | 114.3 ± 0.2 | 22.15 ± 0.01 |
| CPU, llama.cpp Q8_0, 8 threads | 116.1 ± 2.5 | 18.23 ± 0.13 |

### NPU frequency sweep (decode, 4 trials each)

| NPU MHz | 300 | 400 | 500 | 600 | 700 | 800 | 900 | 1000 |
|---|---|---|---|---|---|---|---|---|
| tok/s | 10.45 | 11.26 | 11.34 | 11.48 | 11.46 | 11.40 | 11.62 | 11.45 |

## Findings

1. **Build did not matter:** the Orin NX gives 43.8 vs 43.5 tok/s with the other build. The NX/Nano gap is hardware: about 11% in decode (43.5 vs 39.4) and about 12% in prefill (1751 vs 1559), for the same weights.
2. **The RK1's NPU decodes at about half the speed of its own four big cores** (11.2 vs 22.2 tok/s), while prefill is about twice as fast on the NPU (about 230 vs 114 tok/s). The two models are not identical (RKLLM W8A8 vs GGUF Q8_0 of the same base model), so this is a comparison of software paths, not of silicon alone.
3. **Decode does not scale with NPU clock above 400 MHz** (10.5 tok/s at 300 MHz, 11.3–11.6 from 400 to 1000 MHz) **or with DRAM clock** (pinning the memory controller from 1068 to 2112 MHz changed 11.2 to 11.4). What limits decode here is not measured. Prefill, which is compute-heavy, is the part the NPU accelerates.
4. **On the RK1 CPU, the four A55 cores hurt decode:** 8 threads gave 15.5 (Qwen3) and 18.2 (TinyLlama) tok/s, 4 big cores gave 19.7 and 22.2 tok/s. Prefill is unchanged or slightly better with 8 threads.
5. **CUDA vs RK1 CPU on the same Qwen3 file:** decode 39–44 vs 19.7 tok/s (2.0–2.2x), prefill 1560–1750 vs 48–52 tok/s (30–37x).

## Corrections and open item

An earlier record (Orange Pi 5 Plus, 28 August, same harness, same library, same driver) gave **18.9 tok/s** NPU decode for this model with performance governors. **That was not reproduced here (11.1–11.4 tok/s on the RK1 with governors pinned to performance and DRAM at 2112 MHz).** The Plus was not re-run today because it is serving another workload, so it is unknown whether the gap is the RK1 (module, memory, power delivery) or the earlier state of the Plus. The Plus figure is recorded as an unreproduced reference, not as evidence of a hardware difference.

## Limitations

One unit of each module; 3–6 repetitions; sd shown is between repetitions, not between boots. Jetsons ran concurrently with the user's idle services and each other's board load. No power was measured, so no energy per token. Only one model per chip pair; the NPU model quantisation differs from the GGUF. RK1 CPU frequency governor was `performance` (observed, not set by these tests). NPU frequency is reported as the devfreq step, not measured independently.

## Reproduction

`data/raw/npu-rk1-2026-09-24/` (harness JSON per condition, sweep log), `data/raw/llamabench-2026-09-24/README.md`. Harness: `bench.py` and the sweep from the Orange Pi 5 Plus harness with paths changed.

## Addendum: repeat run (same day, about three hours later)

The `tp bench llm` command (3 repetitions, same model file and binaries) reproduced the figures within 1% for decode and 1 to 1.5% for prefill:

| Node | Prefill first run → repeat (t/s) | Decode first run → repeat (t/s) |
|---|---|---|
| Orin NX (CUDA) | 1748.5 → 1735.3 | 43.82 → 43.55 |
| Orin Nano (CUDA) | 1559.4 → 1544.2 | 39.44 → 39.41 |
| RK1 CPU, 4 big cores | 47.7 → 47.9 | 19.67 → 19.76 |

One repeat on one day is not a stability study, but it shows the measurements are repeatable on this board when the same procedure is used.
