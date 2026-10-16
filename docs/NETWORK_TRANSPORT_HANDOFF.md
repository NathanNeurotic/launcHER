# UDPFS, UDPBD and SMBv1 checkpoint - 2026-10-15

User priority: complete transport support before resuming Sony early startup.
Continue on PR #23, branch `codex/popstarter-replacement`. Do not merge.
Parser checkpoint `a30c223` was pushed before the network work.

Reference inspected: RiptOPL `origin/rebuild/main`
`634f2dd2cee69fcd31c5a0b426ca2b57bbe19a2f`.
Use the remote tree, not the older local checkout. RiptOPL's shared UDPFS
transport resets sequence state on rediscovery and waits past stale ACKs
without spending a retry. Its SMB code performs LOGON then OPENSHARE and
interlocks the single NIC against the UDP ministack. Its POPStarter network
editor writes `IPv4[:port] share\nuser\npassword\n`.

Confirmed original gaps and local repairs:

- SMB loaded optional loose IRXs but never logged in or opened a share;
  PS2NETFS incorrectly counted as SMB availability. Replaced by embedded
  DEV9 -> NetMan -> SDK SMAP -> ps2ip-nm -> source-built smbman, then checked
  LOGON/OPENSHARE. A failed share open logs off. State resets after each IOP
  reboot. Both initial loading and Sony post-reset loading use this path.
- TCP/IP's three module arguments are separate NUL-terminated strings,
  parsed from static IPCONFIG.DAT. Credentials are never printed.
- SMB O_EXCL previously ignored: use atomic create dispositions in both NT
  and legacy commands. Preserve missing/exists/access errno. SDK source and
  ABI header pinned to 3304cd864748ce40b1ff9fb41cc5a700f5e573a0.
- UDPFS ACK comparison previously accepted stale ACKs. Real 12-bit serial
  arithmetic, same-alarm stale-ACK waiting, and clean rediscovery state now
  have executable production-code host tests. The existing one-NACK-per-gap
  guard and learned INFORM server port are retained.
- UDPFS CLOSE now validates reply length/type and propagates server errors
  through the iomanX wrapper. Startup propagates AddDrv failure.
- Ministack announces the configured IP with gratuitous ARP before server
  discovery. New private export ordinal 7 releases UDP socket callbacks
  before a failed UDPFS module is unloaded. Existing ordinals are unchanged.
- UDPBD receive bounds cover the remaining destination, zero-length data,
  invalid block shifts and arithmetic overflow. Server write failure is
  retained; module initialization reports failed event/socket allocation.
- Generic SMB handoff keeps DEV9 powered. Device cache reuse requires all
  requested device bits; a partial initialization is never cached. SMB plus
  a UDP network backend is rejected before loading either stack.

Validation to date: the PS2 release target compiled successfully in the
existing ps2homebrew container. All five new host test groups passed:
configuration/creation, actual UDPFS transport, actual UDPBD handlers, actual
EE SMB session controller, and UDPFS close reply/error propagation. All 57
existing POPS checks passed after the source-shape assertions were updated
for the new loading behavior. These
results do not establish hardware streaming or full game/save acceptance.

Before calling transport parity complete, run each mode independently on
physical PS2 with controlled server fixtures: open/seek/read, exclusive
create collision, write/close/reopen/readback, then Ember argv/handoff and
game/save/power-cycle acceptance. Exercise server restart and packet loss.
Do not replay an uncertain save write across a new server session. UDPFS's
rediscovery primitive is fixed; transparent in-game descriptor recovery is
not implemented or claimed. UDPBD flush remains the protocol's existing
no-op: server storage durability still needs validation.

SMB uses memory-card bootstrap files and static addressing. No credentials,
Sony bytes, games, or user saves belong in commits. The existing POPS IOX
dependency and full Sony boot acceptance boundary remain unchanged.

Physical SMB progress (client-local date Oct 15, run IDs are UTC Oct 16):
configuration inventory `20261016T020636-0058` passed. With no listening
server, `20261016T020903-0059` correctly failed at connection (-4097).
After the user started PS2 Servers v0.8.1, `20261016T021127-0060` logged in,
opened the configured share, and enumerated its root read-only. Controlled
file test `20261016T021534-0061` then passed read/seek, atomic EEXIST even
with TRUNC requested, and 8 KiB write/close/reopen/byte comparison. Direct
host hashes confirm both initial files unchanged and NEW.BIN correct.
These tests inherit ps2link's TCP/IP stack; fresh stack/game/save acceptance
is still outstanding. Metadata: `docs/evidence/network_*_hardware.json`.

Reproduce the read-only probe with `prepare_pops_device_inventory.py` and
`--network-config` or `--smb-read-only`. For writes, create a fresh owned
folder with `prepare_network_fixture.py --root SERVER_ROOT --report REPORT`,
run `--smb-files smb0:/LAUNCHER-NET-.../`, then independently run
`verify_network_fixture.py REPORT`. The console probe refuses ordinary
game/save paths. Keep these diagnostic files for evidence; do not reuse the
same folder for another creation run.

## Fresh-IOP network transport probe (2026-10-16)

A clean network transport test requires `SifIopReset("", 0)` to clear ps2link's
inherited network stack and reinitialize `dev9`, `smap`, `ps2ip`/`ministack`,
`smbman`/`udpfs`/`udpbd` from scratch.

Probe tooling:
- `tools/fixtures/network_transport_ee.c`: standalone test harness executing
  `SifIopReset("", 0)`, loading the network stack, connecting, and running
  `network_fixture_test()`.
- `tools/prepare_network_transport_probe.py`: extracts production IRX arrays
  from the launcher build, packages sources into an isolated build directory,
  and generates `ps2.yaml`.

Diagnosis after initial run `20261016T022121-0062`:
- `SifIopReset("", 0)` tears down ps2link and its legacy FILEIO RPC.
- Standard newlib `open()` in `handler_smb.c` (`read_config`) and `init.c`
  (`initSMAPArguments`) targeted legacy FILEIO, failing to open `IPCONFIG.DAT`
  and `SMBCONFIG.DAT` on memory cards.
- `initTCPIPArguments` returned `NULL`, aborting before network driver loading.

Resolution:
- Switched `read_config` and `initSMAPArguments` to `fileXioOpen`, `fileXioRead`,
  and `fileXioClose`.
- Added early `fileXioInit()` binding immediately after `fileXio.irx` loads in
  `loadModuleList`, ensuring memory card access is operational before network
  argument callbacks execute.
- Added structured `NETWORK_STAGE step=...` reporting across GS screen, EE SIO
  hardware serial, and `udptty`.
- Rebuilt probe ELF (`build/network-fresh-v3/build/bin/network.elf`, SHA256
  `6B251EA15A2B8BB66814D2ADD18E78F752582A4C23D79073679799BDA560894F`).

