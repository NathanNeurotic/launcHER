#!/bin/sh
# usage: run_lh.sh NAME ELF TIER(t1|t2) MODE(interp|rec) [LINGER] [extra run_tier args...]
# One emulator run of a launcHER build on the ATA image; appends a summary
# line to runs.log.  Tier 2 dumps kernel+low RAM, the live core and the staging
# area at the end.  Fail markers do NOT include POPS's own "TLB Miss, pc=0xf7..."
# lines.  Environment: AFTER (text the markers are looked for after; default the
# trace build's "Transferring control to trampoline"; a release build has no
# trace lines, use AFTER="SDR driver version"), MARKER (default "Interlaced
# (FIELD)"), TIMEOUT (default 200).
S="<scratch>"
A="$S/authors/handoff-impl"
export TMP="$(cygpath -w $S/tmp-handoff-impl)" TEMP="$(cygpath -w $S/tmp-handoff-impl)" PYTHONDONTWRITEBYTECODE=1
NAME="$1"; ELF="$2"; TIER="$3"; MODE="$4"; LINGER="${5:-8}"
shift 5 2>/dev/null || shift $#
SET=""
[ "$MODE" = "interp" ] && SET="--set EmuCore/CPU/Recompiler:EnableEE=false"
cd "$S/pcsx2-tier" || exit 3
if [ "$TIER" = "t1" ]; then
  python run_tier.py --elf "$ELF" --gameargs "ata:/POPS/TEST.VCD" --hdd-image images/hdd_fat32_vmc.img \
    --timeout 150 $SET --marker "Transferring control to trampoline" --fail-marker "[ps2rig] exit=1" \
    --name "impl-$NAME" --tail 3 "$@" > "$A/logs/run_$NAME.txt" 2>&1
else
  python run_tier.py --elf "$ELF" --gameargs "ata:/POPS/TEST.VCD" --hdd-image images/hdd_fat32_vmc.img \
    --timeout "${TIMEOUT:-200}" $SET --after "${AFTER:-Transferring control to trampoline}" \
    --marker "${MARKER:-Interlaced (FIELD)}" \
    --fail-marker "Trap exception at" --fail-marker "[ps2rig] exit=1" --fail-marker "TLB Miss, pc=0x0 " \
    --fail-marker "Jump to unaligned" --linger "$LINGER" \
    --dump 80000000:100000 --dump 200000:302e60 --dump 1000000:302e60 --name "impl-$NAME" --tail 3 "$@" \
    > "$A/logs/run_$NAME.txt" 2>&1
fi
RC=$?
RUN=$(ls -d "$S"/pcsx2-tier/runs/*"impl-$NAME" | tail -1)
rm -f "$RUN/hdd.raw"
echo "$(date +%H:%M:%S) $NAME tier=$TIER mode=$MODE rc=$RC run=$(basename "$RUN") $(grep -E 'verdict' "$A/logs/run_$NAME.txt" | cut -c1-80)" >> "$A/runs.log"
tail -1 "$A/runs.log"
