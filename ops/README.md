# ops — operating the board from a laptop

`tp` is the single entry point for day-to-day board operation; see
[RUNBOOK.md](RUNBOOK.md) and run `tp help`. `jetson/` holds the host-side
flashing and QSPI helpers used when a Jetson module needs recovery (the
recovery procedure itself is in [../jetson-eeprom-fix/](../jetson-eeprom-fix/)).

## Credentials

`tp` talks to the BMC as `root` over SSH. It defaults to the **vendor default
password** that Turing Pi ships (`turing`), which is also recorded in the
runbook. Override it without editing the script:

```sh
export TP_BMC_PASS=...     # BMC root password
export TP_KNOWN_HOSTS=...  # defaults to ops/known_hosts, which is untracked
```

If this board is ever reachable from outside its own 10.43.0.0/24 network,
change that password first.

## What is deliberately not here

These files live only on the operator's laptop and were **not** imported, so
that nothing machine-specific or large enters a public repository:

| Not imported | Why |
|---|---|
| `user-data.new` / `user-data.orig` | cloud-init seeds containing an SSH public key whose comment identifies a specific laptop, and a first-boot password |
| `known_hosts` | per-laptop SSH state; regenerated on first connection |
| `*.img`, `*.img.xz`, `*.tbz2`, `Linux_for_Tegra/` | ~19 GB of re-downloadable OS images and BSP trees. Recorded in [../docs/STORAGE.md](../docs/STORAGE.md), kept on disk |
| `jetson/qspi-backup-*/` | binary firmware backups; these are the recovery copy and must stay on disk |

Unlike `capability-matrix/` and `jetson-eeprom-fix/`, this directory was copied
**without** its git history, precisely because that history contains the
cloud-init seed above.
