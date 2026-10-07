"""Compare two shard files (e.g. CPU vs GPU over the same range): exit 0 iff identical key/program sets.
Usage: python3 fast/compare_shards.py a.bin b.bin"""
import struct, sys
from pathlib import Path
def load(fn):
    b = Path(fn).read_bytes(); hdr = struct.unpack_from("<8I", b, 0); lo, hi, n = struct.unpack_from("<3Q", b, 32); off = 56 + hdr[7]
    return hdr[1:], (lo, hi), {struct.unpack_from("<QQI", b, off + i * 20)[:2]: struct.unpack_from("<QQI", b, off + i * 20)[2] for i in range(n)}
ha, ra, a = load(sys.argv[1]); hb, rb, b = load(sys.argv[2])
ok = ha == hb and ra == rb and a == b
print(("IDENTICAL" if ok else "DIFFER") + f": {len(a)} vs {len(b)} tables, range {ra} vs {rb}, cfg {'same' if ha == hb else 'differs'}")
if not ok and a.keys() == b.keys(): print("same tables, different first-program ids:", sum(a[k] != b[k] for k in a))
sys.exit(0 if ok else 1)
