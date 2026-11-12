# POPStarter r13's network files for an `SB.` launch (`IPCONFIG.DAT`, `SMBCONFIG.DAT`)

Measured on the original (POPSTARTER.ELF MAIN, external input, unpacked at
EE `0x870000`) on 2026-11-11 and copied into launcHER for `SB.` launches
only. Every other SMB launch keeps launcHER's own rules, unchanged.

**Nothing here was tested on a console.** Every result below is a host test
or the original's code run under an emulator (unicorn) with its file I/O,
its driver calls and three library calls modelled. Where a part of the
original was only read from disassembly and not run, it says so.

## What the original does

All of this is in the launch function. It runs only when the `SB.` test of
`argv[0]` set the mode word `gp+0x3888` to 3 (gate at `0x8721cc`, read; the
test itself is measured, see "The `SB.` test" below).

### Defaults (`0x871788..0x87182c`, measured)

Before either file is read: no server, port 445, user `POPStarter`
(`strncpy` at `0x8717b8`), no password, both password types -1, and the echo
request `ALIVE ECHO TEST` with length 15 (`strcpy` at `0x871820`, length at
`0x87182c`).

### `IPCONFIG.DAT` (`0x8722bc..0x872628`, measured)

1. Open `mc0:/POPSTARTER/IPCONFIG.DAT`, then `mc1:/POPSTARTER/IPCONFIG.DAT`,
   mode 1. An open result of 0 or less is "no file" (measured for 0 and -1).
   Upper-case name only.
2. Neither opens: not an error. A flag (`fp+0x10c8`) is set and
   `ps2smap.irx` is later started with length 0 and a NULL argument pointer.
3. The file that opened must be 7..127 bytes (tests at `0x8722f8`/`0x872308`
   for `mc0:`, `0x8723b8`/`0x8723c8` for `mc1:`), otherwise the launch stops
   (`0x872340`, `0x872400`). A file on `mc0:` with a bad size is never
   skipped in favour of `mc1:`.
4. Count the bytes that are space, CR or LF (loop at `0x872480`). TAB is not
   one of them. Fewer than 2: `SYNTAX ERROR !`, stop at `0x872544`.
5. Turn each of those bytes into NUL (loop at `0x872570`).
6. The argument length is the file size **minus that count** (`0x872624`).
   The block handed to `ps2smap.irx` is the first `length` bytes, so it ends
   `count` bytes before the end of the text.

Examples, as measured (`\0` is one NUL byte):

| File | Length | Block |
|---|---|---|
| `192.168.1.10 255.255.255.0 192.168.1.1` (38 bytes) | 36 | `192.168.1.10\0255.255.255.0\0192.168.1` |
| the same with a trailing CR LF (40 bytes) | 36 | the same block |
| three lines, each ended by CR LF (42 bytes) | 36 | `192.168.1.10\0\0255.255.255.0\0\0192.168` |

Nothing checks that the three parts are addresses.

### `SMBCONFIG.DAT` (`0x872638..0x87345c`, measured)

Format: `server[:port] share[:sharepassword]`, then optionally a user line
and a password line.

1. Open `mc0:/POPSTARTER/SMBCONFIG.DAT`, then `mc1:`, as above. Neither
   opens: stop at `0x8727d4`. Size must be 7..4095 (`0x872674`/`0x872684`,
   `0x872734`/`0x872744`; stops `0x8726bc`, `0x87277c`). As with the IP
   file, a bad file on `mc0:` is not skipped for `mc1:`.
2. Count line breaks: an LF followed by a byte that is not NUL (loop at
   `0x87280c`). With 2 or more (`slti 2` at `0x872880`) the logon password
   type becomes 0 (`0x87288c`) and the text after the first line break is
   the user (`strcpy` at `0x8729a0`), the text after the next is the
   password (`strcpy` at `0x872a50`). With fewer the defaults stay: user
   `POPStarter`, no password, type -1.
3. The search for the pair does not stop at the password. `S`, `u1`, `p1`,
   `u2`, `p2` on five lines keeps `u1`/`p1`; add a sixth line `u3` and the
   user is `p2`, the password `u3`.
