#!/usr/bin/env python3
"""Build a controlled fresh-IOP network fixture from production module arrays."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from prepare_pops_device_inventory import ROOT,array

def prepare(build,out):
    if out.exists() or not out.resolve().is_relative_to((ROOT/'build').resolve()):
        raise ValueError('use a fresh ignored build directory')
    launcher_dir = build / 'launcher' if (build / 'launcher').is_dir() else build
    modules = {}
    for name in ('iomanX', 'fileXio', 'sio2man', 'mcman', 'mcserv', 'ps2dev9', 'netman',
                 'smap_tcpip', 'ps2ip-nm', 'launcher_smbman', 'smap', 'ministack',
                 'udpfs_ioman', 'bdm', 'bdmfs_fatfs', 'udpbd'):
        source = (launcher_dir / f'{name}.irx.c').read_text()
        body = re.search(r'unsigned char\s+\w+\[\].*?=\s*\{(.*?)\};', source, re.S)
        size = re.search(r'unsigned int\s+size_\w+\s*=\s*(\d+)', source)
        if not body or not size:
            raise ValueError('invalid module array ' + name)
        data = bytes(int(x, 16) for x in re.findall(r'0x([0-9a-fA-F]{2})\b', body[1]))
        if len(data) != int(size[1]) or not data.startswith(b'\x7fELF'):
            raise ValueError('bad module ' + name)
        modules[name.replace('-', '_')] = data
    out.mkdir(parents=True)
    shutil.copyfile(ROOT/'tools/fixtures/network_transport_ee.c',out/'network_transport_ee.c')
    for name in ('network_config.h','ipconfig_smap.h','handler_smb.h','common.h'):
        shutil.copyfile(ROOT/'launcher/include'/name,out/name)
    shutil.copyfile(ROOT/'common/include/loader.h',out/'loader.h')
    shutil.copyfile(ROOT/'launcher/iop/smbman/include/ps2smb.h',out/'ps2smb.h')
    shutil.copyfile(ROOT/'launcher/src/handler_smb.c',out/'handler_smb.c')
    shutil.copyfile(ROOT/'common/src/network_config.c',out/'network_config.c')
    fixture=(ROOT/'tools/fixtures/pops_device_inventory_ee.c').read_text()
    start=fixture.index('static int network_fixture_test(')
    end=fixture.index('\nint main(',start)
    (out/'fixture_io.h').write_text(fixture[start:end])
    for name,data in modules.items():(out/f'{name}_irx.c').write_text(array(name,data))
    target={'name':'network','type':'ee','sources':['network_transport_ee.c','handler_smb.c','network_config.c']+
            [f'{name}_irx.c' for name in modules], 'include_dirs':['.'],
            'embed_irx':['udptty'],'libs':['patches','filexio','debug'],'debug':True}
    (out/'ps2.yaml').write_text(json.dumps({'project':'network-transport-probe','targets':[target]},indent=2)+'\n')
    (out/'provenance.json').write_text(json.dumps({name:hashlib.sha256(data).hexdigest()
        for name,data in modules.items()},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--launcher-build',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();prepare(a.launcher_build,a.out)
