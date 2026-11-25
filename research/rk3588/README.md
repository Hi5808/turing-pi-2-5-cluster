# RK3588 research

**Hardware:** node1 = Turing RK1 — RK3588, 8 cores (4x A76 + 4x A55), 31 GB, Mali-G610 MP4,
3-core NPU rated 6 TOPS. Vendor 6.1 kbase kernel.

The RK1 exposes **no power rails**, so this directory carries no energy figures. Where energy
matters the claim is made on the Orins instead, and said so explicitly.

| Paper | Claim | Status |
|---|---|---|
| [004](004-rk3588-npu-llm.md) | The RK3588 NPU cannot run transformer attention; the published decode figure does not reproduce | complete |
| [005](005-rk3588-npu-cnn.md) | What the NPU does do, measured on CNNs, including the 3-core utilisation ceiling | complete |

Upstream engagement from 004/005 is tracked in
[../../capability-matrix/papers/README.md](../../capability-matrix/papers/README.md).

**Candidate channels:** Rockchip / single-board-computer communities. Confirm the exact subreddit
names and their self-promotion rules before posting.
