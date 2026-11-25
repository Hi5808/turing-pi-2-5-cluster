# Capability matrix

> Generated from [`data/capabilities.csv`](data/capabilities.csv) by `scripts/render_matrix.py`. Do not edit by hand.

**Legend.** ✅ works · 🟡 partial · ❌ fails · 🔌 needs hardware/ports not present · ⬜ untested. **Evidence:** MEASURED (this unit, with a log) · INVENTORY (seen on the system, not exercised) · DOCUMENTED (vendor docs, not verified here) · PLANNED · UNKNOWN.

## Progress

| Status | Rows | Share |
|---|---:|---:|
| ✅ WORKS | 42 | 57% |
| 🟡 PARTIAL | 10 | 14% |
| ❌ FAILS | 8 | 11% |
| 🔌 NEEDS-HW | 5 | 7% |
| ⬜ UNTESTED | 9 | 12% |
| **Total** | **74** | |

## A compute

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| A01 | GPU initialises on cold boot | orin-nx-16g | 2 | 🟡 PARTIAL | MEASURED | 2 failures in 18 automated cold boots; 0 in 5 warm reboots | [2026-09-24_gpu-init-cold-boot-failure](logs/2026-09-24_gpu-init-cold-boot-failure.md) |
| A02 | GPU initialises on cold boot | orin-nano-8g | 3 | 🟡 PARTIAL | MEASURED | 1 failure in 18 automated cold boots (+1 earlier unlogged); 0 in 5 warm reboots | [2026-09-24_gpu-init-cold-boot-failure](logs/2026-09-24_gpu-init-cold-boot-failure.md) |
| A03 | CUDA 13.2 / TensorRT 10.16 / VPI 4.1 installed (JetPack 7.2) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | trtexec ResNet18 FP16 1170 qps, INT8 (uncalibrated) 1527 qps | [2026-09-24_tensorrt-dla-orin](logs/2026-09-24_tensorrt-dla-orin.md) |
| A04 | CUDA 13.2 / TensorRT 10.16 / VPI 4.1 installed (JetPack 7.2) | orin-nano-8g | 3 | ✅ WORKS | MEASURED | trtexec ResNet18 FP16 1103 qps, INT8 (uncalibrated) 1714 qps | [2026-09-24_tensorrt-dla-orin](logs/2026-09-24_tensorrt-dla-orin.md) |
| A05 | NPU (RKLLM) works: runtime + driver v0.9.7 | rk3588 | 1 | ✅ WORKS | MEASURED | TinyLlama 1.1B W8A8: 11.2 tok/s decode, ~230 tok/s prefill | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A06 | LLM inference (CUDA) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | Qwen3-1.7B Q4_K_M: 1748 t/s prefill, 43.8 t/s decode (llama.cpp CUDA) | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A07 | LLM inference (CUDA) | orin-nano-8g | 3 | ✅ WORKS | MEASURED | Qwen3-1.7B Q4_K_M: 1559 t/s prefill, 39.4 t/s decode (llama.cpp CUDA) | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A08 | LLM inference (NPU via RKLLM) | rk3588 | 1 | ✅ WORKS | MEASURED | 11.2 tok/s decode, 6 trials; sweep 10.5-11.6 tok/s over 300-1000 MHz | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A09 | LLM inference (CPU only) | rk3588 | 1 | ✅ WORKS | MEASURED | Qwen3-1.7B Q4_K_M: 19.7 t/s decode on 4 big cores (15.5 on 8 threads); TinyLlama Q8_0: 22.2 t/s | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A10 | GPU compute (Mali-G610): OpenCL works, Vulkan fails | rk3588 | 1 | 🟡 PARTIAL | MEASURED | OpenCL 3.0: 435 GFLOPS FP32, 870 FP16, 19.5 GB/s; Vulkan: no usable ICD | [2026-09-24_mali-opencl-and-video-encode](logs/2026-09-24_mali-opencl-and-video-encode.md) |
| A11 | Vision inference (TensorRT) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | ResNet18 FP16 1170 qps (batch 1) | [2026-09-24_tensorrt-dla-orin](logs/2026-09-24_tensorrt-dla-orin.md) |
| A12 | Vision inference (TensorRT) | orin-nano-8g | 3 | ✅ WORKS | MEASURED | ResNet18 FP16 1103 qps (batch 1) | [2026-09-24_tensorrt-dla-orin](logs/2026-09-24_tensorrt-dla-orin.md) |
| A13 | Vision inference (RKNN) | rk3588 | 1 | ✅ WORKS | MEASURED | YOLOv5s 640: 25.9 ms (38.6 fps) 1 core; 16.9 ms (59.1 fps) 3 cores | [2026-09-24_rknn-vision-and-io-survey](logs/2026-09-24_rknn-vision-and-io-survey.md) |
| A14 | DLA offload | orin-nx-16g | 2 | ❌ FAILS | MEASURED | TensorRT: Cannot create DLA engine, 0/1 not available (also as root) | [2026-09-24_tensorrt-dla-orin](logs/2026-09-24_tensorrt-dla-orin.md) |
| A15 | DLA offload | orin-nano-8g | 3 | ❌ FAILS | MEASURED | TensorRT: DLA core 0 not available (expected) | [2026-09-24_tensorrt-dla-orin](logs/2026-09-24_tensorrt-dla-orin.md) |
| A16 | Energy per token (power rails) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | 0.514 J/token total (22.4 W busy, 43.6 t/s), 0.372 net of idle; Qwen3-1.7B Q4_K_M | [2026-09-24_jetson-energy-per-token](logs/2026-09-24_jetson-energy-per-token.md) |
| A17 | Energy per token (power rails) | orin-nano-8g | 3 | ✅ WORKS | MEASURED | 0.512 J/token total (20.2 W busy, 39.5 t/s), 0.331 net of idle; Qwen3-1.7B Q4_K_M | [2026-09-24_jetson-energy-per-token](logs/2026-09-24_jetson-energy-per-token.md) |
| A18 | Energy per token (external meter) | rk3588 | 1 | 🔌 NEEDS-HW | MEASURED | BMC exposes NO power sensing: i2c bus holds only a 24c02 EEPROM, a pcf8563 RTC and the rtl8365mb switch; no hwmon/iio/ADC; API type=power returns on/off state only | [2026-11-24_bmc-power-telemetry](logs/2026-11-24_bmc-power-telemetry.md) |
| A19 | NPU decode vs NPU clock (300-1000 MHz sweep) | rk3588 | 1 | ✅ WORKS | MEASURED | 10.45 t/s at 300 MHz; 11.3-11.6 t/s from 400 to 1000 MHz | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A20 | DRAM controller clock effect on NPU decode | rk3588 | 1 | ✅ WORKS | MEASURED | 1068 -> 2112 MHz: 11.2 -> 11.4 t/s (within noise) | [2026-09-24_llm-decode-cross-chip-and-rk1-npu](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md) |
| A21 | CPU throughput (sysbench, 1 thread / all threads) | rk3588 | 1 | ✅ WORKS | MEASURED | 938 / 5113 events/s | [2026-09-24_cpu-and-memory-cross-chip](logs/2026-09-24_cpu-and-memory-cross-chip.md) |
| A22 | CPU throughput (sysbench, 1 thread / all threads) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | 871 / 6931 events/s | [2026-09-24_cpu-and-memory-cross-chip](logs/2026-09-24_cpu-and-memory-cross-chip.md) |
| A23 | CPU throughput (sysbench, 1 thread / all threads) | orin-nano-8g | 3 | ✅ WORKS | MEASURED | 759 / 4472 events/s | [2026-09-24_cpu-and-memory-cross-chip](logs/2026-09-24_cpu-and-memory-cross-chip.md) |
| A24 | CPU memory read bandwidth, all threads (sysbench) | mixed |  | ✅ WORKS | MEASURED | NX 96.8, Nano 70.2, RK1 56.7 GB/s (GiB-based MiB/s) | [2026-09-24_cpu-and-memory-cross-chip](logs/2026-09-24_cpu-and-memory-cross-chip.md) |
| A25 | Concurrent inference contexts (2+) | rk3588 | 1 | ❌ FAILS | MEASURED | Mali G610: 1 Vulkan context works (decode 9.08 tok/s, Qwen3-0.6B Q4_K_M); a 2nd concurrent context aborts ALL processes with vk::DeviceLostError (waitForFences ErrorDeviceLost) in libggml-vulkan. Not the ~1.2GiB ceiling: 2x378MiB |  |
| A26 | Concurrency beats width at equal resources | rk3588 | 1 | ✅ WORKS | MEASURED | node1 CPU, total thread budget fixed at 8: aggregate decode 35.07 / 53.24 / 57.62 tok/s at 1 / 2 / 3 processes (-t 8/4/2). 3 narrow inferences beat 1 wide one by 1.64x; prefill 94.01 -> 152.35 (1.62x) |  |
| A27 | Two DLA engines scale with each other | orin-nx-16g | 2 | 🟡 PARTIAL | MEASURED | ResNet-18 b1 fp16: 126.70 -> 202.89 qps aggregate on 1 -> 2 engines (1.601x). INT8: 244.57 -> 252.88 qps (1.034x). Shared ceiling ~253 qps |  |
| A28 | DLA INT8 faster than fp16 | orin-nx-16g | 2 | ✅ WORKS | MEASURED | ResNet-18 b1, 1 engine: 244.57 qps / 4.09 ms INT8 vs 126.70 qps / 7.89 ms fp16 = 1.93x; power 13.40 W vs 15.05 W |  |
| A29 | DLA adds capacity alongside a busy GPU | orin-nx-16g | 2 | ❌ FAILS | MEASURED | llama-server Qwen3-14B Q4_K_M 4 streams: 17.07 tok/s alone -> 9.39 tok/s (-45%) with both DLA engines, while DLA falls 202.89 -> 79.64 qps (-61%). Fractions sum to 0.943 (fp16) and 0.738 (INT8) |  |
| A30 | DLA beats the GPU on energy per inference | orin-nx-16g | 2 | ❌ FAILS | MEASURED | ResNet-18 b1: GPU 1360.3 qps at 22.47 W = 60.5 inf/J; best DLA (INT8, 1 engine) 244.57 qps at 13.40 W = 18.25 inf/J. GPU 5.4x throughput and 3.3x efficiency |  |

