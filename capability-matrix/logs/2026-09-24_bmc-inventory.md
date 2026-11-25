# BMC inventory (read-only): what the Turing Pi 2.5.1 management controller exposes

**Platform:** Turing Pi 2.5.1, BMC firmware 2.3.2 (API 1.1, Buildroot 2024.05.1, built 2024-09-03), BMC address 10.43.0.10 on the board's internal network
**Software stack:** `tpi` CLI on the BMC (reached by SSH from the laptop)
**Date:** September 2026

## Question

Which controls does the BMC give, and which measurements can it provide for the experiments?

## Observations (read-only; nothing was changed)

| Item | Observation |
|---|---|
| `tpi` commands | `power`, `usb`, `firmware`, `flash`, `eth` (only `reset`), `uart`, `advanced`, `cooling`, `info`, `reboot` |
| Node power | all four slots report "On" (slot 4 is empty, so its state is not evidence of a module) |
| USB routing | one USB bus routed to one node at a time; currently host to node 1 (alternative port) |
| Cooling | `tpi cooling status`: one device, "system fan", speed 6 of max 6 |
| UART | node 1's console buffer returned kernel text (`dw-dp fde50000.dp ...`); nodes 2, 3 and 4 returned nothing at this moment (quiet consoles, not evidence of a broken UART) |
| Ethernet switch | only a reset command is exposed; no per-port counters or VLAN control through `tpi` |
| BMC hardware sensors | one hwmon device, `pwmfan`; no power or current telemetry for the nodes |
| BMC resources | 116 MB RAM (22 MB used), root filesystem is read-only squashfs (100% full by design) with a 138 MB UBI overlay |

## Findings

1. **The BMC provides no per-node power measurement**, so energy figures for the RK1 need an external meter (matrix row A18 stays open). The Jetsons' figures come from their own on-module rails.
2. **The BMC exposes one fan control and no per-node temperature**; thermal data must come from the nodes.
3. The four-slot power, single-USB-bus routing and per-node UART are the BMC's usable experimental levers: these are what the recovery procedure and the rotation protocol depend on.

## Limitations

Read-only survey of one firmware version; UART read-back was a single sample; `tpi advanced` modes and firmware update were not exercised (irreversible or disruptive).
