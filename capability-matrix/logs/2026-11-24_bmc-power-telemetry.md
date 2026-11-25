# The BMC cannot measure power: closing row A18 as needs-hardware

**Platform:** Turing Pi 2.5.1 board management controller (BMC), `turingpi` Linux 6.8.12 armv7l,
Buildroot 2024.05.1, BMC firmware version 2.3.2, API 1.1, `tpi` 1.0.6
**Date:** 2026-11-24

## Question

Row A18 (energy per token on the RK3588) has been open since September because the RK1 module
exposes no INA3221 rails, unlike both Jetsons. It was recorded for weeks as "blocked on BMC
credentials". Two questions: are the credentials actually the blocker, and can the BMC report
power at all?

## Setup and method

The BMC answers only on the board's private network, so it was reached from node1 as an SSH
ProxyJump. It authenticates as `root` with the vendor default password, over SSH — **not** over
the HTTPS API, which is what had been returning 401/403 and created the false "needs credentials"
blocker.

Everything below is read-only. No node was power-cycled.

- `tpi --help`, `tpi info`, `tpi power status`
- `i2cdetect -y 0` on the BMC's only i2c bus, plus the bound driver for every detected address
- a search of `/sys` for `power*_input`, `curr*_input`, `in*_input`, any `iio` device, any ADC
- the HTTP API: `opt=get&type=power` and `type=other`

## Results

**The BMC has no power-sensing hardware.** Its one i2c bus holds exactly three devices:

| Address | Device | Driver | What it is |
|---|---|---|---|
| 0x50 | 24c02 | `at24` | 2 Kbit EEPROM (board identity) |
| 0x51 | pcf8563 | `rtc-pcf8563` | real-time clock |
| 0x5c | rtl8365mb | `realtek-smi` | the on-board Ethernet switch |

Addresses 0x40–0x45, where an INA219/INA226/INA3221 would sit, are empty. There is no hwmon device
other than `pwmfan`, no `iio` device, no ADC, and no `power`, `curr` or `in` input anywhere in
`/sys`.

The API confirms it from the other direction. `type=power` returns **state, not watts**:

```json
{"response":[{"result":[{"node1":"1","node2":"1","node3":"1","node4":"1"}]}]}
```

`tpi`'s full command set is `power, usb, firmware, flash, eth, uart, advanced, cooling, info,
reboot`. `power` switches nodes on, off and resets them. Nothing in the firmware reports
consumption.

## Findings

1. **A18 is not blocked on credentials, and never was.** The credentials existed all along in the
   operator's own `tp` script. Having them changes nothing, because the measurement is impossible
   with on-board instrumentation. The row's original method note — "needs board-level meter" — was
   right from the start.
2. **The BMC is still useful for this measurement, as a switch rather than a sensor.** It can gate
   each slot's power independently. That turns a *single* external meter into per-node attribution
   by differencing: meter the board input, then power nodes off one at a time and subtract. No
   per-node sensor is required.
3. This also bounds what [research/006](../../research/jetson-orin/006-batching-power-inversion.md) can claim. Its
   finding that module power *falls* as concurrency rises is measured on the two Jetsons only. The
   board-level question — whether it survives the PSU's own conversion losses — needs the meter
   below.

## What would close A18

An inline DC meter on the board's 12 V input, or a wall meter on the PSU. Then:

1. Baseline: all four slots off, board idle. This is the carrier's own overhead — fan, BMC,
   Ethernet switch — which no per-module rail can see and which nothing in this repo has measured.
2. Power each node on alone, idle, and subtract the baseline.
3. Repeat under load. For the RK3588 that gives energy per token directly; for the Jetsons it gives
   a cross-check against their INA3221 rails, and the difference between the two is the carrier +
   regulator loss per node.

Step 1 is worth the meter on its own: board overhead is currently unmeasured and unattributed, and
every tokens-per-joule figure in this repo silently excludes it.

## Limitations

Negative results about absent hardware are only as good as the search. This one covers the i2c bus,
hwmon, iio, the `/sys` input attributes and the documented API on **this** firmware version
(2.3.2, API 1.1). A later firmware could expose a rail that the hardware does not have, which is
unlikely, but the scan should be repeated after any `tpi firmware` upgrade. Possible power sensing
reachable only from a node, rather than from the BMC, was not investigated.

## Reproduction

```sh
SSHPASS=turing sshpass -e ssh -J node1 root@10.43.0.10 \
  'i2cdetect -y 0; for d in /sys/bus/i2c/devices/*/; do \
     echo "$(basename $d): $(cat $d/name 2>/dev/null)"; done; \
   curl -sk "https://127.0.0.1/api/bmc?opt=get&type=power"'
```
