import sys; sys.path.insert(0, "/mnt/nvme/share/studio/research")
import selfmodel as sm
c = sm.connect(); sm.init(c)
rid = sm.start_run(c, "iperf3 + dd O_DIRECT",
  "Tests the two carrier features that could justify the board over 3 SBCs + a switch: the internal "
  "1GbE switch and the shared NFS store. Follows 008's admission that it never used carrier hardware.")
def r(node, eng, m, v, u, meth, **kw): sm.record(c, rid, node, eng, m, v, u, meth, **kw)
r("cluster","net","switch_tput_node1_node2", 937, "Mbit/s", "iperf3 10s, receiver; sender 939 -- 1GbE line rate")
r("cluster","net","switch_tput_node1_node3", 936, "Mbit/s", "iperf3 10s, receiver; sender 939")
r("cluster","net","switch_tput_node2_node3", 941, "Mbit/s", "iperf3 10s, Orin to Orin -- the split-inference path")
r("cluster","net","switch_tput_bidir_aggregate", 1593, "Mbit/s",
  "iperf3 --bidir node2<->node3: 789 TX + 804 RX. Full duplex works; each direction loses ~15% vs 941 "
  "one-way, most likely Orin NIC/CPU overhead, not the fabric (aggregate exceeds one link)")
r("cluster","net","switch_rtt_node1_node2", 0.439, "ms", "ping -c10 -i0.2 avg; min 0.381 max 0.544")
r("cluster","net","switch_rtt_node1_node3", 0.391, "ms", "ping -c10 -i0.2 avg; min 0.299 max 0.454")
r("orinnx","storage","nfs_read_over_carrier", 90.7, "MB/s",
  "dd 2GiB bs=1M iflag=direct from /mnt/share (NFS from node1 over the internal switch). "
  "= 726 Mbit/s, i.e. NFS overhead costs ~22% of the 937 Mbit/s the same path does with iperf3")
r("orinnx","storage","local_nvme_read", 2000.0, "MB/s", "dd 2GiB bs=1M iflag=direct from /dev/nvme0n1 (its own ROOT disk, 931.5GB)")
r("orin1","storage","local_nvme_read", 1900.0, "MB/s", "dd 2GiB bs=1M iflag=direct from /dev/nvme0n1")
r("rk1-node1","storage","local_nvme_read", 1600.0, "MB/s", "dd 2GiB bs=1M iflag=direct; this is the NFS backing store's ceiling")
r("cluster","storage","shared_store_penalty", 22.0, "x",
  "90.7 MB/s over NFS vs 2.0 GB/s on node2's own NVMe. Both Orins have 931.5GB NVMe as ROOT with ~930GB "
  "free, so the shared mount buys a single copy of a model, NOT capacity they lack")
r("orinnx","storage","model_load_penalty_14b", 99.2, "s",
  "Qwen3-14B-Q4_K_M.gguf is 9001752960 bytes (8.38 GiB); at the measured 90.7 MB/s that is ~99 s of cold "
  "model load from /mnt/share vs ~4.5 s from local NVMe. llama-server loads it from NFS in production today")
r("cluster","net","carrier_confers_perf_capability", 0, "bool",
  "NEGATIVE RESULT: neither tested carrier feature provides a capability the modules lack. Switch = commodity "
  "1GbE line rate; shared store = 22x slower than disks already present. Remaining candidate is per-slot BMC "
  "power gating (idle Nano draws 5.81 W per 008), which needs a board-level 12V meter because the BMC has no "
  "power sensing. research/cluster/009")
sm.finish_run(c, rid); print("run", rid)
