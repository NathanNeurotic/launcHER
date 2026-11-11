#!/usr/bin/env python3
"""POPStarter r13's two network files of an SB. launch: IPCONFIG.DAT and
SMBCONFIG.DAT.

The original's launch function reads both from mc0:/POPSTARTER/ or
mc1:/POPSTARTER/ (0x8722bc..0x87345c), turns the first into the argument
block of its network module and the second into the two structures it gives
the SMB driver. launcHER's pure part is common/src/pops_smb_config.c
(pops_parse_ipconfig, pops_parse_smbconfig, pops_netconfig_path); the reader
and the driver calls are in launcher/src/handler_smb.c, used when the launch
is an SB. one. Any other SMB launch keeps the launcher's own parser.

Native needs nothing: fixed texts with their results written out, a second
implementation of the rules in Python compared with the C on boundary and
seeded random texts, and handler_smb.c itself compiled for the host with its
I/O replaced (tools/fixtures/smb_config_host.c).
With POPSTARTER_TEST_ELF and unicorn the original's own code runs as shipped
(tools/trace_original_pops_smb_config.py, its I/O and C-library calls
modelled) and every text must give the same class of result, the same
argument block and the same two structures, byte for byte.
Unchanged compares the non-SB. path of handler_smb.c with the revision before
this work, call for call, when that revision is in the checkout.
Source pins the wiring. Nothing here is a console run, and nothing here says
what a network module or an SMB server does with what it is given.
"""
import ctypes as c
import os
import random
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

OK, SIZE, IP_SYNTAX, NO_SHARE, SERVER_LENGTH, BAD_PORT, OVERFLOW = range(7)
IP_BUFFER, SMB_BUFFER = 128, 4096
LOGON_SIZE, SHARE_SIZE, ECHO_SIZE = 0x218, 0x204, 0x104
SERVER, PORT, USER, PASSWORD, PASSWORD_TYPE = 0x000, 0x010, 0x014, 0x114, 0x214
SHARE_NAME, SHARE_PASSWORD, SHARE_PASSWORD_TYPE = 0x000, 0x100, 0x200
LOGON, LOGOFF, OPENSHARE, CLOSESHARE, ECHO = (0xC0DE0002, 0xC0DE0003, 0xC0DE0005, 0xC0DE0006,
                                              0xC0DE0007)
# The revision before the SB. rules were added to handler_smb.c.
BASE_REVISION = "d31d4a71da95dcf1b56315980772fbf430c95cb6"

HAVE_MAIN = bool(os.environ.get("POPSTARTER_TEST_ELF"))
HAVE_EMU = HAVE_MAIN
if HAVE_EMU:
    try:
        import unicorn  # noqa: F401
        import trace_original_pops_smb_config as T
    except Exception:
        HAVE_EMU = False

_WORK = Path(tempfile.mkdtemp(prefix="pops-smb-config-"))
_SUFFIX = ".dll" if os.name == "nt" else ".so"


def _parser_types(lib):
    lib.pops_parse_ipconfig.argtypes = [c.c_void_p, c.c_int, c.POINTER(c.c_int)]
    lib.pops_parse_smbconfig.argtypes = [c.c_void_p, c.c_int, c.c_void_p, c.c_void_p]
    lib.pops_smbconfig_defaults.argtypes = [c.c_void_p, c.c_void_p]
    lib.pops_smb_echo_request.argtypes = [c.c_void_p]
    lib.pops_netconfig_path.argtypes = [c.c_uint, c.c_char_p, c.c_void_p, c.c_size_t]
    return lib


_STUBS = {
    "tamtypes.h": "#include <stdint.h>\ntypedef uint8_t u8;\n",
    "io_common.h": "#define FIO_O_RDONLY 1\n",
    "fileXio_rpc.h": ("int fileXioDevctl(const char *,int,void *,unsigned,void *,unsigned);\n"
                      "int fileXioOpen(const char *,int,...);\n"
                      "int fileXioRead(int,void *,int);\nint fileXioClose(int);\n"),
    "msg.h": "void msg(const char *,...);\n",
}


def build_handler(handler, name):
    """handler_smb.c for the host: its real parsers (also called directly
    by the tests), its I/O from the fixture."""
    stubs = _WORK / "stubs"
    stubs.mkdir(exist_ok=True)
    for header, text in _STUBS.items():
        (stubs / header).write_text(text)
    out = _WORK / (name + _SUFFIX)
    subprocess.run(["gcc", "-shared", "-fPIC", "-O1", "-std=gnu11", "-Wall", "-Wextra",
                    "-Wno-unused-parameter", "-Werror", "-fno-builtin", "-D_COMMON_H_",
                    "-include", str(stubs / "msg.h"), "-I", str(stubs),
                    "-I", str(ROOT / "launcher/include"), "-I", str(ROOT / "common/include"),
                    "-I", str(ROOT / "launcher/iop/smbman/include"),
                    str(handler), str(ROOT / "common/src/network_config.c"),
                    str(ROOT / "common/src/pops_smb_config.c"),
                    str(ROOT / "tools/fixtures/smb_config_host.c"), "-o", str(out)], check=True)
    lib = c.CDLL(str(out))
    lib.host_add_file.argtypes = [c.c_char_p, c.c_char_p, c.c_int]
    lib.host_set_result.argtypes = [c.c_uint, c.c_int]
    lib.host_tcpip.argtypes = [c.c_void_p, c.c_int]
    lib.host_trace.restype = c.c_char_p
    return _parser_types(lib)


HANDLER = build_handler(ROOT / "launcher/src/handler_smb.c", "handler")
P = HANDLER


# ---------------------------------------------------------------- the C side
def ipconfig(data):
    """(result, length, the 128-byte buffer afterwards)."""
    buf = (c.c_uint8 * IP_BUFFER)()
    size = min(len(data), IP_BUFFER)
    c.memmove(buf, bytes(data[:size]), size)
    length = c.c_int(-99)
    rc = P.pops_parse_ipconfig(buf, size, c.byref(length))
    return rc, length.value, bytes(buf)


def smbconfig(data):
    """(result, logon structure, share structure)."""
    buf = (c.c_uint8 * SMB_BUFFER)(*([0xA5] * SMB_BUFFER))   # the parser must not rely on zeros
    size = min(len(data), SMB_BUFFER)
    c.memmove(buf, bytes(data[:size]), size)
    logon = (c.c_uint8 * (LOGON_SIZE + 8))(*([0xCC] * (LOGON_SIZE + 8)))
    share = (c.c_uint8 * (SHARE_SIZE + 8))(*([0xCC] * (SHARE_SIZE + 8)))
    rc = P.pops_parse_smbconfig(buf, size, logon, share)
    assert bytes(logon[LOGON_SIZE:]) == bytes(share[SHARE_SIZE:]) == b"\xCC" * 8, "write past a structure"
    return rc, bytes(logon[:LOGON_SIZE]), bytes(share[:SHARE_SIZE])


def path(index, name):
    out = c.create_string_buffer(80)
    return out.value.decode() if P.pops_netconfig_path(index, name.encode(), out, 80) else None


def fields(logon, share):
    z = lambda raw: raw.split(b"\0")[0]  # noqa: E731
    return {"server": z(logon[SERVER:PORT]), "port": struct.unpack_from("<i", logon, PORT)[0],
            "user": z(logon[USER:PASSWORD]), "password": z(logon[PASSWORD:PASSWORD_TYPE]),
            "password_type": struct.unpack_from("<i", logon, PASSWORD_TYPE)[0],
            "share": z(share[:SHARE_PASSWORD]),
            "share_password": z(share[SHARE_PASSWORD:SHARE_PASSWORD_TYPE]),
            "share_password_type": struct.unpack_from("<i", share, SHARE_PASSWORD_TYPE)[0]}


# ------------------------------------------- the rules a second time, in Python
class _Past(Exception):
    pass


def default_images():
    logon, share = bytearray(LOGON_SIZE), bytearray(SHARE_SIZE)
    logon[USER:USER + 10] = b"POPStarter"
    struct.pack_into("<i", logon, PORT, 445)
    struct.pack_into("<i", logon, PASSWORD_TYPE, -1)
    struct.pack_into("<i", share, SHARE_PASSWORD_TYPE, -1)
    return logon, share


