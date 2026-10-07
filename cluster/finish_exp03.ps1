param([Parameter(Mandatory=$true)][int]$RunPid)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$branch = 'claude/charming-rubin-pi8nzs'

try {
    Write-Output "Waiting for experiment coordinator PID $RunPid"
    Wait-Process -Id $RunPid -ErrorAction SilentlyContinue
    $validate = @'
import json, pathlib
expected = []
for line in pathlib.Path('cluster/isas_4byte.conf').read_text().splitlines():
    if not line.strip() or line.lstrip().startswith('#'): continue
    name, geom, isa = map(str.strip, line.split('|'))
    w,a,p,i = map(int, geom.split())
    expected.append((name, w, a, p, i, isa.split(','), False))
    if (1 << w) ** 2 <= 256:
        expected.append((name + '_bin', w, a, p, i, isa.split(','), True))
for name,w,a,p,i,isa,binary in expected:
    r = json.loads(pathlib.Path(f'results/exp03_{name}.json').read_text())
    assert (r['W'],r['a'],r['p'],r['I'],r['isa'],r['binary']) == (w,a,p,i,isa,binary), name
    cursor = 0
    for lo,hi in sorted(r['programs_covered']):
        assert lo == cursor and hi > lo, name
        cursor = hi
    assert cursor == 1 << 32 and not r['gaps'], name
assert len(expected) == 23
print('All 23 supported sweeps have verified complete coverage.')
'@
    & python -c $validate
    if ($LASTEXITCODE -ne 0) { throw 'Experiment incomplete or configuration/coverage mismatch.' }
    & python -u fast/check_witnesses.py | Tee-Object -FilePath results/validation/witnesses.log
    if ($LASTEXITCODE -ne 0) { throw 'Witness validation failed.' }
    & python cluster/summarize.py
    if ($LASTEXITCODE -ne 0) { throw 'Summary generation failed.' }
    & python -u fast/map_functions.py
    if ($LASTEXITCODE -ne 0) { throw 'Named-function mapping or witness verification failed.' }
    & python -u cluster/package_witnesses.py
    if ($LASTEXITCODE -ne 0) { throw 'Witness archive verification failed.' }

    $completed = @"
# Experiment 03 completed

Completed at $([DateTimeOffset]::UtcNow.ToString('u')) (UTC).

- 12 unary and 11 supported binary sweeps completed.
- Every sweep covers all 4,294,967,296 programs without gaps or overlaps.
- Total program enumerations: 98,784,247,808.
- Sampled witnesses passed the independent Python reference check.
- W=8 binary was excluded because it exceeds the GPU kernel's table limit.
- See exp03_summary.md, exp03_validation.md and validation/witnesses.log.
"@
    [IO.File]::WriteAllText((Join-Path (Get-Location) 'results/exp03_completion.md'), $completed, [Text.UTF8Encoding]::new($false))
    $resultFiles = @(Get-ChildItem results/exp03_*.json | ForEach-Object FullName)
    & scp @resultFiles results/exp03_summary.md results/exp03_validation.md results/exp03_completion.md adler40:universe-1/results/
    if ($LASTEXITCODE -ne 0) { throw 'Copying final results to Adler failed.' }
    & scp -r results/function-map adler40:universe-1/results/
    if ($LASTEXITCODE -ne 0) { throw 'Copying function maps to Adler failed.' }

    if ((& git branch --show-current).Trim() -ne $branch) { throw 'Branch changed; refusing to publish to an unrelated branch.' }
    $alreadyStaged = @(& git diff --cached --name-only)
    if ($LASTEXITCODE -ne 0 -or $alreadyStaged.Count -gt 0) { throw 'Existing staged changes detected; preserving them and stopping publication.' }
    foreach ($archive in Get-ChildItem results/witnesses -Filter '*.zip' | Sort-Object Name) {
        & git add -- ("results/witnesses/" + $archive.Name)
        if ($LASTEXITCODE -ne 0) { throw 'Staging witness archive failed.' }
        & git diff --cached --quiet
        if ($LASTEXITCODE -eq 1) {
            & git commit -m ("Publish witness archive " + $archive.Name)
            if ($LASTEXITCODE -ne 0) { throw 'Committing witness archive failed.' }
            & git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push origin $branch
            if ($LASTEXITCODE -ne 0) { throw 'Archive push failed; verified data remains local.' }
        } elseif ($LASTEXITCODE -ne 0) { throw 'Checking staged archive failed.' }
    }
    & git add -- 'results/exp03_*.json' results/exp03_summary.md results/exp03_validation.md results/exp03_binary_run.log results/validation/witnesses.log results/exp03_completion.md results/witnesses results/function-map
    if ($LASTEXITCODE -ne 0) { throw 'Staging results failed.' }
    & git diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw 'Staged result formatting check failed.' }
    & git commit -m 'Record completed and validated binary cluster experiment'
    if ($LASTEXITCODE -ne 0) { throw 'Committing results failed.' }
    & git push origin $branch
    if ($LASTEXITCODE -ne 0) { throw 'Pushing results failed; verified results remain local.' }
    Write-Output 'COMPLETE: validated results copied to the cluster and pushed to GitHub.'
} catch {
    Write-Error "Experiment finalization stopped: $_"
    exit 1
}
