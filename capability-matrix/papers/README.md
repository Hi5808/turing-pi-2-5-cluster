# Candidate papers

Papers are built from the logs, data and scripts in this directory's siblings, which are the
citable evidence behind them.

**The drafts themselves are not kept in this public repository.** Unpublished drafts live in a
private repo so that putting them here does not count as prior publication at a venue that cares.
When a draft is finished it is copied into
[research-papers](https://github.com/Hi5808/research-papers) under the directory matching its
hardware and given the next `research_N` number there.

What stays here: [TEMPLATE.md](TEMPLATE.md) — the required formal header, the
platform-identification note, and the limitations section every paper must carry.

A paper is **not** started until its evidence rows in [`../MATRIX.md`](../MATRIX.md) are MEASURED.

## Index of drafts

Draft text is kept on node1 at `/mnt/nvme/share/studio/research/papers/drafts/` (with its own
README), not in this repository.

Grouped by the hardware each claim is about, matching the
[`research/`](../../research/) directory split, so a draft and the papers it is built from
belong to the same audience.

| id | hardware | title | built from | status |
|---|---|---|---|---|
| P7 | jetson-orin | Raising decode concurrency lowers absolute module power on Jetson Orin | [research/006](../../research/jetson-orin/006-batching-power-inversion.md) | draft — absolute-power claim CONFIRMED 2026-11-24 across a 16x request-length range; the live contradiction was `--parallel 2` (queueing, not batching). New boundary condition from [003 §6c](../../research/jetson-orin/003-dla-transformer-offload.md): the energy gain holds only while added concurrency still converts into throughput — on DLA in INT8 it reverses (18.25 -> 16.79 inf/J) past the ceiling |
| P8 | cluster (spans both) | Five engines, one serial segment: concurrency amortises a fixed per-submit cost that width cannot | [003](../../research/jetson-orin/003-dla-transformer-offload.md), [005](../../research/rk3588/005-rk3588-npu-cnn.md), [006](../../research/jetson-orin/006-batching-power-inversion.md), [001](../../research/cluster/001-heterogeneous-llm-pipeline.md), [007](../../research/jetson-orin/007-dla-concurrency-fragmentation.md), [010](../../research/rk3588/010-cpu-per-submit-serial-cost.md) | draft — the strongest novel claim here, and the mechanism is now MEASURED ON TWO ENGINES rather than inferred: 0.21 ms per submit on the DLA by depth at a fixed submit count ([007 3b](../../research/jetson-orin/007-dla-concurrency-fragmentation.md)), and 5.485 ms/token on the node1 CPU by thread width, where a fit from width alone predicts the unseen concurrency curve to +0.2% / +5.7% ([010](../../research/rk3588/010-cpu-per-submit-serial-cost.md)). DVFS and thermal excluded on both. Still inferred on the NPU and the Orin GPUs, and the specific shared resource is unidentified on both engines where it is quantified. Two corrections landed 2026-11-25: the CPU's **1.64x is withdrawn for 1.126x** (the old baseline spanned 4xA55+4xA76 and was handicapped by the little cores), and 'width does not scale' is too strong — it scales at 84% efficiency on the CPU, exactly as the 23.7% serial share predicts. The '~253 qps shared ceiling' remains RETRACTED by [007](../../research/jetson-orin/007-dla-concurrency-fragmentation.md); P8's framing no longer uses it. Mali is the engine where the lever does not exist at all — a 2nd concurrent Vulkan context kills the device |
| P9 | rk3588 | The RK3588 NPU cannot run transformer attention | [004](../../research/rk3588/004-rk3588-npu-llm.md), [005](../../research/rk3588/005-rk3588-npu-cnn.md), plus external sources | draft — our contribution is the unreproducible decode figure and the utilisation ceiling; the INT8 defect itself is third-party and unreproduced here. Our corroboration is now posted upstream on [rknn_model_zoo#314](https://github.com/airockchip/rknn_model_zoo/issues/314#issuecomment-7150553192); a maintainer answer to question 1 would settle whether the published decode figure was measured with attention on the NPU or the CPU |

P1, P2, P4, P5 and P6 predate the consolidation and remain in the archived private repo. P5 is
largely superseded by P8.

### Upstream engagement

P9's central open question has been put to the vendor rather than left in a draft. Issue
[rknn_model_zoo#314](https://github.com/airockchip/rknn_model_zoo/issues/314) (INT8 Whisper
producing garbage on RK3588) was opened in April 2025 by an unrelated reporter and, verified
directly on 2026-11-24, has **no maintainer reply**: all four comments carry
`author_association: NONE`, the most recent an independent reproduction from January 2026 using a
different calibration set. At least four separate parties have now reported the same INT8 attention
failure. Our decode-side corroboration was added to that thread on 2026-11-24.
