"""Read live milestone progress from the active Life workers."""
import concurrent.futures
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
status=json.loads((ROOT/'results/life/status.json').read_text())
nodes={r['node'] for r in status.values()}
def read(node):
    names=[name for name,r in status.items() if r['node']==node]
    script='''import csv,json,pathlib,re
names=NAMES
out={}
for name in names:
    root=pathlib.Path('results/life')/name
    if not (root/'stats.csv').exists(): continue
    rows=list(csv.DictReader((root/'stats.csv').read_text().splitlines()))
    rows=[r for r in rows if r.get('deaths') is not None]
    if not rows: continue
    r=rows[-1]; points=[]
    for line in (root/'run.log').read_text(errors='replace').splitlines():
        match=re.search(r'tick\\s+(\\d+).*\\(([0-9.]+)s\\)',line)
        if match: points.append((int(match[1]),float(match[2])))
    item={'tick':int(r['tick']),'alive':int(r['alive']),'distinct_genomes':int(r['distinct_genomes'])}
    if len(points)>1:
        first=points[max(0,len(points)-6)]; last=points[-1]
        if last[1]>first[1]:
            rate=(last[0]-first[0])/(last[1]-first[1]); item['recent_ticks_per_second']=rate
            item['estimated_seconds_to_200k']=(200000-last[0])/rate if rate else None
    out[name]=item
print(json.dumps(out))
'''.replace('NAMES',repr(names))
    r=subprocess.run(['ssh',node,'cd universe-1 && python3 -'],input=script,text=True,capture_output=True,check=True)
    return json.loads(r.stdout)
progress={}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for values in pool.map(read,nodes): progress.update(values)
for name,values in progress.items(): values.update(node=status[name]['node'],gpu=status[name]['gpu'],state=status[name]['state'])
(ROOT/'results/life/progress.json').write_text(json.dumps(progress,indent=2)+'\n')
for name,r in sorted(progress.items()):
    print(name,r['tick'],'/200000; alive',r['alive'],'genomes',r['distinct_genomes'],
          'ETA min',round(r.get('estimated_seconds_to_200k',0)/60,1))
