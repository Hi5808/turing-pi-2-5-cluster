# Full-board restart and data integrity, and what the NVMe "unsafe shutdown" counter really counts

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Turing RK1 (slot 1, eMMC root), Jetson Orin NX 16GB (slot 2) and Orin Nano 8GB (slot 3), both Jetsons on 1 TB NVMe roots
**Software stack:** `tpi` 1.0.7; nvme-cli; Ubuntu 24.04 (RK1) and JetPack 7.2 (Jetsons)
**Date:** September 2026

## Question

Does a full board restart (including the BMC) bring every node back with its data intact, and why did the NVMe drives' "unsafe shutdown" counter rise after clean shutdowns?

## Procedure

1. Baseline snapshot of each node: root filesystem state, kernel storage errors, NVMe health (`critical_warning`, `media_errors`, `percentage_used`, `unsafe_shutdowns`, `power_cycles`), home-directory entry counts, failed units, default route and internet reachability.
2. Clean `systemctl poweroff` of nodes 2 and 3, BMC `power off`; clean shutdown of node 1 (the gateway), BMC `power off`.
3. `tpi reboot` (the tool documents: "Nodes will lose power until booted!").
4. Power on node 1, then nodes 2 and 3; snapshot again.

## Results

| Measure | Result |
|---|---|
| BMC back after `tpi reboot` | ~55 s, with node power state and the parked USB selection remembered |
| Node 1 reachable after power-on | 34 s; the BMC re-acquired its address from node 1's DHCP at the same time |
| Nodes 2 and 3 reachable after power-on | 34 s each |
| Root filesystems | `clean` on all three; 0 kernel storage errors |
| NVMe health (both Jetsons) | `critical_warning 0`, `media_errors 0`, `percentage_used 0%` |
| Home directories | entry counts unchanged (node 1: 7, node 2: 128, node 3: 62) |
| Nodes in USB recovery mode after restart | none |

## The unsafe-shutdown counter

The counter rose by 1 (and `power_cycles` by 2) on both Jetsons after one clean cold cycle. To find out whether shutdown timing was responsible:

| Step (node 2, chronological) | `power_cycles` | `unsafe_shutdowns` |
|---|---:|---:|
| baseline | 13 | 7 |
| clean poweroff; power cut ~15-20 s later (the node stopped answering after ~4 s); power on | 15 (+2) | 8 (+1) |
| warm reboot | 15 (+0) | 8 (+0) |
| clean poweroff; **90 s** wait; BMC power cut; power on | 17 (+2) | 9 (+1) |

Node 3 behaved the same on the first cold cycle (`power_cycles` 12 to 14, `unsafe_shutdowns` 8 to 9).

**Interpretation.** The increment is independent of the shutdown wait (about 15-20 s versus 90 s) and absent on a warm reboot, so it is not caused by cutting power before the OS finished quiescing the drive. It is produced **at cold boot**, consistent with the NVMe slot's power being toggled once during startup, before any I/O. That mechanism is a hypothesis; it was not observed directly (no rail measurement).

## Method notes and limits

- The BMC's own reboot cuts power to every node, including the node that serves DHCP to the BMC. The procedure was run only after a fallback path to the BMC that needs no DHCP (its IPv6 link-local address, through a local TCP forwarder) had been proven.
- One board, one restart of the whole board; the two Jetson NVMe drives are the same model, so the counter behaviour is not established for other drives.
- The BMC did not need to be told the intended node power state: it restored what it had saved.
