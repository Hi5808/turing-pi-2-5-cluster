# Energy per generated token on Orin NX and Orin Nano (module input power)

**Platform:** Turing Pi 2.5.1; node 2 Jetson Orin NX 16GB, node 3 Jetson Orin Nano 8GB, both MAXN_SUPER
**Software stack:** JetPack 7.2, `tegrastats`, llama.cpp CUDA (builds 7044859 on NX, 749f688 on Nano), Qwen3-1.7B Q4_K_M, all layers on GPU
**Date:** September 2026

## Question

What does a generated token cost in energy on each Orin, and can the RK1 be included?

## Setup and method

- `tegrastats` (200 ms interval requested; about 1 sample per second was logged) sampled `VDD_IN` (module input power) for 8 s idle, then during `llama-bench -p 0 -n 128 -r 8` (decode only).
- "Busy" samples are those with GPU utilisation of at least 50%. Energy per token = mean busy power / measured decode rate (total), and (busy − idle) / rate (net of idle).
- "Idle" is not a quiet system: the triage services were running with their models loaded (GPU idle).
- Raw `tegrastats` output: `data/raw/power-2026-09-24/`.
- The RK1 has no on-module power telemetry; it needs an external meter (row A18 stays open).

## Results

| Node | Decode (t/s) | Idle mean (W) | Busy mean (W) [min–max] | Busy samples | J/token total | J/token net of idle |
|---|---|---|---|---|---|---|
| Orin NX 16GB | 43.61 | 6.18 (36 samples) | 22.41 [8.63–23.04] | 109 | 0.514 | 0.372 |
| Orin Nano 8GB | 39.48 | 7.13 (37 samples) | 20.22 [11.86–22.04] | 121 | 0.512 | 0.331 |

GPU clock during the busy phase was about 1157 MHz on the NX (98% utilisation).

## Findings

1. **The two Orins spend about the same energy per token** (0.51 J total) on this model, although the NX decodes 10% faster and draws 2 W more.
2. Both draw about 20–22 W at full GPU load, which is the module input rail, so it includes the memory, CPU and SoC, not just the GPU.
3. The Nano's idle draw is higher than the NX's (7.1 vs 6.2 W) despite the smaller module, but the idle state includes different service loads, so this is not a module comparison.

## Limitations

`VDD_IN` is a module-level rail as reported by the module's own sensors, not a wall or board-input measurement, and its accuracy was not checked. One run per node; about 1 Hz sample rate; decode only (no prefill energy); idle load differs between nodes; the NX min busy value (8.6 W) is a transition sample, so the busy mean includes some ramp samples. No RK1 figure.

## Reproduction

`tegrastats` output and the `llama-bench` command are in Setup; the parsing is a mean over `VDD_IN` fields.
