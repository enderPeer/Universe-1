"""Build and verify the eight outstanding maps on falke64, then translate W=4."""
import json
import socket
import subprocess
from pathlib import Path
from translate_worker import monitored

ROOT=Path(__file__).resolve().parents[1]
TAGS=['w1_nand_jz_bin','w1_nand_skz_bin','w2_o1_bin','w2_o1_swap_bin',
      'w4_o2_nand_bin','w4_o4_full_bin','w4_o3_swap_bin','w4_o2_add_bin']
logs=ROOT/'translate/cluster-logs'; logs.mkdir(exist_ok=True,parents=True)
manifest={'node':socket.gethostname(),'source_commit':'96b8687','maps':{}}
for tag in TAGS:
    shards=sorted((ROOT/'results/shards').glob(tag+'_[0-9][0-9][0-9][0-9].bin'))
    if len(shards)!=64: raise SystemExit(f'{tag}: expected 64 shards, got {len(shards)}')
    result=monitored(['mapper/target/release/u1map','build','--shards',*[str(p) for p in shards],
                      '--threads','10','--out',f'results/maps/{tag}.u1prog',
                      '--named',f'results/maps/{tag}.named.jsonl','--stats',f'results/maps/{tag}.stats.json'],
                     logs/(tag+'-build.log'))
    manifest['maps'][tag]=result
    (logs/'missing-map-builds.json').write_text(json.dumps(manifest,indent=2))
    if result['exit_code']: raise SystemExit(f'Map build failed: {tag}')
    observed=json.loads((ROOT/f'results/maps/{tag}.stats.json').read_text())['operators']
    expected=json.loads((ROOT/f'results/exp03_{tag}.json').read_text())['distinct_operators']
    if observed!=expected: raise SystemExit(f'{tag}: {observed} operators differs from {expected}')
    print(f'{tag}: {observed} operators, all witness keys verified',flush=True)
subprocess.run(['python3','-u','cluster/translate_worker.py','--maps',*[t for t in TAGS if t.startswith('w4_')]],cwd=ROOT,check=True)
