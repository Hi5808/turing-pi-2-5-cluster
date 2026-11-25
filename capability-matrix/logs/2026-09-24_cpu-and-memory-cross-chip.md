# CPU and memory throughput on the three chips (sysbench)

**Platform:** Turing Pi 2.5.1; node 1 Turing RK1 (RK3588: 4x A76 @ up to 2.26 GHz + 4x A55), node 2 Jetson Orin NX 16GB (8x A78AE), node 3 Jetson Orin Nano 8GB (6x A78AE)
**Software stack:** sysbench 1.0.20 on all three; Ubuntu 24.04.1 (RK1, kernel 6.1.0-1025-rockchip), JetPack 7.2 (kernel 6.8.12-1021-tegra); RK1 CPU governor `performance`
**Date:** September 2026

## Question

How do the CPU cores and the CPU-side memory bandwidth compare across the three chips, and does memory bandwidth explain the LLM decode results?

## Setup and method

`sysbench cpu --cpu-max-prime=20000 --time=10` at 1 thread and at all threads, 3 runs each; `sysbench memory --memory-block-size=1M --memory-total-size=30G` read and write at 1 thread and all threads, one run each. Tests ran one node at a time; the user's triage services were running on nodes 2 and 3. Raw output: `data/raw/cpu-2026-09-24/`.

## Results

| Metric | RK1 | Orin NX | Orin Nano |
|---|---|---|---|
| CPU, 1 thread (events/s, 3 runs) | 936.9–942.5 | 869.7–871.2 | 758.6–759.3 |
| CPU, all threads (events/s) | 5112–5114 (8) | 6929–6931 (8) | 4470–4472 (6) |
| Memory read 1 thread (MiB/s) | 23 836 | 25 945 | 23 153 |
| Memory write 1 thread (MiB/s) | 11 094 | 15 975 | 13 916 |
| Memory read all threads (MiB/s) | 56 695 | 96 751 | 70 221 |
| Memory write all threads (MiB/s) | 54 683 | 58 674 | 46 612 |

## Findings

1. **The RK1's big cores lead single-thread performance** (about 938 vs 870 vs 759 events/s), but its four A55 cores make it the **middle chip with all threads** (5112), behind the NX's eight A78AE cores (6930) and ahead of the Nano's six (4471).
2. **CPU-side memory read bandwidth with all threads: NX 96.8 GB/s, Nano 70.2 GB/s, RK1 56.7 GB/s** (MiB/s converted with 1 MiB = 1.048576 MB, so these are about 101, 74 and 59 GB/s in decimal units). The NX's figure is close to its module's specified memory bandwidth, as measured by this tool with all cores.
3. The ordering of memory read bandwidth (NX > Nano > RK1) matches the ordering of CUDA decode rates (43.8 vs 39.4 tok/s) only for the two Jetsons; it does not explain the RK1's NPU decode result (unchanged when its DRAM clock was doubled).
4. The GPU's view of memory bandwidth on the RK1 (19.5 GB/s in clpeak) is about a third of the CPU's (56.7 GB/s), so GPU-side bandwidth would limit any Mali workload before DRAM does.

## Limitations

One run per memory test; sysbench memory measures a synthetic copy loop, not application access patterns; different thread counts (8/8/6) reflect the core counts, so "all threads" is not equal work per chip; services running on the Jetsons; no frequency logging during the runs.

## Reproduction

Command lines above; results in `data/raw/cpu-2026-09-24/`.
