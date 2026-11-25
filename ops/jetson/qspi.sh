#!/bin/bash
# Direct (no temporary-Linux) boot-flash (QSPI) tools for the ONE Jetson in recovery mode.
# Uses NVIDIA's first-stage loader only. The NVMe is never touched.
#   ./qspi.sh prepare  - detect the module + build NVIDIA's command file (writes NOTHING to the module)
#   ./qspi.sh dump     - READ every QSPI partition to ~/turing-pi/jetson/qspi-backup-<TARGET> (read-only)
# Everything is logged to ~/turing-pi/jetson/qspi.log
set -euo pipefail
L4T="$HOME/turing-pi/jetson/Linux_for_Tegra"
BL="$L4T/bootloader"
CFG="$BL/generic/cfg/flash_t234_qspi.xml"
TARGET="${TARGET:?Set which module first: TARGET=nano or TARGET=nx  (e.g. TARGET=nx ./qspi.sh dump)}"
OUT="$HOME/turing-pi/jetson/qspi-backup-$TARGET"
LOG="$HOME/turing-pi/jetson/qspi.log"
BOARD="jetson-orin-nano-devkit-super-qspi"

one_in_recovery() {
    [ "$(lsusb | grep -c '0955:7[35]23')" = 1 ] || { echo "Need exactly ONE Jetson in recovery mode."; exit 1; }
}

case "${1:-}" in
prepare)
    one_in_recovery
    cd "$L4T"
    sudo ./flash.sh --no-flash "$BOARD" internal 2>&1 | tee -a "$LOG"
    [ -s "$BL/flashcmd.txt" ] && echo "OK: command file ready: $BL/flashcmd.txt"
    ;;
dump)
    [ -s "$BL/flashcmd.txt" ] || { echo "Run './qspi.sh prepare' first."; exit 1; }
    one_in_recovery
    mkdir -p "$OUT"
    sudo -v
    python3 - "$BL" "$CFG" "$OUT" "$LOG" <<'PY' 2>&1 | tee -a "$LOG"
import subprocess, sys, os, hashlib
import xml.etree.ElementTree as ET
bl, cfg, out, log = sys.argv[1:5]
base = open(os.path.join(bl, "flashcmd.txt")).read().strip()
i = base.rfind('--cmd "')
if i < 0:
    sys.exit("no --cmd found in flashcmd.txt")
j = base.find('"', i + 7)
parts, inst = [], "0"
for d in ET.parse(cfg).getroot().iter("device"):
    if d.attrib.get("type") != "spi":
        continue
    inst = d.attrib.get("instance", "0")
    for p in d.iter("partition"):
        s = (p.find("size").text or "").strip()
        if p.attrib["name"] == "secondary_gpt" or not s:
            continue
        parts.append((p.attrib["name"], int(s, 0)))

def run(shell_cmd):
    return subprocess.run(["sudo", "bash", "-c", "cd '%s' && %s" % (bl, shell_cmd)],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

# 1) Start the module ONCE the way NVIDIA's tool does (this also reads BCT).
sess = os.path.join(out, "BCT.bin")
print("== starting module session (reads BCT)", flush=True)
r = run(base[:i] + '--cmd "read BCT %s"' % sess + base[j + 1:])
if not (os.path.exists(sess) and os.path.getsize(sess) == 1048576):
    print(r.stdout[-2500:])
    sys.exit("FAILED to start the session. Power-cycle the module into recovery mode and try again.")
print("   session OK", flush=True)

# 2) Read every partition with the low-level reader, in the same session.
ok, bad = ["BCT"], []
for name, size in parts:
    if name == "BCT":
        continue
    dst = os.path.join(out, name + ".bin")
    r = run("./tegradevflash_v2 --read /spi/%s/%s '%s'" % (inst, name, dst))
    got = os.path.getsize(dst) if os.path.exists(dst) else -1
    if got == size:
        print("   OK   %-22s %d bytes" % (name, size), flush=True)
        ok.append(name)
    else:
        print("   FAIL %-22s got=%s expected=%s" % (name, got, size), flush=True)
        print(r.stdout[-500:], flush=True)
        bad.append(name)
        if len(bad) >= 3:
            print("Three partitions failed, stopping.")
            break
subprocess.run(["sudo", "chown", "-R", str(os.getuid()), out])
with open(os.path.join(out, "SHA256SUMS"), "w") as f:
    for name in ok:
        dst = os.path.join(out, name + ".bin")
        f.write("%s  %s\n" % (hashlib.sha256(open(dst, "rb").read()).hexdigest(), name + ".bin"))
total = len(parts) + (0 if any(n == "BCT" for n, _ in parts) else 1)
print("\nSUMMARY: %d partitions read OK, %d failed: %s" % (len(ok), len(bad), bad))
sys.exit(0 if not bad else 1)
PY
    ;;
flash)
    # Writes ONLY the module's boot flash (QSPI). The NVMe is never touched.
    one_in_recovery
    # 1) the verified backup must exist and be intact
    ( cd "$OUT" && [ "$(ls -1 *.bin | wc -l)" -ge 60 ] && sha256sum -c --quiet SHA256SUMS ) \
        || { echo "Backup missing or damaged in $OUT. Run './qspi.sh dump' first."; exit 1; }
    # 2) Turing's required carrier-EEPROM setting must be applied (this board has no carrier EEPROM)
    for f in "$BL/tegra234-mb2-bct-common.dtsi" "$BL/generic/BCT/tegra234-mb2-bct-misc-p3767-0000.dts"; do
        grep -q "cvb_eeprom_read_size = <0x0>" "$f" \
            || { echo "EEPROM setting not applied in $f"; echo "Apply it first (see the instructions from Claude)."; exit 1; }
    done
    echo "Backup verified. EEPROM setting applied."
    echo "This writes the module's boot flash (QSPI) only. The NVMe is not touched."
    read -r -p "Type FLASH to continue: " ans
    [ "$ans" = "FLASH" ] || { echo "Cancelled."; exit 1; }
    cd "$L4T"
    sudo ./flash.sh "$BOARD" internal 2>&1 | tee -a "$LOG"
    ;;
*) echo "usage: $0 prepare|dump|flash"; exit 2 ;;
esac
