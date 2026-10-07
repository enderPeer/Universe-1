"""Validate and summarize the completed, monitored cluster translation run."""
import hashlib
import json
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path
import corpus

ROOT=Path(__file__).resolve().parents[1]
rows=json.loads((ROOT/'translate/report_merged.json').read_text())
baseline=json.loads(subprocess.check_output(['git','show','96b8687:translate/report_merged.json'],cwd=ROOT))
un,bi=corpus.tables(); groups=defaultdict(list)
for key,row in rows.items(): groups[key.split('/')[0]].append(row)
assert len(groups)==14
for tag,items in groups.items():
    expected=bi if tag.endswith('_bin') else un
    assert len(items)==len(expected) and {r['name'] for r in items}==set(expected)
    assert all(not r['ok'] or (r['compiled'] and r['test_ok']) for r in items)
    if not tag.endswith('_bin'):
        assert all(r['search_depth']==4 and r['basis_extra']==256 for r in items)
for tag in ['w4_o2_nand_bin','w4_o4_full_bin','w4_o3_swap_bin','w4_o2_add_bin']:
    assert all(r.get('binary_composition') and r.get('names_refreshed') for r in groups[tag])
expected_new={r['file'].removesuffix('.u1prog'):r for r in json.loads((ROOT/'results/maps/new-map-manifest.json').read_text())}
assert len(expected_new)==8
for tag,entry in expected_new.items():
    stats=json.loads((ROOT/f'results/maps/{tag}.stats.json').read_text())
    expected=json.loads((ROOT/f'results/exp03_{tag}.json').read_text())
    assert stats['operators']==entry['operators']==expected['distinct_operators']
example_tests=json.loads((ROOT/'translate/examples/test-results.json').read_text())
assert len(example_tests)==12 and all(r['compiled'] and r['test_ok'] for r in example_tests.values())

node_stats={}
for node in ['adler40','knecht24','specht32','falke64']:
    manifest=json.loads((ROOT/f'translate/cluster-logs/{node}/{node}-translation.json').read_text())
    attempts=[a for m in manifest['maps'].values() for a in m['attempts']]
    assert all(m['status']=='complete' for m in manifest['maps'].values())
    node_stats[node]={'translation_wall_seconds':sum(a['wall_seconds'] for a in attempts),
                      'translation_peak_rss_bytes':max(a['peak_group_rss_bytes'] for a in attempts),
                      'memory_fallbacks':sum(a['rss_cap_exceeded'] for a in attempts)}
builds=json.loads((ROOT/'translate/cluster-logs/falke64/missing-map-builds.json').read_text())['maps']
assert set(builds)==set(expected_new)
assert all(r['exit_code']==0 and not r['rss_cap_exceeded'] for r in builds.values())
node_stats['falke64'].update(map_build_wall_seconds=sum(v['wall_seconds'] for v in builds.values()),
                             map_build_peak_rss_bytes=max(v['peak_group_rss_bytes'] for v in builds.values()))
never={kind:[name for name in names if not any(r['ok'] and r['name']==name for r in rows.values())]
       for kind,names in [('unary',un),('binary',bi)]}
gained=[key for key,row in rows.items() if key in baseline and row['ok'] and not baseline[key]['ok']]
lost=[key for key,row in baseline.items() if row['ok'] and not rows.get(key,{}).get('ok')]
assert not lost
archive=ROOT/'translate/emitted_sources.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for path in sorted((ROOT/'translate/out').rglob('*')):
        if path.is_file() and path.suffix in ('.rs','.log','.jsonl'):
            z.write(path,path.relative_to(ROOT).as_posix())
