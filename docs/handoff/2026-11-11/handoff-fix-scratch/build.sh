#!/bin/sh
# usage: build.sh TAG   -> builds release (build-handoff) and trace (build-handoff-trace)
# inside the worktree in Docker, logs to logs/build-TAG-{release,trace}.log,
# copies the ELFs to elfs/TAG-{release,trace}[_unc].elf and prints sizes, hashes
# and warning-line counts.
S="<scratch>"
A="$S/authors/handoff-impl"
W="the handoff worktree"
TAG="$1"
mkdir -p "$A/elfs" "$A/logs"
build() {
  dir="$1"; kind="$2"; flags="$3"
  MSYS_NO_PATHCONV=1 docker run --rm -v "$(cygpath -w "$W"):/workspace" -w /workspace \
    ghcr.io/ps2homebrew/ps2homebrew:main sh -c \
    "apk add cmake >/dev/null 2>&1; git config --global --add safe.directory /workspace; which python3; python3 --version; cmake -B $dir $flags && cmake --build $dir --target launcHER" \
    > "$A/logs/build-$TAG-$kind.log" 2>&1
  rc=$?
  echo "$kind rc=$rc warning lines: $(grep -c 'warning:' "$A/logs/build-$TAG-$kind.log")"
  grep -E "handoff layout|Checking the POPS handoff|Built target launcHER|error" "$A/logs/build-$TAG-$kind.log" | head -20
  if [ $rc -eq 0 ]; then
    cp "$W/$dir/release/launcHER.elf" "$A/elfs/$TAG-$kind.elf"
    cp "$W/$dir/launcher/launcher_unc.elf" "$A/elfs/$TAG-${kind}_unc.elf"
    ls -l "$A/elfs/$TAG-$kind.elf" "$A/elfs/$TAG-${kind}_unc.elf" | awk '{print $5, $9}'
    sha256sum "$A/elfs/$TAG-$kind.elf" "$A/elfs/$TAG-${kind}_unc.elf"
  fi
}
build build-handoff release ""
build build-handoff-trace trace "-DLAUNCHER_BOOT_TRACE=ON -DDEBUG=ON"
cd "$W" && git status --short | head -30
