# RK1 Mali-G610 (OpenCL yes, Vulkan no) and hardware video encode on all three chips

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Node 1 Turing RK1 (RK3588, 32 GB), node 2 Jetson Orin NX 16GB, node 3 Jetson Orin Nano 8GB
**Software stack:** RK1: Ubuntu 24.04.1, kernel 6.1.0-1025-rockchip, libmali-g610-x11 1.0.5-2 (g13p0), GStreamer with `gstreamer1.0-rockchip1` (MPP). Jetsons: JetPack 7.2, GStreamer nvv4l2 elements
**Date:** September 2026

## Question

What can the RK1's GPU do beyond the NPU, and which chips have working hardware video encoders?

## Setup and method

- GPU: `clinfo`, `vulkaninfo`, and `clpeak` (raw output in `data/raw/gpu-video-2026-09-24/rk1_clpeak.txt`); GPU governor was `performance` at 1000 MHz.
- Video: `gst-launch-1.0 videotestsrc num-buffers=600 pattern=ball` at 1920x1080 30 fps to each encoder into `fakesink sync=false`; frames per second = 600 / wall time, three runs each (includes pipeline start-up).
- The triage services stayed running on nodes 2 and 3; the RK1 had nothing else running.

## Results

### Mali-G610 (RK1)

| Item | Result |
|---|---|
| OpenCL | works: OpenCL 3.0, 4 compute units, 1000 MHz, 31 GiB shared memory |
| FP32 / FP16 compute | about 435 / 870 GFLOPS (clpeak) |
| INT (32-bit) | about 123 GIOPS |
| Global memory bandwidth (float4) | 19.5 GB/s |
| Vulkan | **fails**: no ICD installed; the installed Mali blob exports no `vkGetInstanceProcAddr`, so a hand-written ICD manifest was rejected by the loader. Mesa's panvk route would need the `panthor` kernel driver, not the `/dev/mali0` driver on this kernel (not tested) |

### Hardware video encode, 1080p, unthrottled (fps, 3 runs)

| Chip | Encoder | fps |
|---|---|---|
| RK1 | MPP H.264 | 59.7, 59.5, 59.7 |
| RK1 | MPP H.265 | 59.7, 59.7, 59.4 |
| RK1 | x264 CPU, veryfast, 8 cores | 39.2, 36.4, 36.5 |
| RK1 | source only (no encoder) | 61.6, 61.7, 61.7 |
| Orin NX | NVENC H.264 / H.265 / AV1 | 56.8, 53.4, 53.3 / 53.5, 54.9, 54.9 / 55.3, 56.2, 56.7 |
| Orin NX | x264 CPU | 20.1, 20.2, 20.2 |
| Orin Nano | NVENC | **absent**: no `v4l2-nvenc` device and no nvv4l2 encoder elements (decode only, `v4l2-nvdec` present) |
| Orin Nano | x264 CPU | 17.9, 17.8, 17.8 |

## Findings

1. **The Mali GPU is usable through OpenCL** (about 0.4 TFLOPS FP32, 0.9 TFLOPS FP16), but **not through Vulkan** on this image, which rules out Vulkan-backed llama.cpp on it. No LLM was run on OpenCL.
2. **The hardware encoders on the RK1 and the NX are faster than the test source can feed them.** The RK1's MPP encoders run at the source-only rate (about 60 fps), and the NX at about 55 fps with a slower source path (`nvvidconv` copy). These are therefore lower bounds; the encoders' real ceilings were not measured. Their claim here is only "at least 1080p at 55–60 fps, any of H.264/H.265 (and AV1 on the NX)".
3. **The Orin Nano has no hardware encoder**, matching the documentation; the CPU x264 path reaches about 18 fps at 1080p veryfast.
4. CPU x264 comparison: RK1 (8 cores) about 37 fps, NX about 20, Nano about 18, at identical settings.

## Limitations

Synthetic source; encoder ceiling not measured (source-bound); no quality or bitrate comparison; no decode tests; OpenCL only via `clpeak`, no application workload; the memory bandwidth figure is the GPU's view, not the SoC's total.

## Reproduction

Commands are in Setup; raw outputs under `data/raw/gpu-video-2026-09-24/`.