4. CR and LF become NUL (`0x872a84`).
5. The share is everything after the **first space of the file** up to the
   line end (`0x872b04`), spaces included. A `:` inside it, other than as
   its last byte, starts the share password (`strcpy` at `0x872bd4`, share
   password type 0 at `0x872bdc`). The share is copied with `strncpy` and no
   terminator is written after it (`0x872c30`). No space in the file: stop
   at `0x872c7c`.
6. The text before the first space is the server. 22 bytes or more: stop at
   `0x872cc0`.
7. The port's `:` is looked for in the **first 17 bytes of the file**, not
   in the server: the search runs on past the server's end. So
   `10.0.0.2 s:` is a bad port, and a `:` in the share, user or password
   that falls inside the first 17 bytes is taken for the port marker
   (`1.1.1.1 S` / `me:81` / `pw` gives port 81).
8. The port is 1..5 decimal digits, at most 65535. Stops: `0x872d74` (no
   digits, or 6 or more bytes), `0x872de4`, `0x872e58`, `0x872ecc`,
   `0x872f40`, `0x872fb4` (a non-digit at position 1..5), `0x87327c` (above
   65535). Port 0 is accepted.
9. The server is copied last, with `strncpy` and no terminator
   (`0x8732b8`). A server of 16 bytes fills the field; 17 to 21 bytes run on
   into the port and the first byte of the user.

Nothing checks that the server is an address; a host name is accepted and
passed on.

### Long values

No length is checked before the copies. Inside a structure a long value
simply runs on into the next field (a user of 256 bytes or more into the
password, a password of 256 or more into the logon password type, and so
on). From these lengths the copy leaves the structure and overwrites the
globals that follow it:

| Value | Bytes from which it writes past its structure |
|---|---|
| user | 516 |
| logon password | 260 |
| share password | 260 |
| share | 517 |

What follows is live data (`gp+0x3b98` has 18 references in MAIN,
`gp+0x3704`, `gp+0x3708` and `gp+0x370c` are read elsewhere). Measured with
two different fill patterns: 81 fixed texts of this kind all change bytes
outside the two structures, and the longest accepted values (515, 259, 259,
516) change nothing outside.

### Connecting (`0x874128..0x8742e4`, measured)

Three `devctl` calls on `mass0:`, each given its structure's own address and
size and no output buffer:

1. LOGON (`0xC0DE0002`, `0x218` bytes)
2. ECHO (`0xC0DE0007`, `0x104` bytes)
3. OPENSHARE (`0xC0DE0005`, `0x204` bytes)

A negative result stops the launch (`0x8742e4`, `0x8742b8`, `0x87428c`).
The message has a `%d`; the value printed is always 0 (the register still
holds the 0 of the comparison), not the driver's result. Any result of 0 or
more is success.

Then `mass:/POPS/POPS_IOX.PAK` is opened, mode 1, up to **119** times with
no pause between tries, a negative result meaning "try again". After 119
failures the launch stops (`0x874210`). On success `gp+0x3868` and
`gp+0x3450` are set to 1.

### The `SB.` test (`0x8714bc..0x871658`, measured)