def model_ip(data):
    size = len(data)
    if size < 7 or size > 127:
        return SIZE, None, None
    text = bytearray(data) + bytes(IP_BUFFER - size)
    count = sum(1 for b in data if b in b" \r\n")
    if count < 2:
        return IP_SYNTAX, None, None
    for i in range(size):
        if text[i] in b" \r\n":
            text[i] = 0
    return OK, size - count, bytes(text)


def model_smb(data):
    logon, share = default_images()
    size = len(data)
    if size < 7 or size > 4095:
        return SIZE, logon, share
    t = bytearray(data) + bytes(SMB_BUFFER + 1 - size)

    def text_at(at):
        return bytes(t[at:t.index(0, at)])

    def strcpy(image, offset, at):
        s = text_at(at) + b"\0"
        if offset + len(s) > len(image):
            raise _Past()
        image[offset:offset + len(s)] = s

    def line_break(k):
        return t[k] == 10 and t[k + 1] != 0

    try:
        if sum(1 for k in range(size) if line_break(k)) >= 2:
            struct.pack_into("<i", logon, PASSWORD_TYPE, 0)
            i = 0
            while i < size:
                if line_break(i):
                    i += 1
                    j = i
                    while j < size:
                        if line_break(j):
                            j += 1
                            t[j - 1] = 0
                            if t[j - 2] == 13:
                                t[j - 2] = 0
                            strcpy(logon, USER, i)
                            i = j
                            while i < size:
                                if t[i] == 10:
                                    t[i] = 0
                                    if t[i - 1] == 13:
                                        t[i - 1] = 0
                                    break
                                i += 1
                            strcpy(logon, PASSWORD, j)
                            break
                        j += 1
                i += 1
        for k in range(size):
            if t[k] in (10, 13):
                t[k] = 0
        space = bytes(t[:size]).find(b" ")
        if space < 0:
            return NO_SHARE, logon, share
        t[space] = 0
        i = space
        while t[i + 1] != 0:
            if t[i] == 0x3A:
                t[i] = 0
                strcpy(share, SHARE_PASSWORD, i + 1)
                struct.pack_into("<i", share, SHARE_PASSWORD_TYPE, 0)
                break
            i += 1
        name = text_at(space + 1)
        if len(name) > SHARE_SIZE:
            raise _Past()
        share[:len(name)] = name
        if len(text_at(0)) >= 22:
            return SERVER_LENGTH, logon, share
        for k in range(17):
            if t[k] == 0x3A:
                t[k] = 0
                digits = text_at(k + 1)
                if not 1 <= len(digits) <= 5 or not all(48 <= d <= 57 for d in digits):
                    return BAD_PORT, logon, share
                if int(digits) > 0xFFFF:
                    return BAD_PORT, logon, share
                struct.pack_into("<i", logon, PORT, int(digits))
                break
        server = text_at(0)
        logon[:len(server)] = server
        return OK, logon, share
    except _Past:
        return OVERFLOW, logon, share


# ----------------------------------------------------------------- the texts
IP_FIXED = [
    b"192.168.1.10 255.255.255.0 192.168.1.1", b"192.168.1.10 255.255.255.0 192.168.1.1\r\n",
    b"192.168.1.10 255.255.255.0 192.168.1.1\n", b"192.168.1.10\r\n255.255.255.0\r\n192.168.1.1\r\n",
    b"192.168.1.10\n255.255.255.0\n192.168.1.1\n", b"192.168.1.10\r255.255.255.0\r192.168.1.1",
    b"192.168.1.10", b"192.168.1.10 255.255.255.0", b"192.168.1.10\t255.255.255.0\t192.168.1.1",
    b"192.168.1.10\t255.255.255.0 192.168.1.1", b"1 2 3 4", b"1 2 3", b"1 2 3 ", b" 1 2 3",
    b"123456", b"1234567", b"12345 7", b"1234 6 ", b" " * 7, b"\n" * 7, b"\r" * 7, b"\r\n" * 4,
    b"", b"1", b"1 2", b"12 45", b"12 4 6", b"1 3 5 7", b"abcdefg", b"abc efg", b"a c efg",
    b"a\0c e g", b"1.1.1.1 2.2.2.2 3.3.3.3\0", b"\0" * 7, b"\0 \0 \0 \0", b"  \0\0\0\0\0",
    b"1.1.1.1 2.2.2.2 3.3.3.3 4.4.4.4 5.5.5.5", b"a" * 127, b"a b " + b"c" * 123,
    b"a b " + b"c" * 124, b"a" * 126, b"a" * 128, b" " * 127, b" " * 128, b" " * 126 + b"x",
    b"x" + b" " * 126, b"1.1.1.1 2.2.2.2 3.3.3.3" + b" " * 104, b"1.1.1.1 2.2.2.2 3.3.3.3" + b" " * 105,
    b"a " * 63 + b"a", b"a " * 64, b"a" * 200, b"a b c" + b"d" * 300,
]


def random_ip(rng):
    kind = rng.randrange(6)
    if kind < 3:
        seps = [b" ", b" ", b"\r\n", b"\n", b"\r", b"\t", b"  ", b" \n"]
        parts = []
        for _ in range(rng.choice([1, 2, 3, 3, 3, 4, 5])):
            n = rng.choice([0, 1, 3, 7, 9, 11, 13, 15, 16, 30, 40])
            parts.append(bytes(rng.choice(b"0123456789.") for _ in range(n)))
            parts.append(rng.choice(seps))
        if rng.randrange(3):
            parts.pop()
        return b"".join(parts)
    if kind < 5:
        n = rng.choice([5, 6, 7, 8, 9, 20, 50, 100, 125, 126, 127, 128, 129, 140])
        return bytes(rng.choice(b"  \r\n\t\0.12ab") for _ in range(n))
    n = rng.randrange(0, 20)
    return bytes(rng.randrange(256) for _ in range(n))


