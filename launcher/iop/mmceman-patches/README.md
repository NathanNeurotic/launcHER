# mmceman patches

Applied in order by `launcher/CMakeLists.txt` to a copy of the `launcher/iop/mmceman`
submodule (pinned at ps2-mmce/mmceman `de28936`) before mmceman is built.

They are the same files, at the same pin, that RiptOPL builds its mmceman with
(NathanNeurotic/Open-PS2-Loader `.github/patches/`, applied by
`.github/scripts/install_coherent_mmce.sh`). Ember keeps the IOP launcHER sets up, so on
MMCE it reads its BIOS, settings and game folder through this driver.

| Patch | Fixes |
|---|---|
| `mmceman-fs-close-fd-leak.patch` | A failed close no longer strands one of the 16 file slots. |
| `mmceman-fs-open-enoent.patch` | A file the card says is absent returns `-ENOENT`, not a bare `-1`. |
| `mmceman-fs-dopen-enoent.patch` | The same for a folder. |
| `mmceman-fs-dread-eof.patch` | The end of a listing returns 0 (end), not -1 (error). |
| `mmceman-fs-dread-entry.patch` | Each listed entry returns 1, not the card's iterator descriptor. That descriptor is 0 when the card's descriptor 0 is free, and 0 means "end of directory", so the folder read as empty. From ps2-mmce/mmceman pull request 11 by AKuHAK. |

Drop a patch once the same fix is in the pinned upstream commit.
