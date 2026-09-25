# Project charter: a cross-chip edge-AI testbed on one Turing Pi 2.5

## Decision (September 2026)

The board is a **research testbed**. It carries three different AI SoCs on one 1 GbE fabric, which few published setups do (typical builds use one chip type). The product is a set of dated, reproducible, evidence-graded results and the papers built from them. Practical uses (a private AI endpoint, a home for the triage appliances, camera AI, a build farm) are allowed to grow out of the results but are not the goal.

## Principles

1. Nothing counts without a log and raw data (see [METHODOLOGY](METHODOLOGY.md)).
2. Never overwrite the user's data or services. Irreversible steps (fuses, firmware, power-loss tests) need explicit sign-off.
3. Report negative results and retractions.
4. Every result names its unit, software versions and limits; one unit of each module means no population claims.

## Where things stand

68 matrix rows across compute, cluster, infrastructure, media, storage, low-level and reliability tracks; 15 logs. Headline findings so far: the QSPI-only recovery for foreign-carrier modules; the intermittent GPU cold-boot failure and its self-heal; the mini-PCIe negative result; the RK1 NPU decoding at half the speed of its own CPU; the NX's DLA cores unusable; identical NVMe drives behaving differently by host.

## Roadmap

| Phase | Work | Needs |
|---|---|---|
| 1. Close the open questions | Reproduce or retract the Orange Pi 5 Plus NPU figure; cross-chip energy with an external meter; NX DLA cause; RPC split over 1 GbE | RPC needs a decision on how to expose the server; meter needs hardware |
| 2. Add a fourth node | Second Orin Nano in slot 4: unit-to-unit variance, USB 3.0, rotation sessions | The module, its NVMe, PSU rating |
| 3. Papers | Turn P1 to P6 into research-papers drafts | Rows behind each paper MEASURED |
| 4. Optional services | Router/agent, monitoring, k3s | User go-ahead per service |

## Reproducing

Scripts: [`scripts/bench/`](../scripts/bench) (RK1 soak, RKNN, RKLLM benchmark and NPU frequency sweep). Raw data under `data/raw/`.
