#!/bin/sh
# usage: analyse.sh RUN_FOLDER_NAME [CONTROL_RUN_FOLDER_NAME]
# Post-run analysis of one Tier 2 run: report words, thread table, log
# comparison with the control, live core vs staged core.
S="<scratch>"
A="$S/authors/handoff-impl"; V="$S/authors/handoff-vdyn"
export PYTHONDONTWRITEBYTECODE=1
R="$S/pcsx2-tier/runs/$1"
C="$S/pcsx2-tier/runs/${2:-20261111T060910-control-popstarter-interp}"
echo "=== $1"
echo "--- report words at 0x00084300"
python "$A/ksys.py" "$R/ee_80000000_100000.bin" words 80084300 8
echo "--- thread table"
python "$V/kstate.py" "$R/ee_80000000_100000.bin" > "$A/logs/kstate_$1.txt" 2>&1
grep -iE "current|count|thread|^ +[0-9]+ " "$A/logs/kstate_$1.txt" | head -24
echo "--- kstate diff vs control (handler lists, dispatch, syscalls)"
python "$V/kstate.py" "$C/ee_80000000_100000.bin" > "$A/logs/kstate_ctl_tmp.txt" 2>&1
diff "$A/logs/kstate_ctl_tmp.txt" "$A/logs/kstate_$1.txt" | head -40
echo "--- trace lines of interest"
grep -aE "licence at|Matched title|Handoff|Trap exception|TLB Miss|Jump to unaligned|tlb refill" "$R/emulog.txt" | cut -c1-140 | head -20
echo "--- cmplog vs control"
python "$V/cmplog.py" "$C/emulog.txt" "$R/emulog.txt" --show 40 2>&1 | head -80
echo "--- live core vs staged core"
python "$A/core_diff.py" "$R" --list 60 --watch 206c20:206ec0 --watch 207200:207280 --watch 201a30:201cd0
