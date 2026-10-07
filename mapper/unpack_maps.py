"""Restore large .u1prog maps from their verified repository ZIP archives."""
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]/'results/maps'
for item in json.loads((root/'new-map-manifest.json').read_text()):
    if 'archive' not in item: continue
    assert Path(item['file']).name==item['file'] and Path(item['archive']).name==item['archive']
    target=root/item['file']; source=root/item['archive']
    if target.exists():
        with target.open('rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=item['sha256']:
                raise ValueError(f'Existing map differs; preserve or move it before extracting: {target}')
        continue
    with source.open('rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==item['archive_sha256']
    temporary=target.with_suffix('.u1prog.tmp')
    with zipfile.ZipFile(source) as archive:
        assert archive.namelist()==[item['file']]
        with archive.open(item['file']) as src,temporary.open('wb') as dst: shutil.copyfileobj(src,dst)
    with temporary.open('rb') as f: assert hashlib.file_digest(f,'sha256').hexdigest()==item['sha256']
    temporary.replace(target)
    print('Restored',target)
