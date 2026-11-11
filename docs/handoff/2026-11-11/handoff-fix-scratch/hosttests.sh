#!/bin/sh
# usage: hosttests.sh TAG [with|without|both]
# Runs every tools/test_*.py of the worktree, one after the other, without and
# with the reference inputs; one summary line per file in logs/host_TAG.txt.
S="<scratch>"
A="$S/authors/handoff-impl"
W="the handoff worktree"
mkdir -p "$S/tmp-handoff-impl" "$A/logs/host"
export TMP="$(cygpath -w $S/tmp-handoff-impl)" TEMP="$(cygpath -w $S/tmp-handoff-impl)" PYTHONDONTWRITEBYTECODE=1
TAG="$1"; WHICH="${2:-both}"
OUT="$A/logs/host_$TAG.txt"
: > "$OUT"
cd "$W" || exit 3
run_all() {
  MODE="$1"
  for f in tools/test_*.py; do
    b=$(basename "$f" .py)
    python "$f" > "$A/logs/host/${TAG}_${MODE}_$b.txt" 2>&1
    rc=$?
    echo "$MODE $b rc=$rc $(grep -E '^Ran |^OK|^FAILED' "$A/logs/host/${TAG}_${MODE}_$b.txt" | tr '\n' ' ')" >> "$OUT"
  done
}
if [ "$WHICH" != "with" ]; then
  unset POPS_TEST_ELF POPSTARTER_TEST_ELF POPS_HANDOFF_ELF
  run_all without
fi
if [ "$WHICH" != "without" ]; then
  export POPS_TEST_ELF="<workspace>/POPS/POPS.ELF"
  export POPSTARTER_TEST_ELF="<workspace>/POPSLoader/bin/POPSLDR/PROFILES/MAIN/POPSTARTER.ELF"
  [ -n "$HANDOFF_ELF" ] && export POPS_HANDOFF_ELF="$HANDOFF_ELF"
  run_all with
fi
echo "done $(date +%H:%M:%S) fail=$(grep -vc 'rc=0 ' "$OUT")" >> "$OUT"
cd "$W" && git status --short | grep -vE '^( M|\?\?|M |A ) ' >> "$OUT"
