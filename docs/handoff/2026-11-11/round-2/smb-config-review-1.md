# Review: IPCONFIG.DAT / SMBCONFIG.DAT rules and the SMB echo for SB. launches

Target: merge 21c3476 (branch tip ef663b2), docs/POPSTARTER_SMB_CONFIG.md.
Reviewer worktree: `<scratch>/audit-smb/tree` (detached at ef663b2), with TMP/TEMP/TMPDIR set to `<scratch>/audit-smb/tmp`.
`<scratch>` = <scratch>

Verdict: **merge after fixes**. On every input I tried, the parser matches the original. The switch does not do what the doc says it does: in one boot, a session made under one set of rules is reused for a launch that should use the other set.

## What I ran (verified)

1. `python tools/test_pops_smb_config.py` with `POPSTARTER_TEST_ELF` and `POPS_TEST_ELF` set: `Ran 37 tests in 12.817s OK`, no skips. That includes the Original (unicorn) and Unchanged (needs d31d4a7) classes.
2. `<scratch>/audit-smb/fuzz.py`, my own differential check. It compares `common/src/pops_smb_config.c`, built as a host DLL, with the original's blocks run through `tools/trace_original_pops_smb_config.py`. The inputs are my own: 47 fixed SMBCONFIG edge texts, covering embedded NULs, CR-only line ends, a leading LF, `:` at the start or end of the share, server lengths 15 to 18 with a port, ports `00445`, `065535`, `65536`, `-1`, `+1`, sizes 4095 and 4096, and 255- and 256-byte user, password and share values. To those I added 3000 seeded random texts, plus 12 fixed and 600 random IPCONFIG texts (TAB, NUL, sizes 5 to 130).
   Result: `SMBCONFIG texts: 3046 ... differences: 0` (ok 1162, bad-port 1196, size 43, no-share 298, server-length 346, overflow 1) and `IPCONFIG texts: 612 ... differences: 0`.
   For accepted texts, "same" means the class matches and both driver structures match byte for byte. For IPCONFIG it means the length and the buffer.
3. `<scratch>/audit-smb/session.py` and `session2.py`: `launcher/src/handler_smb.c` built for the host with the repo's own fixture (`tools/fixtures/smb_config_host.c`), driven through consecutive launch attempts in one boot. Results are below.
4. Code reading, with the line numbers cited below.

Not done: no EE build (an author build exists at `build-pr23/.../pops_smb_config.c.obj`; I did not run it), and no console or server run.

## Is anything outside "PS1 target and SB. name" changed?

In a single launch with a fresh module load: no. `sb_rules()` (handler_smb.c:20) requires `popsTarget`, and `popsTarget` is written only at common.c:183 (`case Device_SMB:`) from `isPopsTarget(argv[0])`, which is a `.vcd` extension test (handler_pops.c:51). An ELF on `smb:` with an SB.-named launcher gives launcHER's own rules:

```
launchPath(smb:/EMBER/ember.elf) pops=0 sb=1  ['tcpip 32', "LOGON user=b'guest' ptype=-1", 'OPENSHARE ptype=-1', 'connect 0']
```

Ember on mass, ata or hdd never loads the SMB modules, so `initTCPIPArguments` and `launcher_smb_connect` are never reached (init.c module masks at :189-192 and :471).

The exception is a module load cached across launch attempts (finding 1).

## Findings

### 1. (major) A session made under POPStarter's rules is reused for a later non-PS1 smb: launch, Ember included

`loadModules` returns early when the device's modules are already loaded (init.c:248, `if (!forceIOPReset && currentDevice && (currentDevice & device) == device) return 0;`). In that case neither `initTCPIPArguments` nor `launcher_smb_connect` runs again. `launcher_smb_set_pops_target` changes only the flag and never invalidates the live session.

Path loops that try several targets in one boot: the quickboot CNF loop (handler_quickboot.c:420) and the OSDM loop (handler_osdm.c:287). The SB. flag comes from an SB.-named launcher (handler_quickboot.c:138, main.c:75).

Sequence:
1. Path 1 is `smb:/POPS/Game.VCD` and the VCD is missing. `initModules` succeeds, then `tryFile` fails (common.c:114).
2. Path 2 is `smb:/EMBER/ember.elf`.

Harness output:

```
path 1: launchPath(smb:/POPS/Game.VCD) pops=1 sb=1  ['tcpip 29', "LOGON user=b'guest' ptype=0", 'DEVCTL c0de0007', 'OPENSHARE ptype=-1', 'connect 0']
path 2: launchPath(smb:/EMBER/ember.elf) pops=0 sb=1 (cached) ['connect 0']
```

