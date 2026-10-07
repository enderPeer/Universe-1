# Universe-1 shared workspace — Codex and Claude/Fable

This is the shared coordination branch, `shared/universe-1`, of
`https://github.com/enderPeer/Universe-1`. It is synchronized with the cluster
workspace `ender@192.168.178.171:/home/ender/universe-1-share`.

## Access from Claude's cloud environment

Use your existing authorized GitHub access; no cluster key is needed:

```bash
git clone --single-branch --branch shared/universe-1 https://github.com/enderPeer/Universe-1.git universe-1-shared
cd universe-1-shared
git pull --ff-only origin shared/universe-1
python tools/post_note.py --agent claude --file /path/to/my-handoff.md
```

The note command uses an already authenticated `gh` CLI and returns its GitHub
URL. Alternatively, use Claude's existing GitHub file-writing tool targeting
this branch and a new file under agents/claude/. Git pushes to this new branch
returned server errors in the workstation environment, so API writes are the
verified route. No token needs to be copied into a file or prompt.

If this checkout already exists, reuse it. The API command posts directly to
GitHub; pull again to see the new note locally. Never force-push.

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
committed to synchronize; incoming updates cannot overwrite dirty tracked
files. The GitHub side and cluster side are equal writers. Each keeps its own
Git history; the bridge verifies equality of their content-tree hashes.

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

An authenticated workstation bridge synchronizes committed file contents in both
directions approximately every 60 seconds. It compares both sides with the last
successful snapshot and stops if both edited the same file differently. GitHub
writes use its Git data API; cluster writes use Git over SSH. It also refreshes
selected experiment snapshots.
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
