#!/bin/bash
# Works on whichever ONE Jetson is currently in recovery mode (NX 0955:7323 or Nano 0955:7523).
#   ./jetson.sh rootfs   - one-time: unpack NVIDIA's sample root filesystem (sudo)
#   ./jetson.sh check    - which Jetson is visible in recovery mode? (no sudo, read-only)
#   ./jetson.sh backup   - back up its boot flash (sudo, READ-ONLY on the module)
#   ./jetson.sh flash    - write new boot flash (sudo, QSPI ONLY, never touches the NVMe)
set -euo pipefail
L4T="$HOME/turing-pi/jetson/Linux_for_Tegra"
IMAGES="$L4T/tools/backup_restore/images"
BOARD_BACKUP="jetson-orin-nano-devkit-super"
BOARD_FLASH="jetson-orin-nano-devkit-super-qspi"
one_in_recovery() {
    [ "$(lsusb | grep -c '0955:7[35]23')" = 1 ] || { echo "Need exactly ONE Jetson in recovery mode (see: ./jetson.sh check)."; exit 1; }
}
case "${1:-}" in
rootfs)
    # One-time: NVIDIA's backup/flash tools build their temporary flasher image
    # from this sample root filesystem. qemu-user-static is called
    # qemu-user-binfmt on this Ubuntu.
    RFS="$HOME/turing-pi/jetson/Tegra_Linux_Sample-Root-Filesystem_R39.2.0_aarch64.tbz2"
    [ -f "$RFS" ] || { echo "Root filesystem download not finished: $RFS"; exit 1; }
    sudo apt-get install -y qemu-user-binfmt binfmt-support
    cd "$L4T/rootfs"
    sudo tar xpf "$RFS"
    cd "$L4T"
    sudo ./apply_binaries.sh
    echo "rootfs ready." ;;
check)
    lsusb | grep -E "0955:7[35]23" || { echo "No Jetson in recovery mode seen."; exit 1; } ;;
backup)
    one_in_recovery
    cd "$L4T"
    sudo systemctl stop udisks2.service || true
    sudo service nfs-kernel-server start || true
    sudo ./tools/backup_restore/l4t_backup_restore.sh -b "$BOARD_BACKUP"
    echo "Backup written to: $IMAGES" ;;
flash)
    [ -d "$IMAGES" ] && [ -n "$(ls -A "$IMAGES" 2>/dev/null)" ] || { echo "No backup in $IMAGES. Run './jetson.sh backup' first."; exit 1; }
    one_in_recovery
    echo "This writes the boot flash (QSPI) only. The NVMe is not touched."
    read -r -p "Backup exists. Type FLASH to continue: " ans
    [ "$ans" = "FLASH" ] || { echo "Cancelled."; exit 1; }
    cd "$L4T"
    sudo ./flash.sh "$BOARD_FLASH" internal ;;
*) echo "usage: $0 check|backup|flash"; exit 2 ;;
esac
