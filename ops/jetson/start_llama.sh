#!/bin/bash
# Per-node launcher. The binary path differs between nodes -- node2 built llama.cpp in-tree,
# node3 uses a release tarball -- so each node keeps its own copy of this script and the
# systemd unit just calls it. Single source of truth for the model path and the server args.
#
#   node2 (orinnx): BIN=/home/orinnx/llama.cpp/build/bin/llama-server
#                   MODEL=/home/orinnx/models/Qwen3-14B-Q4_K_M.gguf
#   node3 (orin1):  BIN=/home/orin1/llama-arm64/llama-b10533/llama-server
#                   MODEL=/home/orin1/models/qwen3-4b-q4km.gguf
#
# Models are staged on local NVMe, NOT /mnt/share: NFS costs 81.5 s of cold start vs 9.8 s
# local (research/cluster/009 Finding 4). Keep the NFS copy as the distribution master.
BIN=/home/CHANGEME/path/to/llama-server
MODEL=/home/CHANGEME/models/CHANGEME.gguf

export LD_LIBRARY_PATH="$(dirname "$BIN"):$LD_LIBRARY_PATH"
exec "$BIN" -m "$MODEL" \
  --host 0.0.0.0 --port 8101 -c 8192 --parallel 8 --cache-ram 0 -ngl 99
