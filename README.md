# Turing Pi 2.5 Cluster — Research & Projects

Research log and engineering notes for a three-node heterogeneous ARM cluster built on a
Turing Pi 2.5 board. The cluster's purpose is hardware research: measuring what genuinely
different accelerator architectures can do when they share one chassis, one 1GbE backplane
and one control plane.

The three nodes are deliberately *not* identical, and that asymmetry is the subject of the
research rather than an inconvenience to be abstracted away.

| Slot | Module | Compute | Accelerators | RAM | Role |
|------|--------|---------|--------------|-----|------|
| node1 | Turing RK1 (RK3588) | 4x Cortex-A76 + 4x Cortex-A55 | Mali-G610 MP4, 6 TOPS NPU, 8K H.264/265 **encode + decode** | 31 GB | control plane, WiFi uplink, only route off-cluster |
| node2 | Jetson Orin NX 16GB | 8-core Cortex-A78AE | 1024 CUDA + 32 tensor cores (~157 TOPS), **2x DLA**, 1x NVENC, 1x NVDEC | 16 GB | heaviest accelerator |
| node3 | Jetson Orin Nano 8GB | 6-core Cortex-A78AE | 1024 CUDA cores (~67 TOPS), **no DLA, no encoder**, NVDEC only | 8 GB | smallest node |

## The constraint that shapes everything

Measured, not estimated (see [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md)):

- Each node gets full 1GbE line rate (~119 MB/s), and the backplane switch is **non-blocking
  for pairwise traffic** — node2 and node3 can talk at line rate without touching node1's link.
- node1 has a **single** 1GbE port, so any hub-and-spoke pattern caps at ~119 MB/s aggregate.
- Local NVMe reads run 1700–2000 MB/s.

**Moving a byte between nodes costs roughly 16x reading it locally.** Every architecture in
this repo is therefore shared-nothing and data-local: only control messages cross the wire.

### What this rules out

Documented so it does not get re-litigated: tensor-parallel inference (needs ~10 GB/s of
all-reduce against 0.119 GB/s available), distributed filesystems or shared volumes spanning
nodes, live workload migration, and anything that fans raw video frames through node1.
Raw 1080p30 is ~93 MB/s — a single stream saturates a link. Encoded H.265 is a different
story entirely, where the limit is encoder count, not bandwidth.

## Contents

- [docs/HARDWARE.md](docs/HARDWARE.md) — per-node capability and hard limits
- [docs/MEASUREMENTS.md](docs/MEASUREMENTS.md) — benchmark numbers with method
- [docs/STORAGE.md](docs/STORAGE.md) — ledger of large artifacts on the cluster
- [runbooks/k3s-clean-slate.md](runbooks/k3s-clean-slate.md) — reproducible teardown/rebuild
- [runbooks/pipeline-parallel-llm.md](runbooks/pipeline-parallel-llm.md) — run a model split across the Jetsons
- [research/](research/) — research papers, filed by the hardware the claim is about:
  [jetson-orin/](research/jetson-orin/), [rk3588/](research/rk3588/), [cluster/](research/cluster/)
- [capability-matrix/](capability-matrix/) — the evidence-graded capability map: feature x chip x slot, with 17 dated logs, raw results and draft papers
- [jetson-eeprom-fix/](jetson-eeprom-fix/) — QSPI/EEPROM recovery tooling for a Jetson that will not boot on this carrier

## One repo

All research on this board lives here. Two previously separate repositories were merged in with
their full history on 2026-11-24:

| Was | Now | Contents |
|---|---|---|
| `turing-pi-2.5-capability-matrix` | [`capability-matrix/`](capability-matrix/) | 17 dated measurement logs, raw data, bench scripts, 5 draft papers, and `MATRIX.md` generated from `data/capabilities.csv` |
| `turing-pi-2.5-jetson-eeprom-fix` | [`jetson-eeprom-fix/`](jetson-eeprom-fix/) | EEPROM fix, QSPI-only recovery and USB-park scripts, with host notes |

Both keep their original directory structure rather than being flattened into `research/`, because
each has internal relative links and a generator script that reads its own `data/` paths. Their
commits are reachable in this repository's history under their original paths; the source repos
are archived read-only so existing links still resolve.

The split had a cost worth recording: `capability-matrix/logs/2026-09-24_jetson-energy-per-token.md`
measured energy per token in September and [research/006](research/jetson-orin/006-batching-power-inversion.md)
revisited it in November, and the two sat in different repositories without either referencing the
other. They are now cross-linked in both directions.

## Results so far

A 32.76B-parameter dense model (Qwen3-32B Q3_K_M, 14.87 GiB) runs at 2.46 t/s split across an Orin NX
and an Orin Nano, having failed to load on either node individually. Aggregate throughput reaches
5.85 t/s decode at 4 concurrent streams. Details and the measurements that contradicted our
assumptions are in [research/002](research/cluster/002-pipeline-parallel-measurements.md).

The Orin NX's two DLA engines compile more of a transformer block than NVIDIA's own layer table
documents — RMSNorm, Softmax and the full attention core all build with GPU fallback *disabled* —
but lose to the GPU by 2.1x to 33.7x at decode shapes, so a ggml DLA backend is not worth building.
Follow-up measurement killed the consolation prize too: the GPU alone already uses **97% of the
module's 102 GB/s**, so DLA+GPU is 13% *slower* than the GPU by itself and the two DLA engines are
slower together than one — the DLA is not an additive second compute stream. At prefill shapes it
will not even compile. Capability map, concurrency table and the corrections are in
[research/003](research/jetson-orin/003-dla-transformer-offload.md).

node1's 3-core RK3588 NPU — recorded in earlier notes as having no userland, which was wrong — is
**2.0x faster than node1's own CPU at prefill** (219.9 vs 110.7 t/s) and **1.7x slower at decode**
(9.67 vs 16.11 t/s), with all three cores evenly loaded at ~62% and none saturated. Same
fixed-function signature as the DLA, opposite prefill outcome. That win over its own CPU does not
make node1 an inference stage: an Orin prefills ~10x faster still (1966.8 t/s against the NPU's
219.9), and node1's 31 GB cannot hold a 32B model's w8a8 weights, so there is no prompt length at
which routing prefill away from the node that will decode pays off. Project 001's constraint that
node1 only orchestrates stands — for capacity and engine speed, not the weak-CPU reason 001 gave.
The transfer cost 004 had named as the decider turned out to be affordable (105.1 MB/s backplane,
~18% of prefill) and was the wrong thing to bet on.
[research/004](research/rk3588/004-rk3588-npu-llm.md).

## Method

Every entry records what was measured, how, and what the result rules out. Negative results
are kept — on this hardware they are usually the more useful half, because the interesting
failures are architectural rather than incidental.
