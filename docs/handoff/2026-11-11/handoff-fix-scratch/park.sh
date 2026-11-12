#!/bin/sh
# usage: park.sh lh ELF NAME | park.sh control NAME
# Experiment aid: park POPS at its first instruction (a `b .` poked through
# PINE: into the staged core for launcHER, into 0x200000 for POPStarter) and
# dump kernel RAM, the scratch folder and some hardware registers a few seconds
# later.  EE interpreter.  The parked run never reaches POPS's own code.
S="<scratch>"
A="$S/authors/handoff-impl"
export TMP="$(cygpath -w $S/tmp-handoff-impl)" TEMP="$(cygpath -w $S/tmp-handoff-impl)" PYTHONDONTWRITEBYTECODE=1
DUMPS="--dump 80000000:100000 --dump 70000000:4000 --dump 200000:302e60 --dump 1000f000:20 --dump 1000e000:20 --dump 1000c000:10 --dump 1000c400:10 --dump 10000000:20 --dump 10000800:20 --dump 10001000:20 --dump 10001800:20"
cd "$S/pcsx2-tier" || exit 3
if [ "$1" = "lh" ]; then
  NAME="$3"
  python run_tier.py --elf "$2" --gameargs "ata:/POPS/TEST.VCD" --hdd-image images/hdd_fat32_vmc.img \
    --timeout 200 --set EmuCore/CPU/Recompiler:EnableEE=false \
    --poke-on "POPS: Rebooting IOP with external image" --poke 1000008=1000ffff --poke 100000c=0 \
    --poke-repeat 60 --poke-interval 0.005 \
    --after "Transferring control to trampoline" --marker "# Restart Without Memory Clear Done." \
    --fail-marker "Trap exception at" --fail-marker "[ps2rig] exit=1" --linger 5 \
    $DUMPS --name "impl-$NAME" --tail 6 > "$A/logs/run_$NAME.txt" 2>&1
else
  NAME="$2"
  python run_tier.py --elf control/XX.TEST.ELF --usb-image images/fat32_pak.img \
    --timeout 200 --set EmuCore/CPU/Recompiler:EnableEE=false \
    --poke-on "USBHDFSD: connect: devId=2" --poke 200000=1000ffff --poke 200004=0 \
    --poke-repeat 700 --poke-interval 0.005 \
    --after "USBHDFSD: connect: devId=2" --marker "# Restart Without Memory Clear Done." \
    --fail-marker "Trap exception at" --linger 5 \
    $DUMPS --name "impl-$NAME" --tail 6 > "$A/logs/run_$NAME.txt" 2>&1
fi
RC=$?
RUN=$(ls -d "$S"/pcsx2-tier/runs/*"impl-$NAME" | tail -1)
rm -f "$RUN/hdd.raw" "$RUN/usb.img"
echo "$(date +%H:%M:%S) $NAME park rc=$RC run=$(basename "$RUN") $(grep -E 'verdict|poked' "$A/logs/run_$NAME.txt" | tr '\n' ' ' | cut -c1-150)" >> "$A/runs.log"
tail -1 "$A/runs.log"