## B cluster

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| B01 | Shared WiFi gateway (DHCP+DNS+NAT) hosted on one node | rk3588 | 1 | ✅ WORKS | MEASURED | nodes 2,3 + BMC route through node 1's WiFi; survives node-1 reboot and full-board cold start | [2026-09-24_wifi-gateway-network](logs/2026-09-24_wifi-gateway-network.md) |
| B02 | Model endpoint routing across nodes | mixed |  | ⬜ UNTESTED | PLANNED |  |  |
| B03 | Model split across nodes (llama.cpp RPC) over 1 GbE | mixed |  | ⬜ UNTESTED | PLANNED |  |  |
| B04 | Kubernetes (k3s) with GPU and NPU device plugins | mixed |  | ⬜ UNTESTED | PLANNED |  |  |
| B05 | Inter-node TCP throughput and latency (1 GbE fabric) | mixed |  | ✅ WORKS | MEASURED | 941 Mbit/s on every pair, 0 retransmits; RTT 0.14 ms (2<->3), 0.26 ms via node 1 | [2026-09-24_cluster-network-1gbe](logs/2026-09-24_cluster-network-1gbe.md) |

## C infra

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| C01 | BMC remote control via tpi (power/USB/UART/flash) | bmc |  | ✅ WORKS | MEASURED | tpi 1.0.7 against BMC firmware 2.3.2 | [2026-09-23_qspi-recovery-foreign-carrier](logs/2026-09-23_qspi-recovery-foreign-carrier.md) |
| C02 | BMC reboot restores node power state | bmc |  | ✅ WORKS | MEASURED | BMC back in ~55 s; note: reboot cuts power to all nodes | [2026-09-24_full-board-reboot-integrity](logs/2026-09-24_full-board-reboot-integrity.md) |
| C03 | Local storage node (1 TB NVMe) with checksum-verified I/O | rk3588 | 1 | ✅ WORKS | MEASURED | fio 3 reps: seq write 1765 MB/s, rand write QD1 41k IOPS, rand read QD32 140k IOPS (supersedes dd 1.2/1.8 GB/s) | [2026-09-24_nvme-fio-all-nodes](logs/2026-09-24_nvme-fio-all-nodes.md) |
| C04 | NFS model store shared to the other nodes | rk3588 | 1 | ✅ WORKS | MEASURED | 117 MB/s write, 110 MB/s read (wire-limited); 1 GiB checksum matched | [2026-09-24_nfs-share-from-node1](logs/2026-09-24_nfs-share-from-node1.md) |
| C05 | Monitoring (Prometheus/Grafana) | mixed |  | ⬜ UNTESTED | PLANNED |  |  |
| C06 | ARM64 CI/build runner | rk3588 | 1 | ⬜ UNTESTED | PLANNED |  |  |
| C07 | Remote access as subnet router (Tailscale) | rk3588 | 1 | ⬜ UNTESTED | PLANNED |  |  |

