# Witness program shards for Fable

The actual binary witness shards are stored here in ordinary Git as ZIP
archives, split by sweep and, when needed, into numbered parts. They do not
require Git LFS or access to the LAN cluster. Download **all parts** of a run.
`manifest.json` lists every archive, SHA-256 checksum, and included shard.
Only completed sweeps are packaged; the finalizer adds the remaining sweeps.

After cloning this branch, extract from the repository root:

```python
import hashlib, json, pathlib, zipfile
root = pathlib.Path('results/witnesses')
manifest = json.loads((root / 'manifest.json').read_text())
for run in manifest['runs']:
    for item in run['archives']:
        path = root / item['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256']
        with zipfile.ZipFile(path) as archive:
            assert archive.namelist() == item['shards']
            for name in archive.namelist():
                assert name.startswith('results/shards/') and '..' not in pathlib.PurePosixPath(name).parts
            archive.extractall('.')
```

This restores `results/shards/<ISA>_<chunk>.bin` exactly. Source copies are
also retained at `/home/ender/universe-1/results/shards/` on the producing
cluster nodes and `C:\Users\end\Desktop\u1\results\shards\` on the coordinator.

## Binary format (for a Rust mapper)

All fields are little-endian; records have **no padding**.

| Offset | Type | Meaning |
|---:|---|---|
| 0 | 8 x u32 | magic `0x55314231`, W, a, p, I, opcode bits, binary flag, ISA length |
| 32 | 3 x u64 | program range start (inclusive), end (exclusive), record count |
| 56 | ISA-length x u8 | primitive IDs in opcode order |
| 56 + ISA length | record-count x 20 bytes | each record: key-low u64, key-high u64, minimum program ID u32 |

Primitive ID order is `PNAME` in `fast/merge.py` / `fast/u1.c`. Decode a
program's instruction k as `(program_id >> (k * I)) & ((1 << I) - 1)`;
opcode uses the high opcode bits and operand uses the remaining low bits.
For each key, take the minimum program ID across **all shards of that run**.
That is the minimum numeric program ID, not a shortest-length proof.

Keys are exact packed truth tables when the table fits 128 bits, otherwise
two 64-bit hashes. Hashed keys cannot reconstruct a truth table: execute the
witness with `sim/machine.py` or a compatible mapper. Unary inputs iterate x;
binary inputs iterate x then y. The execution budget is 256 steps.
