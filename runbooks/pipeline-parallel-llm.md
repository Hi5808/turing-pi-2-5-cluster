# Runbook: pipeline-parallel LLM across the Jetsons

Runs one model split across node2 (Orin NX) and node3 (Orin Nano), orchestrated by node1. Use this
when a model does not fit a single node — **and only then**: splitting a model that already fits
costs 4% (dense) to 18.5% (MoE). Measurements in [research/002](../research/cluster/002-pipeline-parallel-measurements.md).

## Prerequisites (one-time, already done)

All three nodes on the **same llama.cpp commit** — the RPC wire format changes between ggml releases
and mismatched builds hang at handshake. Currently `704485942ab54bbbbf1f241b3550ffba35f5f37e`.

| Node | Binary | Built with |
|---|---|---|
| node2 | `~/llama.cpp/build-rpc/bin/ggml-rpc-server` | `-DGGML_RPC=ON -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=87-real` |
| node3 | `~/llama.cpp/build-rpc/bin/ggml-rpc-server` | same |
| node1 | `/mnt/nvme/llama.cpp/build-rpc/bin/{llama-bench,llama-batched,llama-batched-bench,llama-perplexity}` | `-DGGML_RPC=ON` (CPU only — node1 computes nothing) |

On node3, `cmake` is not on the non-interactive PATH: use
`/home/orin1/opt/cmake-3.31.6-linux-aarch64/bin/cmake`.

`llama-cli` and `llama-server` **cannot be built** on a node without a JS toolchain at this commit:
they pull a web-UI asset target whose prebuilt bundle is missing an asset the validator requires, and
`LLAMA_BUILD_UI=OFF` does not gate it. Use `llama-batched` for generation instead — it takes `--rpc`
and has no server dependency.

## 1. Lock clocks (worth up to +6.9%)

```
ssh node2 'sudo jetson_clocks --store /tmp/clocks.before; sudo jetson_clocks'
ssh node3 'sudo jetson_clocks --store /tmp/clocks.before; sudo jetson_clocks'
```

**Not persistent across reboot** — re-apply each boot. Restore with `sudo jetson_clocks --restore
/tmp/clocks.before`. The gain scales inversely with per-token work: large on a fast MoE, negligible on
a slow dense model.

## 2. Start the workers (backplane only)

```
ssh node2 'setsid nohup ~/llama.cpp/build-rpc/bin/ggml-rpc-server -H 10.43.0.12 -p 50052 > ~/rpc.log 2>&1 &'
ssh node3 'setsid nohup ~/llama.cpp/build-rpc/bin/ggml-rpc-server -H 10.43.0.13 -p 50052 > ~/rpc.log 2>&1 &'
```

The RPC server has **no authentication or encryption** and is single-client. Bind to `10.43.0.x`
only, never a routable interface.

Confirm each log prints its CUDA device and, importantly, `available_memory_kb` — **this value moves
with system state** (12.21 GiB vs 13.90 GiB observed on the same node), so read it at launch rather
than trusting a previous figure.

**Restart the workers between model changes.** They retain the previous model's allocation after a
client disconnects.

## 3. Run

```
RPC=10.43.0.12:50052,10.43.0.13:50052
M=/mnt/nvme/share/models/<model>.gguf
cd /mnt/nvme/llama.cpp

# benchmark
./build-rpc/bin/llama-bench -m $M --rpc $RPC -ngl 99 -p 128 -n 64 -r 1

# generate text
./build-rpc/bin/llama-batched -m $M --rpc $RPC -ngl 99 -n 64 -np 1 -c 512

# aggregate throughput across concurrent streams
./build-rpc/bin/llama-batched-bench -m $M --rpc $RPC -ngl 99 -npp 128 -ntg 32 -npl 1,2,4 -c 2048 -ctk q8_0 -ctv q8_0
```

### Do not pass `--tensor-split`

A capacity-derived ratio (`69,31`) **failed to load the model at all**, aborting before weight
transfer, because large indivisible tensors (token embeddings, output head) sit whole on one device
and do not obey the ratio. Let llama.cpp allocate by free memory.

### Settings that matter

- `-ngl 99` — all layers to the RPC devices.
- **Single stream:** leave KV at f16. `-ctk/-ctv q8_0` costs 2.9% because it trades compute for memory
  that is not short.
- **Multiple streams:** use `-ctk q8_0 -ctv q8_0`. N streams need N× the KV cache, and the quantisation
  is what buys the stream count. Batching is the real throughput lever — 2.43×–2.79× aggregate decode.
- `-fa` can be left at `auto`; it is already enabled.
- `-ub` tuning does nothing here — the link runs at 4–8% utilisation.
- Keep `-c` modest. `-c 4096` at 4 streams on a 14.87 GiB model **killed the client silently** with no
  OOM message while the workers kept the model resident; `-c 2048` completed. Write each run's output
  to its own file and record exit codes, or you cannot distinguish a crash from an empty result.

## 4. Stop

```
ssh node2 'sudo fuser -k 50052/tcp'
ssh node3 'sudo fuser -k 50052/tcp'
```

Do not use `pkill -f ggml-rpc-server` over SSH — the binary's path appears in the invoking command
line, so it kills its own session. The `[g]`-bracket trick does not help.

## 5. Validity checks for any measurement

- **Swap must not grow.** Record it before and after; a spill invalidates the number. Distinguish
  pre-existing swap from run-caused swap by sampling at idle first.
- **Measure marginal, not total, network bytes** — weight distribution (~15 GB) swamps per-token cost.
  Difference two runs of different token counts.
- Expect ~703 KB/token, dominated by the vocabulary-sized logit return to node1 (~594 KiB for a
  151,936-token vocabulary), not by activations.