with zipfile.ZipFile(archive) as z: assert z.testzip() is None
summary={'translation_rows':len(rows),'passing_translations':sum(r['ok'] for r in rows.values()),
         'baseline_passing_translations':sum(r['ok'] for r in baseline.values()),
         'distinct_corpus_functions_translated':55-sum(map(len,never.values())),
         'remaining_functions':never,'improvements_on_existing_maps':gained,'regressions':lost,
         'selected_examples_passed':len(example_tests),'new_maps_built':8,
         'source_revisions':sorted({r['source_commit'] for r in rows.values()}),
         'rss_limit_bytes':40_000_000_000,'rss_sampling_interval_seconds':.25,
         'per_node':node_stats,
         'builds':{k:{f:v[f] for f in ('wall_seconds','peak_group_rss_bytes','exit_code')} for k,v in builds.items()},
         'emitted_sources_archive':archive.name,'emitted_sources_sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
(ROOT/'translate/run_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
lines=['# Completed cluster translation run','',
       'The initial unary depth-4 run used 96b8687 with extra=256. The four new binary checks used the 87185a8 composition/naming update plus the name-refresh hook (deployed source 1a83882). Source revisions and modes are recorded per target.', '',
       f"{summary['passing_translations']} map/function translations compiled and passed; {summary['distinct_corpus_functions_translated']}/55 distinct corpus functions were translated. All seven unary maps completed depth 4 without fallback. All eight missing maps were built and their counts match the exhaustive sweep results.", '',
       '## Per-node timings','',
       'Wall times below are sums of monitored commands on each node. They include load/verification/search/test work, but exclude source deployment, data transfers, and the pause for the upstream update. Nodes ran concurrently; these totals are not whole-job elapsed time. RSS is sampled every 250 ms.', '',
       '| Node | Translation seconds | Peak translation RAM (GB) | Map-build seconds | Peak map-build RAM (GB) |',
       '|---|---:|---:|---:|---:|']
for node,r in node_stats.items():
    lines.append(f"| {node} | {r['translation_wall_seconds']:.1f} | {r['translation_peak_rss_bytes']/1e9:.2f} | {r.get('map_build_wall_seconds',0):.1f} | {r.get('map_build_peak_rss_bytes',0)/1e9:.2f} |")
lines+=['','## Comparison with the original report','',
        f"The original report had {summary['baseline_passing_translations']} passing map/function translations. Existing maps gained these six successes with the wider/deeper unary search; no baseline success was lost:",'']
lines += ['- '+key for key in gained]
lines+=['','## Remaining targets','',
        '**Unary:** '+', '.join(never['unary'])+'.','',
        '**Binary:** '+', '.join(never['binary'])+'.','',
        'These were not found in the configured search. Unary prefixes use restricted bases, and the new binary search uses the listed pre/post/two-binary-stage forms, not arbitrary composition of all functions.','',
        '## Artifacts and validation','',
        '- [Full matrix](REPORT.md) and [machine-readable rows](report_merged.json).',
        '- [All emitted sources and logs](emitted_sources.zip): extract from the repository root with `python -m zipfile -e translate/emitted_sources.zip .`.',
        '- [Selected examples](examples/manifest.json) and [12 passing example tests](examples/test-results.json). All ten Dimension42 corpus examples are represented.',
        '- [Map extraction and checksums](../results/maps/README.md). The largest two maps are ordinary ZIP archives in Git, preserving the U1PROG01 format.',
        '- [Raw node timings and logs](cluster-logs/) and [summary with archive checksum](run_summary.json). No emitted test failed and no interpreter or emitted-file repair was made.',
        '- The RSS guard was separately tested with a disposable allocation at a lower threshold; it stopped only that test process group.','',
        '## Proposed next ISA','',
        '`SWAP,ADD,NAND,XOR,SHR,MUL,SKZ,HALT` with W=4, a=2, p=3, I=4 (3 opcode bits, 1 operand bit). This retains the winning four operations, adds high-to-low bit flow and XOR, and permits halting multiplication.', '',
        'Reference-verified constructive witnesses in [next_isa_proposal.json](next_isa_proposal.json) implement Gray code in 5 steps, multiplication and square in 2, and a XOR b XOR 7 in 7. Three Gray-code stages implement ungray in 15 steps. Gray/ungray are still missing from the current search; multiplication and XOR-7 now translate in two non-halting-budget stages with a 512-step bound, so the proposal also targets latency.', '',
        'This is a proposal, not an exhaustive new sweep. Its operand field shrinks from two bits to one compared with the champion. Evaluate coverage and halting cost together. The HALT/SWAP/ADD/NAND/ROL combination and its binary sweep already exist.', '',
        'The exp05 branch-free SWAP/ADD/NAND/SHR candidate still wraps the PC under current semantics; it does not automatically halt after eight instructions. A one-pass comparison needs an explicitly different termination rule.','']
(ROOT/'translate/CLUSTER_RUN.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps(summary,indent=2))
