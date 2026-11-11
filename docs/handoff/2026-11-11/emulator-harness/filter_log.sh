#!/bin/sh
# usage: filter_log.sh <emulog.txt>  - launcHER/POPS part of a run without the I/O chatter, duplicates collapsed
awk '/ELF host:.* with entry/{f=1} f' "$1" | grep -v "open name\|Unknown device\|open fd\|# Initialize\|Known devices\|POPS config\|MODULE_.*not found\|POPS_READ_FAIL stage=open\|DEV9: \|RegisterLibraryEntries\|^\[ *[0-9.]*\] *$" | awk '{k=substr($0,14)} k!=prev{print} {prev=k}' | cut -c1-${2:-230}
