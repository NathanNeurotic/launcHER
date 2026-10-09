#!/usr/bin/env python3
import re
import sys
from pathlib import Path

LIBCRYPT_SERIES = [
    "SCES-01492", "SCES-00311", "SCES-01495",  # MediEvil
    "SLES-02529", "SLES-02530", "SLES-02531", "SLES-02532", "SLES-02533",  # Resident Evil 3
    "SLES-02080", "SLES-02081", "SLES-02082", "SLES-02083", "SLES-02084",  # FF8 Disc 1
    "SLES-12080", "SLES-12081", "SLES-12082", "SLES-12083", "SLES-12084",  # FF8 Disc 2
    "SLES-22080", "SLES-22081", "SLES-22082", "SLES-22083", "SLES-22084",  # FF8 Disc 3
    "SLES-32081", "SLES-32082", "SLES-32083", "SLES-32084",  # FF8 Disc 4
    "SLES-02965", "SLES-02966", "SLES-02967", "SLES-02968", "SLES-02969",  # FF9 Disc 1
    "SLES-12965", "SLES-12966", "SLES-12967", "SLES-12968", "SLES-12969",  # FF9 Disc 2
    "SLES-22965", "SLES-22966", "SLES-22967", "SLES-22968", "SLES-22969",  # FF9 Disc 3
    "SLES-32965", "SLES-32966", "SLES-32967", "SLES-32968", "SLES-32969",  # FF9 Disc 4
    "SLES-02207", "SLES-02208", "SLES-02209", "SLES-02210", "SLES-02211",  # Dino Crisis
    "SCES-02105",  # Crash Team Racing
    "SCES-02834",  # Crash Bash
    "SCES-01564", "SCES-02028", "SCES-02029", "SCES-02030", "SCES-02031",  # Ape Escape
    "SLES-01301", "SLES-02024", "SLES-02025", "SLES-02026",  # Soul Reaver
    "SLES-01226",  # Actua Ice Hockey 2
    "SLES-03324",  # Asterix Mega Madness
    "SCES-02365", "SCES-02366", "SCES-02367", "SCES-02369", "SCES-02488", "SCES-02489", "SCES-02491",  # Barbie
    "SLES-02977", "SLES-03605",  # BDFL Manager
    "SLES-02293",  # Canal+ Premier Manager
    "SCES-02004", "SCES-02005", "SCES-02006", "SCES-02007", "SCES-01695",  # Mulan
    "SCES-01516", "SCES-01518", "SCES-01519",  # Tarzan
    "SLES-03191",  # 102 Dalmatians
    "SLES-02538",  # Superbike 2000
    "SLES-01715",  # Eagle One
    "SLES-02722", "SLES-02724",  # F1 2000
    "SCES-01979",  # Formula One 99
    "SLES-02767",  # Frontschweine
    "SLES-02328", "SLES-02329", "SLES-02330", "SLES-12328", "SLES-12329",  # Galerians
    "SCES-01704",  # Esto Es Futbol
    "SCES-01702",  # Fussball Live
    "SLES-02758", "SLES-02759", "SLES-02760", "SLES-02761", "SLES-02762",  # Vagrant Story
    "SCES-01909",  # WipEout 3
    "SCES-02104",  # Spyro 2
    "SCES-02835",  # Spyro 3
    "SLES-02558", "SLES-02559", "SLES-02560", "SLES-02561", "SLES-02562", "SLES-12558",  # Parasite Eve II
    "SLES-02688", "SLES-02689", "SLES-02690", "SLES-02691", "SLES-02692",  # NFS Porsche
    "SLES-02742", "SLES-02743", "SLES-02744", "SLES-02745",  # RE Survivor
    "SLES-02662",  # SaGa Frontier 2
    "SLES-01826",  # Ronaldo V-Football
    "SLES-02572",  # TOCA World Touring Cars
    "SLES-02700", "SLES-02701", "SLES-02702", "SLES-02703", "SLES-02704",  # UEFA Euro 2000
    "SLES-01997",  # V-Rally 2
]

KNOWN_MODES = {
    # Gran Turismo 2: Mode 2 (fast cache) + Mode 4 (skip GPU locks)
    "SCES-02380": 0x0A, "SCES-12380": 0x0A, "SCUS-94455": 0x0A, "SCUS-94488": 0x0A,
    "SCPS-10116": 0x0A, "SCPS-10117": 0x0A,
    # Tekken 3: Mode 2
    "SCES-01237": 0x02, "SLUS-00402": 0x02, "SLPS-01300": 0x02, "SLPS-91202": 0x02,
    # Castlevania: SOTN: Mode 1 + Mode 2
    "SLES-00524": 0x03, "SLUS-00067": 0x03, "SLPM-86023": 0x03,
    # Chrono Cross: Mode 1
    "SLUS-01041": 0x01, "SLUS-01080": 0x01, "SLPS-02364": 0x01, "SLPS-02365": 0x01,
    # Valkyrie Profile: Mode 7 (throttle cycle counter)
    "SLUS-01156": 0x40, "SLUS-01179": 0x40, "SLPS-02480": 0x40, "SLPS-02481": 0x40,
    # MediEvil: Mode 1
    "SCES-01492": 0x01, "SCES-00311": 0x01, "SCUS-94227": 0x01,
    # Crash Team Racing: Mode 2
    "SCES-02105": 0x02, "SCUS-94426": 0x02, "SCPS-10118": 0x02,
    # Dino Crisis: Mode 1
    "SLES-02207": 0x01, "SLUS-00922": 0x01, "SLPS-02180": 0x01,
    # Resident Evil 3: Mode 1
    "SLES-02529": 0x01, "SLUS-00923": 0x01, "SLPS-02300": 0x01,
}

