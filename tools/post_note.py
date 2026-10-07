"""Post a uniquely named handoff using existing GitHub CLI authentication."""
import argparse
import base64
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
payload = {'branch':'shared/universe-1','message':args.agent+' handoff: '+args.file.name,
           'content':base64.b64encode(content).decode()}
result = subprocess.run(['gh','api','--method','PUT','repos/enderPeer/Universe-1/contents/'+path,'--input','-'],
                        input=json.dumps(payload), text=True, capture_output=True)
if result.returncode:
    raise SystemExit(result.stderr+'\n'+result.stdout)
print(json.loads(result.stdout)['content']['html_url'])
