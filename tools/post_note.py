"""Post a uniquely named handoff using existing GitHub CLI authentication."""
import argparse
import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--agent', choices=('claude','codex'), required=True)
parser.add_argument('--file', type=Path, required=True)
args = parser.parse_args()
content = args.file.read_bytes()
content.decode('utf-8')
if len(content) > 1024**2:
    raise SystemExit('Use an artifact link for notes larger than 1 MiB')
name = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]+'.md'
path = 'agents/'+args.agent+'/'+name
def api(route, data=None):
    cmd = ['gh','api','repos/enderPeer/Universe-1/git/'+route]
    if data is not None: cmd += ['--input','-']
    result = subprocess.run(cmd, input=json.dumps(data).encode() if data is not None else None, capture_output=True)
    if result.returncode: raise SystemExit(result.stderr.decode(errors='replace'))
    return json.loads(result.stdout)

ref = api('ref/heads/shared/universe-1')
parent = ref['object']['sha']
old = api('commits/'+parent)
tree = api('trees', {'base_tree':old['tree']['sha'], 'tree':[{'path':path,'mode':'100644','type':'blob','content':content.decode('utf-8')}]})
commit = api('commits', {'message':args.agent+' handoff: '+args.file.name,'tree':tree['sha'],'parents':[parent]})
api('refs/heads/shared/universe-1', {'sha':commit['sha'],'force':False})
print('https://github.com/enderPeer/Universe-1/blob/shared/universe-1/'+path)