A fresh launch of the same ELF logs on with password type -1 and passes a 32-byte IP block. The cached session was made with password type 0, the 29-byte block and an echo. With the same SMBCONFIG.DAT (`10.0.0.2 SHARE\nguest\n\n`), the Ember ELF is therefore read over a session that launcHER's rules would have set up differently. The doc's claim, "Unchanged, and that includes a launch that is not a PS1 game but carries an SB. name", does not hold here. The Ember profile builds SMB in (CMakeLists.txt:52).

The same happens if `launchPOPS` fails before the IOP reboot, for example when POPS_IOX.PAK is missing, because `forceIOPReset` is only set later (init.c:487).

Fix: record which rule set the live session was made with. When `launchPath` dispatches a target whose rule set differs, force a reload (`forceIOPReset`, or reset `connected` and reload the network modules).

### 2. (major) A quickboot or OSDM SB. VCD launch connects under launcHER's rules first and POPStarter's rules only after the reboot

When the SB. comes only from the VCD's own name (CNF `path=smb:/POPS/SB.Game.VCD`, launcher not SB.-named), the flag is set in `launchPOPS` (handler_pops.c:983-987). That is after `handleGenericPath` has already called `initModules(Device_SMB)` (common.c:107).

Stage 1 therefore uses launcHER's own rules. Stage 1 covers the IP arguments and the SMB connect used to find the VCD and POPS_IOX.PAK. Stage 2, `initPopsServices` after the reboot (handler_pops.c:1912 -> init.c:471), uses POPStarter's. Harness, with files the original accepts:

```
stage1 (sb=0,pops=1) no IPCONFIG.DAT         tcpip=-1 connect=0 ['msg SMB: IPCONFIG.DAT must contain console IP, netmask and gateway']
stage2 (sb=1,pops=1) no IPCONFIG.DAT         tcpip=0  connect=0 []
stage1 (sb=0,pops=1) SMBCONFIG with 4th line tcpip=32 connect=-22 ['msg SMB: Invalid SMBCONFIG.DAT']
stage2 (sb=1,pops=1) SMBCONFIG with 4th line tcpip=29 connect=0 []
stage1 (sb=0,pops=1) host name server        tcpip=32 connect=-22 ['msg SMB: Invalid SMBCONFIG.DAT']
stage2 (sb=1,pops=1) host name server        tcpip=29 connect=0 []
```

A `tcpip=-1` makes `loadModuleList` fail ("Failed to initialize arguments", init.c), so such a launch stops before `launchPOPS`.

For `10.0.0.2 SHARE`, both stages connect, but stage 1 logs on as user `''` and stage 2 as `POPStarter`, with an echo. One launch can thus log on under two different identities.

Direct `main.c` launches are not affected, because main.c:75 sets the flag before `launchPath`.

Fix: decide the SB. state for the dispatched target before `initModules`, for example `pops_is_sb_prefix(argv[0])` in the `Device_SMB` case. Or have `launchPOPS` force the reload described in finding 1 when the rules change.

### 3. (minor, not measured) The short IP block reaches ps2ip_nm with an unterminated gateway

This is faithful to the original. For `10.0.0.9 255.255.255.0 10.0.0.1` (31 bytes) the SB. path hands over 29 bytes (`tcpip 29` above), so the block ends `...\010.0.0.` with no NUL. The original gives the same block to its own `ps2smap.irx`. launcHER gives it to `ps2ip_nm`, which launcHER's own rule always feeds three terminated strings (32 bytes).

What `ps2ip_nm` does with the truncated gateway, or with no arguments when IPCONFIG.DAT is absent (`tcpip=0`), was not measured. The doc says so. I could not find the module's source in the repo to settle it. Every SB. launch that has an IPCONFIG.DAT depends on this.

## Parity (verified)

- The parser matches the original on 3046 SMBCONFIG and 612 IPCONFIG texts of my own (above), and the suite's 37 tests pass.
- The overflow refusal is the one documented divergence. My corpus hit it only once; the suite's Original test checks it against out-of-structure writes.
- `launcher_smbman` handles `SMB_DEVCTL_ECHO` (launcher/iop/smbman/src/smb_fio.c:1115 -> smb.c `smb_Echo`), so the echo call is not rejected as an unknown devctl. Whether it succeeds against a server was not run.

## Notes (not findings)

- An SB. VCD on a non-smb device (explicit `mass:/SB.x.VCD`, or the `mass0:/POPS/` fallback candidate at launch_args.c:727) leaves `popsTarget` at its old value. It is 0 on a fresh boot and 1 after an smb: candidate was tried. So the rule set used by `pops_load_smb_stack` depends on what ran earlier. The SMB modules are not loaded for that device either way (pre-existing behaviour), so this changes at most the failure message.
- The doc's statement that module loads before dispatch (quickboot's own CNF device, the all-devices probe) use launcHER's rules holds: `popsTarget` is 0 until the first `launchPath`.
