#! /bin/sh
cat /sys/class/power_supply/BAT0/power_now 
E1=$(cat /sys/class/powercap/intel-rapl:0/energy_uj)
sleep 1
E2=$(cat /sys/class/powercap/intel-rapl:0/energy_uj)
echo "scale=2; ($E2 - $E1)/1000000" | bc
