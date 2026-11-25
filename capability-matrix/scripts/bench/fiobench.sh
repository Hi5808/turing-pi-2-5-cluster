#!/bin/bash
# usage: fiobench.sh <test-dir> <out-dir>   (file-based fio, direct I/O, 3 repetitions)
D=$1; O=$2; mkdir -p $D $O
F="--ioengine=libaio --direct=1 --time_based --runtime=20 --ramp_time=3 --group_reporting --filename=$D/fio.dat --size=4G --output-format=json"
DEV=$(findmnt -no SOURCE -T $D | sed 's/p\?[0-9]*$//')
T0=$(sudo -n nvme smart-log $DEV 2>/dev/null | awk -F: '/^temperature/{print $2}' | tr -d ' ')
echo "start $(date -Is) dev=$DEV temp=$T0" > $O/meta.txt
fio --name=prep --rw=write --bs=1M --size=4G --filename=$D/fio.dat --direct=1 --output-format=terse >/dev/null 2>&1
for rep in 1 2 3; do
  fio --name=seqread    --rw=read      --bs=1M --iodepth=32 $F --output=$O/r${rep}_seqread.json
  fio --name=seqwrite   --rw=write     --bs=1M --iodepth=32 $F --output=$O/r${rep}_seqwrite.json
  fio --name=randread1  --rw=randread  --bs=4k --iodepth=1  $F --output=$O/r${rep}_randread_qd1.json
  fio --name=randread32 --rw=randread  --bs=4k --iodepth=32 $F --output=$O/r${rep}_randread_qd32.json
  fio --name=randwrite1 --rw=randwrite --bs=4k --iodepth=1  $F --output=$O/r${rep}_randwrite_qd1.json
  fio --name=randwrite32 --rw=randwrite --bs=4k --iodepth=32 $F --output=$O/r${rep}_randwrite_qd32.json
done
T1=$(sudo -n nvme smart-log $DEV 2>/dev/null | awk -F: '/^temperature/{print $2}' | tr -d ' ')
echo "end $(date -Is) temp=$T1" >> $O/meta.txt
rm -f $D/fio.dat; echo done >> $O/meta.txt