def popcount(v: int) -> int:
    return bin(v).count("1")

def main():
    repo_root = Path("C:/Users/natha/Github/REPOP")
    db_md = repo_root / "docs/COMPATIBILITY_DATABASE.md"
    libcrypt_md = repo_root / "DKWDRV/upstream/docs/files/libcrypt.md"

    if not db_md.exists():
        print(f"Error: {db_md} not found", file=sys.stderr)
        sys.exit(1)

    # 1. Parse LibCrypt canonical database
    lib_keys = {}
    if libcrypt_md.exists():
        for line in libcrypt_md.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("|") and not line.startswith("| :") and not line.startswith("| Game"):
                parts = [x.strip() for x in line.split("|")[1:-1]]
                if len(parts) >= 3 and parts[1].isdigit():
                    raw_s = parts[0]
                    norm_s = f"{raw_s[:4]}-{raw_s[4:]}" if len(raw_s) == 9 else raw_s
                    key = int(parts[1])
                    title = parts[2].replace('"', '\\"')
                    # Validate 8-bit invariant
                    if key > 0 and popcount(key) == 8:
                        lib_keys[norm_s] = (key, title)
                    elif key == 0:
                        lib_keys[norm_s] = (0, title)

    with open(db_md, "r", encoding="utf-8") as f:
        text = f.read()

    entries = []
    seen_serials = set()

    for line in text.splitlines():
        if line.startswith("|") and not line.startswith("| #") and not line.startswith("|--"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 4:
                title = parts[1].replace('"', '\\"')
                serials_raw = parts[2].replace("`", "")
                region = parts[3]
                for raw_s in serials_raw.split("/"):
                    s = raw_s.strip()
                    if s and s not in seen_serials:
                        seen_serials.add(s)
                        has_lib = 1 if (s in lib_keys or s in LIBCRYPT_SERIES or "LibCrypt" in title) else 0
                        key = lib_keys.get(s, (0, ""))[0]
                        mode = KNOWN_MODES.get(s, 0)
                        if has_lib:
                            mode |= 0x20  # Mode 6 (LibCrypt subchannel bypass)
                        entries.append((s, title, mode, has_lib, key))

    # Add any remaining LibCrypt titles not in the main compatibility table
    for s, (key, title) in lib_keys.items():
        if s not in seen_serials:
            seen_serials.add(s)
            entries.append((s, title, 0x20, 1, key))

    # Sort entries by serial for binary search
    entries.sort(key=lambda e: e[0])

    out_file = Path("common/src/pops_compat_db.c")
    with open(out_file, "w", encoding="utf-8") as out:
        out.write('/* Auto-generated compatibility database from COMPATIBILITY_DATABASE.md and libcrypt.md */\n')
        out.write('#include "pops_compat_db.h"\n')
        out.write('#include <ctype.h>\n')
        out.write('#include <string.h>\n\n')

        out.write('static const PopsCompatEntry s_compat_entries[] = {\n')
        for s, title, mode, libcrypt, key in entries:
            out.write(f'  {{ "{s}", "{title}", 0x{mode:02X}, {libcrypt}, 0x{key:04X}, 0, 0 }},\n')
        out.write('};\n\n')

        out.write(f'#define COMPAT_ENTRY_COUNT {len(entries)}\n\n')

        out.write('size_t pops_compat_db_count(void) {\n')
        out.write('  return COMPAT_ENTRY_COUNT;\n')
        out.write('}\n\n')

        out.write('const PopsCompatEntry *pops_compat_db_get(size_t index) {\n')
        out.write('  if (index >= COMPAT_ENTRY_COUNT)\n')
        out.write('    return NULL;\n')
        out.write('  return &s_compat_entries[index];\n')
        out.write('}\n\n')

        out.write('''static void normalize_for_lookup(const char *in, char *out, size_t out_size) {
  size_t pos = 0;
  while (*in && pos < out_size - 1) {
    if (isalnum((unsigned char)*in)) {
      out[pos++] = (char)toupper((unsigned char)*in);
    }
    in++;
  }
  out[pos] = '\\0';
}

const PopsCompatEntry *pops_compat_db_lookup(const char *serial) {
  if (!serial || !serial[0])
    return NULL;

  char key[32];
  normalize_for_lookup(serial, key, sizeof(key));
  if (!key[0])
    return NULL;

  /* Linear scan with normalized comparison */
  for (size_t i = 0; i < COMPAT_ENTRY_COUNT; ++i) {
    char entry_key[32];
    normalize_for_lookup(s_compat_entries[i].serial, entry_key, sizeof(entry_key));
    if (!strcmp(key, entry_key))
      return &s_compat_entries[i];
  }

  return NULL;
}
''')

    print(f"Generated {out_file} with {len(entries)} entries.")

if __name__ == "__main__":
    main()
