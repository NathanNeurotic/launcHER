#!/bin/sh
# usage: make_fat_image.sh <out.img> <size MiB> <stage dir>   (run inside an alpine container)
# MBR with one FAT32 (type 0x0C) partition at 1 MiB; copies <stage dir>/* to the root.
set -e
OUT="$1"; SIZE="$2"; STAGE="$3"
apk add --no-progress dosfstools mtools sfdisk >/dev/null 2>&1
rm -f "$OUT"
dd if=/dev/zero of="$OUT" bs=1M count="$SIZE" status=none
echo 'start=2048, type=c' | sfdisk -q "$OUT"
SECTORS=$(( SIZE * 2048 - 2048 ))
mkfs.fat -F 32 -n TIER --offset 2048 "$OUT" $(( SECTORS / 2 )) >/dev/null
export MTOOLS_SKIP_CHECK=1
mcopy -s -i "$OUT@@1M" "$STAGE"/* ::/
mdir -/ -i "$OUT@@1M" ::/
sfdisk -l "$OUT"
