"""Check sampled GPU shard witnesses against the independent Python machine.

Run from the repository root after a sweep. Checks up to 3 records from every
shard of each completed result, using a fixed seed for reproducibility.
"""
import argparse
import json
import random
import struct
from pathlib import Path

from crosscheck import key
from sim.machine import Config, Machine


rng = random.Random(7132)
parser=argparse.ArgumentParser(); parser.add_argument('--experiment',choices=['exp03','exp05'],default='exp03'); args=parser.parse_args()
total = 0
for result in sorted(Path("results").glob(f"{args.experiment}_*.json")):
    data = json.loads(result.read_text())
    if "distinct_operators" not in data:
        continue
    tag = result.stem.removeprefix(args.experiment+'_')
    cfg = Config(W=data["W"], a=data["a"], p=data["p"], I=data["I"])
    machine = Machine(cfg, tuple(data["isa"]))
    checked = 0
    for path in sorted(Path("results/shards").glob(f"{tag}_[0-9][0-9][0-9][0-9].bin")):
        blob = path.read_bytes()
        header = struct.unpack_from("<8I", blob)
        lo, hi, count = struct.unpack_from("<3Q", blob, 32)
        offset = 56 + header[7]
        assert header[0] == 0x55314231 and len(blob) == offset + count * 20, path
        for index in rng.sample(range(count), min(3, count)):
            klo, khi, program = struct.unpack_from("<QQI", blob, offset + index * 20)
            assert lo <= program < hi, (path, program)
            code = [(program >> (k * cfg.I)) & ((1 << cfg.I) - 1) for k in range(1 << cfg.p)]
            table = machine.truth_table_binary(code) if data["binary"] else machine.truth_table_unary(code)
            assert key(table, cfg.W) == (klo, khi), (path, program)
            checked += 1
    assert checked, f"No shards found for {result}"
    total += checked
    print(f"{tag}: {checked} sampled witnesses agree with Python", flush=True)
print(f"TOTAL: {total} sampled witnesses agree", flush=True)
