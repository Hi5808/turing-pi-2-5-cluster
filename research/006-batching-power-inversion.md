# 006 — Raising concurrency *lowers* inference power

**Platform:** node2 (Jetson Orin NX 16GB) and node3 (Jetson Orin Nano 8GB), both MAXN_SUPER.
Qwen3-4B Q4_K_M, llama.cpp b10362-5-g704485942, `llama-server --parallel N --cache-ram 0 -ngl 99`.
**Date:** 2026-11-24. **Status:** measured, two independent parts.

## Abstract

Going from 2 concurrent decode streams to 8 **reduces total module power** while **increasing**
throughput by 37–41%. node2 drops 4.51 W for +41.2% tokens; node3 drops 3.69 W for +37.3%. The
GPU clock is pinned at every load level, so this is not a DVFS artefact; the effect is 40–70x the
measurement noise; and the on-die thermal sensors independently agree, with 8 streams running
*cooler* than 2 on both modules.

The practical consequence inverts the usual advice. Edge inference power is normally budgeted as
proportional to utilisation, which makes throttling and duty-cycling the recommended way to save
energy. These measurements say the dominant cost at low concurrency is a **fixed per-decode-step
overhead**, so on a power- or thermally-limited device the correct move is the opposite: queue the
work up and run it batched. Batching is an efficiency lever, not only a throughput lever.

## Relation to the September measurement

`capability-matrix/logs/2026-09-24_jetson-energy-per-token.md` measured 0.514 and 0.512 J/token on
these same two modules in September and concluded that they "spend about the same energy per
token". That is consistent with the c1 row below (0.846 vs 0.919 tok/J, 8.6% apart) and was not
wrong — it was single-stream only, which is the one condition where the modules do look alike.
This study varies the dimension that log held fixed.

## Correction to previously recorded figures

An earlier pass recorded 2.261 tok/J (node2) and 2.270 tok/J (node3) with the conclusion that
"idle is 7 of 8.8 W loaded, inference costs ~1.4 W marginal, duty cycle dominates", and that the
two modules were efficiency-equivalent within 0.4%.

**All of that was wrong**, and for an instructive reason: the telemetry window outlasted the
benchmark inside it, so those windows were ~93% and ~84% idle. The figures were measuring the
idle floor with a benchmark-shaped blip in the middle. The fix was `load_hold.py`, which pins N
concurrent streams for a fixed duration so a 150 s window contains nothing but steady state.

Two downstream claims died with it: marginal inference cost is ~14–18 W, not 1.4 W, and the
modules are *not* equivalent — node3 is more efficient at every concurrency level (+8.6/+9.1/+7.4%
at c1/c2/c8) while node2 delivers +17.7% throughput at c8.

## Method

Three steady-state windows of 150 s each, separated by 40 s of idle, preceded by an idle window.
**20 s is trimmed from every window edge** so stream ramp-up and drain cannot contaminate a mean.
Power is read from the module's INA3221 rails (`VDD_IN` total, `VDD_CPU_GPU_CV`, `VDD_SOC`) by a
k3s DaemonSet sampling at 10 s; each mean below therefore rests on 11–12 samples, and the standard
deviation of each is printed rather than summarised.

Throughput is the aggregate across streams, measured by the load generator from the server's own
token counts, not inferred from power.

Runs `bbea950aae3d` (node2) and `16490e0d2a38` (node3) in `selfmodel.db`. This document's tables
are generated from that database by `finding_batch_power.py`; no figure is transcribed by hand.

## Results

### node2 — Orin NX 16GB

| level | agg tok/s | module total (W) | CPU+GPU+CV (W) | SOC (W) | n | GPU MHz | SOC °C |
| --- | --: | --: | --: | --: | --: | --: | --: |
| idle | 0 | 7.62 ±0.04 | 2.30 ±0.02 | 2.39 ±0.02 | 11 | 1173 | 61.4 |
| c1 | 19.70 | 23.31 ±0.17 | 11.74 ±0.10 | 5.01 ±0.05 | 12 | 1173 | 70.2 |
| c2 | 37.47 | 25.67 ±0.35 | 13.85 ±0.29 | 5.10 ±0.03 | 11 | 1173 | 74.0 |
| c8 | 52.92 | 21.16 ±0.04 | 12.49 ±0.03 | 3.62 ±0.02 | 11 | 1173 | 72.6 |

**c2 → c8:** throughput **+41.2%**, module power **−4.51 W** (CPU+GPU −1.36 W, SOC −1.48 W).

### node3 — Orin Nano 8GB

| level | agg tok/s | module total (W) | CPU+GPU+CV (W) | SOC (W) | n | GPU MHz | SOC °C |
| --- | --: | --: | --: | --: | --: | --: | --: |
| idle | 0 | 5.76 ±0.02 | 0.53 ±0.02 | 2.32 ±0.02 | 11 | 306 | 45.2 |
| c1 | 17.81 | 19.37 ±0.10 | 8.61 ±0.05 | 4.65 ±0.02 | 11 | 1020 | 55.3 |
| c2 | 32.74 | 20.50 ±0.19 | 9.67 ±0.14 | 4.63 ±0.03 | 12 | 1020 | 59.6 |
| c8 | 44.95 | 16.81 ±0.35 | 8.63 ±0.08 | 3.37 ±0.15 | 12 | 1020 | 57.9 |

**c2 → c8:** throughput **+37.3%**, module power **−3.69 W** (CPU+GPU −1.04 W, SOC −1.26 W).