SMB_FIXED = [
    b"192.168.137.11 games", b"192.168.1.5:139 PS2SMB:sharepw\nuser\npass\n",
    b"192.168.1.5:139 PS2SMB:sharepw\r\nuser\r\npass\r\n", b"192.168.1.100 PS2SMB\n\n\n",
    b"192.168.1.100:1445 Share Name\r\ntest user\r\npass word\r\n", b"10.0.0.2 SHARE\nuser\n",
    b"10.0.0.2 SHARE\nuser\npass", b"10.0.0.2 SHARE\nuser\npass\n", b"10.0.0.2 SHARE\nuser\npass\n\n",
    b"10.0.0.2 SHARE\nuser\npass\nmore\n", b"10.0.0.2 SHARE\nuser\npass\nu2\np2\n",
    b"10.0.0.2 SHARE\nu1\np1\nu2\np2\nu3\np3\n", b"10.0.0.2 SHARE\nu1\np1\nu2\np2\nu3\n",
    b"10.0.0.2 SHARE\n\nuser\npass\n", b"10.0.0.2 SHARE\nuser\n\npass\n",
    b"10.0.0.2 SHARE\ruser\rpass\r", b"10.0.0.2 SHARE\r\nuser\r\n", b"10.0.0.2 SHARE\n\r\n\r\n",
    b"10.0.0.2 SHARE\nuser\r\r\npass\r\r\n", b"10.0.0.2 SHARE\nus er\npa ss\n",
    b"\n10.0.0.2 SHARE\nuser\npass\n", b"\n\n10.0.0.2 SHARE\n", b"host\nshare name\nuser\n",
    b"10.0.0.2\nSHARE x\nuser\npass\n", b"10.0.0.2 SHARE\nuser\npass\n" + b"\0",
    b"10.0.0.2 SHARE\nuser\0x\npass\n", b"10.0.0.2 SHARE\0\nuser\npass\n",
    b"10.0.0.2 ", b"10.0.0.2  ", b"10.0.0.2  x", b"10.0.0.2 x ", b"10.0.0.2 a b c ",
    b"10.0.0.2 :", b"10.0.0.2 ::", b"10.0.0.2 :p", b"10.0.0.2 :pw", b"10.0.0.2 s:", b"10.0.0.2 s:p",
    b"10.0.0.2 s:p:q", b"10.0.0.2 s::", b"10.0.0.2 s:p w\nuser\npass\n", b"10.0.0.2 s:\nuser\npass\n",
    b"10.0.0.2 sh:are\r\nuser\r\npass", b"10.0.0.2 s\n:p\nx\n",
    b"10.0.0.2", b"1234567", b"123456", b"12345 ", b"123456 ", b" 234567", b" " * 7, b"\n" * 7,
    b"", b"a", b"a b", b"\0" * 7, b"\0\0\0 \0\0\0", b"ab\0 cdef", b"ab\0:1 cdef",
    b"10.0.0.2\tSHARE\n", b"10.0.0.2\tSHARE x\n", b"hostname SHARE", b"my-nas.local SHARE",
    b"10.0.0.2:445 S", b"10.0.0.2:0 S", b"10.0.0.2:00000 S", b"10.0.0.2:1 S", b"10.0.0.2:65535 S",
    b"10.0.0.2:65536 S", b"10.0.0.2:99999 S", b"10.0.0.2:100000 S", b"10.0.0.2:000001 S",
    b"10.0.0.2: S", b"10.0.0.2:12a S", b"10.0.0.2:a S", b"10.0.0.2:-1 S", b"10.0.0.2:+1 S",
    b"10.0.0.2:1:2 S", b"10.0.0.2:: S", b"10.0.0.2:4 5 S", b":445 S", b": S", b"::1 SHARE",
    b"10.0.0.2:44\x355 S", b"10.0.0.2:\xb9 S", b"10.0.0.2:/ S", b"10.0.0.2:: S",
    b"10.0.0.2:445\tS x", b"10.0.0.2:445\nS x", b"10.0.0.2:445\r\nSHARE x\r\nu\r\np\r\n",
    b"123456789012345 S", b"1234567890123456 S", b"12345678901234567 S", b"123456789012345678 S",
    b"12345678901234567890 S", b"123456789012345678901 S", b"1234567890123456789012 S",
    b"123456789012345678901 share\nu\np\n", b"12345678901234567:80 share\nu\np\n",
    b"1234567890123456:80 share\nu\np\n", b"123456789012345:80 share\nu\np\n",
    b"12345678901234567890:1 S", b"1234567890123456:12345 S", b"1234567890123456:123456 S",
    b"123456789012345:65535 S", b"12345678901234567:8 S", b"1234567890123456:8\0 S",
    b"12345678901234567890123456789 S", b"x" * 21 + b"\nS x", b"x" * 22 + b"\nS x",
    b"10.0.0.2 S" + b"\n" * 100, b"10.0.0.2 S\n" + b"u" * 255 + b"\n" + b"p" * 255 + b"\n",
]
# Lengths around the ends of the fields and of the two structures: a user of
# 516 bytes, a password or share password of 260 and a share of 517 are the
# first that would be written past a structure.
EDGES = [0, 1, 2, 15, 16, 17, 254, 255, 256, 257, 258, 259, 260, 261, 300, 511, 512, 513, 514,
         515, 516, 517, 518, 600, 1100, 1300]
for _n in EDGES:
    SMB_FIXED.append(b"10.0.0.2 S\n" + b"u" * _n + b"\npw\n")
    SMB_FIXED.append(b"10.0.0.2 S\nme\n" + b"p" * _n + b"\n")
    SMB_FIXED.append(b"10.0.0.2 S\nme\n" + b"p" * _n)
    SMB_FIXED.append(b"10.0.0.2 " + b"s" * _n)
    SMB_FIXED.append(b"10.0.0.2 " + b"s" * _n + b"\nme\npw\n")
    SMB_FIXED.append(b"10.0.0.2 sh:" + b"w" * _n)
    SMB_FIXED.append(b"10.0.0.2 " + b"s" * _n + b":" + b"w" * 3 + b"\nme\npw\n")
    SMB_FIXED.append(b"10.0.0.2 S\n" + b"u" * _n + b"\n" + b"p" * _n + b"\n")
for _n in (6, 7, 8, 4094, 4095, 4096, 4097, 5000):
    SMB_FIXED.append((b"10.0.0.2 S\n" + b"\n" * 5000)[:_n])
    SMB_FIXED.append((b"1 S" + b"x" * 5000)[:_n])
    SMB_FIXED.append(b" " * _n)
    SMB_FIXED.append(b"x" * _n)


def random_smb(rng):
    def word(alphabet, lengths):
        return bytes(rng.choice(alphabet) for _ in range(rng.choice(lengths)))

    kind = rng.randrange(10)
    if kind >= 8:
        n = rng.choice([5, 6, 7, 8, 12, 20, 40, 80])
        return bytes(rng.choice(b"  \r\n\n::\t\0a1.x") for _ in range(n))
    eol = rng.choice([b"\n", b"\n", b"\r\n", b"\r\n", b"\r", b"\n\n", b"\r\r\n"])
    text = word(b"0123456789.", [0, 1, 7, 9, 11, 13, 14, 15, 15, 15, 16, 17, 18, 20, 21, 22, 25])
    if rng.randrange(3) == 0:
        text += rng.choice([b":", b":0", b":7", b":139", b":445", b":1445", b":65535", b":65536",
                            b":99999", b":123456", b":12a", b":-1", b"::", b":4 4"])
        if rng.randrange(4) == 0:
            text += word(b"0123456789", [1, 2, 3])
    text += rng.choice([b" ", b" ", b" ", b" ", b"  ", b"\t", b""])
    long = [0, 1, 2, 5, 8, 8, 8, 20, 60, 255, 256, 257, 259, 260, 261, 400, 515, 516, 517, 700]
    text += word(b"abcXYZ019$_ ", long)
    if rng.randrange(4) == 0:
        text += b":" + word(b"abc019 :", long)
    for _ in range(rng.choice([0, 0, 1, 2, 2, 2, 2, 3, 4, 5])):
        text += eol + word(b"abcXYZ019 @.", long)
    if rng.randrange(2):
        text += eol
    if kind >= 6 and text:
        text = bytearray(text)
        for _ in range(rng.choice([1, 1, 2, 4])):
            text[rng.randrange(len(text))] = rng.choice(b"\0\n\r :\t\xff")
        text = bytes(text)
    if kind == 5 and text:
        text = text[:rng.randrange(len(text) + 1)]
    return text


def ip_texts():
    rng = random.Random(0x49504346)
    return IP_FIXED + [random_ip(rng) for _ in range(500)]


def smb_texts():
    rng = random.Random(0x534D4243)
    return SMB_FIXED + [random_smb(rng) for _ in range(700)]


# ------------------------------------------------------------ handler on host
CANDIDATES = ["mc0:/POPSTARTER/%s", "mc1:/POPSTARTER/%s", "mc0:/POPSTARTER/%l", "mc1:/POPSTARTER/%l",
              "mc0:/POPS/%s", "mc0:/POPS/%l", "mc1:/POPS/%s", "mc1:/POPS/%l",
              "mc0:/SYS-CONF/%s", "mc0:/SYS-CONF/%l", "mc1:/SYS-CONF/%s", "mc1:/SYS-CONF/%l"]


def candidates(name):
    return [p.replace("%s", name).replace("%l", name.lower()) for p in CANDIDATES]


def session(lib, files, sb, steps=("tcpip", "connect"), results=(), chunk=0, read_error=0,
            close_error=0):
    """Run handler_smb.c entry points; returns (trace lines, tcpip bytes or None)."""
    lib.host_reset()
    for name, data in files.items():
        assert lib.host_add_file(name.encode(), bytes(data), len(data)) >= 0
    lib.host_set_sb(sb)
    lib.host_set_read_chunk(chunk)
    lib.host_set_read_error(read_error)
    lib.host_set_close_error(close_error)
    for cmd, result in results:
        lib.host_set_result(cmd, result)
    args = None
    for step in steps:
        if step == "tcpip":
            out = (c.c_uint8 * 256)()
            n = lib.host_tcpip(out, 256)
            args = None if n < 0 else bytes(out[:n])
        elif step == "connect":
            lib.host_connect()
        else:
            lib.launcher_smb_reset()
    return lib.host_trace().decode("latin-1").splitlines(), args


def opens(trace):
    return [line.split()[1] for line in trace if line.startswith("open ")]