`SB.` or `sb.` (not mixed case) directly after any `:`, `/` or `\` anywhere
in `argv[0]` (10 strings that match, 8 that do not, each with messages on
and off). A match sets the mass flag to 1, the mode to 3 and turns the
screen messages on. `XX.` is looked for only when no `SB.` was found.

### Read from the disassembly, not run

- Module set, each looked for on `mc0:` then `mc1:` under `/POPSTARTER/`,
  open result 0 or less meaning absent, start result having to be above 0:
  `poweroff.irx` (`0x87345c`), `ps2dev9.irx` (`0x8735c4`), `smsutils.irx`
  (optional, `0x87372c`), `ps2ip.irx` (`0x8738b4`), `ps2smap.irx` with the
  IP block (`0x873a1c`, start at `0x873b58`/`0x873b78`), `smbman.irx`
  (`0x873bc4`). Before them the embedded `iomanx` (`0x9200d0`) and `filexio`
  (`0x922b00`) are started.
- `smbman.irx` is edited in RAM before it starts (`0x873ce0..0x873eb4`,
  start at `0x873ec4`): at every 4-byte-aligned offset below `size - 8`
  where the eight bytes are `smb\0SMB\0`, they become `mass\0\0\0\0`. That
  is why the calls above go to `mass0:` and the PAK is opened on `mass:`.
- `mass:/POPS/iomanx.irx` and `mass:/POPS/filexio.irx` are read from the
  share if present (`0x877564..0x8777c4`; found when the open result is 0 or
  more; at least `0x11` bytes or `INVALID`; absent is not fatal) and are
  started after the IOP reset in place of the embedded ones
  (`0x87ade8..0x87afa0`).
- After the IOP reset (`0x87b5f4..0x87b9ac`, `SB.` only): the same modules
  are started again from RAM in the same order, then LOGON (`0x87b8b8`),
  ECHO (`0x87b8e0`), OPENSHARE (`0x87b908`). Failures print the message
  without a number. No PAK loop this time.
- The fatal exit (`0x8709f8`) sends CLOSESHARE then LOGOFF when
  `gp+0x3450` is 1.

## launcHER

- `common/src/pops_smb_config.c` (header `common/include/pops_smb_config.h`)
  holds the rules as pure buffer logic: `pops_parse_ipconfig`,
  `pops_parse_smbconfig`, `pops_smbconfig_defaults`,
  `pops_smb_echo_request`, `pops_netconfig_path`. The parsers fill byte
  images of the driver's structures exactly as the original leaves them;
  `handler_smb.c` has static assertions that the images are the size of
  `smbLogOn_in_t`, `smbOpenShare_in_t` and `smbEcho_in_t`.
- The switch is `sb_rules()` in `launcher/src/handler_smb.c`. It returns
  the rule set decided for the target being dispatched from the share
  (`targetRules`, set by `launcher_smb_set_target`).
- The decision is made in `launchPath`'s `case Device_SMB:`
  (`launcher/src/common.c`), **before** `handleGenericPath` loads the
  share's modules. POPStarter's rules need both:
  - the target is a PS1 disc image (`isPopsTarget(argv[0])`);
  - its `SB.` state is on, decided the way `launchPOPS` will decide it: an
    `SB.` prefix on the target (`pops_is_sb_prefix`) turns it on, an `XX.`
    prefix (`pops_is_xx_prefix`) turns it off, otherwise the state set
    before dispatch stays (`pops_get_active_sb_launch()`). That state is set
    by an `SB.`-named launcher (`main.c`, `handler_quickboot.c`, existing
    code), whatever it then launches, which is why the PS1-target half is
    needed.

  So an `SB.` VCD named in a quickboot CNF or an OSDM path gets POPStarter's
  rules in the first stage too, not only after the IOP reboot (review
  finding 2).
- `handler_smb.c` also records the rule set that the loaded network
  module's arguments and session were set up with (`liveRules`). It is set
  in `initTCPIPArguments` and cleared by `launcher_smb_reset`, which
  `loadModuleList` calls on every module load.
  `launcher_smb_set_target` returns nonzero when the target needs the other
  rule set. `case Device_SMB:` then calls `initModulesReload()`
  (`launcher/src/init.c`, one line: `forceIOPReset = 1`). The next
  `initModules` reboots the IOP and loads the share's modules again, under
  the target's rules, instead of returning early because they are already
  loaded. A setup made for an `SB.` PS1 attempt that went no further (VCD
  missing, `launchPOPS` stopping before the IOP reboot) is therefore never
  reused for a later ELF on the share in the same boot, Ember included.
  The same applies the other way round (review finding 1). A setup made
  under the rules the target needs is reused as before.
- `handler_smb.c` has three hunks in existing functions:
  - `initTCPIPArguments` records `liveRules`, then returns
    `sb_tcpip_arguments(length)` under `sb_rules()`;
  - `launcher_smb_connect` returns `sb_connect()` under `sb_rules()`, after
    its "already connected" test;
  - `launcher_smb_reset` also clears `liveRules`.

  Everything else new in the file is static code reached only through
  those tests, plus the setter.
- `launcher/src/common.c` has that one hunk in `launchPath` and two
  `#include` lines (`handler_smb.h`, `launch_args.h`). `launcher/src/init.c`
  has `initModulesReload`, declared in `init.h`. `main.c`, `handler_pops.c`
  and `handler_quickboot.c` are not touched.

### Where the files are looked up

`pops_netconfig_path(index, name, out, capacity)` is the one place that
decides it. In order:

