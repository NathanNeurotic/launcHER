# Private POPS IOMANX compatibility module

The five SDK source files in `src/` are from ps2dev/ps2sdk commit
`3304cd864748ce40b1ff9fb41cc5a700f5e573a0` (the production Docker SDK),
under Academic Free License 2.0; see the adjacent LICENSE and retained notices.

launcHER changes the legacy-state migration in `ioman_sbv.c` and cleans up
failed hook registration in `iomanX.c`. The owned `sony_ioman_layout.h` validates
and snapshots the two selected Sony IOMAN layouts before any migration writes.
Sony 2.03 uses linked device nodes and 32 file slots; Sony 2.01 uses a device
array and 32 file slots. Neither original module nor firmware bytes are included.

This is a separate POPS module. Do not replace the stock module used by normal
launcher or Ember initialization. The containing external IOP images must pass
the launcher's existing exact identity guards before this module is used.
