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

| id | title | built from | status |
|---|---|---|---|
| P7 | Raising decode concurrency lowers absolute module power on Jetson Orin | [research/006](../../research/006-batching-power-inversion.md) | draft — efficiency claim solid; absolute-power claim conditional on workload shape after a live re-check failed to reproduce it under short-request serving |
| P8 | Three fixed-function accelerators, one ceiling: throughput comes from concurrency, never from widening an inference | [003](../../research/003-dla-transformer-offload.md), [005](../../research/005-rk3588-npu-cnn.md), [006](../../research/006-batching-power-inversion.md), [001](../../research/001-heterogeneous-llm-pipeline.md) | draft — the strongest novel claim here; mechanism inferred across three engines, not isolated |
| P9 | The RK3588 NPU cannot run transformer attention | [004](../../research/004-rk3588-npu-llm.md), [005](../../research/005-rk3588-npu-cnn.md), plus external sources | draft — our contribution is the unreproducible decode figure and the utilisation ceiling; the INT8 defect itself is third-party and unreproduced here. Our corroboration is now posted upstream on [rknn_model_zoo#314](https://github.com/airockchip/rknn_model_zoo/issues/314#issuecomment-7150553192); a maintainer answer to question 1 would settle whether the published decode figure was measured with attention on the NPU or the CPU |

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