1. `mc0:/POPSTARTER/NAME` (the original's)
2. `mc1:/POPSTARTER/NAME` (the original's)
3. `mc0:/POPSTARTER/name`, `mc1:/POPSTARTER/name` (lower case)
4. `mc0:/POPS/NAME`, `mc0:/POPS/name`, `mc1:/POPS/NAME`, `mc1:/POPS/name`
5. `mc0:/SYS-CONF/NAME`, `mc0:/SYS-CONF/name`, `mc1:/SYS-CONF/NAME`,
   `mc1:/SYS-CONF/name`

Entries 3 to 5 are launcHER's own places, kept as a fallback after the
original's two. As in the original, the first file that opens is the file:
one that opens and is then refused is not skipped for a later one. Other
readers of `SB.` network files can be routed through the same function.

### Outside an `SB.` launch

Unchanged, and that includes a launch that is not a PS1 game but carries an
`SB.` name, and a PS1 game launched from `smb:` without one.
`Unchanged.test_same_calls_as_before` builds `handler_smb.c` as it was at
`d31d4a7` and as it is now and compares every open, read, close, `devctl`
(name, command, bytes) and message over 900 seeded random sessions spread
over the three cases (neither, `SB.` name only, PS1 target only); they are
identical, and more than 150 of the sessions reach a full connect.
`Handler.test_an_sb_name_and_a_ps1_target_are_both_needed` says the same
without needing the old revision: 300 seeded file sets give the same calls
in the three cases, and more than 150 of them give different calls on an
`SB.` launch of a PS1 game.

Module loads that happen before a target is dispatched (the quickboot
configuration file's own device, the all-devices probe) are in the "no PS1
target" case and so use launcHER's own rules, as before this work.

Several targets in one boot (the quickboot CNF and OSDM path loops try one
after another): when the share's modules were set up for an `SB.` PS1
attempt, the next target that is not one gets a fresh module load. Its
calls are the ones `d31d4a7` makes when it loads the modules for that
target (`Unchanged.test_a_launch_after_an_sb_launch`, the review's
sequence: an SB.-named launcher, `smb:/POPS/Game.VCD` that is not there,
then `smb:/EMBER/ember.elf`; and an `SB.` VCD whose `launchPOPS` stops
before the IOP reboot, then the ELF). What is new for such a target is the
reload itself: an IOP reboot that `d31d4a7` did not do there, because its
modules were already loaded. It happens only after a setup under
POPStarter's rules, which only an `SB.` PS1 launch makes. Two targets
needing the same rules keep the loaded setup, as before
(`Dispatch.test_the_same_rules_keep_the_setup`).

`popsTarget`'s old stickiness is kept in another form: `targetRules` is set
only in `case Device_SMB:`. An `SB.` VCD on another device (`mass:`, the
`mass0:/POPS/` fallback) that reaches `pops_load_smb_stack` without the
share's modules loaded is connected under the rules of the last target
dispatched from the share (0 on a fresh boot). Before this fix it was the
last target's PS1 flag combined with the current `SB.` state. The share's
modules may still be resident from that earlier load (a `mass:` dispatch
goes through the live-stack path in `loadModules`, which does not reset the
IOP), so the first-stage connect can really log on under that stale rule
set; read from the code, not run. They are not loaded after the IOP reboot
(`initPopsServices` loads no SMB modules for a `mass:` VCD), so the
second-stage `pops_load_smb_stack` fails and such a launch fails either way.
Not changed further here.

## Copied as it is

- The IP block is short by the number of separators, so the last part
  (normally the gateway) loses its last characters.
- TAB is not a separator in `IPCONFIG.DAT`.
- No check that the parts of `IPCONFIG.DAT` or the server are addresses.
- The first file that opens decides; a bad one on `mc0:` is not skipped.
- The port's `:` is looked for in the first 17 bytes of the file.
- The user and password search goes on after the password (item 3 above).
- Empty user and password lines (`10.0.0.2 S` followed by two empty lines)
  give an empty user and an empty password with password type 0, not the
  guest defaults. One line after the first (a user and no password) is
  ignored: the defaults stay.
- The share is everything after the first space, spaces included; a `:` as
  its last byte stays part of the name.
- No terminator after the server or the share, and long values running on
  inside a structure.
- Port 0 is accepted.
- Without `IPCONFIG.DAT` the network module gets no arguments.
- LOGON, then ECHO, then OPENSHARE; only a negative result is a failure.

## Not the same as the original

- **Values long enough to leave a structure are refused**
  (`POPS_NETCONFIG_OVERFLOW`) with a message, instead of overwriting what
  follows. This is the one class of input where the parser's result differs.
- An open result of 0 is a file in launcHER (`fd < 0` is the test); in the
  original it is "no file". Whether launcHER's fileXio ever returns 0 for
  these opens was not measured.
- launcHER looks in ten more places after the original's two (above).
- A failed read or close stops the step with the driver's error. The
  original's handling of those results was not traced.
- launcHER reads at most the buffer size (128 or 4096 bytes) and takes a
  full buffer as "too big"; the original takes the size by seeking. For a
  file whose size and delivered bytes agree the result is the same.
- The device is `smb:` and the modules are launcHER's embedded ones
  (`netman`, `smap_tcpip`, `ps2ip_nm`, `launcher_smbman`). None of the
  original's external `.irx` files is loaded, `smbman` is not renamed, and
  no `iomanx.irx`/`filexio.irx` is taken from the share.
- The IP block goes to launcHER's `ps2ip_nm`, not to `ps2smap.irx`. What
  `ps2ip_nm` does with the short block, or with no arguments, is not
  measured.
- No 119-try loop on the share's `POPS/POPS_IOX.PAK`. launcHER also requires
  `POPS_IOX.PAK` for these launches, but through its own lookup
  (`findPopsDependenciesForMode` in `handler_pops.c`): one try per folder,
  and a copy on a memory card or another device is accepted, so a share
  without the file does not by itself stop the launch.
- After a failed ECHO or OPENSHARE launcHER logs off and returns the
  driver's error; the original stops the whole launch.
- Messages are launcHER's own wording.
- The `SB.` test itself is launcHER's (`extract_base_name`,
  `launch_args.c:93-122`): last path component only, mixed case accepted, a
  bare name accepted. Not changed by this work.
- The post-reset sequence is launcHER's: `init.c` calls
  `launcher_smb_reset` and then `launcher_smb_connect` again each time it
  loads the module list, so both files are read and parsed again.
- A launch whose VCD is on `smb:` but whose name has no `SB.` keeps
  launcHER's own parser.

## Evidence

`tools/test_pops_smb_config.py` (in CI), 43 tests; 30 need no inputs (3 of
those need revision `d31d4a7` in the checkout).
`tools/trace_original_pops_smb_config.py` runs the original's blocks.

The texts: 552 for `IPCONFIG.DAT` (52 fixed, 500 seeded random; 545
distinct) and 1052 for `SMBCONFIG.DAT` (352 fixed, 700 seeded random; 1045
distinct).

- Original, `IPCONFIG.DAT` (`POPSTARTER_TEST_ELF`, unicorn): for all 552
  the C gives the same class as the original (309 accepted, 127 syntax, 116
  size) and, when accepted, the same length and the same 128-byte buffer.
  The length and block the original passes to its module start call were
  compared for 112 texts on both cards (118 starts), plus the no-file case.
- Original, `SMBCONFIG.DAT`: for all 1052 the same class (415 accepted, 129
  bad port, 31 no share, 65 size, 114 server length, 298 overflow) and,
  when accepted, both structures byte for byte (`0x218` and `0x204` bytes).
  For every text that is not an overflow, nothing else in the original's
  data area changes.
- Original, the rest: defaults and echo request; which card and that a bad
  file on `mc0:` is final; open results 3, 1, 0, -1, -2; the eight bad-port
  stops; the message strings; the `SB.` test; the three `devctl` calls with
  their bytes, the 0 printed on failure and the 119 opens.
- The three library calls the trace models (`strlen`, `strcpy`, `strncpy`)
  were checked against the shipped ones: 148 cases, 444 comparisons. The
  only calls leaving the traced blocks are those and the modelled I/O.
- Native (no inputs): the same texts against a second, independent
  implementation of the rules in Python; literal examples; the refusals;
  the lookup order.
- Handler (no inputs): `handler_smb.c` built for the host with stand-in
  I/O. On an `SB.` launch the argument block and the two `devctl`
  structures are the parser's for all 552 and 1052 texts; first-file-decides
  at each of the 12 places; missing file; read and close errors; failures
  and reconnect.
- Dispatch (no inputs): launch attempts in one boot through the host build
  of `handler_smb.c`, with `init.c`'s module cache and reload,
  `case Device_SMB:`'s decision and `launchPOPS`'s `SB.` update modelled
  in Python. The prefix tests are `common/src/launch_args.c` itself, built
  for the host; `isPopsTarget`, the `case Device_SMB:` text, the cache test
  in `loadModules`, `initModulesReload` and `launchPOPS`'s prefix override
  are pinned by Source. `common.c`, `init.c` and `handler_pops.c` are not
  run on the host. Results:
  - Finding 1: after `smb:/POPS/Game.VCD` (SB.-named launcher) or
    `smb:/POPS/SB.Game.VCD` with `launchPOPS` stopping before the reboot,
    `smb:/EMBER/ember.elf` gets the calls of a fresh launch of it
    (`tcpip 32`, LOGON password type -1, OPENSHARE, no echo).
  - Finding 2: for `smb:/POPS/SB.Game.VCD` and `smb:/POPS/sb.Game.vcd` from
    a launcher that is not SB.-named, with four file sets (no
    `IPCONFIG.DAT`, a fourth `SMBCONFIG.DAT` line, a host name, the plain
    one), the first stage makes the calls of an `SB.` launch and the load
    after the IOP reboot makes the same calls.
  - An `XX.` VCD from an SB.-named launcher uses launcHER's rules in both
    stages. Before the fix its first stage used POPStarter's rules and the
    second launcHER's.
  - On `pr23/integ` (`4e90fda`) with only this test file changed, 5 tests
    fail: three Dispatch tests, `Unchanged.test_a_launch_after_an_sb_launch`
    and the Source pin. `Dispatch.test_the_same_rules_keep_the_setup` and
    `test_the_decision` pass there.
- Unchanged (needs revision `d31d4a7` in the checkout): above.
- Source: the hunks, the CMake list and the CI step.

For scale: of the 1052 texts, the original's rules accept 415 and launcHER's
own parser accepts 69 (a text of 1024 bytes or more counted as refused, as
its reader does); 67 are accepted by both, and for 47 of those the server,
port, share, user and password are the same.

Mutation checks, each done once by hand: changing the port search from 17
to 16 bytes makes both the Native and the Original comparison fail; dropping
the PS1-target half of the switch makes the two Unchanged tests and
`Handler.test_an_sb_name_and_a_ps1_target_are_both_needed` fail (both done
before the dispatch fix, when the switch was `popsTarget &&
pops_get_active_sb_launch()`). After it: removing the `liveRules` record in
`initTCPIPArguments`, or making `launcher_smb_set_target` always return 0,
makes `Dispatch.test_a_setup_under_popstarters_rules_is_not_reused`,
`Unchanged.test_a_launch_after_an_sb_launch` and the Source pin fail.

## Not measured

Anything on a console. In particular:

- that launcHER's `ps2ip_nm` comes up with the original's short argument
  block, and what address it takes with no `IPCONFIG.DAT`. Open question
  (review finding 3, minor): for `10.0.0.9 255.255.255.0 10.0.0.1` the
  block is 29 bytes and ends with `10.0.0.`, the first 7 bytes of the
  gateway, with no NUL after them. The original gives the same block to its own `ps2smap.irx`;
  launcHER gives it to `ps2ip_nm`, whose own rule always gets three
  terminated strings. What `ps2ip_nm` reads past the block, or does with
  no arguments, is not known and its source is not in the repository.
  Every `SB.` launch with an `IPCONFIG.DAT` depends on it;
- that `launcher_smbman` answers the ECHO `devctl` as the original's
  `smbman` does;
- a guest share (no user and password lines, password type -1) and a share
  with a password;
- the whole `SB.` launch through to a running game;
- the IOP reboot and module reload that `initModulesReload` asks for
  between two launch attempts.

The module set, the `smbman` rename, the share's `iomanx.irx` and
`filexio.irx`, and the post-reset sequence were read, not run, and are not
reproduced.
