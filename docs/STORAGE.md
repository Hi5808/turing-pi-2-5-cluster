# Storage ledger

Tracks large artifacts added to the cluster, so disk use stays accountable and nothing large is
orphaned. Node1's `/mnt/nvme` is the only bulk volume that matters: its 29 GB eMMC root cannot hold
models, and `/mnt/nvme/share` is NFS-exported to both Jetsons at `/mnt/share`.

**node1 `/mnt/nvme`: 916G total, 185G used, 732G free (21%) as of 2026-11-18.**

## Models added for project 001

| File | Bytes | GiB | Added | Purpose |
|---|---|---|---|---|
| `share/models/Qwen3-32B-Q3_K_M.gguf` | 15,971,778,208 | 14.87 | 2026-11-17 | **The impossible model** — exceeds any single node's allocatable memory; primary result of research 002 |
| `share/models/Qwen3-30B-A3B-Q3_K_M.gguf` | 14,711,847,488 | 13.70 | 2026-11-17 | MoE arm of the dense-vs-MoE comparison at constant Q3_K_M quantisation |

Both from the `unsloth/Qwen3-*-GGUF` repositories; sizes verified against the HTTP
`content-length` before and after transfer. Quantisation is deliberately identical across the two so
architecture is the only variable.

Total GGUF in the shared store: **68G**. Visible from all three nodes via NFS — one copy, no
duplication.

## Pre-existing duplication worth reclaiming

Identified during the project inventory, **not yet acted on** (left alone deliberately; these belong
to the product-studio pipeline):

| Path | Waste | Note |
|---|---|---|
| `node2:/home/orinnx/studio-models/` | ~13.0 GiB | Exact-size duplicates of 4 files already in the NFS share |
| `node3:/home/orin1/studio-models/sdxl_base_q8_0.gguf` | 4.20 GiB | Duplicate of the share copy |

Roughly **17 GiB reclaimable** by pointing those at `/mnt/share/models`, if the studio pipeline
tolerates NFS latency on first load.

## Other artifacts from this work

| Path | Size | Keep? |
|---|---|---|
| `node1:/mnt/nvme/backups/k3s-20261117-2217` | 6.4G | **Keep** — the clean-slate restore point |
| `node1:/mnt/nvme/k3s.old-20261117` | 237M | Deletable once the rebuilt cluster is trusted; retains the old containerd image store as a second recovery path |
| `node1:/mnt/nvme/llama.cpp/build-rpc` | 76M | **Keep** — holds the RPC client binaries |
| `node1:/mnt/nvme/llama.cpp/build-cli` | 4.3M | Deletable — failed build attempt |
| `node1:/mnt/nvme/llama.cpp/build-cli2` | 28M | Deletable — failed build attempt |
| `node3:/home/orin1/llama.cpp/build-rpc` | — | **Keep** — the CUDA RPC worker built for this project |

## Practice

Check `df` before any multi-GB download. Models belong only in `/mnt/nvme/share/models` on node1, so
every node reads one copy. Record additions here with exact byte counts.
