# Turing Pi 2.5: operator's runbook

Your one command: `~/turing-pi/ops/tp` (add `alias tp=~/turing-pi/ops/tp` to your shell profile). Run `tp help`.

## The board in one paragraph

Four slots, one management chip (the BMC), one built-in network switch. Slot 1 = Turing RK1 (Ubuntu; also the network gateway and file server). Slot 2 = Jetson Orin NX 16GB. Slot 3 = Jetson Orin Nano 8GB. Slot 4 = empty. Everything is on the private network 10.43.0.0/24: BMC .10, node 1 .1, node 2 .12, node 3 .13. Node 1 connects the board to the internet through its Wi-Fi USB dongle. Your laptop reaches it through the Ethernet cable to the board.

## Every day

| I want to | Do |
|---|---|
| See if everything is healthy | `tp status` |
| Get a shell on a node | `tp shell 1` (or 2, 3) |
| Restart a node safely | `tp reboot N` (warm reboot; safest) |
| Turn a node fully off | `tp shutdown N`, wait 30 s, `tp power off N` |
| Turn it back on | `tp power on N` (Jetsons take 2–3 minutes) |
| Check drives | `tp disk` (want: `critical_warning 0`, `media_errors 0`) |
| Keep a health history (uptime, GPU-missing events, temperatures) | `tp record-install` once; later `tp history` (stop with `tp record-remove`) |
| Re-run the standard speed test on every node | `tp bench llm` (about 3 minutes; compare with the reference line it prints) |
| See recent errors | `tp logs N` |

**Normal looks like:** all three nodes show uptime and "GPU ok" (Mali ok on node 1), internet "online", temperatures under about 75 °C, power "On" for nodes 1–3 (node 4 shows On for an empty slot; ignore it).

## When something is wrong

| Symptom | Likely cause | What to do |
|---|---|---|
| `tp status` says a node UNREACHABLE | Node still booting, or Ethernet cable to the laptop unplugged | Wait 3 minutes. Check the cable to the board. `tp console N` shows what it's doing. If still dead: `tp power cycle N`. |
| Jetson shows "GPU MISSING" | The known cold-boot fault (about 1 in 10 cold boots) | Do nothing for about 3 minutes; the self-heal service reboots it. If it persists: `tp reboot N`. |
| "OFFLINE" | Node 1 lost Wi-Fi or its dongle | `tp wifi`. Unplug and replug the USB dongle, then `tp reboot 1`. |
| Laptop can't reach anything | Cable unplugged or laptop link down | Replug the cable to the board; confirm the laptop interface is up. |
| A node won't power on | BMC state | `tp power status`; `tp power on N`; `tp bmc 'tpi info'` to confirm the BMC answers. |
| Jetson won't boot at all after some change | Firmware/config problem | Recovery procedure in the public repo `Hi5808/turing-pi-2.5-jetson-eeprom-fix` (scripts `tp-recovery.sh`, `qspi.sh restore`). Backups are in `~/turing-pi/jetson/qspi-backup-nx` and `qspi-backup-nano`. Stop and read the repo README first. |

## Never do these

1. **Never run a normal JetPack update or reflash the Jetsons with SDK Manager or a full flash.** It overwrites the small firmware fix that lets them boot on this board (and a full flash wipes the NVMe). Firmware/capsule updates count too.
2. **Never move or remove a module while the board is powered.** Shut down, power off at the BMC, then move it. The NVMe must travel with the Jetson it belongs to.
3. **Don't hard-cut power to a node that is running unless it's hung.** It logs an "unsafe shutdown" on the NVMe (the count only ever goes up) and risks data. Shut down first.
4. **Don't stop `triage-llm` or `triage-hid` on nodes 2 and 3** unless you mean to; they are your triage appliance.
5. **Don't delete** `/usr/local/sbin/gpu-selfheal.sh` or the `gpu-selfheal` service, `/etc/systemd/system/nvpmodel.service.d/wait-for-gpu.conf` (node 3), or node 1's `gateway-nat` and dnsmasq files. The whole board's internet depends on node 1's gateway.

## Where things live

| Thing | Location |
|---|---|
| This tool and runbook | `~/turing-pi/ops/` |
| Research notebook (matrix, logs, results) | `~/turing-pi-capability-matrix` (private GitHub `Hi5808/turing-pi-2.5-capability-matrix`) |
| Public recovery repo | `~/turing-pi-jetson-recovery` (`Hi5808/turing-pi-2.5-jetson-eeprom-fix`) |
| Firmware backups | `~/turing-pi/jetson/qspi-backup-nx`, `qspi-backup-nano` |
| Node 1 data drive | `/mnt/nvme` on node 1 (models, NFS share `/mnt/nvme/share`) |
| BMC | `root@10.43.0.10`, default password `turing` (change it if the board ever leaves your network) |
| Self-heal history | `/var/lib/gpu-selfheal/history.log` on nodes 2 and 3 |

## Once a month

`tp status`, `tp disk`, and look at `sudo apt list --upgradable` on node 1 (safe to update Ubuntu there; never on the Jetsons without reading rule 1). Pull the latest results with `git pull` in the notebook repo.
