# A blank M.2 NVMe on the RK1 node: verification, first throughput figure, permanent mount

**Platform:** Turing Pi 2.5.1, Turing RK1 (RK3588, 32 GB) in slot 1, M.2 NVMe (PCIe Gen3 x4), operating system on the module's 29 GB eMMC
**Software stack:** Ubuntu 24.04.1, kernel 6.1.0-1025-rockchip, nvme-cli, util-linux `sfdisk`, ext4
**Date:** September 2026

## Observation

The drive (`SSD 1TB`, Silicon Motion SM2263-family controller, firmware T1103N0L) was detected at boot without errors but held no partition table or filesystem, and nothing was mounted. `tpi flash` writes only the module's eMMC, so this state is not a result of the provisioning steps.

## Blankness check (read-only)

| Check | Result |
|---|---|
| `wipefs -n` (dry run) | no signatures |
| `blkid` | nothing |
| first 64 MiB, last 4 MiB, eight 1-MiB samples across the drive | all zero bytes |

A previously discarded ("trimmed") SSD also reads zero, so whether it once held data cannot be determined.

## Health before use

`critical_warning 0`, `percentage_used 0%`, `media_errors 0`, power-on hours 9, temperature 40 °C.

## Result

- One GPT partition, ext4 (label `nvme-data`, no reserved blocks), mounted at `/mnt/nvme` through `fstab` with `nofail`, so a missing drive cannot block boot.
- **Sequential throughput, single run, `dd` with direct I/O, 4 GiB:** write 1.2 GB/s, read 1.8 GB/s.
- **Integrity:** a 1 GiB random file written and then read back from the disk (page cache dropped) matched its SHA-256; the drive reported no media errors afterwards.
- The mount and the data survived a reboot.

## Limits

- The throughput figures are from single `dd` runs, not a controlled benchmark (`fio`, queue-depth sweep, steady-state after the SLC cache fills). They are indicative only, and are recorded as such in the matrix.
- The drive is DRAM-less; sustained-write behaviour was not characterised.
- The equivalent figures for the two Jetson NVMe drives have not been measured, so no cross-chip comparison of the M.2 path is made yet.