def devctls(trace):
    """[(device, command, payload)] of the device-control calls."""
    out = []
    for line in trace:
        if line.startswith("devctl "):
            part = line.split()
            size = int(part[3])
            out.append((part[1], int(part[2], 16), bytes.fromhex(part[4]) if size else b""))
    return out


class Native(unittest.TestCase):
    def test_defaults(self):
        logon = (c.c_uint8 * LOGON_SIZE)(*([0xEE] * LOGON_SIZE))
        share = (c.c_uint8 * SHARE_SIZE)(*([0xEE] * SHARE_SIZE))
        P.pops_smbconfig_defaults(logon, share)
        want_logon, want_share = default_images()
        self.assertEqual((bytes(logon), bytes(share)), (bytes(want_logon), bytes(want_share)))
        self.assertEqual(fields(bytes(logon), bytes(share)), {
            "server": b"", "port": 445, "user": b"POPStarter", "password": b"", "password_type": -1,
            "share": b"", "share_password": b"", "share_password_type": -1})
        echo = (c.c_uint8 * ECHO_SIZE)(*([0xEE] * ECHO_SIZE))
        P.pops_smb_echo_request(echo)
        self.assertEqual(bytes(echo), ECHO_REQUEST)

    def test_ipconfig_examples(self):
        """What the original was measured to hand its network module."""
        z = b"\0"
        for text, length, block in [
                # The length is the size less the separators, so the block
                # stops that many bytes early: the gateway loses its end.
                (b"192.168.1.10 255.255.255.0 192.168.1.1", 36, b"192.168.1.10" + z + b"255.255.255.0" + z + b"192.168.1"),
                (b"192.168.1.10 255.255.255.0 192.168.1.1\r\n", 36, b"192.168.1.10" + z + b"255.255.255.0" + z + b"192.168.1"),
                (b"192.168.1.10 255.255.255.0 192.168.1.1\n", 36, b"192.168.1.10" + z + b"255.255.255.0" + z + b"192.168.1"),
                (b"192.168.1.10\r\n255.255.255.0\r\n192.168.1.1\r\n", 36,
                 b"192.168.1.10" + z * 2 + b"255.255.255.0" + z * 2 + b"192.168"),
                (b"1 2 3 4", 4, b"1" + z + b"2" + z),
                (b" " * 7, 0, b""),
                (b"a b " + b"c" * 123, 125, b"a" + z + b"b" + z + b"c" * 121),
                (b"\0 \0 \0 \0", 4, z * 4)]:
            rc, got_length, buf = ipconfig(text)
            self.assertEqual((rc, got_length, buf[:got_length]), (OK, length, block), text)
        for text in (b"192.168.1.10", b"192.168.1.10 255.255.255.0", b"1234567", b"a" * 127,
                     b"192.168.1.10\t255.255.255.0\t192.168.1.1"):
            self.assertEqual(ipconfig(text)[0], IP_SYNTAX, text)
        for text in (b"", b"1 2 3", b" " * 6, b" " * 128, b"1.1.1.1 2.2.2.2 3.3.3.3" + b" " * 105, b"a b c" + b"d" * 300):
            self.assertEqual(ipconfig(text)[0], SIZE, text)

    def test_ipconfig_against_the_python_rules(self):
        for text in ip_texts():
            rc, length, buf = ipconfig(text)
            want = model_ip(text)
            self.assertEqual(rc, want[0], text)
            if rc == OK:
                self.assertEqual((length, buf), want[1:], text)

    def test_smbconfig_examples(self):
        def parsed(text):
            rc, logon, share = smbconfig(text)
            self.assertEqual(rc, OK, text)
            return fields(logon, share)

        guest = {"server": b"192.168.137.11", "port": 445, "user": b"POPStarter", "password": b"",
                 "password_type": -1, "share": b"games", "share_password": b"",
                 "share_password_type": -1}
        self.assertEqual(parsed(b"192.168.137.11 games"), guest)
        full = {"server": b"192.168.1.5", "port": 139, "user": b"user", "password": b"pass",
                "password_type": 0, "share": b"PS2SMB", "share_password": b"sharepw",
                "share_password_type": 0}
        self.assertEqual(parsed(b"192.168.1.5:139 PS2SMB:sharepw\nuser\npass\n"), full)
        self.assertEqual(parsed(b"192.168.1.5:139 PS2SMB:sharepw\r\nuser\r\npass\r\n"), full)
        self.assertEqual(parsed(b"192.168.1.5:139 PS2SMB:sharepw\nuser\npass"), full)
        # One line break is not enough for a user: the defaults stay.
        one = parsed(b"10.0.0.2 SHARE\nuser\n")
        self.assertEqual((one["user"], one["password_type"]), (b"POPStarter", -1))
        # Two empty lines are an empty user with an empty plain-text password.
        empty = parsed(b"192.168.1.100 PS2SMB\n\n\n")
        self.assertEqual((empty["user"], empty["password"], empty["password_type"]), (b"", b"", 0))
        # The search goes on after the password. Two more lines change
        # nothing, but a third makes the fourth and fifth lines the user and
        # the password.
        later = parsed(b"10.0.0.2 SHARE\nu1\np1\nu2\np2\n")
        self.assertEqual((later["user"], later["password"]), (b"u1", b"p1"))
        later = parsed(b"10.0.0.2 SHARE\nu1\np1\nu2\np2\nu3\n")
        self.assertEqual((later["user"], later["password"]), (b"p2", b"u3"))
        # The share is the rest of the line after the first space of the file.
        self.assertEqual(parsed(b"10.0.0.2 Share Name \nu\np\n")["share"], b"Share Name ")
        self.assertEqual(parsed(b"10.0.0.2  x")["share"], b" x")
        self.assertEqual(parsed(b"10.0.0.2 ")["share"], b"")
        self.assertEqual(parsed(b"host\nshare name\nuser\n")["share"], b"name")
        # A ':' as the last byte of the share stays in the name.
        last = parsed(b"192.168.100.100 s:")
        self.assertEqual((last["share"], last["share_password_type"]), (b"s:", -1))
        first = parsed(b"10.0.0.2 :pw")
        self.assertEqual((first["share"], first["share_password"], first["share_password_type"]),
                         (b"", b"pw", 0))
        # Nothing checks that the server is an address.
        self.assertEqual(parsed(b"my-nas.local SHARE")["server"], b"my-nas.local")
        self.assertEqual(parsed(b"10.0.0.2:0 S")["port"], 0)
        self.assertEqual(parsed(b"10.0.0.2:65535 S")["port"], 65535)
        self.assertEqual(parsed(b"10.0.0.2:00080 S")["port"], 80)

    def test_the_port_search_does_not_stop_at_the_server(self):
        """The ':' of the port is looked for in the first 17 bytes of the
        file, whatever they belong to by then."""
        def parsed(text):
            rc, logon, share = smbconfig(text)
            return rc, fields(logon, share)

        # A share ending in ':' near the start of the file: an empty port.
        self.assertEqual(parsed(b"10.0.0.2 s:")[0], BAD_PORT)
        self.assertEqual(parsed(b"192.168.137.11 s:")[0], BAD_PORT)
        self.assertEqual(parsed(b"192.168.137.111 s:")[0], OK)
        # A ':' in the user name or the password, when that near the start.
        self.assertEqual(parsed(b"1.1.1.1 S\nme:x\npw\n")[0], BAD_PORT)
        rc, got = parsed(b"1.1.1.1 S\nme:81\npw\n")
        self.assertEqual((rc, got["port"], got["user"], got["server"]), (OK, 81, b"me:81", b"1.1.1.1"))
        rc, got = parsed(b"192.168.137.11 S\nme:81\npw\n")
        self.assertEqual((rc, got["port"], got["user"]), (OK, 445, b"me:81"))

    def test_smbconfig_refusals(self):
        for text, want in [
                (b"", SIZE), (b"1 S", SIZE), (b"10.0 S", SIZE), (b"10.0.0.2 " + b"s" * 4087, SIZE),
                (b"10.0.0.2", NO_SHARE), (b"10.0.0.2\tSHARE\n", NO_SHARE), (b"1234567", NO_SHARE),
                (b"1234567890123456789012 S", SERVER_LENGTH), (b"x" * 22 + b"\nS x", SERVER_LENGTH),
                (b"10.0.0.2: S", BAD_PORT), (b"10.0.0.2:65536 S", BAD_PORT),
                (b"10.0.0.2:123456 S", BAD_PORT), (b"10.0.0.2:12a S", BAD_PORT),
                (b"10.0.0.2:-1 S", BAD_PORT), (b"10.0.0.2:1:2 S", BAD_PORT),
                (b"10.0.0.2 S\n" + b"u" * 516 + b"\npw\n", OVERFLOW),
                (b"10.0.0.2 S\nme\n" + b"p" * 260 + b"\n", OVERFLOW),
                (b"10.0.0.2 sh:" + b"w" * 260, OVERFLOW), (b"10.0.0.2 " + b"s" * 517, OVERFLOW)]:
            self.assertEqual(smbconfig(text)[0], want, text[:40])
        self.assertEqual(smbconfig(b"10.0.0.2 " + b"s" * 4086)[0], OVERFLOW)     # 4095 bytes
        self.assertEqual(smbconfig(b"10.0.0.2 S" + b"\n" * 4085)[0], OK)         # 4095 bytes
        self.assertEqual(smbconfig(b"10.0.0.2 S" + b"\n" * 4086)[0], SIZE)       # 4096 bytes

    def test_long_values_run_on_inside_a_structure(self):
        """No terminator is written after the server or the share, and a long
        value runs into the next field, as in the original's structures."""
        rc, logon, share = smbconfig(b"123456789012345678901 share\nu\np\n")
        self.assertEqual(rc, OK)
        self.assertEqual(logon[:21], b"123456789012345678901")
        self.assertEqual(struct.unpack_from("<i", logon, PORT)[0], struct.unpack("<i", b"7890")[0])
        self.assertEqual(logon[USER:USER + 2], b"1\0")
        rc, logon, share = smbconfig(b"12345678901234567:80 share\nu\np\n")
        self.assertEqual((rc, logon[:17]), (OK, b"12345678901234567"))
        self.assertEqual(logon[PORT:PORT + 4], b"7:80")
        rc, logon, share = smbconfig(b"1234567890123456:80 share")
        self.assertEqual((rc, logon[:16], struct.unpack_from("<i", logon, PORT)[0]),
                         (OK, b"1234567890123456", 80))
        rc, logon, share = smbconfig(b"10.0.0.2 " + b"s" * 300 + b":pw")
        self.assertEqual((rc, share[:300], share[300:304]), (OK, b"s" * 300, b"\0" * 4))
        rc, logon, share = smbconfig(b"10.0.0.2 " + b"s" * 516)
        self.assertEqual((rc, share), (OK, b"s" * 516))
        rc, logon, share = smbconfig(b"10.0.0.2 S\n" + b"u" * 515 + b"\npw\n")
        self.assertEqual(rc, OK)
        # The user ran over the password and the type; the password, copied
        # second, then replaced its part.
        self.assertEqual(logon[USER:PASSWORD], b"u" * 256)
        self.assertEqual(logon[PASSWORD:PASSWORD + 3], b"pw\0")
        self.assertEqual(logon[PASSWORD + 3:LOGON_SIZE], b"u" * 256 + b"\0")

    def test_smbconfig_against_the_python_rules(self):
        seen = set()
        for text in smb_texts():
            rc, logon, share = smbconfig(text)
            want = model_smb(text)
            self.assertEqual(rc, want[0], text[:60])
            seen.add(rc)
            if rc == OK:
                self.assertEqual((logon, share), (bytes(want[1]), bytes(want[2])), text[:60])
        self.assertEqual(seen, {OK, SIZE, NO_SHARE, SERVER_LENGTH, BAD_PORT, OVERFLOW})

    def test_paths(self):
        for name in ("IPCONFIG.DAT", "SMBCONFIG.DAT"):
            got = []
            while path(len(got), name):
                got.append(path(len(got), name))
            self.assertEqual(got, candidates(name))
            self.assertEqual(got[:2], ["mc0:/POPSTARTER/" + name, "mc1:/POPSTARTER/" + name])
        out = c.create_string_buffer(b"\x7f" * 40, 40)
        self.assertEqual(P.pops_netconfig_path(0, b"IPCONFIG.DAT", out, 28), 0)
        self.assertEqual(out.raw, b"\x7f" * 40)
        self.assertEqual(P.pops_netconfig_path(0, b"IPCONFIG.DAT", out, 29), 1)
        self.assertEqual(out.raw[:30], b"mc0:/POPSTARTER/IPCONFIG.DAT\0\x7f")


