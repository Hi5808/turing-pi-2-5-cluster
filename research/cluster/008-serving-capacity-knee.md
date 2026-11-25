# 008 — How many people can this cluster actually serve? The knee is 4, not 16

**Platform:** Turing Pi 2.5; node2 Jetson Orin NX 16GB serving Qwen3-14B-Q4_K_M, node3 Jetson
Orin Nano 8GB serving Qwen3-4B-Q4_K_M, both `llama-server` with 8 slots and `n_ctx` 1024 per
slot; node1 Turing RK1 running a 3-stream NPU vision load throughout.
**Date:** 2026-11-24. **Status:** complete. Measurements in `selfmodel.db` run `ec5f653bbfc7`.

## Abstract

Every prior paper in this repository measures one node. This one measures the machine. Streams
are round-robined across both Orin endpoints the way a real service would route them, ramped
1 -> 32, with time-to-first-token and every inter-token gap recorded per stream. Aggregate
throughput saturates at **61.3 tok/s**, but the largest load that still delivers a readable
stream to *every* user is **4 concurrent streams** — 8x smaller than the throughput-optimal
load. Past the 16 available slots the pain does not appear as slower streaming; it appears as a
**41.5 s p95 time-to-first-token** while inter-token latency stays flat. And the energy-optimal
operating point is the *worst* user experience: tok/J peaks at 1.536 exactly where TTFT is 41 s,
and respecting the SLO costs **1.6x more energy per token**.

## 1. Method

Load generator `ramp.py` (committed). Each stream loops streaming `/completion` requests
(`n_predict` 96, `temperature` 0, `cache_prompt` false, `stream` true), recording TTFT once per
request and an inter-token latency for every subsequent token. 45 s per arm plus an 8 s drain.
Rails sampled at 1 Hz on each Orin by a logger running for the whole ramp and sliced by arm
timestamps afterwards (40+ samples per arm per node).

**SLO:** p95 inter-token latency <= 200 ms **and** every stream >= 5 tok/s. That is "a human can
read the output as it arrives, and nobody is starved".

Each endpoint advertises `total_slots` 8, so **16 streams is the last fully concurrent arm**.
The 24 and 32 arms are queueing, not concurrency, and are labelled `concurrent: false` rather
than being silently averaged in — the distinction that invalidated an earlier live measurement
in [006](../jetson-orin/006-batching-power-inversion.md).

## 2. Results

| Streams | Concurrent | Agg tok/s | Slowest stream | TTFT p95 | ITL p95 | NX W | Nano W | 2-module W | tok/J | SLO |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | yes | 7.06 | 7.06 | 220 ms | 136 ms | 25.02 | 5.81 | 30.83 | 0.229 | **pass** |
| 2 | yes | 24.11 | 7.08 | 157 ms | 135 ms | 25.38 | 18.70 | 44.08 | 0.547 | **pass** |
| **4** | yes | **44.33** | **6.47** | 452 ms | 144 ms | 27.56 | 19.82 | 47.38 | 0.936 | **pass** |
| 8 | yes | 43.12 | 4.06 | 671 ms | 231 ms | 25.96 | 18.56 | 44.52 | 0.969 | fail |
| 12 | yes | 49.63 | 2.47 | 895 ms | 379 ms | 26.85 | 18.65 | 45.50 | 1.091 | fail |
| 16 | yes | 60.77 | 2.23 | 980 ms | 417 ms | 23.53 | 16.34 | 39.87 | 1.524 | fail |
| 24 | **no** | 60.99 | 0.19 | **41 279 ms** | 419 ms | 23.44 | 16.37 | 39.81 | 1.532 | fail |
| 32 | **no** | 61.29 | 0.19 | **41 526 ms** | 418 ms | 23.48 | 16.41 | 39.89 | 1.536 | fail |

Zero errors in every arm; 40 000+ token samples total.

### Finding 1 — usable capacity is 4 streams, peak throughput is at 32

The knee is **4**. At 8 streams the slowest user is already down to 4.06 tok/s with p95 inter-token
latency of 231 ms, both outside the SLO. Aggregate throughput keeps climbing to 61.29 tok/s at 32
streams, which is **38% more throughput than the knee delivers** — and completely unusable, because
new users wait 41 s to see a single token. **Capacity claims that quote peak aggregate throughput
overstate serviceable capacity by 8x on this machine.**

### Finding 2 — queueing moves the pain from streaming to starting

