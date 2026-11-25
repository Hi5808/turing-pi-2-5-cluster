#!/bin/bash
# Node 2 (Orin NX 16GB) QSPI-only work. Run steps in order, in your own terminal:
#   ./node2.sh prereqs  - install NVIDIA's helper packages once (sudo, apt)
#   ./node2.sh check    - is node 2 visible in recovery mode? (no sudo, read-only)
#   ./node2.sh backup   - back up node 2's boot flash (sudo, READ-ONLY on the module)
#   ./node2.sh flash    - write new boot flash (sudo, QSPI ONLY, never touches the NVMe)
set -euo pipefail
L4T="$HOME/turing-pi/jetson/Linux_for_Tegra"
IMAGES="$L4T/tools/backup_restore/images"
BOARD_BACKUP="jetson-orin-nano-devkit-super"
BOARD_FLASH="jetson-orin-nano-devkit-super-qspi"

case "${1:-}" in
prereqs)
    # NVIDIA's own script asks for qemu-user-static, which no longer exists by
    # that name on this Ubuntu and is not needed for QSPI/backup. Install only
    # the four packages this laptop is actually missing.
    sudo apt-get install -y abootimg lbzip2 whois python3-usb
    ;;
check)
    lsusb | grep -E "0955:7[35]23" || { echo "No Jetson in recovery mode seen."; exit 1; }
    ;;
backup)
    lsusb | grep -q "0955:7323" || { echo "Node 2 not in recovery mode. Run: tpi usb flash -n 2"; exit 1; }
    [ "$(lsusb | grep -c '0955:7[35]23')" = 1 ] || { echo "Need exactly ONE Jetson in recovery mode."; exit 1; }
    cd "$L4T"
    sudo systemctl stop udisks2.service || true
    sudo service nfs-kernel-server start || true
    sudo ./tools/backup_restore/l4t_backup_restore.sh -b "$BOARD_BACKUP"
    echo "Backup written to: $IMAGES"
    ;;
flash)
    [ -d "$IMAGES" ] && [ -n "$(ls -A "$IMAGES" 2>/dev/null)" ] || { echo "No backup in $IMAGES. Run './node2.sh backup' first."; exit 1; }
    lsusb | grep -q "0955:7323" || { echo "Node 2 not in recovery mode. Run: tpi usb flash -n 2"; exit 1; }
    echo "This writes node 2's boot flash (QSPI) only. The NVMe is not touched."
    read -r -p "Backup exists. Type FLASH to continue: " ans
    [ "$ans" = "FLASH" ] || { echo "Cancelled."; exit 1; }
    cd "$L4T"
    sudo ./flash.sh "$BOARD_FLASH" internal
    ;;
*)
    echo "usage: $0 check|backup|flash"; exit 2 ;;
esac
