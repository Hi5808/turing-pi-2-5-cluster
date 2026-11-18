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
