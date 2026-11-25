# 009 — What does the carrier board actually buy? Measured: packaging, not capability

**Platform:** Turing Pi 2.5.1 carrier; node1 Turing RK1 (10.43.0.1), node2 Jetson Orin NX 16GB
(10.43.0.12), node3 Jetson Orin Nano 8GB (10.43.0.13). Internal 1GbE switch; node1 exports
`/mnt/nvme/share` by NFS, automounted as `/mnt/share` on both Orins.
**Date:** 2026-11-24. **Status:** complete. Measurements in `selfmodel.db` run `a0d98d731391`.

## Abstract

[008](008-serving-capacity-knee.md) ended with an admission: it measured the machine without
using anything the carrier uniquely provides. This paper tests the two carrier features that
could plausibly justify the board over three separate SBCs and a cheap switch — the **internal
1GbE switch** and the **shared NFS store**. The switch delivers full line rate (937–941 Mbit/s,
0.39–0.44 ms RTT, 1.59 Gbit/s aggregate full-duplex), which is exactly what any gigabit switch
delivers. The shared store reads at **90.7 MB/s, 22× slower than the 2.0 GB/s NVMe each Orin
already has as its own root disk**. Neither feature provides a capability the modules lack. On
measured evidence the carrier's value is packaging — one PSU, one footprint, one console — and
the one remaining candidate that could change that verdict, per-slot power gating, cannot be
quantified without a board-level power meter.

## 1. Method

`iperf3` 3.x client/server between node pairs over the carrier's internal switch, 10 s per
direction, plus `--bidir` for full duplex and `ping -c 10 -i 0.2` for RTT. Storage read with
`dd ... bs=1M count=2000 iflag=direct` (2.0 GiB, O_DIRECT so the page cache cannot flatter the
result); local disks read as raw block devices to avoid needing a scratch file. All three nodes
have 8 cores, so neither endpoint is obviously CPU-starved.

## 2. The switch

| Path | Throughput | Notes |
|---|---|---|
| node1 -> node2 | **939 Mbit/s** sender / 937 receiver | line rate |
| node1 -> node3 | **939 Mbit/s** sender / 936 receiver | line rate |
| node2 -> node3 | **941 Mbit/s** | line rate, Orin to Orin |
| node2 <-> node3 full duplex | 789 + 804 = **1593 Mbit/s** aggregate | each direction loses ~15% |

| Path | RTT min/avg/max |
|---|---|
| node1 -> node2 | 0.381 / **0.439** / 0.544 ms |
| node1 -> node3 | 0.299 / **0.391** / 0.454 ms |

**Finding 1 — the switch is exactly a gigabit switch.** It saturates 1GbE in every direction
tested and carries both directions simultaneously at 1.59 Gbit/s, so the backplane is real and
not a bottleneck. It is also, precisely, what a $20 unmanaged gigabit switch does. Nothing here
is a capability the modules would lose on a desk.

The ~15% per-direction loss under simultaneous bidirectional load (941 -> ~800 Mbit/s) is most
likely NIC/CPU overhead on the Orins rather than the switch fabric, since the aggregate exceeds
a single link's capacity. Not isolated.

**Finding 2 — the switch is sufficient for split inference, which is the one thing that needs it.**
[002](002-pipeline-parallel-measurements.md) found that splitting a model across the Orins costs
4% (dense) to 18.5% (MoE) and that logit return dominates wire cost. At 941 Mbit/s and 0.4 ms RTT
the interconnect is not what limits that, so 002's penalty is not a carrier limitation and would
not improve with faster networking on this workload.

## 3. The shared store

| Read path | Throughput | vs local |
|---|---|---|
| node2 <- NFS `/mnt/share` over the switch | **90.7 MB/s** | — |
| node2 own NVMe (`/dev/nvme0n1`) | **2.0 GB/s** | **22× faster** |
| node3 own NVMe | **1.9 GB/s** | **21× faster** |
| node1 own NVMe (the NFS backing store) | 1.6 GB/s | 18× faster than serving it |

**Finding 3 — shared storage is a 22× performance penalty, not a capability.** Both Orins carry
a 931.5 GB NVMe as their *root* disk with ~930 GB free. They do not need node1's disk for space;
the shared mount exists so one copy of a model serves every node. That convenience is real, but
it is paid for at 90.7 MB/s.

**Finding 4 — the penalty was being paid in production, and has now been measured and fixed.**
`llama-server` on node2 loaded `Qwen3-14B-Q4_K_M.gguf` (9 001 752 960 bytes = 8.38 GiB) from
`/mnt/share`. Both models were staged onto their node's local NVMe and the cold-start load timed
A/B, dropping caches (`vm.drop_caches=3`) before each arm so neither side was favoured, with
readiness defined as HTTP 200 on `/health`:

