# NFS share of the RK1's NVMe to the Jetsons: wire-limited and checksum-clean

**Platform:** Turing Pi 2.5.1; node 1 Turing RK1 (NFS server, 1 TB NVMe at `/mnt/nvme`), node 3 Jetson Orin Nano (client)
**Software stack:** Ubuntu 24.04.1 `nfs-kernel-server`; JetPack 7.2 `nfs-common`; NFS 4.2, rsize/wsize 1 MiB, `sync` export
**Date:** September 2026

## Question

Can the RK1's NVMe serve as shared storage for the other nodes, and at what speed?

## Setup and method

- Node 1 exports `/mnt/nvme/share` to `10.43.0.0/24` (`rw,sync,no_subtree_check,no_root_squash`), added to `/etc/exports`; the NFS server service is active and **left enabled**. `no_root_squash` was chosen for convenience on a private board-internal network and is a security trade-off.
- Node 3 mounted it at `/mnt/nfs-test` (not persisted in fstab; lost on reboot).
- `fio`: 2 GiB file, 1 MiB blocks, QD8, direct I/O, sequential write then sequential read, one run each.
- Integrity: 1 GiB from `/dev/urandom` written over NFS, SHA-256 of the source compared with the file as seen on node 1's disk.

## Results

| Test | Result |
|---|---|
| Sequential write over NFS | 117 MB/s |
| Sequential read over NFS | 110 MB/s |
| 1 GiB random-file integrity | SHA-256 prefix `a4949430322da007` identical on client source and server disk |

## Findings

1. **NFS to the RK1's NVMe runs at the 1 GbE wire limit** (117 MB/s; TCP line rate measured earlier is about 117 MB/s), far below the drive's local throughput (see the fio log). The network, not the drive, is the limit.
2. The read figure (110 MB/s) is slightly below the wire limit at QD8 with one run; the reason was not investigated.
3. The write-integrity check passed for one file.

## Limitations

One client, one run per direction, one file; no concurrent clients (both Jetsons at once would share the RK1's single gigabit link); no small-file or metadata benchmark; the export is open to the whole board subnet with `no_root_squash`.

## Reproduction

Commands in Setup; results in `data/raw/nfs-2026-09-24/`.
