# BDM FatFs compatibility work

Baseline copied from ps2dev/ps2sdk commit
`3304cd864748ce40b1ff9fb41cc5a700f5e573a0`, directory
`iop/fs/bdmfs_fatfs/src`. The accompanying LICENSE is the SDK's AFL-2.0
license. Copyright notices are retained. This checkpoint is unmodified source;
it is not built or selected by launcHER yet.

The corresponding FatFs dependency is fjtrujy/FatFs, branch `iop-r0.16`,
pinned to commit `18cc3d9e07473a6aa3d783a66224b243a7b4974c`.
Archive: https://codeload.github.com/fjtrujy/FatFs/tar.gz/18cc3d9e07473a6aa3d783a66224b243a7b4974c
SHA256: `ef0ce9710869f1932c328c5c4b07a707fdf08fa72e203f1fb1fa9ef67e288b81`.
FatFs retains its own permissive license in its source files.

Physical configuration probe `20261014T075656-0033` gets past unavailable
optional global cards, then fails on an absent ATA PATCHES.TXT with errno 4.
The SDK driver returns raw negative FRESULT values instead of errno and hides
read/write/readdir failures as zero. Correct that boundary rather than treating
errno 4 as a missing file in the EE configuration parser. Also preserve
exclusive creation semantics before testing real VMC creation.

Next: translate each FatFs API result to negative errno, propagate stream
failures, test missing paths versus actual I/O faults, build a pinned module,
and repeat the read-only configuration probe. No Sony data belongs here.
