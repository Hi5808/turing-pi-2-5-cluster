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
- [research/](research/) — numbered research log, newest last

## Results so far

A 32.76B-parameter dense model (Qwen3-32B Q3_K_M, 14.87 GiB) runs at 2.46 t/s split across an Orin NX
and an Orin Nano, having failed to load on either node individually. Aggregate throughput reaches
5.85 t/s decode at 4 concurrent streams. Details and the measurements that contradicted our
assumptions are in [research/002](research/002-pipeline-parallel-measurements.md).

The Orin NX's two DLA engines compile more of a transformer block than NVIDIA's own layer table
documents — RMSNorm, Softmax and the full attention core all build with GPU fallback *disabled* —
but lose to the GPU by 2.1x to 33.7x at decode shapes, so a ggml DLA backend is not worth building.
Capability map and numbers in [research/003](research/003-dla-transformer-offload.md).

## Method

Every entry records what was measured, how, and what the result rules out. Negative results
are kept — on this hardware they are usually the more useful half, because the interesting
failures are architectural rather than incidental.
