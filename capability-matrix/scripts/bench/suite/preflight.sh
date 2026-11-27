#!/bin/bash
# Validate instrumentation and flags BEFORE any arm runs. Every check here exists because its
# absence once produced a plausible-looking wrong number -- see PITFALLS.md.
# Usage:  bash preflight.sh <node>        where node is node1 | orinnx | orin1
# Exit 0 = safe to run the suite on that node. Non-zero = do not run; the numbers would be junk.
set -u
NODE="${1:?usage: preflight.sh <node1|orinnx|orin1>}"
FAIL=0
ok   () { printf "  OK    %s\n" "$1"; }
bad  () { printf "  FAIL  %s\n" "$1"; FAIL=1; }
warn () { printf "  warn  %s\n" "$1"; }

echo "=== preflight: $NODE ==="

# ---- instrumentation paths (pitfall 4: a missing path reads as 0 and looks like throttling) ----
case "$NODE" in
  orinnx|orin1)
    RAIL=/sys/bus/i2c/devices/1-0040/hwmon/hwmon3
    for f in in1_input curr1_input; do
      [ -r "$RAIL/$f" ] && ok "rail $f readable" || bad "rail $f MISSING ($RAIL)"
    done
    [ -r /sys/class/devfreq/17000000.gpu/cur_freq ] \
      && ok "GPU clock path (/sys/class/devfreq/17000000.gpu/cur_freq)" \
      || bad "GPU clock path missing -- do NOT use /sys/devices/17000000.gpu/devfreq/..., it does not exist here"
    [ -r /sys/devices/platform/gpu.0/load ] && ok "gpu.0/load readable" || bad "gpu.0/load missing"
    [ -r /sys/class/thermal/thermal_zone8/temp ] && ok "tj zone" || bad "thermal_zone8 (tj) missing"
    n=$(ls -d /sys/class/thermal/cooling_device* 2>/dev/null | wc -l)
    [ "$n" -gt 0 ] && ok "$n cooling devices" || bad "no cooling devices"
    ;;
  node1)
    [ -r /sys/class/thermal/thermal_zone0/temp ] && ok "soc thermal zone" || bad "thermal_zone0 missing"
    warn "node1 exposes NO power rails -- energy claims are impossible here, by design"
    for c in 0 4; do
      p=/sys/devices/system/cpu/cpu$c/cpufreq/cpuinfo_max_freq
      [ -r "$p" ] && ok "cpu$c max $(( $(cat $p)/1000 )) MHz" || bad "cpu$c cpufreq missing"
    done
    # pitfall: an 8-thread budget spans 4x A55 + 4x A76 and makes per-core reasoning meaningless
    a55=$(grep -c "0xd05" /proc/cpuinfo); a76=$(grep -c "0xd0b" /proc/cpuinfo)
    [ "$a55" = 4 ] && [ "$a76" = 4 ] && ok "big.LITTLE 4x A55 (0xd05) + 4x A76 (0xd0b) as expected" \
      || warn "unexpected core mix: $a55 A55, $a76 A76 -- check the pinning in e2"
    ;;
esac

# ---- the CPU-only flag trap (pitfall 2) ----
BIN=""
for c in ~/llama.cpp-new/build/bin ~/llama.cpp/build/bin /mnt/nvme/llama-rpc-build/bin ~/llama-arm64/llama-b10533; do
  [ -x "$c/llama-completion" ] && { BIN="$c"; break; }
done
if [ -z "$BIN" ]; then
  warn "no llama-completion found; skipping backend checks"
else
  ok "llama binaries: $BIN"
  ls "$BIN" | grep -q "^libggml-cuda" && ok "CUDA backend present" \
    || warn "NO libggml-cuda.so -- this build is CPU-only and -ngl 99 is a SILENT NO-OP (this is what hid orin1 running on CPU for 3 months)"
  M=$(ls ~/models/*.gguf /mnt/nvme/share/models/*.gguf 2>/dev/null | head -1)
  if [ -n "${M:-}" ]; then
    dec () {  # $1 = extra flags ; echoes decode tok/s, parsed off the DECODE line only (pitfall 3)
      LD_LIBRARY_PATH="$BIN" "$BIN/llama-completion" -m "$M" $1 -p hi -n 32 \
        --ignore-eos --no-warmup -st --no-display-prompt 2>&1 |
        grep -oP 'eval time =\s+[\d.]+ ms /\s+\d+ runs.*?\(\s*[\d.]+ ms per token,\s+\K[\d.]+'
    }
    t1=$(dec "-ngl 0 -dev none -t 1"); t4=$(dec "-ngl 0 -dev none -t 4")
    if [ -n "${t1:-}" ] && [ -n "${t4:-}" ]; then
      same=$(python3 -c "print(1 if abs($t4-$t1)/$t1 < 0.05 else 0)")
      [ "$same" = 1 ] \
        && bad "CPU-only decode is FLAT across thread counts ($t1 vs $t4) -- the knob is disconnected, you are not measuring the CPU" \
        || ok "CPU-only responds to -t: 1 thread $t1, 4 threads $t4 tok/s"
    else
      bad "could not parse decode rate -- check the regex anchors on 'runs' (pitfall 3)"
    fi
  else
    warn "no .gguf model found; skipping the flag check"
  fi
fi

# ---- shell hygiene the suite depends on (pitfalls 5, 6) ----
command -v bc >/dev/null && ok "bc present" || bad "bc missing (timings need it)"
command -v python3 >/dev/null && ok "python3 present" || bad "python3 missing"
sudo -n true 2>/dev/null && ok "passwordless sudo" || warn "sudo needs a password -- e3/e4/e5 stop and start the managed service and will stall"

echo
[ "$FAIL" = 0 ] && echo "PREFLIGHT PASS: $NODE" || echo "PREFLIGHT FAIL: $NODE -- fix the above before trusting any number"
exit "$FAIL"