## D media/sensing

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| D01 | HDMI output | rk3588 | 1 | ✅ WORKS | MEASURED | RK1 desktop captured over HDMI (factory image) |  |
| D02 | USB 2.0 host (Wi-Fi dongle RTL8822BU) | rk3588 | 1 | 🟡 PARTIAL | MEASURED | in-kernel rtw88: FAILS (register timeouts -110); vendor 88x2bu: WORKS (5 GHz, 867 Mbit/s link) | [2026-09-24_mini-pcie-wifi-investigation](logs/2026-09-24_mini-pcie-wifi-investigation.md) |
| D03 | USB 3.0 host | any | 4 | 🔌 NEEDS-HW | DOCUMENTED |  |  |
| D04 | Camera (CSI/DSI) | any | 1 | 🔌 NEEDS-HW | DOCUMENTED |  |  |
| D05 | CAN bus | orin-nx-16g | 2 | 🔌 NEEDS-HW | INVENTORY | can0 interface present |  |
| D06 | GPIO / I2C / SPI header | any |  | 🟡 PARTIAL | MEASURED | software interfaces enumerated on all nodes (GPIO/I2C/SPI/CAN/UART/PWM); physical 40-pin header not tested | [2026-09-24_rknn-vision-and-io-survey](logs/2026-09-24_rknn-vision-and-io-survey.md) |
| D07 | Hardware video encode | orin-nx-16g | 2 | ✅ WORKS | MEASURED | NVENC H.264/H.265/AV1 1080p >=55 fps (source-bound) | [2026-09-24_mali-opencl-and-video-encode](logs/2026-09-24_mali-opencl-and-video-encode.md) |
| D08 | Hardware video encode | rk3588 | 1 | ✅ WORKS | MEASURED | MPP H.264/H.265 1080p >=59.5 fps (source-bound) | [2026-09-24_mali-opencl-and-video-encode](logs/2026-09-24_mali-opencl-and-video-encode.md) |
| D09 | Hardware video encode | orin-nano-8g | 3 | ❌ FAILS | MEASURED | no v4l2-nvenc device, no nvv4l2 encoder elements; x264 CPU ~18 fps 1080p | [2026-09-24_mali-opencl-and-video-encode](logs/2026-09-24_mali-opencl-and-video-encode.md) |
| D10 | CPU x264 1080p veryfast (cross-chip) | rk3588 | 1 | ✅ WORKS | MEASURED | RK1 ~37 fps, NX ~20 fps, Nano ~18 fps | [2026-09-24_mali-opencl-and-video-encode](logs/2026-09-24_mali-opencl-and-video-encode.md) |