ECHO_REQUEST = b"ALIVE ECHO TEST".ljust(256, b"\0") + struct.pack("<i", 15)


class Handler(unittest.TestCase):
    """handler_smb.c on an SB. launch."""
    GOOD_IP = b"192.168.1.10 255.255.255.0 192.168.1.1"
    GOOD_SMB = b"192.168.1.5:139 PS2SMB:sharepw\r\nuser\r\npass\r\n"

    def test_no_ipconfig_starts_the_module_without_arguments(self):
        trace, args = session(HANDLER, {}, 1, ("tcpip",))
        self.assertEqual(opens(trace), candidates("IPCONFIG.DAT"))
        self.assertEqual(args, b"")
        self.assertEqual(trace[-1], "tcpip 0")
        self.assertFalse([line for line in trace if line.startswith("msg ")])

    def test_ipconfig_block_is_the_parsers(self):
        for text in ip_texts():
            trace, args = session(HANDLER, {"mc0:/POPSTARTER/IPCONFIG.DAT": text}, 1, ("tcpip",),
                                  chunk=random.Random(len(text)).choice([0, 0, 1, 7, 100]))
            rc, length, buf = ipconfig(text)
            self.assertEqual(opens(trace), ["mc0:/POPSTARTER/IPCONFIG.DAT"], text)
            if rc == OK:
                self.assertEqual(args, buf[:length], text)
            else:
                self.assertIsNone(args, text)
                self.assertEqual(len([line for line in trace if line.startswith("msg ")]), 1, text)

    def test_the_first_file_that_opens_decides(self):
        for name, good, bad, step in (("IPCONFIG.DAT", self.GOOD_IP, b"short", "tcpip"),
                                      ("SMBCONFIG.DAT", self.GOOD_SMB, b"short", "connect")):
            places = candidates(name)
            for at in range(len(places)):
                # A good file at `at`, an unacceptable one after it.
                files = {places[at]: good}
                if at + 1 < len(places):
                    files[places[at + 1]] = bad
                trace, args = session(HANDLER, files, 1, (step,))
                self.assertEqual(opens(trace), places[:at + 1], (name, at))
                self.assertEqual(trace[-1], "tcpip 36" if step == "tcpip" else "connect 0", (name, at))
                # An unacceptable one at `at` is not skipped for a good one after it.
                if at + 1 < len(places):
                    trace, args = session(HANDLER, {places[at]: bad, places[at + 1]: good}, 1, (step,))
                    self.assertEqual(opens(trace), places[:at + 1], (name, at))
                    self.assertEqual(trace[-1], "tcpip NULL" if step == "tcpip" else "connect -22",
                                     (name, at))
                    self.assertFalse(devctls(trace))

    def test_connect_passes_the_parsers_structures(self):
        for text in smb_texts():
            trace, _ = session(HANDLER, {"mc1:/POPSTARTER/SMBCONFIG.DAT": text}, 1, ("connect",),
                               chunk=random.Random(len(text)).choice([0, 0, 1, 500]))
            rc, logon, share = smbconfig(text)
            self.assertEqual(opens(trace), candidates("SMBCONFIG.DAT")[:2], text[:60])
            calls = devctls(trace)
            if rc != OK:
                self.assertEqual((calls, trace[-1]), ([], "connect -22"), text[:60])
                self.assertEqual(len([line for line in trace if line.startswith("msg ")]), 1)
                continue
            self.assertEqual(trace[-1], "connect 0", text[:60])
            self.assertEqual([call[:2] for call in calls],
                             [("smb:", LOGON), ("smb:", ECHO), ("smb:", OPENSHARE)])
            self.assertEqual((calls[0][2], calls[-1][2]), (logon, share), text[:60])
            self.assertEqual(calls[1][2], ECHO_REQUEST)

    def test_missing_smbconfig(self):
        trace, _ = session(HANDLER, {}, 1, ("connect",))
        self.assertEqual(opens(trace), candidates("SMBCONFIG.DAT"))
        self.assertEqual(trace[-1], "connect -2")
        self.assertFalse(devctls(trace))

    def test_failures_and_reconnect(self):
        files = {"mc0:/POPSTARTER/SMBCONFIG.DAT": self.GOOD_SMB}
        trace, _ = session(HANDLER, files, 1, ("connect", "connect"))
        self.assertEqual([call[1] for call in devctls(trace)], [LOGON, ECHO, OPENSHARE])
        self.assertEqual(trace[-2:], ["connect 0", "connect 0"])       # the second does nothing
        trace, _ = session(HANDLER, files, 1, ("connect", "reset", "connect"))
        self.assertEqual([call[1] for call in devctls(trace)], [LOGON, ECHO, OPENSHARE] * 2)
        # A negative result stops it, as in the original; the launcher then
        # logs off (the original stops the whole launch there).
        trace, _ = session(HANDLER, files, 1, ("connect",), results=[(LOGON, -13)])
        self.assertEqual([call[1] for call in devctls(trace)], [LOGON])
        self.assertEqual(trace[-1], "connect -13")
        trace, _ = session(HANDLER, files, 1, ("connect",), results=[(ECHO, -5)])
        self.assertEqual([call[1] for call in devctls(trace)], [LOGON, ECHO, LOGOFF])
        self.assertEqual(trace[-1], "connect -5")
        trace, _ = session(HANDLER, files, 1, ("connect", "connect"), results=[(OPENSHARE, -13)])
        self.assertEqual([call[1] for call in devctls(trace)], [LOGON, ECHO, OPENSHARE, LOGOFF] * 2)
        self.assertEqual(trace[-1], "connect -13")
        # Only a negative result is a failure.
        trace, _ = session(HANDLER, files, 1, ("connect",),
                           results=[(LOGON, 1), (ECHO, 7), (OPENSHARE, 0x1001)])
        self.assertEqual(trace[-1], "connect 0")

    def test_read_errors(self):
        for step, name, good in (("tcpip", "IPCONFIG.DAT", self.GOOD_IP),
                                 ("connect", "SMBCONFIG.DAT", self.GOOD_SMB)):
            for kw in ({"read_error": -5}, {"close_error": -5}):
                trace, args = session(HANDLER, {"mc0:/POPSTARTER/" + name: good}, 1, (step,), **kw)
                self.assertEqual(trace[-1], "tcpip NULL" if step == "tcpip" else "connect -5")
                self.assertFalse(devctls(trace))

    def test_other_smb_launches_keep_the_launchers_parser(self):
        """Not an SB. launch: the launcher's own rules and places, unchanged."""
        files = {"mc0:/POPSTARTER/SMBCONFIG.DAT": b"my-nas.local SHARE\nuser\npass\n",  # the original accepts this
                 "mc1:/POPSTARTER/SMBCONFIG.DAT": b"192.168.1.100:1445 PS2SMB\nuser\npassword\n",
                 "mc0:/POPSTARTER/ipconfig.dat": b"192.168.1.10 255.255.255.0 192.168.1.1\r\n"}
        trace, args = session(HANDLER, files, 0)
        self.assertEqual(args, b"192.168.1.10\0" b"255.255.255.0\0" b"192.168.1.1\0")
        self.assertEqual(opens(trace), ["mc0:/POPSTARTER/IPCONFIG.DAT", "mc0:/POPSTARTER/ipconfig.dat",
                                        "mc0:/POPSTARTER/SMBCONFIG.DAT"])
        self.assertEqual(trace[-1], "connect -22")
        del files["mc0:/POPSTARTER/SMBCONFIG.DAT"]
        trace, args = session(HANDLER, files, 0, ("connect",))
        calls = devctls(trace)
        # No echo outside an SB. launch.
        self.assertEqual([call[:2] for call in calls], [("smb:", LOGON), ("smb:", OPENSHARE)])
        got = fields(calls[0][2], calls[1][2])
        self.assertEqual((got["server"], got["port"], got["user"], got["password"], got["share"],
                          got["share_password"], got["password_type"], got["share_password_type"]),
                         (b"192.168.1.100", 1445, b"user", b"password", b"PS2SMB", b"password", 0, 0))
        trace, args = session(HANDLER, {}, 0, ("tcpip",))
        self.assertIsNone(args)             # without IPCONFIG.DAT the launcher's rule is an error


