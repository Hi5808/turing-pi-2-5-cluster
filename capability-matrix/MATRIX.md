# Capability matrix

> Generated from [`data/capabilities.csv`](data/capabilities.csv) by `scripts/render_matrix.py`. Do not edit by hand.

**Legend.** ✅ works · 🟡 partial · ❌ fails · 🔌 needs hardware/ports not present · ⬜ untested. **Evidence:** MEASURED (this unit, with a log) · INVENTORY (seen on the system, not exercised) · DOCUMENTED (vendor docs, not verified here) · PLANNED · UNKNOWN.

## Progress

| Status | Rows | Share |
|---|---:|---:|
| ✅ WORKS | 52 | 55% |
| 🟡 PARTIAL | 11 | 12% |
| ❌ FAILS | 18 | 19% |
| 🔌 NEEDS-HW | 5 | 5% |
| ⬜ UNTESTED | 9 | 9% |
| **Total** | **95** | |

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
| A26 | Concurrency beats width at equal resources | rk3588 | 1 | ✅ WORKS | MEASURED | node1 CPU at a constant HOMOGENEOUS budget of 3x A76 (cpu4,5,6): 43.122 tok/s for 1 stream x 3 threads vs 48.538 for 3 streams x 1 thread = 1.126x, both sd <1%, 5 reps. Width 1->3 cores scales 2.518x of 3x (84%). |  |
| A27 | Two DLA engines scale with each other | orin-nx-16g | 2 | 🟡 PARTIAL | MEASURED | ResNet-18 b1 fp16: 126.70 -> 202.89 qps on 1 -> 2 engines (1.601x). INT8: 244.57 -> 252.88 (1.034x). conv_pure (strict DLA, 0 GPU layers): 627.73 -> 1133.80 qps (1.806x) |  |
| A28 | DLA INT8 faster than fp16 | orin-nx-16g | 2 | ✅ WORKS | MEASURED | ResNet-18 b1, 1 engine: 244.57 qps / 4.09 ms INT8 vs 126.70 qps / 7.89 ms fp16 = 1.93x; power 13.40 W vs 15.05 W |  |
| A29 | DLA adds capacity alongside a busy GPU | orin-nx-16g | 2 | ❌ FAILS | MEASURED | llama-server Qwen3-14B Q4_K_M 4 streams: 17.07 tok/s alone -> 9.39 tok/s (-45%) with both DLA engines, while DLA falls 202.89 -> 79.64 qps (-61%). Fractions sum to 0.943 (fp16) and 0.738 (INT8) |  |
| A30 | DLA beats the GPU on energy per inference | orin-nx-16g | 2 | ❌ FAILS | MEASURED | ResNet-18 b1: GPU 1360.3 qps at 22.47 W = 60.5 inf/J; best DLA (INT8, 1 engine) 244.57 qps at 13.40 W = 18.25 inf/J. GPU 5.4x throughput and 3.3x efficiency |  |
| A31 | DLA concurrency limited by DRAM bandwidth | orin-nx-16g | 2 | ❌ FAILS | MEASURED | Fastest 2-engine arm (conv_pure, 1133.80 qps) uses 4.76 GB/s of 102.4 GB/s peak = 4.6%, counting weights plus all 9 activations |  |
| A32 | One GPU-fallback op is cheap | orin-nx-16g | 2 | ❌ FAILS | MEASURED | Two identical 8x(Conv+ReLU) models differing by ONE elementwise add: 627.73 -> 535.52 qps single engine (-14.7%), +0.274 ms latency, and 2-engine scaling 1.806x -> 1.628x |  |
| A33 | DLA 2-engine scaling predicted by engine fragmentation | orin-nx-16g | 2 | ✅ WORKS | MEASURED | Monotonic across a 4.5x throughput range: 1 DLA node / 0 GPU ops = 1.806x; 1 node / 1 GPU op = 1.628x; ResNet-18 fp16 9 nodes = 1.601x; ResNet-18 INT8 16 nodes = 1.034x |  |
| A34 | DLA 2nd-engine cost is a fixed per-submit serialization | orin-nx-16g | 2 | ✅ WORKS | MEASURED | Scaling rises with work per submit: 1.391x / 1.822x / 1.917x at 2 / 8 / 32 convs (single-engine latency 0.44 / 1.59 / 6.12 ms). Activating engine 2 adds a flat 0.21 +- 0.05 ms per inference across a 13.8x latency range |  |
| A35 | Serve concurrent users at readable latency | any |  | 🟡 PARTIAL | MEASURED | Knee = 4 concurrent streams (p95 ITL<=200ms and every stream >=5 tok/s). 16 slots exist but 8 streams already breaks SLO (slowest 4.06 tok/s, ITL p95 231ms). Peak 61.29 tok/s at 32 streams needs 41.5s TTFT |  |
| A36 | Aggregate tok/s detects serving failure | any |  | ❌ FAILS | MEASURED | Past the 16-slot limit ITL p95 stays FLAT (417/419/418 ms) while TTFT p95 goes 980ms -> 41.3s -> 41.5s and the slowest stream falls to 0.19 tok/s, all while aggregate reads a healthy 61 tok/s |  |
| A37 | Efficiency optimum is a shippable operating point | any |  | ❌ FAILS | MEASURED | tok/J peaks at 1.536 (32 streams) where TTFT p95 is 41.5s; the SLO-respecting knee runs at 0.936 tok/J. Serving users costs 1.64x the energy per token of benchmarking |  |
| A38 | Round-robin is fair across heterogeneous nodes | any |  | ❌ FAILS | MEASURED | Nano/4B plateaus 43.4 tok/s vs NX/14B 17.9 tok/s, so the same service hands one user 7.1 tok/s and the next 17.0. The smaller module carries 2.42x the throughput |  |
| A46 | Per-submit serial cost isolated on a second engine (CPU) | rk3588 | 1 | ✅ WORKS | MEASURED | Fit t(n)=S+W/n on a WIDTH sweep only (17.100/31.398/43.050 tok/s at 1/2/3 A76 cores): S=5.485 ms/token serial, W=52.965, R2=1.0000, serial share 23.7%. Predicts the unseen CONCURRENCY curve to +0.2% (k=1) and +5.7% (k=3). |  |
| A47 | Per-submit serial cost present on the RK3588 NPU (3rd engine) | rk3588 | 1 | ✅ WORKS | MEASURED | Width sweep by core mask, 1 context on n cores: 35.59/44.12/63.90 fps at n=1/2/3 (5 reps). Fit t(n)=S+W/n gives S=11.827 ms serial, W=16.874 ms, R2=0.8796, serial share 67.8% at 3 cores. Predicts the unseen 3-context concurrency arm at 104.53 vs 96.11 measured (+8.8%). |  |
| A48 | big.LITTLE: one A55 core in a thread set costs ~26-32% of decode | rk3588 | 1 | ❌ FAILS | MEASURED | Qwen3-0.6B Q4_K_M CPU-only, 3 reps, taskset per cluster: 4xA76 46.81 tok/s; +1xA55 31.83 (-32.0%); +2xA55 34.89 (-25.5%); +4xA55 34.41 (-26.5%). 4xA55 alone 12.39. A76/A55 ratio at equal core count 3.78x. Width on A76: 17.13/31.33/41.60/46.81 at n=1..4. |  |
| A49 | Orin Nano: GPU vs CPU decode, 4.29x throughput at lower power | orin-nano-8g | 3 | ✅ WORKS | MEASURED | Same binary (074f1f3), same model, same flags, -c 2048 --parallel 4. k=1: CPU 9.34 tok/s @13.33 W (0.701 tok/J) vs GPU 20.38 @12.57 W (1.621). k=4: CPU 21.47 @12.72 W (1.688) vs GPU 92.12 @12.55 W (7.340). Idle 6.731 W. GPU is 4.29x throughput and 4.35x tok/J at 4 streams, at LOWER package power. |  |
| A50 | Cold start is 95% one opaque load block, and not disk-bound | orin-nx-16g | 2 | ✅ WORKS | MEASURED | Qwen3-14B-Q4_K_M (8.4 GB), 2 reps, phases from llama-server's own timestamps: GPU cold 0.006/7.609/0.411/0.018 = 8.044 s total (open/load/ctxinit/slots); GPU warm 8.350 s; CPU cold 25.428 s; CPU warm 27.150 s. |  |

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
| A39 | Internal switch reaches 1GbE line rate | any |  | ✅ WORKS | MEASURED | iperf3: node1->node2 937, node1->node3 936, node2->node3 941 Mbit/s receiver; full duplex node2<->node3 789+804=1593 Mbit/s aggregate; RTT 0.391-0.439 ms avg |  |
| A40 | Shared NFS store is a performance win | any |  | ❌ FAILS | MEASURED | 90.7 MB/s read over the carrier switch (dd 2GiB O_DIRECT) vs 2.0 GB/s on node2's own NVMe and 1.9 GB/s on node3's = 22x penalty. NFS also costs ~22% of the wire (726 of 937 Mbit/s) |  |
| A41 | Carrier provides a performance capability the modules lack | any |  | ❌ FAILS | MEASURED | Neither of the two testable carrier features qualifies: switch = commodity 1GbE line rate, shared store = 22x slower than disks already present on every node |  |
| A42 | Staging models on local NVMe cuts model load time | any |  | ✅ WORKS | MEASURED | Cold start to HTTP 200 on /health, caches dropped before each arm: Qwen3-14B (8.38 GiB) 81.50 s from NFS vs 9.81 s from local NVMe = 8.31x, saving 71.7 s per cold start |  |
| A43 | LLM service survives a reboot unattended | orin-nano-8g | 3 | ✅ WORKS | MEASURED | node3 rebooted twice. Unit returns enabled+active, NRestarts=0, health 200, still serving the LOCAL staged model, k3s Ready, generation verified. Pre-Linux cost 199 s -> 123 s after TimeoutStopSec=15; time to service ready 214 s -> 141 s |  |
| A44 | llama-server stops cleanly on SIGTERM | any |  | ❌ FAILS | MEASURED | ISOLATED and STILL PRESENT ON CURRENT MASTER. Necessary condition: an in-flight SSE stream idle in rd.next() when SIGTERM lands (~25%: 5/20 arms on b10533, 2/6 on a 074f1f3 build of 2026-11-26). Duration governed by sse_ping_interval, proved by intervention: default 30 -> 30.43/30.32/30.32/30.29/30.27 s and 31.46/31.48 s on master; --sse-ping-interval 5 -> 6.34/6.35/5.38 s. Never an intermediate value. Inside a caught stall all 9 surviving threads sit in futex_wait_queue, the listener thread is gone, the client socket stays ESTAB, and the log gap between 'cleaning up before exit' and 'cancel task' is exactly 30.0034 s, then exit in 164 ms. |  |
| A45 | Reboot cost is dominated by the OS | orin-nano-8g | 3 | ❌ FAILS | MEASURED | Attributed from the persistent journal: OS shutdown 16 s, Tegra firmware/bootloader 107 s, Linux boot 33.0 s. Firmware alone is 66% of the 161 s between reboot command and a booted kernel+userspace |  |
| A51 | Sustained single-module load does NOT throttle: 86 C plateau, clocks at max | orin-nx-16g | 2 | ✅ WORKS | MEASURED | 2 concurrent streams, 600 s: tj plateaus 84-86 C, GPU held 1173 MHz (min=max, never clamped), CPU 1984 MHz, 27.04-27.12 W, fan 2/3 (not maxed), ALL eight *-throttle-alert cooling devices 0 throughout. Settled to tj 73 C / 8.13 W / gpu_load 0. |  |

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
