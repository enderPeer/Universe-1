# Shared workspace for Codex and Claude/Fable

- Cluster: `ender@192.168.178.171:/home/ender/universe-1-share` (`ssh adler40`).
- Cloud access: [shared/universe-1 branch](https://github.com/enderPeer/Universe-1/tree/shared/universe-1).
- Read its README, ARTIFACTS.json, snapshots/, and agents/ handoffs first.
- Claude writes agents/claude/ using its existing GitHub authorization.
- Codex writes agents/codex/ through the cluster or GitHub API.

The dedicated branch is separate from code and artifact publishing. A background
workstation bridge synchronizes committed file contents both ways approximately
every 60 seconds. GitHub writes use its Git data API, after Git pushes to the
new branch returned server errors. Cluster writes use Git over SSH. Both sides
keep their own Git history; matching content-tree hashes verify synchronization.
Three-way file comparisons detect conflicts, and the bridge refuses to overwrite
uncommitted cluster changes. It refreshes selected project status snapshots;
arbitrary chat messages and uncommitted files are not automatically exported.

The cluster stays LAN-only; no private keys or tokens are shared. The GitHub
branch inherits this repository's existing permissions and visibility.

Local bridge cache: `.shared-bridge/` (excluded locally from the main repo;
do not use it as a handoff editing location).
Start/restart: `pwsh cluster/start_share_bridge.ps1`.
One-shot sync, when the background bridge is stopped:
`python cluster/share_bridge.py --once`.
Status: `results/share-bridge-status.json`; logs: `results/share-bridge*.log`.
The workstation must remain online; this process does not survive a reboot.