def _base_handler():
    try:
        text = subprocess.run(["git", "-C", str(ROOT), "show", BASE_REVISION + ":launcher/src/handler_smb.c"],
                              capture_output=True, check=True).stdout
    except Exception:
        return None
    if b"pops_get_active_sb_launch" in text:
        return None
    source = _WORK / "base" / "handler_smb.c"
    source.parent.mkdir(exist_ok=True)
    source.write_bytes(text)
    return build_handler(source, "handler_base")


BASE = _base_handler()


@unittest.skipUnless(BASE is not None, "revision %s is not in this checkout" % BASE_REVISION[:7])
class Unchanged(unittest.TestCase):
    """Outside an SB. launch handler_smb.c makes the same calls with the same
    bytes as the revision before this work."""

    def test_same_calls_as_before(self):
        rng = random.Random(0x4F4C4421)
        ips, smbs = ip_texts(), smb_texts()
        good_ip = [b"192.168.1.10 255.255.255.0 192.168.1.1\r\n", b"10.0.0.5\n255.0.0.0\n10.0.0.1\n"]
        good_smb = [b"192.168.1.100:1445 PS2SMB\nuser\npassword\n", b"192.168.1.100 PS2SMB\n\n\n",
                    b"192.168.1.100:1445 Share Name\r\ntest user\r\npass word\r\n"]
        dirs = ["mc0:/POPSTARTER/", "mc1:/POPSTARTER/", "mc0:/POPS/", "mc1:/POPS/", "mc0:/SYS-CONF/",
                "mc1:/SYS-CONF/", "mc0:/OTHER/"]
        runs = connected = 0
        for _ in range(900):
            files = {}
            for name, good, texts in (("IPCONFIG.DAT", good_ip, ips), ("SMBCONFIG.DAT", good_smb, smbs)):
                for _n in range(rng.choice([0, 1, 1, 1, 2, 3])):
                    place = rng.choice(dirs) + (name if rng.randrange(3) else name.lower())
                    files[place] = rng.choice(good) if rng.randrange(3) else rng.choice(texts)[:1500]
            kw = {"steps": rng.choice([("tcpip", "connect"), ("connect", "connect"),
                                       ("tcpip", "connect", "reset", "connect"), ("tcpip",)]),
                  "chunk": rng.choice([0, 0, 1, 16, 1000]),
                  "results": rng.choice([(), (), (), [(LOGON, -13)], [(OPENSHARE, -5)]]),
                  "read_error": rng.choice([0] * 9 + [-5]), "close_error": rng.choice([0] * 9 + [-5])}
            now = session(HANDLER, files, 0, **kw)
            before = session(BASE, files, 0, **kw)
            self.assertEqual(now, before, (files, kw))
            runs += 1
            connected += "connect 0" in now[0]
        self.assertGreater(connected, 150)
        self.assertEqual(runs, 900)

    def test_the_sb_flag_is_the_only_switch(self):
        """The same files give different calls on an SB. launch, so the
        comparison above is not vacuous."""
        files = {"mc0:/POPSTARTER/SMBCONFIG.DAT": b"my-nas.local SHARE\nuser\npass\n"}
        self.assertEqual(session(BASE, files, 1), session(BASE, files, 0))
        self.assertNotEqual(session(HANDLER, files, 1), session(HANDLER, files, 0))


def _image_text(addr):
    raw = T.image()[addr - T.BASE:addr - T.BASE + 96]
    return raw[:raw.index(0)]


