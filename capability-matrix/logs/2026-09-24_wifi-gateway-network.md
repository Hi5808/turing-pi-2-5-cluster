# Turning one node into the gateway for a four-slot cluster board: shared Wi-Fi without a router cable

**Platform:** Turing Pi 2.5.1 (BMC 2.3.2). Turing RK1 in slot 1 as gateway with a USB Wi-Fi adapter; Jetson Orin NX (slot 2) and Orin Nano (slot 3) as clients; BMC on the board's managed switch
**Software stack:** Ubuntu 24.04.1 (RK1, kernel 6.1.0-1025-rockchip), `dnsmasq`, `nftables`, `netplan`/`systemd-networkd`, NetworkManager on the Jetsons
**Date:** September 2026

## Problem

The board had no Ethernet route to a router. Its nodes and its BMC were reachable only through a wired connection shared from a laptop, and the laptop had to stay connected for the nodes to have internet access.

## Design

One node with a working uplink provides everything the others need, on a dedicated range:

- Gateway node: static address on the board's switch network, forwarding enabled, `nftables` masquerade out of the Wi-Fi interface, and `dnsmasq` for DHCP and DNS (upstream resolvers taken from the node's own Wi-Fi configuration).
- Fixed addresses for the BMC and both Jetsons **by hardware address**.
- A temporary alias address on the old range on the gateway so it could still reach not-yet-migrated hosts during the switch.
- The laptop changed from "sharing" to an ordinary DHCP client; the sharing profile was kept, disabled, as the undo path.
- Clients told to keep asking for an address indefinitely, so a full-board power-up works even if they start before the gateway's DHCP is ready.

## Migration (what was done, in order)

1. Prepare the gateway with services stopped and the address change not yet applied.
2. Apply the gateway's addresses; verify it still reaches the old-range hosts through the alias.
3. Start DHCP on the gateway; switch the laptop to client mode.
4. Renew node 3, then node 2, each through the gateway as a jump host; check address, default route, DNS and internet from each.
5. Renew the BMC's address by signalling its DHCP client (release, then discover).
6. Reboot the gateway; verify addresses, forwarding, NAT and DHCP return by themselves.

## Results

| Check | Result |
|---|---|
| Each node's default route and DNS | via the gateway |
| Internet reachability from nodes 2 and 3 (HTTPS) | HTTP 200 through the gateway's Wi-Fi |
| Gateway reboot | services return unaided; node 3 kept internet through it |
| Full-board cold start ([log](2026-09-24_full-board-reboot-integrity.md)) | gateway answers 34 s after power-on; the BMC obtains its reserved address from it at the same time |
| Uplink quality | 5 GHz, negotiated 867 Mbit/s, about -59 dBm |

## Findings worth keeping

- **Interface names are not stable across boots** on the RK1 (`end0` and `end1` both occurred), so addressing is matched by pattern/MAC, never by name.
- The BMC's DHCP client is BusyBox `udhcpc`; a release (USR2) followed by a discover (USR1) moved it to its new address without a BMC reboot.
- Two independent paths to the BMC when the router side is down: through the gateway node over Wi-Fi, and directly over IPv6 link-local from a wired PC. The wired PC's IPv6 must be enabled on that interface for the second path to work (it had been disabled and had to be re-enabled).
- A jump-host SSH (`-J`) does not apply per-hop options given with `-o`; use an explicit `ProxyCommand` when host-key policy must apply to the jump hop as well.

## Limits

- Throughput and latency through the gateway were **not** measured; only reachability and address assignment.
- The design has a single point of failure: the gateway's Wi-Fi link.
- No firewalling beyond NAT was configured.
