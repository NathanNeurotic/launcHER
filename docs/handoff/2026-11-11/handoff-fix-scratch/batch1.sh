#!/bin/sh
# Final-build emulator batch, one run at a time: Tier 1 x3 (recompiler),
# Tier 2 x3 (interpreter), both on the trace build v2.
A="<scratch>/handoff-impl"
E="$A/elfs/v2-trace.elf"
for i in 1 2 3; do sh "$A/run_lh.sh" "v2-t1-rec-$i" "$E" t1 rec; done
for i in 1 2 3; do sh "$A/run_lh.sh" "v2-t2-interp-$i" "$E" t2 interp 8; done
tasklist | grep -i pcsx2 || echo "no pcsx2 process at all"
