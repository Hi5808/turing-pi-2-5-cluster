#!/bin/bash
# 300 s all-core sysbench load; sample every 5 s
OUT=/mnt/nvme/soak_rk1.csv
echo "t_s,soc_C,bigcore0_C,bigcore1_C,little_C,npu_C,gpu_C,cpu4_MHz,cpu0_MHz,fan_pwm" > $OUT
sysbench cpu --cpu-max-prime=200000 --threads=8 --time=300 run > /mnt/nvme/soak_rk1_sysbench.txt 2>&1 &
SP=$!
t=0
while kill -0 $SP 2>/dev/null; do
  r(){ echo $(( $(cat $1) / 1000 )); }
  echo "$t,$(r /sys/class/hwmon/hwmon0/temp1_input),$(r /sys/class/hwmon/hwmon1/temp1_input),$(r /sys/class/hwmon/hwmon2/temp1_input),$(r /sys/class/hwmon/hwmon3/temp1_input),$(r /sys/class/hwmon/hwmon6/temp1_input),$(r /sys/class/hwmon/hwmon5/temp1_input),$(( $(cat /sys/devices/system/cpu/cpu4/cpufreq/scaling_cur_freq) / 1000 )),$(( $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq) / 1000 )),$(cat /sys/class/hwmon/hwmon8/pwm1 2>/dev/null)" >> $OUT
  sleep 5; t=$((t+5))
done
echo SOAK_DONE >> $OUT