@unittest.skipUnless(HAVE_EMU, "needs POPSTARTER_TEST_ELF and unicorn")
class Original(unittest.TestCase):
    """The original's own code, run as shipped."""

    @classmethod
    def setUpClass(cls):
        cls.emu = T.Emulator()

    def test_modelled_library_calls_mean_what_the_shipped_ones_do(self):
        rng = random.Random(7)
        cases = []
        for n in list(range(0, 24)) + [31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257, 520]:
            text = bytes(rng.randrange(1, 256) for _ in range(n))
            for src in (0, 1, 5, 8):
                cases.append((text, rng.choice([0, 1, n, n + 1, n + 9, max(n - 1, 0), 16]), src,
                              rng.choice([0, 3, 8])))
        self.assertEqual(T.library_check(cases), 3 * len(cases))
        self.assertGreaterEqual(len(cases), 140)

    def test_only_these_calls_leave_the_blocks(self):
        targets = set()
        for start, end in (T.DEFAULTS, T.CONFIG, T.SMAP, T.CONNECT):
            targets.update(t for t in T.call_targets(start, end))
        wrappers = set(range(T.WRAPPERS[0], T.WRAPPERS[1], 4))
        self.assertTrue(targets - wrappers <= set(T.STUBS), [hex(t) for t in targets])
        self.assertEqual(len(self.emu.mults), 10)
        self.assertTrue(all(T.CONFIG[0] <= a < T.CONFIG[1] for a in self.emu.mults))

    def test_sb_prefix(self):
        """The SB. test of argv[0]: `SB.` or `sb.` right after any ':', '/'
        or '\\' of the path, and it turns the messages on."""
        yes = [b"mass:/SB.GAME.ELF", b"mass:/sb.GAME.ELF", b"mc0:/SB.DIR/GAME.ELF", b"mass:\\SB.GAME.ELF",
               b"smb0:SB.GAME.ELF", b"mass:/SB.", b"mass:/SB.XX.GAME.ELF", b"mass:/XX.A/SB.B.ELF",
               b"mass:/SB.A/XX.B.ELF", b"hdd0:SB.x:pfs:/GAME.ELF"]
        no = [b"mass:/Sb.GAME.ELF", b"mass:/sB.GAME.ELF", b"SB.GAME.ELF", b"mass:/xSB.GAME.ELF",
              b"mass:/SB", b"mass:/POPS/GAME.ELF", b"", b"mass:/ SB.GAME.ELF"]
        for quiet in (1, 0):
            for argv0 in yes:
                self.assertEqual(T.scan(self.emu, argv0, quiet), {"mass": 1, "smb": 3, "quiet": 0}, argv0)
            for argv0 in no:
                got = T.scan(self.emu, argv0, quiet)
                self.assertEqual((got["smb"], got["quiet"]), (0, quiet), argv0)
        # An XX. name is looked for only when no SB. name was found.
        self.assertEqual(T.scan(self.emu, b"mass:/XX.SB.GAME.ELF")["smb"], 0)
        self.assertEqual(T.scan(self.emu, b"mass:/XX.SB.GAME.ELF")["mass"], 1)

    def test_defaults_and_echo(self):
        out = T.configure(self.emu, {T.SMB_PATHS[0]: b"1234567"})     # stops at the share
        self.assertEqual(out["message"], "smb-no-share")
        want_logon, want_share = default_images()
        self.assertEqual((out["logon"], out["share_raw"]), (bytes(want_logon), bytes(want_share)))
        echo = (c.c_uint8 * ECHO_SIZE)()
        P.pops_smb_echo_request(echo)
        self.assertEqual(out["echo"], bytes(echo))

    def original_ip(self, text, card=0):
        out = T.configure(self.emu, {T.IP_PATHS[card]: text, T.SMB_PATHS[0]: b"192.168.0.2 SHARE"})
        if out["fatal"] is None:
            return OK, out
        return {"ip-size-mc0": SIZE, "ip-size-mc1": SIZE, "ip-syntax": IP_SYNTAX}[out["message"]], out

    def test_ipconfig(self):
        classes = {OK: 0, SIZE: 0, IP_SYNTAX: 0}
        for text in ip_texts():
            want, out = self.original_ip(text)
            rc, length, buf = ipconfig(text)
            self.assertEqual(rc, want, text)
            classes[rc] += 1
            self.assertEqual(out["ip_absent"], 0)
            self.assertFalse(out["outside"], text)
            if rc == OK:
                self.assertEqual((length, buf), (out["ip_length"], out["ip_block"]), text)
        self.assertGreater(min(classes.values()), 60, classes)

    def test_ipconfig_is_what_the_network_module_is_started_with(self):
        rng = random.Random(3)
        texts = IP_FIXED + [random_ip(rng) for _ in range(60)]
        started = 0
        for text in texts:
            rc, length, buf = ipconfig(text)
            for card in (0, 1):
                got = T.start_smap(self.emu, text, card=card)
                if rc != OK:
                    self.assertIsNone(got, text)
                    continue
                arg_length, null, block, _size = got
                self.assertEqual((arg_length, null, block), (length, False, buf[:length]), text)
                started += 1
        self.assertGreater(started, 60)
        # Without the file: no arguments at all.
        self.assertEqual(T.start_smap(self.emu, None)[:3], (0, True, b""))

    def original_smb(self, text, sentinel=0):
        out = T.configure(self.emu, {T.SMB_PATHS[0]: text}, sentinel=sentinel)
        ends = {T.GP + T.G_LOGON: T.GP + T.G_LOGON + LOGON_SIZE,
                T.GP + T.G_SHARE: T.GP + T.G_SHARE + SHARE_SIZE}
        past = False
        for _kind, dst, count, _site in out["copies"]:
            home = [end for start, end in ends.items() if start <= dst < end]
            self.assertEqual(len(home), 1, hex(dst))
            past = past or dst + count > home[0]
        if past:
            return OVERFLOW, out
        if out["fatal"] is None:
            return OK, out
        return {"smb-size-mc0": SIZE, "smb-no-share": NO_SHARE, "smb-server-length": SERVER_LENGTH,
                "smb-bad-port": BAD_PORT}[out["message"]], out

    def test_smbconfig(self):
        classes = {k: 0 for k in (OK, SIZE, NO_SHARE, SERVER_LENGTH, BAD_PORT, OVERFLOW)}
        for text in smb_texts():
            want, out = self.original_smb(text)
            rc, logon, share = smbconfig(text)
            self.assertEqual(rc, want, text[:80])
            classes[rc] += 1
            self.assertEqual(out["ip_absent"], 1)
            if rc != OVERFLOW:
                # Nothing but the two structures changes.
                self.assertFalse(out["outside"], text[:80])
            if rc == OK:
                self.assertEqual((logon, share), (out["logon"], out["share_raw"]), text[:80])
        self.assertGreater(min(classes.values()), 25, classes)

    def test_what_is_refused_as_too_long_is_a_write_past_a_structure(self):
        """The one class the C does not reproduce: the original writes these
        over whatever follows its structure."""
        cases = [text for text in SMB_FIXED if smbconfig(text)[0] == OVERFLOW]
        self.assertGreater(len(cases), 40)
        for text in cases:
            for sentinel in (0x5A, 0xA7):
                want, out = self.original_smb(text, sentinel)
                self.assertEqual(want, OVERFLOW)
                self.assertTrue(out["outside"], text[:40])
        # And the longest values that are accepted change nothing outside.
        for text in (b"10.0.0.2 S\n" + b"u" * 515 + b"\npw\n", b"10.0.0.2 S\nme\n" + b"p" * 259 + b"\n",
                     b"10.0.0.2 sh:" + b"w" * 259, b"10.0.0.2 " + b"s" * 516):
            for sentinel in (0x5A, 0xA7):
                want, out = self.original_smb(text, sentinel)
                self.assertEqual((want, out["outside"]), (OK, {}), text[:40])
                self.assertEqual(smbconfig(text)[1:], (out["logon"], out["share_raw"]))

    def test_which_card(self):
        good = b"10.0.0.1 S1"
        for name, paths, size0, size1, missing in (
                ("ip", T.IP_PATHS, "ip-size-mc0", "ip-size-mc1", None),
                ("smb", T.SMB_PATHS, "smb-size-mc0", "smb-size-mc1", "smb-missing")):
            base = {} if name == "smb" else {T.SMB_PATHS[0]: good}
            text = good if name == "smb" else b"1.1.1.1 2.2.2.2 3.3.3.3"

            def run(files):
                out = T.configure(self.emu, dict(base, **files))
                return out["message"], [p for p, _mode, _fd in out["opens"] if p in paths]

            self.assertEqual(run({paths[0]: text}), (None, [paths[0]]))
            self.assertEqual(run({paths[1]: text}), (None, list(paths)))
            self.assertEqual(run({paths[0]: text, paths[1]: b"short"}), (None, [paths[0]]))
            # A file the first card has but that is not accepted: the second is not tried.
            self.assertEqual(run({paths[0]: b"short", paths[1]: text}), (size0, [paths[0]]))
            self.assertEqual(run({paths[1]: b"short"}), (size1, list(paths)))
            self.assertEqual(run({}), (missing, list(paths)))
        out = T.configure(self.emu, {T.SMB_PATHS[0]: good})
        self.assertEqual([mode for _p, mode, _fd in out["opens"]], [1, 1, 1])
        # Lower-case names are not looked for.
        out = T.configure(self.emu, {T.SMB_PATHS[0].replace("SMBCONFIG.DAT", "smbconfig.dat"): good})
        self.assertEqual(out["message"], "smb-missing")
        self.assertEqual([p for p, _m, _f in out["opens"]], list(T.IP_PATHS) + list(T.SMB_PATHS))

    def test_messages(self):
        for addr, key in T.MESSAGES.items():
            text = _image_text(addr)
            if key.startswith("ip-size") or key.startswith("smb-size"):
                self.assertIn(b"mc%s:/POPSTARTER/" % key[-1:].encode(), text)
                self.assertIn(b"IPCONFIG.DAT" if key.startswith("ip") else b"SMBCONFIG.DAT", text)
            elif key == "smb-missing":
                self.assertIn(b"SMBCONFIG.DAT", text)
            else:
                self.assertIn(b"SYNTAX ERROR", text)

    def test_connect(self):
        echo = (c.c_uint8 * ECHO_SIZE)()
        P.pops_smb_echo_request(echo)
        logon, share = default_images()
        ok = T.connect(self.emu)
        self.assertEqual([(call[0], call[1], call[2], call[4]) for call in ok["calls"]],
                         [("mass0:", LOGON, LOGON_SIZE, True), ("mass0:", ECHO, ECHO_SIZE, True),
                          ("mass0:", OPENSHARE, SHARE_SIZE, True)])
        self.assertEqual([call[3] for call in ok["calls"]], [bytes(logon), bytes(echo), bytes(share)])
        self.assertEqual([call[5] for call in ok["calls"]], [(0, 0)] * 3)      # no output buffer
        self.assertEqual((ok["fatal"], ok["connected"], ok["folder_checked"]), (None, 1, 1))
        self.assertEqual(ok["opens"], [("mass:/POPS/POPS_IOX.PAK", 1)])
        # A negative result stops it there; the number printed is the 0 of
        # the comparison, not the driver's result.
        for kw, made in (({"logon": -13}, 1), ({"echo": -13}, 2), ({"openshare": -13}, 3)):
            got = T.connect(self.emu, **kw)
            self.assertEqual(len(got["calls"]), made, kw)
            self.assertEqual((got["connected"], got["opens"]), (0, []), kw)
            self.assertIsNotNone(got["fatal"])
            self.assertEqual(got["prints"][-1][2], (0,), kw)
        for kw in ({"logon": 1}, {"echo": 7}, {"openshare": 0x1001}):
            self.assertIsNone(T.connect(self.emu, **kw)["fatal"], kw)       # only < 0 is a failure
        # The folder check: up to 119 opens of the PAK, no pause between them.
        for failures, want in ((0, 1), (3, 4), (118, 119)):
            got = T.connect(self.emu, opens_before_success=failures)
            self.assertEqual((len(got["opens"]), got["fatal"], got["connected"]), (want, None, 1))
        for failures in (119, None):
            got = T.connect(self.emu, opens_before_success=failures)
            self.assertEqual((len(got["opens"]), got["connected"]), (119, 0))
            self.assertIsNotNone(got["fatal"])


