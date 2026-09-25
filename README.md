# Turing Pi 2.5 capability matrix

A public **lab notebook** that tries to answer one question with evidence: *what can a Turing Pi 2.5 board actually do when it carries three different AI chips at once?*

The board holds a Turing RK1 (Rockchip RK3588 with a 6-TOPS NPU), a Jetson Orin NX 16GB and a Jetson Orin Nano 8GB, and one empty slot. The point is not a spec-sheet comparison. It is a **complete, evidence-graded map**: every chip, every feature, every port, each marked works / partial / fails / needs-hardware / untested, with a dated log, raw results and stated limitations behind each cell.

**Current status:** see [MATRIX.md](MATRIX.md) (generated from [`data/capabilities.csv`](data/capabilities.csv)).

## Why this is interesting

1. **Three architectures on one 1 GbE fabric.** Two CUDA GPUs of different size, and an NPU-based SoC, sharing storage, a network and a management controller. Cross-architecture comparisons on identical hardware are rare.
2. **The board's I/O is a hard constraint.** Each expansion port belongs to one slot, so what a chip can be tested on depends on where it sits. The study is therefore organised by **chip × slot**, with a rotation protocol that covers all twelve combinations in four sessions. See the [port map](docs/PORT-MAP.md).
3. **Negative results are recorded.** Several things here did not work the first way, and one theory was retracted. The logs keep that.

## Layout

| Path | What |
|---|---|
| [`MATRIX.md`](MATRIX.md) | The list: features × chips × slots, with status and evidence |
| [`data/`](data) | Single source of truth (CSV): capabilities and slot coverage |
| [`logs/`](logs) | One file per experiment: question, setup, method, results, limits |
| [`docs/PORT-MAP.md`](docs/PORT-MAP.md) | Which ports belong to which slot, what is verified, the rotation protocol |
| [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) | Evidence levels and the rules every entry follows |
| [`papers/`](papers) | Candidate papers built from the logs, and the template |
| [`scripts/`](scripts) | `render_matrix.py` and (later) the benchmark harness |

## Results so far (all with logs)

- Booting Jetson modules that were provisioned for another carrier, **without overwriting their NVMe**, and restoring the original firmware: [log](logs/2026-09-23_qspi-recovery-foreign-carrier.md) · [scripts](https://github.com/Hi5808/turing-pi-2.5-jetson-eeprom-fix)
- An **intermittent GPU start-up failure on Jetson Orin cold boots** (about 1 in 10, never on warm reboots) and a verified self-healing mitigation: [log](logs/2026-09-24_gpu-init-cold-boot-failure.md)
- A mini-PCIe Wi-Fi/Bluetooth card whose USB function works and whose PCIe function fails on **two different SoCs**: [log](logs/2026-09-24_mini-pcie-wifi-investigation.md)
- Full-board restart integrity, and what the NVMe "unsafe shutdown" counter really counts: [log](logs/2026-09-24_full-board-reboot-integrity.md)
- One node as the gateway for the whole board: [log](logs/2026-09-24_wifi-gateway-network.md)
- A first storage figure for the RK1's NVMe: [log](logs/2026-09-24_node1-nvme-storage.md)
- fio on the NVMe of all three nodes (same drive model, same link): host-dependent write speed and a read-throughput state effect on all three: [log](logs/2026-09-24_nvme-fio-all-nodes.md)
- One model on three chips, and the RK3588 NPU against its own CPU (NPU decode is about half the speed of the four big cores; an earlier 18.9 tok/s figure was not reproduced): [log](logs/2026-09-24_llm-decode-cross-chip-and-rk1-npu.md)
- TensorRT on both Orins; the NX's DLA cores exist in the device tree but TensorRT cannot use them: [log](logs/2026-09-24_tensorrt-dla-orin.md)
- RK1 Mali GPU (OpenCL works, Vulkan does not) and hardware video encode on all three chips: [log](logs/2026-09-24_mali-opencl-and-video-encode.md)
- Energy per token on both Orins (about 0.51 J each on the same model): [log](logs/2026-09-24_jetson-energy-per-token.md)
- Inter-node network: 941 Mbit/s on every pair, 0.14 ms Jetson-to-Jetson: [log](logs/2026-09-24_cluster-network-1gbe.md)
- NFS share of the RK1 NVMe: wire-limited, checksum-clean: [log](logs/2026-09-24_nfs-share-from-node1.md)

## Method in one paragraph

Nothing counts as a result without a dated log. Statuses never claim more than their evidence: `WORKS` needs measurements on this unit. Counts are always reported with denominators, cold and warm restarts are never mixed, and irreversible operations (firmware, fuses) are preceded by a verified backup and a tested restore. Details in [METHODOLOGY](docs/METHODOLOGY.md).

## Limits of this study

One board, one unit of each module, a consumer laptop as the driving host. Nothing here is a statement about the wider population of boards or modules. Storage figures are from three-repetition fio runs; other figures may still be single runs and are indicative only.

## Reproducing

```bash
python3 scripts/render_matrix.py          # regenerate MATRIX.md from the CSV data
python3 scripts/render_matrix.py --check  # CI-style: fail if MATRIX.md is stale
```

## License

MIT, see [LICENSE](LICENSE).
