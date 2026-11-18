# Measurements

**Platform:** Turing Pi 2.5 board; node1 = Turing RK1 (RK3588, 31 GB); node2 = Jetson Orin NX 16GB;
node3 = Jetson Orin Nano 8GB.
**Software stack:** Ubuntu 24.04.5 LTS on all three; node1 kernel 6.1.0-1025-rockchip;
nodes 2–3 JetPack 7.2 / L4T R39.2 / CUDA 13.2, kernel 6.8.12-1021-tegra; k3s v1.36.4+k3s1.
**Date:** 2026-11-17.

## Abstract

Interconnect and storage throughput were measured to decide whether a multi-stream
architecture is viable on this chassis. It is not. The backplane delivers full 1GbE per node
but node1 — which owns the only uplink and the control plane — has a single port, making it a
hard ~119 MB/s aggregate bottleneck for any hub-and-spoke design. Local NVMe is 15–17x faster
than the wire, which inverts the usual cluster assumption that data should move to compute.

## Network

`iperf3`, 5 seconds, 4 parallel streams, over the backplane (10.43.0.0/24).

| Path | Throughput | Note |
|---|---|---|
| node2 -> node1 | 951 Mb/s (119 MB/s) | line rate |
| node3 -> node1 | 951 Mb/s (119 MB/s) | line rate |
| node2 <-> node3 | 941 Mb/s (118 MB/s) | peer-to-peer, never touches node1's link |

All links negotiate 1000Mb/s full duplex. The onboard switch is non-blocking for pairwise
traffic: a node2<->node3 transfer at line rate leaves node1's bandwidth fully available.

## Storage

`dd` with `iflag=direct` (2 GB) on the Jetsons; `hdparm -t --direct` on node1.

| Node | Device | Sequential read |
|---|---|---|
| node1 | NVMe (`/mnt/nvme`) | 1879 MB/s |
| node2 | `/dev/nvme0n1` | 1700 MB/s |
| node3 | `/dev/nvme0n1` | 2000 MB/s |

**Ratio of local read to cross-node transfer: ~16x.**

## Derived limits

- Raw 1080p30 YUV420 = ~93 MB/s. One stream saturates a link. 4K raw (~373 MB/s) is impossible.
- Encoded H.265 1080p30 at 8 Mbps = ~100 streams per link. For encoded work the bottleneck is
  the number of encoder engines, not the network.
- Tensor-parallel LLM inference needs all-reduce bandwidth on the order of 10 GB/s. Available:
  0.119 GB/s. Not viable, by two orders of magnitude.
- Pipeline-parallel LLM inference moves only layer-boundary activations — on the order of
  10 KB per token for a 14B-class model. Bandwidth is irrelevant; the design is latency-bound.

## Media engine asymmetry

A hard constraint that invalidates treating the nodes as interchangeable:

| Node | Encode | Decode |
|---|---|---|
| node1 (RK3588) | 8K H.264/H.265 | 8K H.264/H.265 |
| node2 (Orin NX) | 1x NVENC | 1x NVDEC |
| node3 (Orin Nano) | **none** | NVDEC only |

node3 physically cannot encode video. node1 — normally thought of as "just" the control node —
holds the strongest transcode engine in the chassis.


## Pipeline-parallel LLM inference, 2026-11-18

Full method and findings in [../research/002](../research/002-pipeline-parallel-measurements.md).

### Single-node decode (same model, Qwen3-4B Q4_K_M)

| Node | INT8 TOPS | pp512 | tg128 |
|---|---|---|---|
| node2 Orin NX | ~157 | 744.61 | 20.00 |
| node3 Orin Nano | ~67 | 671.38 | 18.16 |

**A 2.3× TOPS gap yields a 9% decode difference** — decode is memory-bandwidth-bound and both modules
have 102 GB/s. Do not size pipeline stages from TOPS.

### Allocatable memory (moves with system state)

| Node | Total | Allocatable observed |
|---|---|---|
| node2 | 15599 MiB | 12.21–13.90 GiB |
| node3 | 7547 MiB | 5.39 GiB |

Unified CPU+GPU memory; a 1.7 GiB swing on node2 between a loaded and a freshly restarted worker.
Read `available_memory_kb` from the worker at launch; never reuse an earlier figure.

### Pipeline cost and per-token traffic

| Model | Single node | Split 2 nodes | Penalty |
|---|---|---|---|
| Dense 14B Q4 | 7.49 t/s | 7.19 t/s | −4.0% |
| MoE 30B-A3B Q3 | 18.63 t/s | 15.18 t/s | −18.5% |
| Dense 32B Q3 | **OOM both nodes** | 2.46 t/s | n/a |

Per-token network cost ~703 KB, of which ~666 KB is **inbound logits** to the orchestrator
(151,936-token vocabulary × 4 bytes ≈ 594 KiB). ~40 Mbit/s, **4% of the 1GbE link**; bandwidth
ceiling would be ~169 tok/s. Orchestrator CPU at 7.4%. The pipeline is compute-bound.

### Batched decode (aggregate throughput)

| Streams | Dense 32B decode | MoE 30B decode |
|---|---|---|
| 1 | 2.41 t/s | 12.64 t/s |
| 2 | 4.31 t/s (1.79×) | 19.91 t/s (1.58×) |
| 4 | 5.85 t/s (2.43×) | 23.58 t/s (1.87×) |
| 8 | — | 35.30 t/s (2.79×) |

Batching gain scales with how **weight-read-bound** the model is: dense streams 14.87 GiB of weights
per token against the MoE's ~1.4 GiB, so dense benefits more per stream added.
