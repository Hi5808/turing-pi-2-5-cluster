# Measurements

**Platform:** Turing Pi 2.5 board; node1 = Turing RK1 (RK3588, 31 GB); node2 = Jetson Orin NX 16GB;
node3 = Jetson Orin Nano 8GB.
**Software stack:** Ubuntu 24.04.5 LTS on all three; node1 kernel 6.1.0-1025-rockchip;
nodes 2–3 JetPack 7.2 / L4T R39.2 / CUDA 13.2, kernel 6.8.12-1021-tegra; k3s v1.36.4+k3s1.
**Date:** 2026-11-17.

## Abstract

Interconnect and storage throughput were measured to decide whether a multi-stream
architecture is viable on this chassis. It is not. The backplane delivers full 1GbE per node
but node1 — which owns the only uplink and the control plane — has a single port, making it a
hard ~119 MB/s aggregate bottleneck for any hub-and-spoke design. Local NVMe is 15–17x faster
than the wire, which inverts the usual cluster assumption that data should move to compute.

## Network

`iperf3`, 5 seconds, 4 parallel streams, over the backplane (10.43.0.0/24).

| Path | Throughput | Note |
|---|---|---|
| node2 -> node1 | 951 Mb/s (119 MB/s) | line rate |
| node3 -> node1 | 951 Mb/s (119 MB/s) | line rate |
| node2 <-> node3 | 941 Mb/s (118 MB/s) | peer-to-peer, never touches node1's link |

All links negotiate 1000Mb/s full duplex. The onboard switch is non-blocking for pairwise
traffic: a node2<->node3 transfer at line rate leaves node1's bandwidth fully available.

## Storage

`dd` with `iflag=direct` (2 GB) on the Jetsons; `hdparm -t --direct` on node1.

| Node | Device | Sequential read |
|---|---|---|
| node1 | NVMe (`/mnt/nvme`) | 1879 MB/s |
| node2 | `/dev/nvme0n1` | 1700 MB/s |
| node3 | `/dev/nvme0n1` | 2000 MB/s |

**Ratio of local read to cross-node transfer: ~16x.**

## Derived limits

- Raw 1080p30 YUV420 = ~93 MB/s. One stream saturates a link. 4K raw (~373 MB/s) is impossible.
- Encoded H.265 1080p30 at 8 Mbps = ~100 streams per link. For encoded work the bottleneck is
  the number of encoder engines, not the network.
- Tensor-parallel LLM inference needs all-reduce bandwidth on the order of 10 GB/s. Available:
  0.119 GB/s. Not viable, by two orders of magnitude.
- Pipeline-parallel LLM inference moves only layer-boundary activations — on the order of
  10 KB per token for a 14B-class model. Bandwidth is irrelevant; the design is latency-bound.

## Media engine asymmetry

A hard constraint that invalidates treating the nodes as interchangeable:

| Node | Encode | Decode |
|---|---|---|
| node1 (RK3588) | 8K H.264/H.265 | 8K H.264/H.265 |
| node2 (Orin NX) | 1x NVENC | 1x NVDEC |
| node3 (Orin Nano) | **none** | NVDEC only |

node3 physically cannot encode video. node1 — normally thought of as "just" the control node —
holds the strongest transcode engine in the chassis.


## Pipeline-parallel LLM inference, 2026-11-18

Full method and findings in [../research/002](../research/cluster/002-pipeline-parallel-measurements.md).

### Single-node decode (same model, Qwen3-4B Q4_K_M)

| Node | INT8 TOPS | pp512 | tg128 |
|---|---|---|---|
| node2 Orin NX | ~157 | 744.61 | 20.00 |
| node3 Orin Nano | ~67 | 671.38 | 18.16 |

**A 2.3× TOPS gap yields a 9% decode difference** — decode is memory-bandwidth-bound and both modules
have 102 GB/s. Do not size pipeline stages from TOPS.

### Allocatable memory (moves with system state)

| Node | Total | Allocatable observed |
|---|---|---|
| node2 | 15599 MiB | 12.21–13.90 GiB |
| node3 | 7547 MiB | 5.39 GiB |

Unified CPU+GPU memory; a 1.7 GiB swing on node2 between a loaded and a freshly restarted worker.
Read `available_memory_kb` from the worker at launch; never reuse an earlier figure.

### Pipeline cost and per-token traffic

| Model | Single node | Split 2 nodes | Penalty |
|---|---|---|---|
| Dense 14B Q4 | 7.49 t/s | 7.19 t/s | −4.0% |
| MoE 30B-A3B Q3 | 18.63 t/s | 15.18 t/s | −18.5% |
| Dense 32B Q3 | **OOM both nodes** | 2.46 t/s | n/a |

Per-token network cost ~703 KB, of which ~666 KB is **inbound logits** to the orchestrator
(151,936-token vocabulary × 4 bytes ≈ 594 KiB). ~40 Mbit/s, **4% of the 1GbE link**; bandwidth
ceiling would be ~169 tok/s. Orchestrator CPU at 7.4%. The pipeline is compute-bound.

