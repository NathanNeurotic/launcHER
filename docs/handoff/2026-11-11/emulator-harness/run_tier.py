#!/usr/bin/env python3
"""Run a PS2 ELF headless in the scratch copy of RIPPCSX2 and grade the log.

The emulator copy lives in <this dir>/emu (portable.txt keeps every setting,
card and log inside it).  Nothing under the owner's RIPPCSX2 folder is used.

  python run_tier.py --elf PATH [--gameargs "a b"] [--timeout 60]
                     [--marker TEXT] [--fail-marker TEXT ...] [--after TEXT]
                     [--usb-image IMG] [--hdd-image IMG] [--mc1 CARD]
                     [--linger SEC] [--speed N] [--renderer N] [--show]
                     [--set SECTION:KEY=VALUE ...] [--dump ADDR:LEN ...]
                     [--pin ADDR=VALUE ... [--pin-after TEXT]]

Exit code: 0 marker seen, 1 a fail marker seen, 2 timeout / emulator exited
without the marker, 3 setup error.  The log path is printed on the last line.
Only the emulator process started here is terminated.
"""
import argparse
import os
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
EMU_DIR = os.path.join(HERE, "emu")
EMU_EXE = os.path.join(EMU_DIR, "pcsx2-qtx64-avx2.exe")
RUNS_DIR = os.path.join(HERE, "runs")

INI = """[UI]
SettingsVersion = 1
SetupWizardIncomplete = false
ConfirmShutdown = false
PauseOnFocusLoss = false
StartPaused = false
InhibitScreensaver = false
[Folders]
Bios = {bios}
Snapshots = snaps
Savestates = sstates
MemoryCards = memcards
Logs = logs
Cheats = cheats
Patches = patches
UserResources = resources
Cache = cache
Textures = textures
InputProfiles = inputprofiles
Videos = videos
[Filenames]
BIOS = SCPH-39001.rom0
[EmuCore]
EnablePatches = false
EnableCheats = false
EnableFastBoot = true
EnableGameFixes = false
HostFs = true
EnableDiscordPresence = false
SaveStateOnShutdown = false
WarnAboutUnsafeSettings = false
[EmuCore/GS]
Renderer = {renderer}
VsyncEnable = false
[EmuCore/Speedhacks]
EECycleRate = 0
EECycleSkip = 0
[Framerate]
NominalScalar = {speed}
[SPU2/Output]
Backend = Null
OutputMuted = true
[Achievements]
Enabled = false
[AutoUpdater]
CheckAtStartup = false
[DEV9/Eth]
EthEnable = false
[DEV9/Hdd]
HddEnable = {hdd_enable}
HddFile = {hdd_file}
[MemoryCards]
Slot1_Enable = {mc1_enable}
Slot1_Filename = {mc1_name}
Slot2_Enable = false
Slot2_Filename = Mcd002.ps2
[Logging]
EnableSystemConsole = false
EnableFileLogging = true
EnableTimestamps = true
EnableVerbose = {verbose}
EnableEEConsole = true
EnableIOPConsole = true
[InputSources]
Keyboard = false
Mouse = false
SDL = false
DInput = false
XInput = false
[Pad1]
Type = DualShock2
[Pad2]
Type = None
[USB1]
Type = {usb_type}
Msd_ImagePathMsd = {usb_image}
[USB2]
Type = None
"""


def running_emulators():
    """PIDs of every pcsx2 process on the machine (ours or not)."""
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq pcsx2-qtx64-avx2.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True).stdout
    pids = []
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[1].isdigit():
            pids.append(int(parts[1]))
    return pids


PINE_SLOT = 28711  # not the default 28011, so another emulator's IPC is never touched


