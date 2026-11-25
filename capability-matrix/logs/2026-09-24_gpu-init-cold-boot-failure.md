# Intermittent GPU initialisation failure on Jetson Orin cold boots, and a self-healing mitigation

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Jetson Orin NX 16GB (slot 2) and Jetson Orin Nano 8GB (slot 3), each booting a JetPack 7.2 system from a 1 TB NVMe, both with the QSPI-only boot-firmware fix applied ([log](2026-09-23_qspi-recovery-foreign-carrier.md))
**Software stack:** Jetson Linux R39.2.0, Ubuntu 24.04.4, kernel 6.8.12-1021-tegra, open NVIDIA kernel module r595 plus `nvgpu`, `nvpmodel`, systemd 255
**Date:** September 2026

## Question

After a reboot, node 3's GPU was found not working (`nvidia-smi`: "No devices were found"), although it had worked earlier the same day. Is that a one-off, a property of one module, or a boot-mode-dependent failure?

## Failure signature

On a failing boot:

- `/dev/nvhost-gpu` is absent; `nvidia-smi` prints `libnvrm_gpu.so: NvRmGpuLibOpen failed, error=4` / "No devices were found".
- The kernel log shows `gk20a 17000000.gpu: loading …/ga10b/acr-gsp.data.encrypt.bin.prod failed with error -40` for **every** firmware search path, even though the file exists (`/lib/firmware/nvidia/ga10b/acr-gsp.data.encrypt.bin.prod`, 9472 bytes), followed by `ga10b_load_riscv_acr_ucodes … ucode get fail`, `ACR bootstrap failed`, `nvgpu_finalize_poweron … Failed initialization for: g->ops.acr.acr_construct_execute`, and `ga10b_acr_patch_wpr_info_to_ucode: invalid mem acr_falcon2_sysmem_desc`.
- The `nvpmodel` service fails or hangs waiting for the GPU's `devfreq_dev` files.

On good boots none of the `acr-gsp` errors appear. (Failed remote-procedure-call messages from the display engine, `NVRM_RPC_DCE … Failed RM ctrl call`, appear on **both** good and bad boots on both modules and are not diagnostic.)

## Method

An automated loop restarted **both Jetsons together**, then, 35 s after each answered SSH, recorded: `/dev/nvhost-gpu`, `nvidia-smi -L`, the count of `acr-gsp … failed` kernel-log lines, the `nvpmodel` unit state and the root-filesystem state.

- **Cold:** clean `poweroff`, 45 s wait, BMC `power off`, 6 s, BMC `power on`.
- **Warm:** `systemctl reboot`.

A boot is BAD if `/dev/nvhost-gpu` is missing or `nvidia-smi -L` does not list a GPU.

## Results

| Run | Boots per node | Node 2 (Orin NX) GPU failures | Node 3 (Orin Nano) GPU failures |
|---|---|---|---|
| 1 (script bug found, stopped) | 3 cold | 0 | 0 |
| 2 | 2 cold + 5 warm | 0 | 0 |
| 3 (after `nvpmodel` wait drop-in on node 3) | 5 cold | 1 | 1 |
| 4 (self-heal enabled on both) | 8 cold | 1 (self-recovered in ~165 s) | 0 |
| **Total** | **18 cold, 5 warm** | **2 of 18 cold; 0 of 5 warm** | **1 of 18 cold; 0 of 5 warm** |

One further failure on node 3 was observed at the first check after a full board power-off, before the loop existed (not counted above; counting it gives 2 of 19).

Separate `nvpmodel` behaviour on node 3, GPU otherwise up: the service failed on **3 of the first 5 cold boots** and 0 of 5 warm reboots (a race with the GPU's `devfreq` files). After the drop-in, the service no longer failed while the GPU was up; on the one later failing boot it waited as designed. Node 2's `nvpmodel` never failed in 10 boots of the first two runs.

## Findings

1. **The failure is not confined to one module.** Both the NX and the Nano fail, at roughly 1 in 10 cold boots (2/18 and 1/18–2/19; the samples are too small to distinguish the rates).
2. **It is boot-mode dependent in this data:** 0 of 10 warm reboots (5 per node) failed, against 3 of 36 logged cold boots (4 of 37 counting the one earlier event). The samples are small; this is a pattern, not an estimate.
3. **A warm reboot recovers it** every time it was needed.

## Mitigation and its verification

A oneshot service (`gpu-selfheal.service`) waits up to ~3 minutes for a working GPU after boot and, if none, reboots, at most **twice in a row**, then leaves the node up with a log entry. Counters reset when the GPU is confirmed. History is written to a file on the NVMe because the Jetsons' journals do not survive a power cycle.

| Test | Outcome |
|---|---|
| Forced failure (test flag) | reboot 1 of 2, reboot 2 of 2, then "leaving the system up, needs attention"; timestamps recorded |
| Normal path | GPU confirmed, counters cleared |
| Real failure (run 4, node 2) | GPU absent 35 s after boot; recovered by itself ~165 s later with no operator action |

## Limits

- **The cause is unknown.** Candidates: the boot-firmware change (10 partitions differ from the original), the board's power-on timing at cold start, or JetPack 7.2 itself. The original firmware cannot be tested on this board (it does not boot here), so the first candidate cannot be excluded by this experiment.
- Small samples; both modules were power-cycled simultaneously, so they are not independent trials.
- A search of public reports found related "GPU firmware bootstrap" issues on Orin modules and a newer JetPack (7.2.1) but no confirmation of this exact signature; a newer JetPack was **not** tried, because a firmware capsule update would overwrite the board-specific boot fix.
- The self-heal was observed to fire once for real; one event is not a reliability estimate.
