# RK3588 research

**Hardware:** node1 = Turing RK1 — RK3588, 8 cores (4x A76 + 4x A55), 31 GB, Mali-G610 MP4,
3-core NPU rated 6 TOPS. Vendor 6.1 kbase kernel.

The RK1 exposes **no power rails**, so this directory carries no energy figures. Where energy
matters the claim is made on the Orins instead, and said so explicitly.

Two gotchas this hardware forces on any benchmark here, both of which have already produced
withdrawn numbers: it is **4x A76 + 4x A55**, so a thread budget spanning both core types makes
per-core reasoning meaningless and can make a *wider* inference slower; and a CPU-only llama.cpp
run on the `llama-rpc-build` binary needs **both** `-ngl 0` and `-dev none`, or every layer is
silently offloaded to Mali. See [010](010-cpu-per-submit-serial-cost.md) Corrections.

| Paper | Claim | Status |
|---|---|---|
| [004](004-rk3588-npu-llm.md) | The RK3588 NPU cannot run transformer attention; the published decode figure does not reproduce | complete |
| [005](005-rk3588-npu-cnn.md) | What the NPU does do, measured on CNNs, including the 3-core utilisation ceiling | complete |
| [010](010-cpu-per-submit-serial-cost.md) | The per-submit serial cost isolated on the A76 CPU: fit it from thread width, test it against concurrency. Withdraws the 1.64x concurrency figure for 1.126x | complete |

Upstream engagement from 004/005 is tracked in
[../../capability-matrix/papers/README.md](../../capability-matrix/papers/README.md).

**Candidate channels:** Rockchip / single-board-computer communities. Confirm the exact subreddit
names and their self-promotion rules before posting.