def pine_read(addr, length, slot=PINE_SLOT):
    """Read EE RAM through PCSX2's PINE socket (MsgRead64 batches)."""
    out = bytearray()
    with socket.create_connection(("127.0.0.1", slot), timeout=10) as sock:
        pos, end = addr, addr + ((length + 7) & ~7)
        while pos < end:
            count = min(0x4000, (end - pos) // 8)
            body = b"".join(bytes([3]) + struct.pack("<I", pos + 8 * i) for i in range(count))
            sock.sendall(struct.pack("<I", len(body) + 4) + body)
            need, got = 5 + 8 * count, bytearray()
            while len(got) < need:
                chunk = sock.recv(need - len(got))
                if not chunk:
                    raise OSError("PINE socket closed")
                got += chunk
            if got[4] != 0:
                raise OSError("PINE read failed at 0x%08x" % pos)
            out += got[5:]
            pos += 8 * count
    return bytes(out[:length])


def pine_write32(pairs, repeat=1, interval=0.0, slot=PINE_SLOT):
    """Write 32-bit words into EE RAM through PINE (MsgWrite32 = opcode 6).

    The batch is sent `repeat` times over one connection; returns how many
    batches the emulator acknowledged."""
    body = b"".join(bytes([6]) + struct.pack("<II", addr, value) for addr, value in pairs)
    packet = struct.pack("<I", len(body) + 4) + body
    done = 0
    with socket.create_connection(("127.0.0.1", slot), timeout=10) as sock:
        for _ in range(repeat):
            sock.sendall(packet)
            got = bytearray()
            while len(got) < 5:
                chunk = sock.recv(5 - len(got))
                if not chunk:
                    raise OSError("PINE socket closed")
                got += chunk
            if got[4] == 0:
                done += 1
            if interval:
                time.sleep(interval)
    return done


def pin_words(pairs, stop, report, slot=PINE_SLOT):
    """Experiment aid, run in a thread: poll 32-bit EE RAM words through PINE
    and, once a word has been seen holding its VALUE, write VALUE back every
    time something else overwrites it.  `report` collects (seconds, addr, seen)."""
    read = b"".join(bytes([2]) + struct.pack("<I", addr) for addr, _ in pairs)
    read = struct.pack("<I", len(read) + 4) + read
    need = 5 + 4 * len(pairs)
    armed = [False] * len(pairs)
    began = time.time()

    def exchange(sock, packet, size):
        sock.sendall(packet)
        got = bytearray()
        while len(got) < size:
            chunk = sock.recv(size - len(got))
            if not chunk:
                raise OSError("PINE socket closed")
            got += chunk
        return got

    while not stop.is_set():
        try:
            with socket.create_connection(("127.0.0.1", slot), timeout=5) as sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                while not stop.is_set():
                    got = exchange(sock, read, need)
                    if got[4] != 0:
                        time.sleep(0.01)
                        continue
                    words = struct.unpack_from("<%dI" % len(pairs), got, 5)
                    for i, (addr, value) in enumerate(pairs):
                        if words[i] == value:
                            if not armed[i]:
                                armed[i] = True
                                report.append((time.time() - began, addr, None))
                        elif armed[i]:
                            body = bytes([6]) + struct.pack("<II", addr, value)
                            exchange(sock, struct.pack("<I", len(body) + 4) + body, 5)
                            report.append((time.time() - began, addr, words[i]))
        except OSError:
            time.sleep(0.05)


def checkpoint_watch(flag, regions, run_dir, stop, report, after_event, slot=PINE_SLOT):
    """Experiment aid, run in a thread: poll the 32-bit EE RAM word at `flag`
    through PINE.  When the guest stores the next checkpoint number there
    (1, 2, 3 ... in order), dump the given regions to cpN_<addr>_<len>.bin in
    the run folder, then write 0 back so the guest (which spins on the word)
    continues."""
    expect = 1
    began = time.time()
    after_event.wait()
    while not stop.is_set():
        try:
            word = struct.unpack("<I", pine_read(flag, 8, slot)[:4])[0]
        except OSError:
            time.sleep(0.05)
            continue
        if word != expect:
            time.sleep(0.002)
            continue
        t0 = time.time()
        for addr, length in regions:
            try:
                data = pine_read(addr, length, slot)
                with open(os.path.join(run_dir, "cp%d_%08x_%x.bin" % (expect, addr, length)), "wb") as handle:
                    handle.write(data)
            except OSError as exc:
                report.append("checkpoint %d: dump %08x failed: %s" % (expect, addr, exc))
        try:
            pine_write32([(flag, 0)], slot=slot)
        except OSError as exc:
            report.append("checkpoint %d: release failed: %s" % (expect, exc))
        report.append("checkpoint %d reached %.2fs after watch start, dumps took %.2fs"
                      % (expect, t0 - began, time.time() - t0))
        expect += 1


def pine_savestate(run_dir, slot_no=9, wait=40.0, slot=PINE_SLOT):
    """Ask the emulator for a save state (PINE MsgSaveState = opcode 9) and
    move what it writes under emu/sstates into the run folder.  The .p2s is a
    zip; a Screenshot.png inside it is extracted next to it.  Returns a list of
    report lines."""
    import zipfile
    out = []
    sdir = os.path.join(EMU_DIR, "sstates")
    os.makedirs(sdir, exist_ok=True)
    before = {n: os.path.getmtime(os.path.join(sdir, n)) for n in os.listdir(sdir)}
    try:
        with socket.create_connection(("127.0.0.1", slot), timeout=10) as sock:
            body = bytes([9, slot_no])
            sock.sendall(struct.pack("<I", len(body) + 4) + body)
            sock.settimeout(wait)
            got = bytearray()
            while len(got) < 5:
                chunk = sock.recv(5 - len(got))
                if not chunk:
                    break
                got += chunk
            out.append("savestate: PINE reply %s" % got.hex())
    except OSError as exc:
        out.append("savestate: PINE request failed: %s" % exc)
    deadline, new = time.time() + wait, []
    while time.time() < deadline:
        new = [n for n in os.listdir(sdir)
               if n.endswith(".p2s") and before.get(n) != os.path.getmtime(os.path.join(sdir, n))]
        if new:
            sizes = [os.path.getsize(os.path.join(sdir, n)) for n in new]
            time.sleep(1.5)
            if sizes == [os.path.getsize(os.path.join(sdir, n)) for n in new] and all(sizes):
                break
        time.sleep(0.5)
    if not new:
        out.append("savestate: no new .p2s under emu/sstates after %.0fs" % wait)
        return out
    for name in new:
        dest = os.path.join(run_dir, name)
        shutil.move(os.path.join(sdir, name), dest)
        out.append("savestate: %s (%d bytes)" % (dest, os.path.getsize(dest)))
        try:
            with zipfile.ZipFile(dest) as archive:
                out.append("savestate: members %s" % ", ".join(archive.namelist()))
                for member in archive.namelist():
                    if member.lower().endswith(".png"):
                        with open(os.path.join(run_dir, "savestate_" + os.path.basename(member)), "wb") as handle:
                            handle.write(archive.read(member))
                        out.append("savestate: extracted %s" % member)
        except (OSError, zipfile.BadZipFile) as exc:
            out.append("savestate: cannot read the archive: %s" % exc)
    return out


def read_log(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError:
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elf", required=True)
    ap.add_argument("--gameargs", default="")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--marker", default="", help="pass when this text appears in the log")
    ap.add_argument("--fail-marker", action="append", default=[], help="fail at once when this text appears")
    ap.add_argument("--after", default="", metavar="TEXT",
                    help="look for the markers only in the log that follows the first TEXT")
    ap.add_argument("--usb-image", default="", help="raw disk image for USB port 1 mass storage")
    ap.add_argument("--hdd-image", default="", help="raw DEV9 HDD image")
    ap.add_argument("--mc1", default="", help="memory card file name inside emu/memcards")
    ap.add_argument("--linger", type=float, default=0.0, help="keep running this long after the marker")
    ap.add_argument("--speed", type=float, default=1.0, help="frame limiter scalar (1 = real time)")
    ap.add_argument("--renderer", type=int, default=13, help="13 software, 11 null, -1 auto")
    ap.add_argument("--verbose", action="store_true", help="PCSX2 verbose/dev log")
    ap.add_argument("--show", action="store_true", help="do not pass -nogui (window visible)")
    ap.add_argument("--set", action="append", default=[], metavar="SECTION:KEY=VALUE",
                    help="extra ini setting, e.g. EmuCore/CPU/Recompiler:EnableEE=false (EE interpreter)")
    ap.add_argument("--dump", action="append", default=[], metavar="ADDR:LEN",
                    help="before stopping, save EE RAM (hex ADDR, hex LEN) to the run folder via PINE")
    ap.add_argument("--poke-on", default="", metavar="TEXT",
                    help="experiment aid: when TEXT appears in the log, apply the --poke writes")
    ap.add_argument("--poke", action="append", default=[], metavar="ADDR=VALUE",
                    help="32-bit EE RAM write (hex) applied via PINE once --poke-on is seen")
    ap.add_argument("--poke-repeat", type=int, default=400,
                    help="repeat the pokes this many times")
    ap.add_argument("--poke-interval", type=float, default=0.005,
                    help="seconds between repeated pokes")
    ap.add_argument("--pin", action="append", default=[], metavar="ADDR=VALUE",
                    help="experiment aid: once the 32-bit EE RAM word at ADDR (hex) has held VALUE, "
                         "restore VALUE whenever it is overwritten (polled through PINE)")
    ap.add_argument("--pin-after", default="", metavar="TEXT",
                    help="start the --pin polling only after TEXT appears in the log")
    ap.add_argument("--cp-flag", default="", metavar="ADDR",
                    help="experiment aid: EE RAM word (hex) the guest sets to 1, 2, 3 ... and spins on; "
                         "each time, the --cp-dump regions are saved and the word is cleared")
    ap.add_argument("--cp-dump", action="append", default=[], metavar="ADDR:LEN",
                    help="region (hex) saved at every checkpoint as cpN_<addr>_<len>.bin")
    ap.add_argument("--cp-after", default="", metavar="TEXT",
                    help="start watching the checkpoint word only after TEXT appears in the log")
    ap.add_argument("--in-place", action="store_true",
                    help="attach the given images directly (default: attach a per-run copy, the master stays pristine)")
    ap.add_argument("--savestate", action="store_true",
                    help="before stopping (after the dumps), ask for a save state through PINE and move the "
                         ".p2s and the Screenshot.png inside it into the run folder")
    ap.add_argument("--name", default="", help="run folder suffix")
    ap.add_argument("--tail", type=int, default=40, help="log lines to print at the end")
    args = ap.parse_args()

    if not os.path.isfile(EMU_EXE):
        print("setup error: no emulator copy at", EMU_EXE)
        return 3
    elf = os.path.abspath(args.elf)
    if not os.path.isfile(elf):
        print("setup error: no ELF at", elf)
        return 3

    stamp = time.strftime("%Y%m%dT%H%M%S") + (("-" + args.name) if args.name else "")
    run_dir = os.path.join(RUNS_DIR, stamp)
    os.makedirs(run_dir)
    # host: is the ELF's folder; run from a copy so the guest cannot write
    # into the source build directory.
    host_dir = os.path.join(run_dir, "host")
    os.makedirs(host_dir)
    run_elf = os.path.join(host_dir, os.path.basename(elf))
    shutil.copyfile(elf, run_elf)
    log = os.path.join(run_dir, "emulog.txt")

    usb_image = os.path.abspath(args.usb_image) if args.usb_image else ""
    hdd_image = os.path.abspath(args.hdd_image) if args.hdd_image else ""
    if not args.in_place:
        if usb_image:
            usb_image = shutil.copyfile(usb_image, os.path.join(run_dir, "usb.img"))
        if hdd_image:
            hdd_image = shutil.copyfile(hdd_image, os.path.join(run_dir, "hdd.raw"))

    ini = INI.format(
        bios=os.path.join(EMU_DIR, "bios"),
        renderer=args.renderer,
        speed=args.speed,
        hdd_enable="true" if args.hdd_image else "false",
        hdd_file=hdd_image,
        mc1_enable="true" if args.mc1 else "false",
        mc1_name=args.mc1 or "Mcd001.ps2",
        verbose="true" if args.verbose else "false",
        usb_type="Msd" if args.usb_image else "None",
        usb_image=usb_image,
    )
    # Merge overrides into the template so no section or key is duplicated.
    sections, current = {}, None
    for line in ini.splitlines():
        if line.startswith("[") and line.endswith("]"):
            current = sections.setdefault(line[1:-1], {})
        elif " = " in line and current is not None:
            key, _, value = line.partition(" = ")
            current[key] = value
    if args.dump or args.poke or args.pin or args.cp_flag or args.savestate:
        sections["EmuCore"]["EnablePINE"] = "true"
        sections["EmuCore"]["PINESlot"] = str(PINE_SLOT)
    for item in args.set:
        section, _, rest = item.partition(":")
        key, _, value = rest.partition("=")
        if not section or not key:
            print("setup error: bad --set", item)
            return 3
        sections.setdefault(section, {})[key] = value
    ini = ""
    for name, keys in sections.items():
        ini += "[%s]\n" % name
        for key, value in keys.items():
            ini += "%s = %s\n" % (key, value)
    os.makedirs(os.path.join(EMU_DIR, "inis"), exist_ok=True)
    with open(os.path.join(EMU_DIR, "inis", "PCSX2.ini"), "w", encoding="utf-8") as handle:
        handle.write(ini)
    shutil.copyfile(os.path.join(EMU_DIR, "inis", "PCSX2.ini"), os.path.join(run_dir, "PCSX2.ini.used"))

    others = running_emulators()
    cmd = [EMU_EXE, "-batch"]
    if not args.show:
        cmd.append("-nogui")
    cmd += ["-fastboot", "-logfile", log, "-elf", run_elf]
    if args.gameargs:
        cmd += ["-gameargs", args.gameargs]
    with open(os.path.join(run_dir, "command.txt"), "w", encoding="utf-8") as handle:
        handle.write(subprocess.list2cmdline(cmd) + "\n")
    print("command:", subprocess.list2cmdline(cmd))
    print("other emulator PIDs left alone:", others)

    proc = subprocess.Popen(cmd, cwd=EMU_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    verdict, code = "TIMEOUT", 2
    started = time.time()
    pokes = [(int(x.partition("=")[0], 16), int(x.partition("=")[2], 16)) for x in args.poke]
    poked = not (pokes and args.poke_on)
    pins = [(int(x.partition("=")[0], 16), int(x.partition("=")[2], 16)) for x in args.pin]
    pin_stop, pin_report, pin_thread = threading.Event(), [], None
    cp_stop, cp_report, cp_event, cp_thread = threading.Event(), [], threading.Event(), None
    if args.cp_flag:
        cp_regions = [(int(x.partition(":")[0], 16), int(x.partition(":")[2], 16)) for x in args.cp_dump]
        cp_thread = threading.Thread(target=checkpoint_watch, daemon=True,
                                     args=(int(args.cp_flag, 16), cp_regions, run_dir, cp_stop, cp_report, cp_event))
        cp_thread.start()
    try:
        while time.time() - started < args.timeout:
            text = read_log(log)
            if args.cp_flag and not cp_event.is_set() and args.cp_after in text:
                cp_event.set()
            if pins and pin_thread is None and args.pin_after in text and (args.pin_after or text):
                pin_thread = threading.Thread(target=pin_words, args=(pins, pin_stop, pin_report), daemon=True)
                pin_thread.start()
            if not poked and args.poke_on in text:
                poked = True
                try:
                    done = pine_write32(pokes, args.poke_repeat, args.poke_interval)
                except OSError as exc:
                    done = 0
                    print("poke failed:", exc)
                print("poked %d word(s) %d time(s) %.1fs after start" % (len(pokes), done, time.time() - started))
            scope = text
            if args.after:
                cut = text.find(args.after)
                scope = text[cut + len(args.after):] if cut >= 0 else ""
            hit = next((m for m in args.fail_marker if m in scope), None)
            if hit:
                verdict, code = "FAIL (" + hit + ")", 1
                break
            if args.marker and args.marker in scope:
                verdict, code = "PASS", 0
                if args.linger:
                    time.sleep(args.linger)
                break
            if proc.poll() is not None:
                verdict, code = "EMULATOR EXITED (%s)" % proc.returncode, 2
                break
            time.sleep(0.25 if poked else 0.01)
        cp_stop.set()
        cp_event.set()
        if cp_thread is not None:
            cp_thread.join(timeout=60)
            for line in cp_report:
                print(line)
        pin_stop.set()
        if pin_thread is not None:
            pin_thread.join(timeout=10)
            for when, addr, seen in pin_report:
                if seen is None:
                    print("pin: %08x armed %.3fs after polling began" % (addr, when))
                else:
                    print("pin: %08x was overwritten with %08x at %.3fs, restored" % (addr, seen, when))
        for item in args.dump:
            a, _, n = item.partition(":")
            a, n = int(a, 16), int(n, 16)
            try:
                data = pine_read(a, n)
                path = os.path.join(run_dir, "ee_%08x_%x.bin" % (a, n))
                with open(path, "wb") as handle:
                    handle.write(data)
                print("dumped", path)
            except OSError as exc:
                print("dump failed:", item, exc)
        if args.savestate and proc.poll() is None:
            for line in pine_savestate(run_dir):
                print(line)
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    elapsed = time.time() - started
    left = [p for p in running_emulators() if p == proc.pid]
    text = read_log(log)
    if not args.marker and code == 2 and verdict == "TIMEOUT":
        verdict = "RAN TO TIMEOUT (no marker requested)"
    lines = text.splitlines()
    print("---- last %d log lines ----" % min(args.tail, len(lines)))
    for line in lines[-args.tail:]:
        print(line.encode("ascii", "replace").decode())
    print("---- verdict: %s after %.1fs; our PID %d still alive: %s ----" % (verdict, elapsed, proc.pid, bool(left)))
    print("log:", log)
    return code


if __name__ == "__main__":
    sys.exit(main())
