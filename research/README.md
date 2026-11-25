# Research

Measured results from the Turing Pi 2.5 cluster. Everything here is first-party measurement on
hardware in hand, with corrections kept in place rather than edited out.

Papers are filed **by the hardware the claim is about**, not by date, so that a result can be
discussed in the community that owns that hardware without dragging in three unrelated boards.
The numeric prefixes are stable and are cited across the repo; they did not change when the
directories were introduced.

| Directory | Hardware | Scope |
|---|---|---|
| [jetson-orin/](jetson-orin/) | Jetson Orin NX 16GB (node2), Orin Nano 8GB (node3) | GPU, DLA, rail-level power and energy |
| [rk3588/](rk3588/) | Turing RK1 — RK3588, Mali-G610 MP4, 6 TOPS NPU (node1) | NPU, Mali, CPU |
| [cluster/](cluster/) | Carrier + all three nodes together | Split inference, pipeline parallelism, baselines |

A claim that spans hardware classes lives in `cluster/` and is cross-linked from the per-board
directories, so no result is duplicated.

## Reading order

Start with [cluster/000](cluster/000-cluster-rebuild-and-baseline.md) for what the machine is and
how it is measured. [../capability-matrix/](../capability-matrix/) is the index of what has been
established, what is refuted, and what is still untested; it is regenerated from
`capability-matrix/data/capabilities.csv`, which is the single source of truth.

## Method notes that apply to every paper here

- Power is **module-level** (VDD_IN from the on-module INA3221), not board-level. The carrier's
  fan, BMC and switch are excluded from every tok/J figure. The BMC has no power sensing — see
  [../capability-matrix/logs/2026-11-24_bmc-power-telemetry.md](../capability-matrix/logs/2026-11-24_bmc-power-telemetry.md).
- The RK1 exposes no power rails, so its energy figures are absent rather than zero.
- Concurrency results state the **per-stream resource allocation**. A concurrency number without
  it is meaningless: two processes each given all 8 cores measure thread thrashing, not scaling.
