# Universe-1 shared workspace — Codex and Claude/Fable

This is the shared coordination branch, `shared/universe-1`, of
`https://github.com/enderPeer/Universe-1`. It is synchronized with the cluster
workspace `ender@192.168.178.171:/home/ender/universe-1-share`.

## Access from Claude's cloud environment

Use your existing authorized GitHub access; no cluster key is needed:

```bash
git clone --single-branch --branch shared/universe-1 https://github.com/enderPeer/Universe-1.git universe-1-shared
cd universe-1-shared
git pull --no-rebase origin shared/universe-1
# Add a uniquely named note in agents/claude/, then:
git add agents/claude/
git commit -m "Claude handoff: describe the update"
git push origin HEAD:shared/universe-1
```

If this checkout already exists, use it instead of cloning again. Pull before
editing. If another writer moved the branch, fetch/merge and retry; never force-push.

## Access from Codex / the LAN

```bash
ssh adler40
cd /home/ender/universe-1-share
git status
# Create a note under agents/codex/ and commit it with your own author identity.
git -c user.name=Codex -c user.email=codex@localhost add agents/codex/
git -c user.name=Codex -c user.email=codex@localhost commit -m "Codex handoff: describe the update"
```

The bridge fetches committed cluster changes. Direct cluster edits must be
committed to synchronize; uncommitted changes block incoming updates rather
than being overwritten. The GitHub side and cluster side are equal writers.

## What to share

- `agents/codex/` and `agents/claude/`: dated, uniquely named handoffs, findings,
  active work, blockers, and requests. Each agent writes its own directory.
- `decisions/`: agreed decisions in separate dated files.
- `snapshots/`: Codex-owned experiment results/status and hardware inventory.
- `ARTIFACTS.json`: where to find source, witness archives, maps, and raw data.

Include source commit, affected files, evidence/tests, and next action in each
handoff. A note is coordination data, not proof that the recipient has read it.
Do not store private keys, access tokens, credentials, or unrelated project data.
Keep large datasets in their existing artifact locations and share references.

## Synchronization

An authenticated workstation bridge synchronizes this branch in both directions
approximately every 60 seconds. It also refreshes selected experiment snapshots.
It uses existing GitHub and SSH credentials without copying them to the cluster.
No inbound internet endpoint or tunnel is opened.

The bridge requires the Codex workstation to remain awake and online. It is a
background process, not a reboot-persistent service. Restart from the project
with `pwsh cluster/start_share_bridge.ps1`. Runtime status lives at
`C:/Users/end/Desktop/u1/results/share-bridge-status.json` and the matching logs.

On merge conflicts, dirty checkouts, authentication failures, or failed pushes,
the bridge records `needs_attention` and preserves both histories. An agent must
resolve the conflict before synchronization can continue. Use separate handoff
files to avoid simultaneous edits to the same document.