class Source(unittest.TestCase):
    def setUp(self):
        self.src = (ROOT / "launcher/src/handler_smb.c").read_text()

    def body(self, signature):
        start = self.src.index(signature)
        return self.src[start:self.src.index("\n}\n", start)]

    def test_sb_launches_use_the_originals_rules(self):
        tcpip = self.body("char *initTCPIPArguments(uint32_t *length) {")
        self.assertLess(tcpip.index("if (pops_get_active_sb_launch())\n    return sb_tcpip_arguments(length);"),
                        tcpip.index('read_config("IPCONFIG.DAT"'))
        connect = self.body("int launcher_smb_connect(void) {")
        gate = connect.index("if (pops_get_active_sb_launch())\n    return sb_connect();")
        self.assertLess(connect.index("if (connected) return 0;"), gate)
        self.assertLess(gate, connect.index('read_config("SMBCONFIG.DAT"'))
        self.assertEqual(self.src.count("pops_get_active_sb_launch()"), 2)
        self.assertIn("pops_parse_ipconfig(text, n, &size)", self.body("static char *sb_tcpip_arguments("))
        sb = self.body("static int sb_connect(void) {")
        self.assertIn("pops_parse_smbconfig(text, result, (unsigned char *)&logon, (unsigned char *)&share)", sb)
        self.assertIn("_Static_assert(sizeof(logon) == POPS_SMB_LOGON_SIZE", sb)
        self.assertIn("_Static_assert(sizeof(share) == POPS_SMB_SHARE_SIZE", sb)
        self.assertLess(sb.index("SMB_DEVCTL_LOGON,"), sb.index("pops_smb_echo_request((unsigned char *)&echo);"))
        self.assertLess(sb.index("pops_smb_echo_request("), sb.index("SMB_DEVCTL_ECHO, &echo, sizeof(echo)"))
        self.assertLess(sb.index("SMB_DEVCTL_ECHO,"), sb.index("SMB_DEVCTL_OPENSHARE,"))
        self.assertIn("_Static_assert(sizeof(echo) == POPS_SMB_ECHO_SIZE", sb)
        # Only the SB. path sends it.
        self.assertEqual(self.src.count("SMB_DEVCTL_ECHO"), 1)
        reader = self.body("static int read_sb_config(")
        self.assertIn("pops_netconfig_path(i, name, path, sizeof(path))", reader)

    def test_the_launchers_own_parser_is_still_there(self):
        self.assertEqual(self.src.count("launcher_parse_tcpip_config("), 1)
        self.assertEqual(self.src.count("launcher_parse_smb_config("), 1)
        self.assertIn('"mc0:/POPSTARTER/", "mc1:/POPSTARTER/", "mc0:/POPS/", "mc1:/POPS/",\n'
                      '    "mc0:/SYS-CONF/", "mc1:/SYS-CONF/"', self.src)

    def test_built_and_tested(self):
        cmake = (ROOT / "launcher/CMakeLists.txt").read_text()
        self.assertIn("src/handler_smb.c ../common/src/network_config.c ../common/src/pops_smb_config.c", cmake)
        workflow = (ROOT / ".github/workflows/build.yml").read_text()
        self.assertIn("python tools/test_pops_smb_config.py", workflow)
        for script in ("tools/prepare_network_transport_probe.py", "tools/prepare_pops_device_inventory.py"):
            self.assertIn("pops_smb_config.c", (ROOT / script).read_text(), script)

    def test_sizes_match_the_driver_header(self):
        header = (ROOT / "launcher/iop/smbman/include/ps2smb.h").read_text()
        for line in ("#define SMB_DEVCTL_LOGON             0xC0DE0002",
                     "#define SMB_DEVCTL_OPENSHARE         0xC0DE0005",
                     "#define SMB_DEVCTL_ECHO              0xC0DE0007",
                     "{ // size = 536\n    char serverIP[16];\n    int serverPort;\n    char User[256];\n"
                     "    char Password[256];\n    int PasswordType;",
                     "{ // size = 520\n    char ShareName[256];\n    char Password[256];\n    int PasswordType;",
                     "{ // size = 260\n    char echo[256];\n    int len;"):
            self.assertIn(line, header)
        # The header's comment on the share structure says 520; it is 516
        # (handler_smb.c asserts both sizes when it is compiled).
        self.assertEqual((LOGON_SIZE, SHARE_SIZE, ECHO_SIZE), (16 + 4 + 256 + 256 + 4, 256 + 256 + 4, 256 + 4))


if __name__ == "__main__":
    unittest.main()