Across the 16 -> 24 -> 32 arms, inter-token latency is *flat* (417, 419, 418 ms) while TTFT p95
goes 980 ms -> 41.3 s -> 41.5 s. Once a request wins a slot it streams exactly as fast as before;
it simply waits far longer to begin. The slowest stream collapses to **0.19 tok/s** — a user who
has effectively been dropped while the dashboard still reports 61 tok/s. **Aggregate throughput is
blind to this failure, and so is any monitor that only watches tokens per second.**

### Finding 3 — P7 reproduces at cluster scale, across two modules

Two-module power *falls* as concurrency rises — 47.38 W at 4 streams down to **39.87 W at 16** —
while throughput rises, so tok/J climbs monotonically **0.229 -> 1.536, a 6.7x improvement**.
[006](../jetson-orin/006-batching-power-inversion.md) measured this on single modules against
request length; it holds here for independent streams across two different modules running two
different models. This is the strongest form of the claim so far.

### Finding 4 — the efficiency optimum is the worst place to run

tok/J is maximal (1.536) precisely at 32 streams, where TTFT p95 is 41.5 s. The SLO-respecting
point (4 streams, 0.936 tok/J) is **39% less efficient**, so serving users costs **1.6x the energy
per token** that benchmarking the same hardware does. Every efficiency figure in this repository,
including our own, is measured at a load no product would ship. Stated plainly so that nobody —
us included — quotes a tok/J number as though it were achievable at an acceptable latency.

### Finding 5 — naive round-robin is unfair across heterogeneous nodes

The endpoints plateau at very different rates: NX/14B at **17.9 tok/s** total, Nano/4B at
**43.4 tok/s** total. Round-robin therefore hands one user 7.1 tok/s and the next 17.0 tok/s from
the same service. The smaller module serving the smaller model carries **2.4x** the throughput of
the larger one. A heterogeneous cluster needs weighted or latency-aware routing; equal-share
routing wastes the fast node and punishes whoever lands on the slow one.

## 3. What this says about the carrier board

It does not settle it, and that is worth being explicit about: **this experiment never used the
carrier's distinguishing hardware.** Each node served independently over the internal switch, so
the result would be identical with three boards on a desk and a cheap switch. The board-specific
question — what the internal 1GbE switch, shared NVMe, per-slot power gating and BMC console
actually buy over three separate SBCs — is tested in [002](002-pipeline-parallel-measurements.md)
for split inference only, and is otherwise **open**. The honest summary today is that nothing
measured here requires the carrier.

## 4. Limitations

- **The load generator ran on node1, and stole from it.** The NPU background load averaged
  **56 fps (min 22)** during the ramp against 89-103 fps measured alone, because `ramp.py`'s
  up-to-32 SSE-parsing threads competed for the same 8 RK3588 cores. That degradation is a
  harness artifact, **not** cluster interference, and node1's NPU numbers from this run must not
  be used. Future runs put the generator off-cluster.
- Power is **two modules only**. The RK1 exposes no rails, and the carrier's fan, BMC and switch
  are excluded, so every tok/J here understates whole-machine energy. A board-level meter on the
  12 V input remains the missing instrument.
- At 1 stream the idle Nano (5.81 W) sits in the denominator, which is why that arm's tok/J is
  worst; it is a routing artifact, not a power result.
- The two endpoints run **different models**, so Finding 5 conflates node capability with model
  size. Separating them needs the same model on both, which the Nano's 8 GB cannot hold at 14B.
- Aggregate throughput at 8 streams (43.12) is marginally *below* 4 streams (44.33). Unexplained;
  likely batching granularity on the 14B node, but within plausible run-to-run variation and not
  repeated.
- One 45 s sample per arm, no repeats. The power figures are tight (sd <= 0.6 W) but the
  throughput numbers carry single-run variance.
- `n_ctx` is 1024 per slot, so these are short conversations; long contexts would move the knee
  down.

## 5. Reproduction

```sh
# generator off-cluster next time; rails logged on each Orin for the whole ramp
scp raillog.py orinnx:/tmp/; scp raillog.py orin1:/tmp/
ssh orinnx 'setsid python3 -u /tmp/raillog.py /tmp/rails.csv &'
ssh orin1  'setsid python3 -u /tmp/raillog.py /tmp/rails.csv &'
python3 ramp.py                 # 8 arms, 1..32 streams, writes ramp.json
python3 join_rails.py rails_nx.csv rails_nano.csv ramp.json   # writes ramp_joined.json
```

Raw output: [`capability-matrix/data/cluster/ramp_joined.json`](../../capability-matrix/data/cluster/ramp_joined.json).
