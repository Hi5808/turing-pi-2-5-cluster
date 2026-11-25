#!/bin/bash
# A/B cold-start model load: NFS vs local NVMe. Caches dropped before each so neither is favoured.
# $1 = model basename, $2 = user
MODEL="$1"; U="$2"
BIN="$3"          # binary path differs per node; pass it in rather than assume
PAT="llama-server"          # held in a var so pkill cannot match this script's own command line
ARGS="--host 0.0.0.0 --port 8101 -c 8192 --parallel 8 --cache-ram 0 -ngl 99"

stop(){ pkill -f "$PAT" 2>/dev/null; sleep 3; }
cold(){ sync; echo 3 > /proc/sys/vm/drop_caches; sleep 2; }

timeit(){   # $1 = model path, $2 = label
  stop; cold
  local t0 t1
  t0=$(date +%s.%N)
  sudo -u "$U" env LD_LIBRARY_PATH="$(dirname "$BIN")" nohup $BIN -m "$1" $ARGS >/tmp/ls_$2.log 2>&1 &
  for i in $(seq 1 400); do
    code=$(curl -s -m 2 -o /dev/null -w "%{http_code}" http://127.0.0.1:8101/health 2>/dev/null)
    [ "$code" = "200" ] && break
    sleep 0.5
  done
  t1=$(date +%s.%N)
  echo "$2 ready in $(echo "$t1 - $t0" | bc) s"
}

timeit "/mnt/share/models/$MODEL" nfs
timeit "/home/$U/models/$MODEL" local

# leave the node serving the LOCAL model
stop
sudo -u "$U" env LD_LIBRARY_PATH="$(dirname "$BIN")" setsid nohup $BIN -m "/home/$U/models/$MODEL" $ARGS >/tmp/llama_local.log 2>&1 < /dev/null &
sleep 2
echo "restarted on local model"
