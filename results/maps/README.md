# Universe-1 Rust operator maps

The original 15 maps are joined by the eight binary maps requested in the
cluster handoff. Each map contains the minimum numeric program witness for
every discovered function. Building them re-executed every witness and verified
its shard key; this is not a claim that every witness is shortest or fastest.

The two large new maps are stored as ordinary ZIP files in Git:

- `w4_o2_add_bin.u1prog.zip`: 24,684,247 functions.
- `w4_o3_swap_bin.u1prog.zip`: 7,690,892 functions.

Restore their unchanged `U1PROG01` binary files before using `u1map`:

```bash
python mapper/unpack_maps.py
```

`new-map-manifest.json` records original sizes, counts, and SHA-256 checksums
for all eight new maps, plus archive checksums where applicable. The helper
checks the hashes and refuses to overwrite an existing map with different data.
Python 3.11 or newer is required for this helper.

The `.named.jsonl` and `.stats.json` files are generated with the corrected
vocabulary from `87185a8`. The W=4 name refresh is performed during translation
from the already-loaded map to avoid another expensive full witness replay.
See [the translation report](../../translate/REPORT.md) for search modes,
actual depth, compilation/self-test results, and timing evidence.
