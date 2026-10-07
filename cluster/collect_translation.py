"""Collect completed per-node reports, emitted sources and timing evidence."""
import argparse
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(); parser.add_argument('nodes',nargs='+'); args=parser.parse_args()
for node in args.nodes:
    with tempfile.TemporaryFile() as stream:
        subprocess.run(['ssh',node,'cd universe-1 && tar -cf - translate/out translate/cluster-logs'],stdout=stream,check=True)
        stream.seek(0)
        with tarfile.open(fileobj=stream) as archive:
            count=0
            for member in archive:
                if not member.isfile(): continue
                path=Path(member.name)
                if path.is_absolute() or '..' in path.parts or path.parts[:2] not in [('translate','out'),('translate','cluster-logs')]:
                    raise ValueError(member.name)
                if path.parts[1]=='cluster-logs':
                    destination=ROOT/'translate/cluster-logs'/node/Path(*path.parts[2:])
                else:
                    destination=ROOT/path
                destination.parent.mkdir(parents=True,exist_ok=True)
                with archive.extractfile(member) as src,destination.open('wb') as dst: shutil.copyfileobj(src,dst)
                count+=1
    print(node,count,'files collected',flush=True)
