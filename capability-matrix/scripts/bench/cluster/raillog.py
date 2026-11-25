#!/usr/bin/env python3
"""1 Hz rail logger. Runs on each Orin for the whole ramp; sliced by arm timestamps later."""
import time, sys
HW = "/sys/bus/i2c/devices/1-0040/hwmon/hwmon3"
out = open(sys.argv[1], "w", buffering=1)
out.write("ts,vdd_in,cpu_gpu,soc\n")
while True:
    v = []
    for i in (1, 2, 3):
        try:
            v.append(int(open(f"{HW}/in{i}_input").read()) * int(open(f"{HW}/curr{i}_input").read()) / 1e6)
        except Exception:
            v.append("")
    out.write("%.1f,%s\n" % (time.time(), ",".join(f"{x:.3f}" if x != "" else "" for x in v)))
    time.sleep(1.0)
