"""Publish complete experiment shards as portable ZIP archives plus checksums."""
import hashlib
import json
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/witnesses"
OUT.mkdir(exist_ok=True)
entries = []
for result in sorted((ROOT / "results").glob("exp03_*.json")):
    data = json.loads(result.read_text())
    if "programs_covered" not in data:
        continue
    tag = result.stem.removeprefix("exp03_")
    files = sorted((ROOT / "results/shards").glob(f"{tag}_[0-9][0-9][0-9][0-9].bin"))
    ranges = []
    for path in files:
        with path.open("rb") as src:
            header = src.read(56)
        fields = struct.unpack("<8I3Q", header)
        magic, w, a, p, i, o, binary, nisa, lo, hi, count = fields
        assert magic == 0x55314231, path
        assert (w, a, p, i, o, bool(binary)) == (data['W'], data['a'], data['p'], data['I'], data['opcode_bits'], data['binary']), path
        assert path.stat().st_size == 56 + nisa + count * 20, path
        ranges.append([lo, hi])
    assert sorted(ranges) == sorted(data['programs_covered']), tag
    cursor = 0
    for lo, hi in sorted(ranges):
        assert lo == cursor and hi > lo, tag
        cursor = hi
    assert cursor == 1 << 32, tag
    # Small archives allow reliable incremental pushes over constrained HTTP links.
    groups = [[]]
    size = 0
    for path in files:
        if groups[-1] and size + path.stat().st_size > 16 * 1024**2:
            groups.append([])
            size = 0
        assert path.stat().st_size < 90 * 1024**2, path
        groups[-1].append(path)
        size += path.stat().st_size
    archives = []
    for index, group in enumerate(groups):
        archive = OUT / f"{tag}.part{index + 1:02d}.zip"
        expected = [p.relative_to(ROOT).as_posix() for p in group]
        if not archive.exists():
            temporary = archive.with_suffix('.zip.tmp')
            with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
                for path, name in zip(group, expected):
                    info = zipfile.ZipInfo(name, date_time=(2026, 10, 7, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    bundle.writestr(info, path.read_bytes(), compresslevel=6)
            temporary.replace(archive)
        with zipfile.ZipFile(archive) as bundle:
            assert bundle.namelist() == expected, archive
            assert bundle.testzip() is None, archive
            for path, name in zip(group, expected):
                assert hashlib.sha256(bundle.read(name)).digest() == hashlib.sha256(path.read_bytes()).digest(), path
        assert archive.stat().st_size < 100 * 1024**2, archive
        archives.append({'file': archive.name, 'bytes': archive.stat().st_size,
                         'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                         'shards': expected})
    entries.append({'run': tag, 'result': result.relative_to(ROOT).as_posix(),
                    'programs': cursor, 'shard_count': len(files), 'archives': archives})
    print(f"{tag}: {len(files)} shards in {len(archives)} verified archive(s)", flush=True)
(OUT / 'manifest.json').write_text(json.dumps({'format': 'u1-shards-v1', 'runs': entries}, indent=2) + '\n')
