# Booting Jetson Orin modules that were provisioned for a different carrier: QSPI-only recovery on a Turing Pi 2.5

**Platform:** Turing Pi 2.5.1 (BMC firmware 2.3.2). Jetson Orin NX 16GB (P3767-0000) in slot 2 and Jetson Orin Nano 8GB (P3767-0003) in slot 3, both previously flashed by Seeed Studio's tool for a reComputer J401 carrier and each carrying a 1 TB NVMe with a working JetPack 7.2 system
**Software stack:** Jetson Linux R39.2.0 (JetPack 7.2), `tegraflash`/`tegradevflash_v2` from the NVIDIA BSP, `tpi` 1.0.7, driving host Ubuntu 26.04 x86_64
**Date:** September 2026
**Public write-up and scripts:** <https://github.com/Hi5808/turing-pi-2.5-jetson-eeprom-fix>

## Question

Both modules ran their operating systems correctly in their original carriers. Moved into the Turing Pi without reflashing, neither booted. Can they be made to boot **without overwriting the NVMe** that holds the OS and data?

## Symptoms (both modules)

- Per-node red power LED lit; no status LED; no fan activity.
- BMC reports the node as powered on.
- No output on the BMC's serial capture; no DHCP lease; no IPv6 link-local reply.
- The BMC switch log shows the node's Ethernet link **up at 1 Gbps** (the module or its PHY is powered).
- The module enumerates over USB in recovery mode (`0955:7323` "T234 [Orin NX 16GB] recovery mode" and `0955:7523` "APX"), which means the boot ROM runs and the module is electrically healthy.

## Approaches that did not work

| Approach | Outcome | Why it was unacceptable or failed |
|---|---|---|
| Seeed's flashing tool | not used | rewrites the NVMe |
| NVIDIA `l4t_initrd_flash.sh` / `l4t_backup_restore.sh` | stalls at "Waiting for target to boot-up" | the temporary Linux never presented a USB network device; console silent |
| NVIDIA tools on the NX (early attempts) | `ERROR: might be timeout in USB write` at the applet stage, repeatable | USB link showed no errors in the host kernel log; not isolated; did not recur on later runs after fresh BMC power-cycles |

## Method that worked

1. Put one module in USB recovery mode with a **fresh BMC power-cycle** (`tpi power off`, `tpi usb flash`, `tpi power on`). A soft "reboot to recovery" from the NVIDIA tool leaves the boot ROM unable to start a new session until power-cycled.
2. Start one boot-loader session (`tegraflash.py … read BCT`), then read every QSPI partition with `tegradevflash_v2 --read /spi/0/<name>`: 60 partitions, 64 MiB, each size verified, SHA-256 recorded.
3. Apply the change the Turing Pi documentation prescribes for boards without a carrier EEPROM (`cvb_eeprom_read_size = <0x0>`, carrier EEPROM only; the module EEPROM is left readable) and flash **only** the QSPI using NVIDIA's `…-qspi` board profile (`NO_ROOTFS=1`).

## Results

- Both modules boot their existing NVMe systems on the Turing Pi. The NVMe was never written; home directories and the OS were intact afterwards.
- Comparing the original QSPI against the flashed one (restore in dry-run mode) shows **10 of 56 compared partitions differ**, all in the A and B slots: `mb2`, `MB1_BCT`, `cpu-bootloader` (UEFI and its device tree), `dce-fw`, `VER`. Everything else, including `mb1`, the memory configuration, BPMP and the secure OS, was already identical.
- The modules' UEFI variables carry Seeed's board-spec string (for example `3767-…-recomputer-orin-j401`), so the original provisioning is visible in the firmware; the boot firmware's own device tree, however, is NVIDIA's `p3768` device-kit tree, not a Seeed-specific one.

## Restore test (Orin Nano only)

`restore` compares the module against the backup and rewrites only differing partitions, then reads each back.

| Step | Result |
|---|---|
| Dry run | 56 checked, 46 identical, 10 differ |
| Restore, first attempt | stopped on the first write: read-back mismatch |
| Cause | the write was not preceded by an erase; NOR flash ANDs old and new bytes. NVIDIA's own sparse QSPI update erases first |
| Restore, second attempt (erase then write) | 10 partitions restored, each verified by read-back |
| Boot with the original firmware | did **not** boot on the Turing Pi; dropped to USB recovery mode (the original symptom) |
| Re-flash of the fix | boots normally; NVMe data intact |

## Interpretation and limits

- The result is consistent with "firmware provisioned for another carrier plus a missing carrier EEPROM", but **the exact cause is not proven**: the fix changes the EEPROM setting and NVIDIA's standard configuration together, and ten partitions differ.
- The restore round-trip was verified on the Nano only.
- The NX's earlier USB write timeouts were not isolated.
- One unit of each module on one board.

## Lessons recorded for others

- Fresh power-cycle before every NVIDIA-tool run.
- Erase before write on NOR flash; always verify by read-back.
- The BMC persists the USB flash-mode selection across restarts (see the [port map](../docs/PORT-MAP.md#hazards-learned-the-hard-way)).
