# Same drive model, three hosts: fio on the NVMe of each node, and a read-throughput state effect seen on all three

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Node 1 Turing RK1 (RK3588, 32 GB), node 2 Jetson Orin NX 16GB, node 3 Jetson Orin Nano 8GB. Each node has one M.2 NVMe, model string `SSD 1TB`, firmware `T1103N0L`, negotiated PCIe 8.0 GT/s x4 (Gen3 x4) on all three
**Software stack:** RK1: Ubuntu 24.04.1, kernel 6.1.0-1025-rockchip. Orin NX and Nano: JetPack 7.2, kernel 6.8.12-1021-tegra. fio 3.36 on all
**Date:** September 2026

## Question

The three nodes carry the same drive model on the same link width and speed. How much of the storage performance differs by host chip, and is a `dd` figure (see the node-1 storage log) a fair summary?

## Setup and method

- Script `/tmp/fiobench.sh` (copied to each node), run on all three nodes at the same time. File-based test on the NVMe filesystem (4 GiB file), `ioengine=libaio`, `direct=1`, 20 s per job plus 3 s ramp, 3 repetitions of 6 jobs in a fixed order per repetition: seqread, seqwrite (1 MiB, QD32), randread QD1, randread QD32, randwrite QD1, randwrite QD32 (4 KiB).
- Drive temperature at start and end: 40 °C on all nodes (no thermal throttling visible at this granularity).
- The test files were removed afterwards. The user's triage services were left running on nodes 2 and 3 (so those two hosts were not idle; not quantified).
- Raw fio JSON is in `data/raw/fio-2026-09-24/`, medians in `data/nvme_fio_2026-09-24.csv`.

## Results (median of 3 reps; MB/s = 10^6 bytes/s)

| Workload | Node 1 RK1 | Node 2 Orin NX | Node 3 Orin Nano |
|---|---|---|---|
| Seq write 1M QD32 | 1765 MB/s | 994 MB/s | 995 MB/s |
| Rand read 4k QD1 | 58 MB/s, 14.1k IOPS, p99 81 µs | 48 MB/s, 11.6k IOPS, p99 97 µs | 49 MB/s, 11.9k IOPS, p99 96 µs |
| Rand read 4k QD32 | 572 MB/s, 140k IOPS | 648 MB/s, 158k IOPS | 507 MB/s, 124k IOPS |
| Rand write 4k QD1 | 169 MB/s, 41.3k IOPS, p99 19 µs | 82 MB/s, 19.9k IOPS, p99 40 µs | 87 MB/s, 21.3k IOPS, p99 41 µs |
| Rand write 4k QD32 | 307 MB/s, 75k IOPS | 237 MB/s, 57.7k IOPS | 231 MB/s, 56.5k IOPS |

### Per-repetition sequential read and other unstable jobs (MB/s)

| Job | Node 1 | Node 2 | Node 3 |
|---|---|---|---|
| Seq read 1M QD32, reps 1/2/3 | 2432 / 716 / 711 | 2440 / 728 / 725 | 2358 / 730 / 726 |
| Seq write, reps 1/2/3 | 1764 / 1765 / 1769 | 994 / 994 / 435 | 997 / 995 / 429 |
| Rand write QD32, reps 1/2/3 | 314 / 306 / 307 | 509 / 237 / 156 | 502 / 197 / 231 |

## Findings

1. **Sequential read is state-dependent, identically on all three hosts.** Rep 1 reads about 2.4 GB/s; reps 2 and 3 read about 0.72 GB/s. Since all three hosts show it, it is most likely a property of the drive (the read follows write-heavy jobs of the previous repetition), not of the host. The mechanism was **not** determined; this run cannot separate drive garbage collection from other causes. A median alone (about 720 MB/s) would hide the 2.4 GB/s state, so single `dd` reads such as the earlier 1.8 GB/s are not comparable across runs.
2. **Sequential write and QD1 small-block writes are about 2x faster on the RK1 than on either Jetson** (1765 vs about 995 MB/s; 169 vs 82–87 MB/s). The drive and link are the same, so the host side (controller, driver, kernel version, or the load of the triage services on the Jetsons) is responsible; which one was not isolated.
3. **QD1 random read latency is lowest on the RK1** (p50 59 µs vs 72–74 µs), while at QD32 the Orin NX is highest (158k IOPS vs 140k RK1 and 124k Nano).
4. **Jetson write jobs collapse in later repetitions** (seq write 994 → 435 MB/s, QD32 random write down to 156–231 MB/s); the RK1 stayed flat. Not seen on RK1 in this run, cause unknown.
5. Nodes 2 and 3 track each other closely on most jobs, as expected for the same SoC family and kernel.

## Limitations

One unit of each module, one drive per node, three repetitions, one run. The nodes ran concurrently on a shared board (one PSU) and the Jetsons had the user's services running. Kernels differ (6.1 vs 6.8), as do PCIe host controllers and drivers, so item 2 is a host-stack difference, not a chip-only one. The drive's SLC/DRAM cache behaviour is not documented for this model string; the state effect in item 1 is an observation, not an explanation. Temperatures were sampled only at start and end.

## Reproduction

`scripts/` will hold `fiobench.sh` (copied from the run); raw JSON and the summary CSV are under `data/`.
