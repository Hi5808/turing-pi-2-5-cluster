# 000 — Interconnect baseline and k3s clean slate

**Platform:** Turing Pi 2.5; node1 Turing RK1 (RK3588, 31 GB), node2 Jetson Orin NX 16GB,
node3 Jetson Orin Nano 8GB.
**Software stack:** Ubuntu 24.04.5 LTS; node1 kernel 6.1.0-1025-rockchip; nodes 2–3 JetPack 7.2 /
L4T R39.2 / CUDA 13.2 / kernel 6.8.12-1021-tegra; k3s v1.36.4+k3s1.
**Date:** 2026-11-17.

## Abstract

Establishes the measured baseline for all later work on this chassis and rebuilds the cluster
from scratch to serve as a repeatable starting point. The central finding is that the
interconnect, not compute, is the binding constraint: node1 owns the only uplink and a single
1GbE port, capping hub-and-spoke throughput at ~119 MB/s while local NVMe delivers
1700–2000 MB/s. This forecloses several intuitive architectures and makes one — pipeline-parallel
LLM inference — unusually well suited, because it needs almost no bandwidth.

## 1. Maintenance performed

All three nodes were brought current: ~152 Ubuntu packages on node1, ~320 on node2, ~384 on
node3, plus Tailscale 1.102.4 -> 1.104.7. The entire NVIDIA/CUDA/L4T/PVA stack (126 packages)
was held on both Jetsons, deliberately declining the JetPack 7.2 -> 7.2.1 point release because
it rewrites the QSPI bootloader. Kernel packages were already held. All three rebooted cleanly.

### Finding: upgrading Tailscale over Tailscale SSH severs the session

The `tailscale` package upgrade restarts `tailscaled`, which kills any SSH session established
through Tailscale SSH. `apt` survived as an orphaned process and completed, but the controlling
shell was gone and the package state was left mid-transaction (unpacked, not configured),
requiring `dpkg --configure -a`. Package work over a Tailscale SSH session must be detached
(`setsid nohup`) or run over a different path.

### Finding: Tailscale SSH host keys are not the host's sshd keys

A host key mismatch on node2 initially looked like a reflashed or compromised machine. It was
neither. Connections to the Tailscale address are served by `tailscaled`'s own SSH server, which
presents a key tied to the node's tailnet identity, not `/etc/ssh/ssh_host_*`. The node's sshd
keys were untouched originals (`nvfb-ssh-keygen.service` had been skipped; mtimes were epoch-0
from a pre-NTP first boot). The mismatch traced to a tailnet re-authentication two months
earlier, evidenced by a `tailscaled.state.<oldname>.bak` file.

## 2. Interconnect baseline

Full numbers and method in [../docs/MEASUREMENTS.md](../../docs/MEASUREMENTS.md). Summary:
951 Mb/s node->node1 on both Jetsons, 941 Mb/s node2<->node3 peer-to-peer, local NVMe
1700–2000 MB/s. The switch is non-blocking pairwise; node1's single port is the bottleneck.

**Consequence:** architectures are viable here only if the wire carries control messages rather
than payloads. Ruled out by measurement: tensor-parallel inference (two orders of magnitude
short on all-reduce bandwidth), distributed filesystems spanning nodes, live migration, and raw
video fan-out through node1. Encoded video is *not* ruled out — ~100 H.265 1080p streams fit per
link — but node3 has no encoder at all, so the limit is engine count, not bandwidth.

## 3. GPU boot race (fixed)

`nvidia-cdi-refresh.service` failed on node3 with
`failed to initialize NVML: Driver Not Loaded`. `nvidia-ctk` had run before the nvgpu driver was
ready, so no CDI spec was written. Host CUDA was unaffected, but container GPU passthrough would
fail until a manual restart — a silent failure mode, since the host looks healthy.

Fixed with a systemd drop-in on both Jetsons that waits for `/dev/nvidia0` and `/dev/nvhost-gpu`
before starting, then retries on failure. **Verified across a reboot:** node3 came back with
`/var/run/cdi/nvidia.yaml` present and no failed units.

## 4. Clean-slate rebuild

The cluster was torn down and rebuilt from a verified backup; procedure in
[../runbooks/k3s-clean-slate.md](../../runbooks/k3s-clean-slate.md). Restoration was from the
exported manifests, not the datastore — the datastore copy is a rollback artifact only, since
replaying it would carry over the state the rebuild exists to discard.

Result: three nodes `Ready`, fresh token and CA, placement labels restored, `nvidia` RuntimeClass
and CDI specs present on both Jetsons, DaemonSet running on all three nodes, and the nine
application deployments restored at zero replicas (an intentionally idle cluster). Full cycle
was roughly 12 minutes of wall clock.

### Finding: `imagePullPolicy: Never` images do not survive uninstall

`k3s-uninstall.sh` wipes containerd's image store. Every workload here uses a locally built
image with `imagePullPolicy: Never`, so all pods came back `ErrImageNeverPull`. The backup had
captured manifests, datastore, certs and application data but **not** container images.

Recovery was possible because the image tarball happened to live in the shared data directory
and was re-importable with `k3s ctr images import` on each node. Two lessons: image export
belongs in any k3s backup, and moving the old data-dir aside instead of deleting it preserves
the previous containerd store as a second recovery path.

### Finding: verifying a sqlite backup read-write corrupts the backup

An integrity check that opened the datastore copy read-write checkpointed the WAL into the main
database file and deleted `state.db-wal`/`-shm`, changing the file's checksum. The verification
step itself invalidated what it was verifying. Datastore copies must be opened with
`file:...?immutable=1`. Checksums should also be generated with relative paths, or they cannot
be verified after the archive moves to another host.

## 5. Next

Direction selected for the rebuilt cluster: heterogeneous pipeline-parallel LLM inference across
three different accelerator architectures, chosen because it is the one promising design where
the 1GbE ceiling is genuinely irrelevant rather than worked around. Proposal in
[001-heterogeneous-llm-pipeline.md](001-heterogeneous-llm-pipeline.md).
