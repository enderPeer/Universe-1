"""Keep existing examples unless a verified result supplies a shorter chain."""
import json
import re
import shutil
from pathlib import Path
import corpus

ROOT=Path(__file__).resolve().parents[1]
requested=['a_plus_b','a_xor_b','2a_plus_b','a_plus_b_plus1','times3',
           'a_plus_5','not_b','a_minus_1','rotl3','a_xor_b_xor7','popcount','square']
rows=json.loads((ROOT/'translate/report_merged.json').read_text())
un,bi=corpus.tables(); expected={**un,**bi}
manifest={}
for name in requested:
    choices=[(key,row) for key,row in rows.items() if row['name']==name and row['ok'] and row.get('test_ok')]
    if not choices:
        manifest[name]={'status':'not_found_in_current_search'}; continue
    key,row=min(choices,key=lambda kv:(kv[1]['stages'],kv[1]['max_steps'],not kv[1]['halts'],kv[0]))
    source=ROOT/row['file']; destination=ROOT/'translate/examples'/source.name
    replace=True
    if destination.exists():
        old=destination.read_text()
        count=int(re.search(r'pub const PROGRAMS: \[u64; (\d+)\]',old).group(1))
        replace=row['stages']<count
    if replace: shutil.copyfile(source,destination)
    text=destination.read_text()
    table=json.loads('['+re.search(r'pub const TABLE:.*?= \[([^\]]*)\]',text).group(1)+']')
    if table!=expected[name]: raise ValueError(f'{name}: example table does not match corpus')
    programs=[int(p.strip(),0) for p in re.search(r'pub const PROGRAMS:.*?= \[([^\]]*)\]',text).group(1).split(',') if p.strip()]
    manifest[name]={'status':'updated' if replace else 'retained_existing_chain',
                    'file':destination.relative_to(ROOT).as_posix(),'stages':len(programs),
                    'programs':[hex(p) for p in programs],'target_table_verified':True,
                    'candidate_map':key.split('/')[0],'candidate_stages':row['stages']}
(ROOT/'translate/examples/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps({k:v['status'] for k,v in manifest.items()},indent=2))
