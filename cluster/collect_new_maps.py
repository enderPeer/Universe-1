"""Fetch the eight completed program maps; archive large maps for GitHub."""
import hashlib
import json
import shutil
import struct
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TAGS=['w1_nand_jz_bin','w1_nand_skz_bin','w2_o1_bin','w2_o1_swap_bin',
      'w4_o2_nand_bin','w4_o4_full_bin','w4_o3_swap_bin','w4_o2_add_bin']
paths=[f'results/maps/{tag}.u1prog' for tag in TAGS]
with tempfile.TemporaryFile() as stream:
    subprocess.run(['ssh','falke64','cd universe-1 && tar -cf - '+' '.join(paths)],stdout=stream,check=True)
    stream.seek(0)
    with tarfile.open(fileobj=stream) as archive:
        received=set()
        for item in archive:
            if not item.isfile() or item.name not in paths: raise ValueError(item.name)
            with archive.extractfile(item) as src,(ROOT/item.name).open('wb') as dst: shutil.copyfileobj(src,dst)
            received.add(item.name)
        assert received==set(paths)
manifest=[]
for tag in TAGS:
    path=ROOT/f'results/maps/{tag}.u1prog'
    with path.open('rb') as f:
        assert f.read(8)==b'U1PROG01'
        w,a,p,i,binary,nisa=struct.unpack('<6I',f.read(24))
        f.read(nisa); count=struct.unpack('<Q',f.read(8))[0]
    result=json.loads((ROOT/f'results/exp03_{tag}.json').read_text())
    assert count==result['distinct_operators']
    assert path.stat().st_size==40+nisa+8*count
    with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    entry={'file':path.name,'operators':count,'bytes':path.stat().st_size,'sha256':digest,
           'build_source_commit':'96b8687'}
    if path.stat().st_size>50*1024**2:
        archive=path.with_suffix('.u1prog.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z: z.write(path,path.name)
        with zipfile.ZipFile(archive) as z:
            assert z.namelist()==[path.name]
            with z.open(path.name) as f: assert hashlib.file_digest(f,'sha256').hexdigest()==digest
        assert archive.stat().st_size<100*1024**2
        entry.update(archive=archive.name,archive_bytes=archive.stat().st_size,
                     archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    manifest.append(entry)
    print(tag,count,'operators;',path.stat().st_size,'bytes',flush=True)
(ROOT/'results/maps/new-map-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
