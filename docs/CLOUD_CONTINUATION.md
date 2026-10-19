# Cloud continuation checkpoint - 2026-10-18

Continue draft PR [#23](https://github.com/NathanNeurotic/launcHER/pull/23)
on `codex/popstarter-replacement`. Do not merge. Fetch before editing and
preserve newer work. Publish validated incremental commits on this branch.
Include `Co-authored-by: ChatGPT <chatgpt@openai.com>` in new commits.

The code checkpoint inspected for this handoff is
`43c6ef10de2a285c247a1d563e190a5ab6da9294`. Local HEAD, the origin tracking
branch and PR head matched. Its GitHub host tests, PS2 build and launcher
argument checks passed; release jobs were skipped. Subsequent commits may
supersede this checkpoint: inspect current CI rather than reusing that result.

## Start here

- `docs/NETWORK_TRANSPORT_HANDOFF.md`: UDPFS, UDPBD and SMBv1 implementation,
  fixtures, test procedure and physical acceptance boundaries.
- `docs/POPSTARTER_HANDOFF.md` and `docs/POPSTARTER_REPLACEMENT.md`: external
  POPS replacement scope, measured startup sequence and remaining parity gaps.
- Inspect commits `5656873`, `3d5446c` and `43c6ef1` for newer PSXCore runtime
  correction work. These arrived after the original network checkpoint and
  must be preserved. Runtime changes are opt-in; consult their guards and
  verification paths before enabling anything.
- `tools/test_network_transports.py`: focused production-code host regressions.
- `tools/prepare_network_transport_probe.py` and
  `tools/fixtures/network_transport_ee.c`: rebuildable fresh-IOP diagnostic.

## Hardware evidence and unresolved work

SMB configuration, login/share enumeration and controlled 8 KiB file I/O
passed on physical PS2, using ps2link's inherited TCP/IP stack. The committed
`docs/evidence/network_*_hardware.json` files record those results. The deliberate
exclusive-create collision corresponds to server status `0xc0000035`; this is
expected test behavior. Direct host readback preserved both initial files and
verified the new file.

Fresh-IOP run `20261016T022121-0062` produced no final acceptance marker after
IOP reset disconnected ps2link. Its new fixture file was absent on the host.
The later fileXio configuration-access repair and staged logging are committed,
but the existence of that repair or a rebuilt probe does not prove a successful
fresh-stack hardware rerun. Verify subsequent rig evidence before claiming it.
Treat the configuration explanation in the network handoff as a source-level
diagnosis unless a captured stopped stage or controlled rerun confirms it.

The diagnostic's UDP branch no longer loads SDK `udptty` after ministack.
Ministack exports its private `mstack` UDP API, without the SDK TCP/IP socket
exports. UDPFS/UDPBD probes now retain GS and EE SIO reporting and explicitly
report `logger_disabled`; only the SMB/ps2ip branch loads `udptty`. This removes
the logger load as a prerequisite to UDP fixture execution. A target rebuild
and captured fresh-stack hardware rerun are still required.

UDPFS and UDPBD physical streaming, restart/loss behavior, full game launch,
save readback and power-cycle acceptance remain separate gates. Host tests and
target builds do not establish those results. UDPBD flush remains a protocol
no-op; transparent UDPFS descriptor recovery is not implemented.

## Reproduction and local-only material

Build diagnostic IRX arrays from current launcher sources, then run the tracked
preparation tool to generate an isolated `ps2.yaml` project. Follow its `--help`
for paths; previous `build/` artifacts and absolute Windows paths are local
evidence, not prerequisites available to a cloud checkout. Use the PS2 SDK
toolchain and repository CI for reproducible host/target checks.

The last observed console address was `192.168.1.10`. PS2 Servers used host
`192.168.1.100`, SMBv1 port `1111`, share `games`, and UDPFS port `62966`.
These are historical local settings, not guaranteed current connectivity.
Use fresh owned `LAUNCHER-NET-*` fixture directories and the tracked prepare/
verify tools; never target ordinary game/save paths or reuse an exclusive-create
fixture. Keep existing diagnostic folders as evidence.

No proprietary Sony binaries, games, saves, credentials, ignored build trees
or machine-specific caches are part of this handoff. A cloud agent can continue
source work and CI independently; physical-console acceptance requires the
local rig or explicit reports with captured results.
