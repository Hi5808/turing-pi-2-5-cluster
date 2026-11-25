# Jetson Orin research

**Hardware:** node2 = Jetson Orin NX 16GB (2 DLA engines, Ampere GPU); node3 = Jetson Orin Nano
8GB (**no DLA** — the SKU omits it entirely). JetPack 7.2 / L4T R39.2 / CUDA 13.2.

Power is read from the on-module INA3221 (`VDD_IN`, `CPU_GPU_CV`, `SOC`) and is module-level, so
carrier overhead is excluded.

| Paper | Claim | Status |
|---|---|---|
| [003](003-dla-transformer-offload.md) | The DLA compiles more of a transformer than documented but is 2.1–33.7x slower than the GPU; do not build a ggml DLA backend | complete |
| [006](006-batching-power-inversion.md) | Raising decode concurrency *lowers* absolute module power while raising throughput | complete |
| [007](007-dla-concurrency-fragmentation.md) | What limits DLA concurrency is engine fragmentation, not bandwidth and not a shared qps ceiling | complete — retracts a claim made in 003 §6c the same day |

**Candidate channels:** Jetson- and NVIDIA-specific communities; the LLM-serving ones for 006.
Confirm the exact subreddit names and their self-promotion rules before posting — this file does
not assert that any particular sub exists or allows link posts.
