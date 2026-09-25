# Inter-node network on the Turing Pi 2.5: line-rate TCP on every pair, and a 0.11 ms Jetson-to-Jetson path

**Platform:** Turing Pi 2.5.1 (onboard switch); node 1 Turing RK1 (gateway, 10.43.0.1), node 2 Orin NX (10.43.0.12), node 3 Orin Nano (10.43.0.13)
**Software stack:** iperf3 (node 1 installed from Ubuntu; Jetsons' existing iperf3 service), Ubuntu 24.04.1 / JetPack 7.2
**Date:** September 2026

## Question

What is the fabric between the three nodes, since it bounds any model split across chips?

## Setup and method

`iperf3 -t 10` TCP, single stream and 4 streams (`-P4`) from node 1 to each Jetson, reverse direction (`-R`) for node 1 to each Jetson, and node 2 to node 3. Latency: 50 pings at 0.2 s interval per pair. The user's triage services were running. Raw output: `data/raw/net-2026-09-24/`.

## Results

| Path | TCP goodput (received) | Retransmits |
|---|---|---|
| Node 1 → node 2 (1 stream) | 941 Mbit/s | 0 |
| Node 2 → node 1 (reverse) | 941 Mbit/s | 0 |
| Node 1 → node 3 | 941 Mbit/s | 0 |
| Node 3 → node 1 (reverse) | 941 Mbit/s | 0 |
| Node 1 → node 2, 4 streams | 941 Mbit/s | 0 |
| Node 1 → node 3, 4 streams | 941 Mbit/s | 0 |
| Node 2 → node 3 | 941 Mbit/s | 0 |

| Pair | RTT min / avg / max (ms), 50 pings, 0% loss |
|---|---|
| Node 2 ↔ node 3 | 0.111 / 0.140 / 0.253 |
| Node 2 → node 1 | 0.247 / 0.261 / 0.395 |
| Node 1 → node 2 | 0.238 / 0.260 / 0.414 |
| Node 1 → node 3 | 0.202 / 0.255 / 0.400 |

## Findings

1. **Every pair reaches 1 GbE line rate (about 941 Mbit/s, roughly 117 MB/s) in both directions with no retransmits**; adding streams does not add throughput, so 1 GbE is the ceiling for any distributed workload. A single 1.2 GB model file therefore takes at least about 10 s to move between nodes.
2. **The Jetson-to-Jetson path is about twice as fast in latency (0.14 ms) as any path involving node 1 (0.26 ms).** The cause was not investigated (a different switch path, or the RK1's Ethernet driver and its gateway role).

## Limitations

TCP only, no UDP or jitter tests; concurrent multi-pair traffic (aggregate switch capacity) was not tested; latency measured with ping, not application-level; the RK1 was also the gateway (NAT/DHCP) during the tests, which were idle for WAN traffic.

## Reproduction

`iperf3` commands as above; results in `data/raw/net-2026-09-24/`.
