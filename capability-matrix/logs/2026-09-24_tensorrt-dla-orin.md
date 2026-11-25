# TensorRT on both Orins: GPU throughput, and DLA cores that exist but cannot be used on the Orin NX

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Node 2 Jetson Orin NX 16GB (device tree: "Orin NX Engineering Reference Developer Kit Super"), node 3 Jetson Orin Nano 8GB, both booted from the QSPI configuration written by the recovery procedure (Nano-Super devkit config, see the qspi-recovery log)
**Software stack:** JetPack 7.2 (R39 rev 2.0), CUDA 13.2, TensorRT 10.16.2, kernel 6.8.12-1021-tegra, MAXN_SUPER
**Date:** September 2026

## Question

Do TensorRT and the Orin NX's DLA cores work on this board, and how do the two Orins compare on the same ONNX model?

## Setup and method

`trtexec --onnx=resnet18.onnx` (same file on both nodes, SHA-256 prefix 3b4d048057854022; dynamic input overridden to 1x3x224x224 by trtexec), `--duration=15 --warmUp=2000`, one run per condition. INT8 was built **without calibration data**, so it measures speed only, not accuracy. Triage services stayed running on both nodes. Logs: `data/raw/trt-2026-09-24/`.

## Results

| Node | Precision / engine | Throughput (qps) | GPU compute mean (ms) |
|---|---|---|---|
| Orin NX | FP16, GPU | 1169.6 | 0.853 |
| Orin NX | INT8 (uncalibrated), GPU | 1527.4 | 0.653 |
| Orin Nano | FP16, GPU | 1102.8 | 0.904 |
| Orin Nano | INT8 (uncalibrated), GPU | 1714.1 | 0.581 |
| Orin NX | DLA core 0, FP16, GPU fallback allowed | **fails**: `Cannot create DLA engine, 0 not available` | |
| Orin NX | DLA core 1, same | **fails**: `... 1 not available` | |
| Orin Nano | DLA core 0 | fails, same message (expected: the Nano has no DLA) | |

### DLA state on the NX (why "fails" is not "absent")

- Device tree: `nvdla0@15880000` and `nvdla1@158c0000` both `status = okay`; the kernel driver probed both (`nvdla 15880000.nvdla0 … syncpt_unit_base …`), no firmware or probe errors in `dmesg`.
- `/dev/nvhost-ctrl-nvdla0/1` exist (root:video, 0660); the user is in `video`; **running as root gave the same error**, so permissions are ruled out.
- `nvdla.bin` firmware and `libnvdla_runtime.so`, `libnvmedia_dla.so`, `libcudla-13-2` are installed.
- An earlier inventory note said "no /dev/nvhost-nvdla* seen"; the correct device names are `nvhost-ctrl-nvdla*`, so that note is corrected here.

## Findings

1. TensorRT works on both Orins with the same file. At batch 1 the NX is only 6% faster than the Nano at FP16 (1170 vs 1103 qps), consistent with a small model that is limited by launch or memory rather than compute. In INT8 the **Nano was faster** (1714 vs 1527 qps); this is one run each and unexplained (uncalibrated INT8 layer choices and the running services were not controlled).
2. **The NX's two DLA cores cannot be used from TensorRT** despite enabled device-tree nodes, a probed driver and present firmware and runtime libraries. The cause was not found. Untested candidates: the module is running the Nano-Super QSPI configuration from the recovery, whose firmware-side (BPMP/MB2) settings may leave DLA unavailable; a JetPack 7.2 issue; a missing user-space component. A stock-configuration NX would be needed to separate these.

## Limitations

One run per condition; INT8 not calibrated; one model; no power measured; one unit of each module; the DLA failure was not compared to a factory-configured NX, so it could be caused by the recovery configuration.

## Reproduction

Commands are in the Setup section; raw `trtexec` logs are under `data/raw/trt-2026-09-24/`.
