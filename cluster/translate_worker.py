"""Run the assigned translation maps, guarding RSS and recording attempts."""
import argparse
import json
import os
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    'adler40':['w4_o3_swap','w4_o4_full'],
    'knecht24':['w4_o2_add','w4_o3_core'],
    'specht32':['w4_o3_arith','w4_o2_nand','w4_o3_bool'],
    'falke64':['w4_o3_core_bin','w4_o3_arith_bin','w4_o3_bool_bin'],
}

def group_rss(pgid):
    total = 0
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit(): continue
        try:
            if os.getpgid(int(entry.name)) != pgid: continue
            for line in (entry/'status').read_text().splitlines():
                if line.startswith('VmRSS:'): total += int(line.split()[1])*1024
        except (ProcessLookupError, PermissionError, FileNotFoundError): pass
    return total

def monitored(command, log, limit=40_000_000_000):
    start=time.monotonic(); peak=0; capped=False
    with log.open('w') as output:
        p=subprocess.Popen(['nice','-n','19','ionice','-c3',*command],cwd=ROOT,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        while p.poll() is None:
            peak=max(peak,group_rss(p.pid))
            if peak>limit:
                capped=True; os.killpg(p.pid,signal.SIGTERM)
                try: p.wait(timeout=5)
                except subprocess.TimeoutExpired: os.killpg(p.pid,signal.SIGKILL)
                break
            time.sleep(.25)
        code=p.wait()
    return {'command':command,'exit_code':code,'wall_seconds':time.monotonic()-start,
            'peak_group_rss_bytes':peak,'rss_cap_exceeded':capped,'log':str(log.relative_to(ROOT))}

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--maps',nargs='*'); args=parser.parse_args()
    node=socket.gethostname(); tags=args.maps or GROUPS[node]
    logs=ROOT/'translate/cluster-logs'; logs.mkdir(parents=True,exist_ok=True)
    manifest={'node':node,'source_commit':'96b8687','rss_limit_bytes':40_000_000_000,'maps':{}}
    path=logs/(node+'-translation.json')
    if path.exists(): manifest=json.loads(path.read_text())
    for tag in tags:
        while tag.endswith('_bin') and (logs/'pause-binary-checks').exists():
            time.sleep(1)
        attempts=[]; manifest['maps'][tag]={'attempts':attempts,'status':'running'}
        for depth in ([1] if tag.endswith('_bin') else [4,3]):
            path.write_text(json.dumps(manifest,indent=2))
            command=['python3','-u','translate/translate.py','--depth',str(depth),'--extra','256',
                     '--maps',f'results/maps/{tag}.u1prog']
            result=monitored(command, logs/f'{node}-{tag}-d{depth}.log')
            result['depth']=depth; attempts.append(result)
            if result['exit_code']==0:
                manifest['maps'][tag].update(status='complete',actual_depth=depth)
                break
            if not result['rss_cap_exceeded']:
                manifest['maps'][tag]['status']='failed'; path.write_text(json.dumps(manifest,indent=2))
                raise SystemExit(f'Failed {tag}; inspect {result["log"]}')
            manifest['maps'][tag]['status']='memory_fallback' if depth==4 else 'memory_limit'
        path.write_text(json.dumps(manifest,indent=2))
        print(tag,manifest['maps'][tag]['status'],flush=True)

if __name__=='__main__': main()