| Load path | Cold start to ready | Effective throughput |
|---|---|---|
| NFS `/mnt/share` over the carrier | **81.50 s** | 105 MB/s |
| local NVMe `~/models` | **9.81 s** | 876 MB/s |
| local NVMe, warm cache | 8.74 s | — |

**8.3x faster, 71.7 s saved on every cold start.** Measurements in `selfmodel.db` run
`3bb165041cfe`.

Both predictions made earlier in this paper were wrong, in opposite directions, and the reasons
are worth keeping:

- **The NFS side was pessimistic.** 81.50 s implies 105 MB/s, *above* the 90.7 MB/s measured with
  `dd iflag=direct` in §3. O_DIRECT defeats readahead, so the O_DIRECT figure understates buffered
  sequential NFS reads by ~16%. The 22x ratio in Finding 3 is a ratio of O_DIRECT reads and should
  not be read as a ratio of real load times.
- **The local side was optimistic.** 9.81 s implies 876 MB/s against 2.0 GB/s of raw sequential
  read — only 44% of what the disk can do, and warm cache saves just 1.1 s more. So local model
  load is **not disk-bound**: mmap, tensor setup and CUDA init dominate. Predicting ~4.5 s from
  disk speed alone was the wrong model of the problem.

Real end-to-end gain is therefore **8.3x, not the ~22x** the storage benchmark suggested. The
staged copies were verified by exact byte size and by generating from each endpoint.

NFS also costs ~22% of the available wire: 90.7 MB/s is 726 Mbit/s against 937 Mbit/s measured by
`iperf3` on the same path, so protocol overhead and not just the link is in play.

## 4. Verdict on the board

Of the carrier's distinguishing hardware:

- **Internal switch** — works perfectly, equals a commodity gigabit switch, confers no advantage.
- **Shared NFS store** — 22× slower than disks the nodes already have; a convenience with a cost.
- **Per-slot power gating (BMC)** — **untested, and the only remaining candidate.** [008](008-serving-capacity-knee.md)
  measured an idle Orin Nano drawing **5.81 W** while doing nothing. If the BMC can gate an idle
  slot to zero, that is a continuous saving no pile of separate SBCs gets for free. Quantifying it
  needs a board-level meter, because the BMC itself has **no power sensing** —
  [2026-11-24_bmc-power-telemetry](../../capability-matrix/logs/2026-11-24_bmc-power-telemetry.md).
- **One PSU, one footprint, one console, UART/USB routing** — real, but packaging, not research.

So the honest conclusion is **negative**: no measured performance capability on this cluster
requires the carrier. That is a useful result rather than a disappointing one, because it says
where to stop looking — further networking or shared-storage work on this board cannot pay off,
and the open question is narrowed to exactly one measurable thing (slot gating) that needs
exactly one missing instrument (an inline 12 V DC meter).

## 5. Limitations

- Line rate is a ceiling test, not a workload test. A real split-inference run moves small
  tensors with latency sensitivity; 002 covers that and this paper does not re-measure it.
- The local-disk comparison reads **raw block devices** while the NFS comparison reads a **file**.
  Both are 2.0 GiB sequential O_DIRECT reads, but they are not identical paths, and a local
  filesystem read would be somewhat slower than the raw figure.
- Single 10 s / 2 GiB samples, no repeats. The numbers are stable at the 1% level across the
  pairs measured but carry no error bars.
- NFS was tested read-only and with default mount options (autofs, defaults). Tuned `rsize`,
  `nconnect` or NFS over RDMA were not attempted and could narrow the 22× gap, though not to
  within an order of magnitude of 2.0 GB/s on a 1GbE link.
- No external-switch control was run: the comparison to "a $20 switch" is against the 1GbE
  standard's line rate, not against a second physical switch measured here.
- Slot gating, the decisive remaining test, is **not** measured.

## 6. Reproduction

```sh
# on each node: iperf3 -s -D
ssh node1 'iperf3 -c 10.43.0.12 -t 10 -f m'            # and .13
ssh node2 'iperf3 -c 10.43.0.13 -t 10 -f m --bidir'
ssh node2 'ping -c 10 -i 0.2 -q 10.43.0.13'
# storage, O_DIRECT so the cache cannot help
ssh node2 'dd if=/mnt/share/models/<big>.gguf of=/dev/null bs=1M count=2000 iflag=direct'
ssh node2 'sudo dd if=/dev/nvme0n1 of=/dev/null bs=1M count=2000 iflag=direct'
```
