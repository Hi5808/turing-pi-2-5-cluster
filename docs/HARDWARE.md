# Hardware

**Platform:** Turing Pi 2.5 cluster board, three populated slots.
**Date:** 2026-11-17.

## node1 — Turing RK1 (RK3588)

- 4x Cortex-A76 + 4x Cortex-A55, 31 GB RAM, Ubuntu 24.04.5, kernel 6.1.0-1025-rockchip (vendor)
- Mali-G610 MP4 GPU; 6 TOPS NPU — **kernel driver present, no userland yet** (unexplored)
- 8K H.264/H.265 encoder and decoder
- 29 GB eMMC root + 916 GB NVMe at `/mnt/nvme` (all bulk data lives here; the eMMC cannot hold it)
- Owns the WiFi uplink and is the only route off-cluster, so it must remain the control plane
- Backplane address 10.43.0.1; acts as gateway for the 10.43.0.0/24 cluster network

## node2 — Jetson Orin NX 16GB

- 8-core Cortex-A78AE, 16 GB, JetPack 7.2 / L4T R39.2 / CUDA 13.2, kernel 6.8.12-1021-tegra
- 1024 CUDA cores + 32 tensor cores, ~157 INT8 TOPS, 102 GB/s memory bandwidth
- **2x DLA** engines; 1x NVENC, 1x NVDEC
- 915 GB NVMe root; backplane 10.43.0.12
- PyTorch works: stock `torch 2.14.0+cu130` aarch64 wheel runs on sm_87 via sm_80 binaries

## node3 — Jetson Orin Nano 8GB

- 6-core Cortex-A78AE, 8 GB, same JetPack/L4T/CUDA/kernel as node2
- 1024 CUDA cores, ~67 INT8 TOPS
- **No DLA. No video encoder.** NVDEC only
- 915 GB NVMe root; backplane 10.43.0.13
- CUDA verified: device `Orin`, sm_8.7, 7547 MB visible

## Known hardware quirks

- **`nvidia-cdi-refresh.service` loses a boot race** on the Jetsons: `nvidia-ctk` can run before
  the nvgpu driver answers NVML, so no CDI spec is generated and container GPU passthrough
  silently breaks until a manual restart. Fixed with a drop-in that waits for `/dev/nvidia0`
  and `/dev/nvhost-gpu`, then retries on failure.
- Kernel packages are apt-held on both Jetsons; a JetPack point release will try to rewrite the
  QSPI bootloader, which is how both units previously needed recovery. Hold the NVIDIA stack
  unless a bootloader flash is actually intended.
- node3's LAN address is currently unreachable; the backplane and Tailscale paths work.
- The Orin Nano has no RTC battery behaviour worth trusting: host SSH keys carry epoch-0 mtimes
  from a first boot before NTP.