### Batched decode (aggregate throughput)

| Streams | Dense 32B decode | MoE 30B decode |
|---|---|---|
| 1 | 2.41 t/s | 12.64 t/s |
| 2 | 4.31 t/s (1.79×) | 19.91 t/s (1.58×) |
| 4 | 5.85 t/s (2.43×) | 23.58 t/s (1.87×) |
| 8 | — | 35.30 t/s (2.79×) |

Batching gain scales with how **weight-read-bound** the model is: dense streams 14.87 GiB of weights
per token against the MoE's ~1.4 GiB, so dense benefits more per stream added.

## DLA vs GPU, transformer components at decode shapes (node2, Orin NX)

TensorRT 11.3.0.99 b99, 200 iterations, median GPU-compute ms. Full method: [research/jetson-orin/003](../research/jetson-orin/003-dla-transformer-offload.md).

| Component | DLA (ms) | GPU (ms) | DLA penalty |
|---|---|---|---|
| rmsnorm | 0.1025 | 0.00781 | 13.1x |
| softmax | 0.0981 | 0.00800 | 12.3x |
| attn_core | 1.8451 | 0.05475 | 33.7x |
| qkv_q (5120->8192) | 1.8247 | 0.8428 | 2.17x |
| conv_8192 | 1.7738 | 0.8428 | 2.10x |
| ffn_gate_tile (5120->6400) | 1.4313 | 0.6569 | 2.18x |
| ffn_down_tile (6400->5120) | 1.4008 | 0.6646 | 2.11x |

DLA loses every component. ResNet-18 on DLA core 0: 7.83 ms mean / 127.7 qps (30 iters).
DLA non-batch dimension cap measured exactly: 8192 passes, 8193 fails.

### DLA/GPU concurrency and prefill shapes (node2, Orin NX) — 2026-11-18

`qkv_q` 5120→8192 GEMM-as-1×1-conv, same engine per device, 20 s per scenario, TRT 11.3.0.99.
83.89 MB fp16 weights read per inference, so qps → DRAM bandwidth directly. Module peak 102.4 GB/s.

| Scenario | Total qps | GB/s | % of peak |
|---|---|---|---|
| GPU alone | 1182.5 | 99.2 | 97% |
| DLA0 alone | 592.4 | 49.7 | 49% |
| DLA0 + GPU | 1025.5 | 86.0 | 84% |
| DLA0 + DLA1 | 539.8 | 45.3 | 44% |
| DLA0 + DLA1 + GPU | 1046.1 | 87.8 | 86% |

The GPU alone saturates memory bandwidth; DLA+GPU is 13% *slower* than GPU alone; the two DLA
engines are slower together than one. DLA is not an additive second compute stream for
bandwidth-bound work.

Prefill shapes (token count in W; decode used W=1), strict DLA, chw16, 200 iterations:

| Component | Tokens | DLA | GPU qps |
|---|---|---|---|
| qkv_q / ffn_gate_tile / ffn_down_tile / rmsnorm | 128 | DLA compile error 8 | 973.0 / 1143.8 / 1210.1 / 2479.3 |
| qkv_q / ffn_gate_tile / ffn_down_tile / rmsnorm | 512 | DLA compile error 8 | 336.8 / 357.2 / 424.4 / 611.2 |
| softmax | 128 | 840.9 | 5116.1 |
| softmax | 512 | 54.6 | 431.0 |
| attn_core | 128 | 94.0 | 2933.7 |

Convs that compile at W=1 fail at W=128/512 with `DLA Compile exception` / error code 8 on
`ForeignNode[/c/Conv]` — a shape rejection, not the 8192 cap (all dims ≤ 6400).

Method: `run007.sh` (concurrency), `export3.py` + `run008.sh` (prefill), on node2 in
`/home/orinnx/dla-transformer/`.

### RK3588 NPU vs node1 CPU, TinyLlama 1.1B (node1) — 2026-11-18

NPU: `TinyLlama-1.1B-plain-w8a8` (1.26 GB) via rkllama 0.0.75 / librkllmrt, 3 NPU cores.
CPU: `tinyllama-1.1b-chat-v1.0.Q8_0.gguf` (1.09 GiB) via llama-bench, `-t 8 -r 2`.

| Workload | NPU | node1 CPU | Winner |
|---|---|---|---|
| Prefill | 219.94 t/s | 110.73 ± 3.61 | NPU 1.99x |
| Decode | 9.67 t/s | 16.11 ± 2.28 | CPU 1.67x |

Decode stable at 9.67–9.76 t/s across 4 runs. `/sys/kernel/debug/rknpu/load` during decode:
Core0 64%, Core1 62%, Core2 60% — all three cores used, none saturated, so decode is dispatch/
latency-bound rather than NPU-compute- or DRAM-bound (~12.2 GB/s moved).

NPU state (corrects "driver present, no userland"): `/dev/dri/renderD129` DRIVER=RKNPU,
`npu@fdab0000` status=okay, devfreq 1.0 GHz, librknnrt 2.3.2, rknn-toolkit-lite2 2.3.2.