Note node3's idle GPU clock of 306 MHz against node2's 1173 MHz — the NX does not drop its GPU
clock at idle, which is most of its 1.87 W higher idle floor.

### Per-token energy by rail

This is where the mechanism shows.

| level | node2 J/tok CPU+GPU | node2 J/tok SOC | node3 J/tok CPU+GPU | node3 J/tok SOC |
| --- | --: | --: | --: | --: |
| c1 | 0.596 | 0.254 | 0.484 | 0.261 |
| c2 | 0.370 | 0.136 | 0.295 | 0.141 |
| c8 | 0.236 | 0.068 | 0.192 | 0.075 |

From c1 to c8, SOC per-token energy falls **3.7x** (node2) and **3.5x** (node3); the compute rail
falls 2.5x on both.

### Tokens per joule

| level | node2 tok/J | node3 tok/J |
| --- | --: | --: |
| c1 | 0.846 | 0.919 |
| c2 | 1.463 | 1.596 |
| c8 | 2.494 | 2.677 |

Whole-module efficiency improves 2.95x (node2) and 2.91x (node3) from c1 to c8.

## Why this is neither DVFS nor a measurement artefact

**Not DVFS.** The GPU clock is identical at every load level on each part — 1173 MHz on node2,
1020 MHz on node3 — and both modules are in MAXN_SUPER. A separate 600 s sustain run found no
throttling: node2 held 1173 MHz with decode rate flat within 0.5% (19.91 → 19.96 tok/s) while the
die went 67.9 → 84.8 °C. At a fixed clock, lower power means genuinely less switching activity, so
**at 2 streams the hardware is burning power without producing tokens.**

**Not an INA3221 artefact.** The die temperatures agree with the shunt, and they are a physically
separate sensor: c8 runs cooler than c2 on both parts despite doing 37–41% more work. An error in
the current-sense path would not reproduce itself in the thermal sensors.

**Not a single-part quirk.** Two different modules, different die sizes, different memory widths,
different idle floors — same sign, same magnitude, same rail split.

## What the mechanism is, and is not

Both rails fall, but not equally, and the split is the informative part. The SOC rail — memory
controller, fabric, and the fixed cost of stepping a decode iteration — loses the larger share of
its per-token energy. That is consistent with a cost paid once per decode *step* regardless of how
many sequences ride on it: at 8 streams it is amortised across 8 tokens instead of 2.

We have **not** isolated the cost to a specific component and do not claim to have. The defensible
statement is that the overhead is per-step rather than per-token, and that it lives
disproportionately outside the compute rail.

## Consequences for this cluster

- Cap *interactive* work at 2 streams per node (the knee: 1.9x throughput for 4–6% per-stream
  latency cost), but run *batch* work at 8, where it is both faster and cheaper.
- Route latency-bound work to node2, energy-bound or bursty work to node3 — its idle floor is
  1.87 W lower and it wins tok/J at every level.
- Do not duty-cycle to save energy on these modules. Queue and batch instead.

## Limits

- One model (Qwen3-4B Q4_K_M) and one runtime. The amortisation argument should generalise; the
  magnitude is not transferable without remeasuring.
- Two parts of the same family. Untested on discrete GPUs, where idle floors and rail topology
  differ substantially.
- 11–12 telemetry samples per window. Tight (sd 0.02–0.35 W) but not a long-run average.
- **c2 is the local power maximum and we did not sweep 3–7 streams**, so the exact location of the
  peak and the shape of the curve between c2 and c8 are unmeasured.
- node1 (RK3588) is absent from this study: the RK1 module exposes no INA3221 rails, so its energy
  is unmeasured rather than zero. This is now a measured dead end rather than an open task — the
  BMC has **no power-sensing hardware at all** (only an EEPROM, an RTC and the Ethernet switch on
  its i2c bus), so closing it needs an external meter. See
  [capability-matrix/logs/2026-11-24_bmc-power-telemetry.md](../capability-matrix/logs/2026-11-24_bmc-power-telemetry.md).
- Everything here is *module* power. The carrier's own overhead — fan, BMC, Ethernet switch — and
  the regulator losses between the board input and each module are outside every rail used here,
  so the tokens-per-joule figures are module-level and exclude board overhead.

## Adjacent open question: the silent batching loss

Once, on 2026-11-22, both Orins' `llama-server` stopped batching simultaneously — two concurrent
streams serialised at half rate each — while **single-stream decode stayed within +0.2% of
nominal**. A restart cleared it; nine reproduction attempts failed.

It remains unproven because no probe was running at the moment it happened, and that is the
point: **a single-request latency health check cannot see this failure.** Any ordinary monitoring
setup would have shown green while the node delivered half its throughput. Since every throughput
figure in this repo depends on batching working, this is a measurement-integrity problem as much
as a bug.

A detector now runs every 15 minutes on node1 (`bench/batch_probe.py` → table `probe_batching`).
It records the single-stream rate, the 2-stream *aggregate* rate, and their ratio, so a detection
carries its own evidence. Healthy baseline measured at install: **1.824** (node2, 14B) and
**1.865** (node3, 4B), against 1.89/1.84 from the concurrency curve. Threshold for a reported loss
is a ratio below 1.25.

Lesson already banked: gate any throughput claim on a *concurrent* probe taken at the time of the
claim, not a latency check. This is the same class of error as the RPC-split run that silently
executed single-node after `pkill -f` matched its own launching shell.
