# Port map and the slot-rotation protocol

**Platform:** Turing Pi 2.5.1 four-slot cluster board (BMC firmware 2.3.2) carrying a Turing RK1 (RK3588, 32 GB), a Jetson Orin NX 16GB and a Jetson Orin Nano 8GB
**Date:** September 2026

## The constraint

Every expansion port on this board is wired to **one specific slot**. A compute module can only use the ports of the slot it sits in. Two consequences for a study that wants to characterise every chip:

1. A chip cannot be tested on a port that lives in a slot it is not in (for example the Jetsons have no free USB host port while they occupy slots 2 and 3, because USB 3.0 belongs to slot 4).
2. Whether a feature "works on chip X" is confounded with "works in slot Y" until the same chip has been tested in more than one slot.

The matrix therefore tracks **chip × slot** coverage (see [MATRIX.md](../MATRIX.md#slot-coverage)), not just chip.

## Documented assignments (vendor sources, not all verified here)

| Slot | Ports documented | Source |
|---|---|---|
| 1 | 4K HDMI out, USB-A (USB 2.0 host), DSI, mini-PCIe #1 (with SIM tray), M.2 | Turing Pi product page; Turing's Jetson article; Geerling 2021 |
| 2 | mini-PCIe #2 (no SIM tray), M.2 | Geerling 2021; Turing Pi product page ("nodes 1 and 2" for the mini-PCIe USB interface) |
| 3 | 2 × SATA III, M.2 | Turing's Jetson article; Geerling 2021 |
| 4 | USB 3.0 (rear ports and front header), M.2 | Turing's Jetson article; Geerling 2021 |
| all | 1 GbE through the board's managed switch; USB routing to the BMC | product page; observed |
| unstated | 40-pin Raspberry-Pi-compatible GPIO header; camera (CSI) connectors | vendor docs are silent on which node — **to be measured** |

The vendor pages disagree in detail and do not state every assignment, so each row is labelled by how it was established.

## Verified on this unit

| Observation | Slot | Chip | Date |
|---|---|---|---|
| HDMI output present | 1 | RK1 | 2026-09-23 |
| USB-A host works (Wi-Fi dongle enumerates and passes traffic) | 1 | RK1 | 2026-09-24 |
| mini-PCIe **USB** pins reach the module (Bluetooth function of the test card enumerates) | 1 and 2 | RK1, Orin NX | 2026-09-24 |
| M.2 NVMe at PCIe Gen3 x4 | 1, 2, 3 | RK1, NX, Nano | 2026-09-24 |
| SATA controller (ASMedia ASM1061) enumerates | 3 | Nano | 2026-09-24 |
| mini-PCIe **PCIe** lane reaches a working link | 1 and 2 | RK1, NX | **not observed** ([log](../logs/2026-09-24_mini-pcie-wifi-investigation.md)) |

Slot 4 is empty, so **USB 3.0 has never been exercised**.

## What is not explorable in the current arrangement

| Feature group | Needs | Currently |
|---|---|---|
| USB 3.0 devices (cameras, capture, fast storage, audio interfaces) | a module in slot 4 | slot empty |
| HDMI / DSI / USB-A host on the Jetsons | a Jetson in slot 1 | RK1 occupies slot 1 |
| SATA on RK1 or NX | that chip in slot 3 | Nano occupies slot 3 |
| mini-PCIe on the Nano | Nano in slot 1 or 2 | Nano in slot 3 |
| Camera and 40-pin GPIO | node assignment measured first | unknown |

## Rotation protocol

Four slots, three modules: a cyclic shift leaves one slot empty per session and covers **all 12 chip × slot pairs in four sessions**.

| Session | Slot 1 | Slot 2 | Slot 3 | Slot 4 |
|---|---|---|---|---|
| S1 (done) | RK1 | Orin NX | Orin Nano | empty |
| S2 | empty | RK1 | Orin NX | Orin Nano |
| S3 | Orin Nano | empty | RK1 | Orin NX |
| S4 | Orin NX | Orin Nano | empty | RK1 |

(Chip `i` sits in slot `((i-1+s) mod 4)+1` in session `s`.)

### Hazards, learned the hard way

- **Power the board off before moving anything.** No hot-swap.
- **The OS travels with the module for the Jetsons.** Each Jetson boots from an NVMe in its slot's M.2 connector, so the NVMe must move with the module, or the module will not find its OS. The RK1 boots from its own eMMC.
- **The Jetson boot firmware fix is slot-independent.** It lives in each module's own QSPI ([log](../logs/2026-09-23_qspi-recovery-foreign-carrier.md)), so it moves with the module.
- **Network identity follows the module** for the Jetsons (the MAC is stored in the module EEPROM), so DHCP reservations by MAC still apply, but the BMC's node numbers change. Every `tpi` command must be re-mapped.
- **The BMC remembers a node's USB flash-mode selection across restarts.** Leave the selection parked on an empty slot after any recovery work, or the module in that slot powers on in USB recovery mode.
- **Slot 4 has no gateway/DHCP role** until a module is placed there; the RK1 currently provides those services from slot 1, so moving it means moving the gateway.
- Handle heatsinks and thermal interfaces deliberately: re-seating a module changes its thermal contact, which confounds any thermal or sustained-throughput measurement between sessions. Re-measure a reference workload after each move.

## Open questions this map should answer

1. Which node does the 40-pin GPIO header belong to, and does it depend on module type?
2. Are the mini-PCIe **PCIe** lanes actually wired for RK1 and Jetson modules, or only USB (as the v2.5 change log's wording suggests)?
3. Does a chip behave identically in every slot for the same port class (for example Gen3 x4 M.2)?
