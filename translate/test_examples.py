"""Compile and run retained/new emitted examples without editing their sources."""
import json
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'translate/examples/manifest.json').read_text())
results={}
with tempfile.TemporaryDirectory(prefix='universe-example-tests-') as temp:
    for name,row in manifest.items():
        if 'file' not in row: continue
        source=ROOT/row['file']; exe=Path(temp)/source.stem
        c=subprocess.run(['rustc','--edition','2021','--test','-O',str(source),'-o',str(exe)],capture_output=True,text=True)
        t=subprocess.run([str(exe)],capture_output=True,text=True) if c.returncode==0 else None
        passed=bool(t and t.returncode==0 and 'test result: ok' in t.stdout)
        results[name]={'file':row['file'],'programs':row['programs'],'compiled':c.returncode==0,
                       'test_ok':passed,'compiler_output':c.stdout+c.stderr,'test_output':t.stdout+t.stderr if t else ''}
        (ROOT/'translate/examples/test-results.json').write_text(json.dumps(results,indent=2)+'\n')
        if not passed: raise SystemExit(f'Emitted example failed: {name}, programs={row["programs"]}')
print(len(results),'example files compiled and passed',flush=True)
