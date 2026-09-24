# Mini-PCIe on the Turing Pi 2.5: why a Wi-Fi/Bluetooth combo card works over USB but not PCIe, on two different SoCs

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Turing RK1 (RK3588, 32 GB) in slot 1; Jetson Orin NX 16GB in slot 2. Test card: Atheros AR5B22 (half-size mini-PCIe: AR9462 Wi-Fi over PCIe, AR3012 Bluetooth over USB)
**Software stack:** RK1: Ubuntu 24.04.1 (ubuntu-rockchip), kernel 6.1.0-1025-rockchip. Orin NX: JetPack 7.2, kernel 6.8.12-1021-tegra
**Date:** September 2026

## Question

The cluster needs Wi-Fi, and this card was available. Does its PCIe (Wi-Fi) function work in a Turing Pi mini-PCIe slot?

## Observations

| Chip / slot | Bluetooth (USB) | Wi-Fi (PCIe) |
|---|---|---|
| RK1, slot 1 | enumerates (`0cf3:311e`) | never appears; port reports `PCIe Link Fail` |
| Orin NX, slot 2 | enumerates (`0cf3:311e`) | never appears; both otherwise-empty x1 controllers report `Phy link never came up` |
| RK1, slot 1 (card returned) | enumerates | same as before |

The card is powered and its USB pins reach the module in both slots, so the failure is specific to the PCIe pins or the card's PCIe function.

## RK1 investigation

1. The `ath9k` driver is present in the RK1 kernel, so a missing driver is not the cause.
2. The device tree enables one x1 controller (`pcie2x1l1`, `pcie@fe180000`), whose PHY (`fee20000`) is **shared with a USB 3.0-only host controller** (`usb@fcd00000`). The boot log said so: `phy type select 4 overwriting type 2`, i.e. the PHY was configured for PCIe and then overwritten for USB3.
3. A device-tree overlay disabling that USB3 host removed the conflict message. **The link still failed** (`LTSSM 0x3`).
4. Forcing the port to Gen1 (`max-link-speed=1`): still failed.
5. All three RK3588 x1 controllers (`fe170000`, `fe180000`, `fe190000`) and their PHYs were enabled in one overlay: **all three failed identically**; no Atheros device on any lane.

## Correction recorded

While the RK1 was the only data point I read `LTSSM 0x3` as "Polling.Compliance: the far end is detected but silent". Step 5 contradicts that: two of those lanes are almost certainly connected to nothing yet reported the same value. **`LTSSM 0x3` here simply means "no device found"**, and the earlier interpretation was withdrawn.

## Conclusion and limits

The same card fails to link on two different SoCs in two different slots, while its USB function works in both. That points to the card's PCIe function or its contacts, not to the RK1 or a specific slot. It is **not proven**: no second card was tried, and vendor documentation does not say whether the mini-PCIe PCIe lanes are wired for RK1 and Jetson modules at all (the v2.5 change log mentions only the USB interface). The matrix records the PCIe rows as FAILS with the cause open, and a second mini-PCIe card as the deciding experiment.

## Workaround measured: USB Wi-Fi adapter (Realtek RTL8822BU, on the RK1's USB-A)

| Driver | Result |
|---|---|
| in-kernel `rtw88_8822bu` | enumerates and probes, then **every register access times out (`-110`)** once the radio is used; holds locks so administrative commands on the interface hang |
| vendor `88x2bu` (already in the kernel tree) with power saving disabled | works: 5 GHz link, reported 867 Mbit/s, zero timeouts across reboots |

The in-kernel driver was displaced by moving its module aside so that only the vendor driver matches the device. Throughput beyond the negotiated link rate was **not** measured.

## Method note

A rebind of the PCIe host driver at runtime was attempted and proved impossible (the driver exposes no bind/unbind); every device-tree test required a reboot. One test was lost because files were written and the node hard-reset before they reached disk; it was redone after `sync`.
