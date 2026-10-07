"""Two-way, content-checked GitHub API / cluster Git sharing bridge."""
import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

BRANCH = 'shared/universe-1'
PROJECT = Path(__file__).resolve().parents[1]
SOURCE_BRANCH = 'claude/charming-rubin-pi8nzs'
WEB = 'https://github.com/enderPeer/Universe-1/blob/'+SOURCE_BRANCH+'/'


def run(repo, args, payload=None, env=None):
    result = subprocess.run(args, cwd=repo, input=payload, capture_output=True, timeout=120, env=env)
    if result.returncode:
        raise RuntimeError(f"{args[0]} {args[1]}: {result.stderr.decode('utf-8',errors='replace').strip()}")
    return result.stdout


def git(repo, *args):
    return run(repo, ['git',*args]).decode('utf-8').strip()


def api(repo, route, data):
    response = run(repo, ['gh','api','repos/enderPeer/Universe-1/git/'+route,'--input','-'], json.dumps(data).encode())
    return json.loads(response)


def tree_files(repo, revision):
    files = {}
    for entry in run(repo,['git','ls-tree','-rz',revision]).split(b'\0'):
        if not entry: continue
        meta, path = entry.split(b'\t',1)
        mode, kind, oid = meta.decode().split()
        if kind != 'blob' or mode not in ('100644','100755'):
            raise RuntimeError('Only regular text files are supported in the shared branch')
        files[path.decode('utf-8')] = [mode, oid]
    return files


def hash_file(repo, content):
    return ['100644',run(repo,['git','hash-object','-w','--stdin'],content).decode().strip()]


def export_snapshots(repo):
    results = []
    for path in sorted((PROJECT/'results').glob('exp03_*.json')):
        data = json.loads(path.read_text())
        if 'distinct_operators' not in data: continue
        results.append({'run':path.stem.removeprefix('exp03_'),'W':data['W'],
                        'binary':data['binary'],'isa':data['isa'],
                        'distinct_operators':data['distinct_operators'],
                        'report':WEB+'results/'+path.name})
    finalizer = PROJECT/'results/exp03_finalize.log'
    log = finalizer.read_text(encoding='utf-8',errors='replace') if finalizer.exists() else ''
    status = {'experiment':'exp03: 32-bit program sweeps','completed_sweeps':len(results),
              'expected_supported_sweeps':23,
              'publication':'complete' if 'COMPLETE: validated results copied' in log else 'in progress or awaiting finalization',
              'published_source_revision':git(PROJECT,'rev-parse','origin/'+SOURCE_BRANCH),
              'cluster_share':'ender@192.168.178.171:/home/ender/universe-1-share',
              'worker_data':'/home/ender/universe-1/results/shards/',
              'coordinator_data':'C:/Users/end/Desktop/u1/results/shards/','runs':results}
    files = {'snapshots/status.json':hash_file(repo,(json.dumps(status,indent=2)+'\n').encode())}
    for src,name in [('docs/cluster-inventory.md','cluster-inventory.md'),
                     ('results/exp03_summary.md','experiment-summary.md'),
                     ('results/exp03_completion.md','experiment-completion.md')]:
        path = PROJECT/src
        if path.exists(): files['snapshots/'+name] = hash_file(repo,path.read_text(encoding='utf-8-sig').encode())
    return files


def write_tree(repo, files):
    env = dict(os.environ, GIT_INDEX_FILE=str((repo/'.git/share-bridge.index').resolve()))
    run(repo,['git','read-tree','--empty'],env=env)
    index = b''.join(f'{mode} {oid}\t{name}\0'.encode() for name,(mode,oid) in sorted(files.items()))
    run(repo,['git','update-index','-z','--index-info'],index,env=env)
    return run(repo,['git','write-tree'],env=env).decode().strip()


