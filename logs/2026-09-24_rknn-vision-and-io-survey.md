# RK1 NPU on a vision model (YOLOv5s), and a software survey of the header-type interfaces on all three nodes

**Platform:** Turing Pi 2.5.1; node 1 Turing RK1 (RK3588 NPU), node 2 Orin NX 16GB, node 3 Orin Nano 8GB
**Software stack:** RK1: Ubuntu 24.04.1, kernel 6.1.0-1025-rockchip, RKNPU driver v0.9.7, `rknn-toolkit-lite2` 2.3.2 (Python 3.12), `librknnrt.so` (md5 a37ee1d5…, identical to the copy on the Orange Pi 5 Plus). Jetsons: JetPack 7.2
**Date:** September 2026

## Question

Does the RK1's NPU run a vision model through the RKNN path, and which low-speed interfaces do the three nodes expose to software?

## Setup and method

- **RKNN:** `yolov5s_relu_rk3588.rknn` (copied from the Orange Pi 5 Plus, same SoC), input 1x640x640x3 uint8 (random data, so no accuracy claim), 20 warm-up runs then 300 timed `inference()` calls, single NPU core (`NPU_CORE_0`) and all three (`NPU_CORE_0_1_2`); NPU clock 1000 MHz. Timing includes the runtime's input handling but not any pre/post-processing. To run it, `librknnrt.so` was copied to `/usr/lib/` on node 1 (one added file). Script and result: `data/raw/rknn-2026-09-24/`.
- **Interfaces:** device nodes and sysfs listings on each node (read-only). Files: `data/raw/io-2026-09-24/`.

## Results

### YOLOv5s 640x640 on the RK1 NPU

| Cores | Mean (ms) | p50 (ms) | p99 (ms) | Throughput (fps) |
|---|---|---|---|---|
| 1 | 25.91 | 24.66 | 35.64 | 38.6 |
| 3 | 16.91 | 16.19 | 23.24 | 59.1 |

### Interfaces visible to software

| | RK1 | Orin NX | Orin Nano |
|---|---|---|---|
| GPIO chips | 6 | 2 (164 + 32 lines) | 2 (164 + 32 lines) |
| I2C buses | 5 (`rk3x-i2c` x3, DP AUX, DDC) | 6 | 6 |
| SPI devices | none | 4 (`spidev0.0/0.1/1.0/1.1`) | 4 |
| CAN | none | `can0` | `can0` |
| UARTs | `ttyS9` | 7 nodes | 7 nodes |
| PWM chips | 1 | 5 | 5 |
| IIO (ADC) | 1 device | none | none |

## Findings

1. **The RKNN path works on the RK1**: YOLOv5s runs at 38.6 fps on one NPU core and 59.1 fps on three (1.53x, well below linear scaling; not investigated).
2. The Jetsons expose identical interface sets in software (NX and Nano are the same SoC family). This says what the SoC drivers expose, **not** what is physically wired to a connector: nothing was attached, and the vendor documentation does not state which node reaches the 40-pin header. The header question is therefore still open and needs a test with a device or loopback.
3. The RK1 lacks SPI and CAN in software; the Jetsons have both.

## Limitations

No real image input or accuracy check; latency is for the model on random data; one model; the Jetsons were not run on this model (no matching ONNX), so this is not a cross-chip comparison; the interface survey does not test any pin.

## Reproduction

`data/raw/rknn-2026-09-24/yolo_rk1.py`; the survey commands are listings under `/dev` and `/sys`.
