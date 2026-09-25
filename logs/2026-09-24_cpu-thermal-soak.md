# Five-minute all-core CPU soak on all three chips: no throttling, three different thermal states

**Platform:** Turing Pi 2.5.1; node 1 Turing RK1 (with the RK1 heatsink fan controlled by the board), node 2 Orin NX 16GB, node 3 Orin Nano 8GB
**Software stack:** sysbench 1.0.20 `cpu --cpu-max-prime=200000 --time=300`, threads = core count; `tegrastats` (Jetsons, 1 s), hwmon and cpufreq sysfs sampled every 5 s (RK1); MAXN_SUPER on the Jetsons, `performance` governor on the RK1
**Date:** September 2026

## Question

Do the chips hold their clocks under five minutes of full CPU load on this board?

## Setup and method

One node at a time, CPU-only load (no GPU/NPU load). The user's triage services were resident on nodes 2 and 3 (GPU idle). Room temperature was not recorded. Raw data: `data/raw/thermal-2026-09-24/`.

## Results

| | RK1 (8 threads) | Orin NX (8 threads) | Orin Nano (6 threads) |
|---|---|---|---|
| Sysbench score (events/s) | 207.65 | 272.54 | 175.77 |
| Clock during load | big cores 2256 MHz throughout | 1984 MHz on all cores in 294 of 295 samples | 1728 MHz in 295 of 295 samples |
| Temperature at start → end | SoC 53 → 62 °C (max 62) | Tj 68.0 → 71.9 °C | Tj 63.7 → 66.2 °C |
| Module input power (VDD_IN) | not available | about 10.0–10.1 W | about 8.8–8.9 W |
| Fan | PWM 100 → 190 (of 255) after load began | n/a (not visible from the node) | n/a |

## Findings

1. **No clock reduction on any chip in five minutes**; the single NX sample at 1344 MHz is the final line, taken as the load ended.
2. The Jetsons' temperatures are higher than the RK1's (Tj 68–72 °C NX, 64–66 °C Nano vs 62 °C RK1) with no throttling seen; the RK1's sensors (SoC/core) and the Jetsons' `tj` are different sensors, so the numbers are not directly comparable.
3. CPU-only load draws about 10 W on the NX and 9 W on the Nano, against about 20–22 W under GPU decode load (energy log), so the GPU is the dominant power consumer.

## Limitations

Five minutes is short of a thermal steady state (the NX Tj was still rising by about 0.6 °C over the last minute); no GPU or combined CPU+GPU+NPU soak (the worst case for a shared enclosure); ambient not recorded; the board's enclosure state (open bench) is not described; no comparison of fan settings.

## Reproduction

`sysbench` command in Setup; logs in `data/raw/thermal-2026-09-24/`.
