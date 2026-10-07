#!/usr/bin/env bash
# Dispatch every ISA in cluster/isas_4byte.conf over all nodes in cluster/nodes.conf.
# Each node gets a contiguous slice of the 2^32 program ids proportional to its thread count.
# Usage: cluster/run_4byte.sh [--binary] [--only name] [--dry]
# Requires: ssh aliases from docs/cluster-inventory.md, gcc with OpenMP on each node, rsync.
set -euo pipefail
cd "$(dirname "$0")/.."
BINARY=""; ONLY=""; DRY=0
while [ $# -gt 0 ]; do case "$1" in
  --binary) BINARY="--binary";; --only) ONLY="$2"; shift;; --dry) DRY=1;; *) echo "bad arg $1"; exit 2;; esac; shift; done
REMOTE=universe-1
mapfile -t NODES < <(grep -v '^#' cluster/nodes.conf | awk 'NF==2')
TOTALW=0; for n in "${NODES[@]}"; do TOTALW=$((TOTALW + ${n#* })); done
mkdir -p results/shards
run_remote() { # alias cmd
  if [ $DRY = 1 ]; then echo "[$1] $2"; else ssh "$1" "$2"; fi; }
echo "== sync + build on ${#NODES[@]} nodes"
for n in "${NODES[@]}"; do a=${n% *}
  if [ $DRY = 1 ]; then echo "[$a] rsync + make"; else
    rsync -az --exclude .git --exclude results ./ "$a:$REMOTE/" &
  fi
done; wait
for n in "${NODES[@]}"; do a=${n% *}; run_remote "$a" "cd $REMOTE && make -s -C fast" & done; wait
SPAN=$((1<<32))
while IFS='|' read -r name geom isa; do
  name=$(echo "$name" | xargs); [ -z "$name" ] && continue; case "$name" in \#*) continue;; esac
  [ -n "$ONLY" ] && [ "$ONLY" != "$name" ] && continue
  read -r W A P I <<<"$(echo "$geom" | xargs)"; isa=$(echo "$isa" | xargs)
  PBITS=$(( (1<<P) * I )); [ $PBITS -ne 32 ] && { echo "skip $name: program bits $PBITS != 32"; continue; }
  echo "== $name  W=$W a=$A p=$P I=$I isa=$isa $BINARY"
  acc=0
  for n in "${NODES[@]}"; do a=${n% *}; w=${n#* }
    lo=$acc; acc=$((acc + SPAN * w / TOTALW)); [ "$a" = "${NODES[-1]% *}" ] && acc=$SPAN; hi=$acc
    out="results/shards/${name}${BINARY:+_bin}_${a}.bin"
    run_remote "$a" "cd $REMOTE && mkdir -p results/shards && nohup fast/u1 --W $W --a $A --p $P --I $I --isa $isa $BINARY --lo $lo --hi $hi --threads $w --out $out > $out.log 2>&1" &
  done; wait
  for n in "${NODES[@]}"; do a=${n% *}
    if [ $DRY = 1 ]; then echo "[$a] fetch results/shards/${name}*_${a}.bin*"; else
      scp -q "$a:$REMOTE/results/shards/${name}${BINARY:+_bin}_${a}.bin"* results/shards/ ; fi
  done
  [ $DRY = 1 ] || python3 fast/merge.py results/shards/${name}${BINARY:+_bin}_*.bin --out results/exp03_${name}${BINARY:+_bin}.json
done < <(grep -v '^\s*#' cluster/isas_4byte.conf)
echo "== done; run: python3 cluster/summarize.py"
