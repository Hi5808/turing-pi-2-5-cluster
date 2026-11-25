import sys; sys.path.insert(0, "/mnt/nvme/share/studio/research")
import selfmodel as sm
c = sm.connect(); sm.init(c)
rid = sm.start_run(c, "ab_load.sh", "Staged models onto each Orin's local NVMe and measured cold-start "
  "model load A/B vs NFS. Caches dropped (vm.drop_caches=3) before each arm; readiness = HTTP 200 on /health.")
def r(n, m, v, u, meth, **kw): sm.record(c, rid, n, "node", m, v, u, meth, **kw)
r("orinnx","model_load_cold_nfs", 81.50, "s",
  "Qwen3-14B-Q4_K_M (8.38 GiB) from /mnt/share over the carrier switch, caches dropped, to HTTP 200 on /health")
r("orinnx","model_load_cold_local", 9.81, "s",
  "same model from /home/orinnx/models on local NVMe, caches dropped, to HTTP 200")
r("orinnx","model_load_speedup_local", 8.31, "x",
  "81.50 -> 9.81 s; saves 71.7 s on every cold start")
r("orinnx","model_load_warm_local", 8.74, "s",
  "local, WITHOUT dropping caches (clean restart). Only 1.1 s better than cold local, so the local path is "
  "NOT disk-bound")
r("orinnx","nfs_effective_load_throughput", 105.0, "MB/s",
  "8.38 GiB / 81.50 s. This EXCEEDS the 90.7 MB/s measured with dd iflag=direct, so the O_DIRECT figure in "
  "research/cluster/009 understates buffered NFS reads by ~16% -- O_DIRECT defeats readahead")
r("orinnx","local_effective_load_throughput", 876.0, "MB/s",
  "8.38 GiB / 9.81 s, against 2.0 GB/s raw sequential read. Load is only ~44% of disk capability, so mmap, "
  "tensor setup and CUDA init dominate the local case, not I/O. Predicting ~4.5 s from disk speed alone was wrong")
sm.record(c, rid, "orin1", "node", "model_load_local_verified", 1, "bool",
  "qwen3-4b-q4km.gguf (2.33 GiB) staged to /home/orin1/models and serving; generation verified. A/B NOT "
  "measured on this node: the harness assumed orinnx's binary path and orin1's llama-server lives at "
  "~/llama-arm64/llama-b10533/, so both arms failed and service was restored instead of re-measured")
sm.finish_run(c, rid); print("run", rid)