## E storage/PCIe

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| E01 | M.2 NVMe (PCIe Gen3 x4) | rk3588 | 1 | ✅ WORKS | MEASURED | fio: seq write 1765 MB/s; seq read 2432 first rep then ~715; rand read 4k QD1 14.1k IOPS; 3 reps | [2026-09-24_nvme-fio-all-nodes](logs/2026-09-24_nvme-fio-all-nodes.md) |
| E02 | M.2 NVMe (PCIe Gen3 x4) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | fio: seq write 994 MB/s (435 in rep 3); seq read 2440 then ~727; rand read QD32 158k IOPS; 3 reps | [2026-09-24_nvme-fio-all-nodes](logs/2026-09-24_nvme-fio-all-nodes.md) |
| E03 | M.2 NVMe | orin-nano-8g | 3 | ✅ WORKS | MEASURED | fio: seq write 995 MB/s (429 in rep 3); seq read 2358 then ~728; rand read QD32 124k IOPS; 3 reps | [2026-09-24_nvme-fio-all-nodes](logs/2026-09-24_nvme-fio-all-nodes.md) |
| E04 | SATA controller | orin-nano-8g | 3 | 🟡 PARTIAL | MEASURED | ASM1061 enumerated; no drive attached |  |
| E05 | mini-PCIe: PCIe function (AR9462 Wi-Fi) | rk3588 | 1 | ❌ FAILS | MEASURED | all three RK3588 x1 controllers tested: link never trains; forced Gen1 also fails | [2026-09-24_mini-pcie-wifi-investigation](logs/2026-09-24_mini-pcie-wifi-investigation.md) |
| E06 | mini-PCIe: PCIe function (AR9462 Wi-Fi) | orin-nx-16g | 2 | ❌ FAILS | MEASURED | both empty x1 controllers report 'Phy link never came up' | [2026-09-24_mini-pcie-wifi-investigation](logs/2026-09-24_mini-pcie-wifi-investigation.md) |
| E07 | mini-PCIe: USB function (Bluetooth AR3012) | rk3588 | 1 | ✅ WORKS | MEASURED | 0cf3:311e enumerates | [2026-09-24_mini-pcie-wifi-investigation](logs/2026-09-24_mini-pcie-wifi-investigation.md) |
| E08 | mini-PCIe: USB function (Bluetooth AR3012) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | 0cf3:311e enumerates | [2026-09-24_mini-pcie-wifi-investigation](logs/2026-09-24_mini-pcie-wifi-investigation.md) |
| E09 | mini-PCIe: other PCIe card | any | 1 | ⬜ UNTESTED | PLANNED |  |  |
| E10 | M.2 accelerator card (e.g. Hailo) | any |  | 🔌 NEEDS-HW | PLANNED |  |  |

