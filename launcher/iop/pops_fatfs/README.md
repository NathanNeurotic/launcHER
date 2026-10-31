# BDM FatFs compatibility work

Baseline copied from ps2dev/ps2sdk commit
`3304cd864748ce40b1ff9fb41cc5a700f5e573a0`, directory
`iop/fs/bdmfs_fatfs/src`. The accompanying LICENSE is the SDK's AFL-2.0
license. Copyright notices are retained; baseline whitespace was normalized.
The launcher builds this wrapper with the pinned FatFs dependency below and
embeds it as `bdmfs_fatfs_irx`, for initial preflight and Sony post-reset I/O.

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

Local repairs translate filesystem API results to negative errno, propagate
read/write/directory errors instead of false EOF, and honor O_CREAT|O_EXCL
before truncation/append flags. Host tests compile the actual filesystem
callbacks with injected FatFs failures and verify that exclusive creation
preserves existing contents. FatFs's internal mount callbacks retain FRESULT.

Reproduce with `python tools/test_pops_fatfs.py` and the regular CMake build.
The dependency archive is downloaded and hash-checked during the target build;
no SDK source checkout or proprietary data is required. Hardware configuration,
game boot and actual-save acceptance are recorded separately in the handoff.