def merge_files(cloud, cluster, baseline):
    desired = {}
    conflicts = []
    for name in sorted(set(cloud)|set(cluster)|set(baseline)):
        a,b,old = cloud.get(name),cluster.get(name),baseline.get(name)
        if a == b: chosen = a
        elif a == old: chosen = b
        elif b == old: chosen = a
        else:
            conflicts.append(name); continue
        if chosen is not None: desired[name] = chosen
    if conflicts:
        raise RuntimeError('Both sides changed these files; resolve explicitly: '+', '.join(conflicts))
    return desired


def sync(repo):
    for remote in ('origin','cluster'):
        git(repo,'fetch',remote,f'refs/heads/{BRANCH}:refs/remotes/{remote}/{BRANCH}')
    cloud_ref, cluster_ref = 'origin/'+BRANCH, 'cluster/'+BRANCH
    cloud_sha, cluster_sha = git(repo,'rev-parse',cloud_ref), git(repo,'rev-parse',cluster_ref)
    cloud, cluster = tree_files(repo,cloud_ref), tree_files(repo,cluster_ref)
    baseline_file = repo/'.git/share-bridge-base.json'
    baseline = json.loads(baseline_file.read_text()) if baseline_file.exists() else {}
    desired = merge_files(cloud, cluster, baseline)
    # These four snapshot files are explicitly owned by the automatic exporter.
    desired.update(export_snapshots(repo))
    wanted_tree = write_tree(repo,desired)
    if desired != cloud:
        entries = []
        for name,(mode,oid) in desired.items():
            blob = run(repo,['git','cat-file','blob',oid])
            if len(blob) > 8*1024**2:
                raise RuntimeError('Share artifact references instead of files larger than 8 MiB: '+name)
            entries.append({'path':name,'mode':mode,'type':'blob','content':blob.decode('utf-8')})
        tree = api(repo,'trees',{'tree':entries})
        if tree['sha'] != wanted_tree: raise RuntimeError('GitHub content tree does not match the verified local tree')
        commit = api(repo,'commits',{'message':'Synchronize cluster handoffs and experiment snapshots',
                                   'tree':wanted_tree,'parents':[cloud_sha]})
        api(repo,'refs/heads/'+BRANCH,{'sha':commit['sha'],'force':False})
        cloud_sha = commit['sha']
    if desired != cluster:
        commit = run(repo,['git','-c','user.name=Universe-1 sharing bridge',
                          '-c','user.email=universe-1-bridge@localhost','commit-tree',wanted_tree,'-p',cluster_sha],
                     f'Synchronize cloud handoffs (GitHub {cloud_sha})\n'.encode()).decode().strip()
        git(repo,'push','cluster',f'{commit}:refs/heads/{BRANCH}')
        cluster_sha = commit
    baseline_file.write_text(json.dumps(desired,indent=2)+'\n')
    return {'content_tree':wanted_tree,'github_revision':cloud_sha,'cluster_revision':cluster_sha}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,default=PROJECT/'.shared-bridge')
    parser.add_argument('--interval',type=int,default=60)
    parser.add_argument('--once',action='store_true')
    args = parser.parse_args()
    lock = (args.repo/'.git/share-bridge.lock').open('a+b')
    lock.seek(0); lock.write(b'1'); lock.flush(); lock.seek(0)
    if os.name == 'nt':
        import msvcrt
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
    else:
        import fcntl
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    previous = None
    while True:
        state = {'checked_at_utc':datetime.now(timezone.utc).isoformat(),'pid':os.getpid()}
        try:
            state.update(status='synced',**sync(args.repo))
            message = 'synced '+state['content_tree']
        except Exception as error:
            state.update(status='needs_attention',error=str(error)); message = str(error)
        (PROJECT/'results/share-bridge-status.json').write_text(json.dumps(state,indent=2)+'\n')
        if message != previous:
            print(state['checked_at_utc'],state['status'],message,flush=True); previous=message
        if args.once: raise SystemExit(0 if state['status']=='synced' else 1)
        time.sleep(max(10,args.interval))


if __name__ == '__main__':
    main()