## F low-level

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| F01 | Boot foreign-carrier modules on this board (QSPI-only reflash) | orin-nx-16g | 2 | ✅ WORKS | MEASURED | boots existing NVMe OS after fix; NVMe untouched | [2026-09-23_qspi-recovery-foreign-carrier](logs/2026-09-23_qspi-recovery-foreign-carrier.md) |
| F02 | Boot foreign-carrier modules on this board (QSPI-only reflash) | orin-nano-8g | 3 | ✅ WORKS | MEASURED | same; restore round-trip verified | [2026-09-23_qspi-recovery-foreign-carrier](logs/2026-09-23_qspi-recovery-foreign-carrier.md) |
| F03 | Restore original QSPI from backup | orin-nano-8g | 3 | ✅ WORKS | MEASURED | 10 partitions restored and verified by read-back | [2026-09-23_qspi-recovery-foreign-carrier](logs/2026-09-23_qspi-recovery-foreign-carrier.md) |
| F04 | Device-tree overlay on RK1 (u-boot fdtoverlays) | rk3588 | 1 | ✅ WORKS | MEASURED | overlay applied and reverted cleanly | [2026-09-24_mini-pcie-wifi-investigation](logs/2026-09-24_mini-pcie-wifi-investigation.md) |
| F05 | NVMe unsafe-shutdown counter behaviour | orin-nx-16g | 2 | 🟡 PARTIAL | MEASURED | +1 unsafe shutdown and +2 power cycles per cold boot; 0 per warm reboot; independent of shutdown wait (~15-20 s vs 90 s) | [2026-09-24_full-board-reboot-integrity](logs/2026-09-24_full-board-reboot-integrity.md) |
| F06 | Custom kernel / DVFS / thermal soak | any |  | 🟡 PARTIAL | MEASURED | 5 min all-core CPU soak: no throttling (RK1 2256 MHz, 62 C; NX 1984 MHz, Tj 72 C; Nano 1728 MHz, Tj 66 C) | [2026-09-24_cpu-thermal-soak](logs/2026-09-24_cpu-thermal-soak.md) |
| F07 | Secure boot / fuses | any |  | ⬜ UNTESTED | PLANNED |  |  |
| F08 | BMC controls and sensors (inventory) | any |  | ✅ WORKS | MEASURED | power/usb/uart/cooling controls work; no node power telemetry; fan 6/6 | [2026-09-24_bmc-inventory](logs/2026-09-24_bmc-inventory.md) |

## G reliability

| ID | Feature | Chip | Slot | Status | Evidence | Result | Log |
|---|---|---|:-:|---|---|---|---|
| G01 | Full-board cold start integrity | any |  | ✅ WORKS | MEASURED | all filesystems clean; NVMe critical_warning 0, media_errors 0 | [2026-09-24_full-board-reboot-integrity](logs/2026-09-24_full-board-reboot-integrity.md) |
| G02 | GPU self-heal service | orin-nx-16g | 2 | ✅ WORKS | MEASURED | 1 real GPU failure recovered without intervention in ~165 s; forced test: 2 reboots then gives up | [2026-09-24_gpu-init-cold-boot-failure](logs/2026-09-24_gpu-init-cold-boot-failure.md) |
| G03 | Fault injection (power loss mid-write) | any |  | ⬜ UNTESTED | PLANNED |  |  |
| G04 | Hardware watchdog | any |  | 🟡 PARTIAL | INVENTORY | Jetsons: /dev/watchdog0 present, systemd RuntimeWatchdogUSec=2min; RK1: no /dev/watchdog* device |  |

## Slot coverage

Each chip can only reach the ports of the slot it sits in ([port map](docs/PORT-MAP.md)), so a feature is only fully explored once every chip has been tested in every slot that offers it. Cells show the session in which a chip was tested in a slot.

| Chip | Slot 1 | Slot 2 | Slot 3 | Slot 4 |
|---|:-:|:-:|:-:|:-:|
| Turing RK1 (RK3588) | S1 | · | · | · |
| Jetson Orin NX 16GB | · | S1 | · | · |
| Jetson Orin Nano 8GB | · | · | S1 | · |

**3 of 12** chip-in-slot combinations tested. Protocol for the rest: [rotation protocol](docs/PORT-MAP.md#rotation-protocol).