Caveat: rkllama reports `total_duration` in ns but `eval_duration`/`prompt_eval_duration` in ms.

### node1 NPU vs Orin NX, and KV-cache transfer (2026-11-18)

TinyLlama-1.1B, `llama-bench -ngl 99` to node2 over the RPC backend:

| Engine | pp128 | pp512 | decode |
|---|---|---|---|
| node1 NPU (3 cores, w8a8) | 219.94 | — | 9.67 |
| node1 CPU (8 threads, Q8_0) | 110.73 ± 3.61 | — | 16.11 ± 2.28 |
| node2 Orin NX (CUDA, Q8_0) | 1966.82 ± 178.43 | 2269.58 ± 41.36 | 45.31 ± 0.40 |

Orin prefills 8.9–10.3x faster than node1's NPU and decodes 4.7x faster. Orin measured through
RPC with a DLA compile occupying one of its cores, so its native rate is at least this high.

Backplane node1 -> node2: **105.1 MB/s** over SSH (600 MB in 5.71 s); 119 MB/s is line rate.

KV cache per token, from GGUF metadata (`2 * n_layer * n_head_kv * n_embd_head * 2` bytes, f16):

| Model | n_layer | n_head_kv | n_embd_head | KV/token |
|---|---|---|---|---|
| TinyLlama-1.1B | 22 | 4 | 64 | 22 KiB |
| Qwen3-32B | 64 | 8 | 128 | 256 KiB |

Qwen3-32B KV transfer vs prefill: 2048 tok = 536.9 MB = 5.11 s against 28.6 s of prefill (~18%).
Transfer is affordable; it was never the blocker. Capacity is: 32B w8a8 exceeds node1's 31 GB.

### The dashboard was a measurement contaminant for 9 hours (2026-11-25)

`live.py` on node1 is a demo dashboard for the [006](../research/jetson-orin/006-batching-power-inversion.md)
batching-power inversion. Its load generators were **not gated on an attached viewer**: two threads
per Orin fired a fresh 48-token completion the instant the previous returned, with
`cache_prompt: False` so every one re-ran prefill.

A forgotten `nohup python3 live.py 8096` was found still doing this after **9 h 06 m** (PPID 1, in
no crontab and no unit). State when caught:

| Node | tj | VDD_IN | gpu_load | loadavg |
|---|---|---|---|---|
| orinnx | **98 C** | 30.2 W | 999 | 0.21 |
| node1 | 72 C (soc) | — | — | 3.10 |
| orin1 | 64 C | — | — | 5.85 |

Two things make this worth recording.

**It was invisible to the usual check.** orinnx read `loadavg 0.21` while pinned, because the work
was entirely in CUDA and never touched a CPU runqueue. `ps` showed llama-server at 2.2% CPU. Only
`gpu_load`, the INA3221 rail and the server's own task counter (221,909) showed it. A node can be
fully loaded and look idle.

**98 C is past the trip but not throttling.** tj trip points are 35 / 74 / **95** / 104 C. Every
`*-throttle-alert` cooling device still read `cur=0` and both CPU clusters sat at 1984 MHz, so
clocks were not clamped; `hot-surface-alert` was the only one tripped, and `pwm-fan` was at state
2 of 3. So a sustained 98 C here is not self-limiting — do not assume the thermal governor will
save a long run.

This load is the contaminant behind the 28.56 W "idle" baseline voided in
[003 §5](../research/jetson-orin/003-dla-transformer-offload.md), and behind the SIGTERM stalls
first misattributed to "aged instances" in matrix row A44 — the trigger is an in-flight stream,
and this dashboard supplies one continuously.

**Fixed** by gating every generator on a recent page poll (`IDLE_GRACE = 30 s`, stamped in
`do_GET` for `/` and `/state`); the `npu_live.py` subprocess is no longer spawned unwatched and is
reaped when the viewer leaves. Verified in all three states:

| State | orinnx gpu_load | orinnx tj | orinnx VDD_IN |
|---|---|---|---|
| unwatched, server up 2 min | 0 | 67 C | 7.93 W |
| polled 18x | 999 | 76 C | 28.15 W |
| 40 s after last poll | 0 | 73 C | 8.21 W |

`live.py` is now **in this repository** at
[`capability-matrix/scripts/bench/cluster/live.py`](../capability-matrix/scripts/bench/cluster/live.py)
(added 2026-11-25; it had been living only on node1, where its directory is not a git repo). The
copy carries the gate, and its docstring records both the 9-hour incident and the fact that it
binds `0.0.0.0` with no authentication -- `GET /set?n=8` starts eight decode streams per module for
anyone who can reach the port, which is fine on a trusted lab LAN and not safe to expose. The
running node1 copy stays at `/mnt/nvme/share/studio/research/live.py` with a timestamped `.bak` of
the unpatched file.

**Before trusting any idle or power figure, check `gpu_load` and the rail, not `uptime`.**
