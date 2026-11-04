#!/bin/bash
# Hard guarantee that the pipelines never exhaust the disk they run on (a shared machine). Every INTERVAL seconds:
#   free < SOFT_GB : truncate aspect logs, shard stdout logs and surefire spool files above MAX_LOG_MB, drop stability scratch
#   free < HARD_GB : freeze every running pipeline (SIGSTOP to the run_project.sh process trees) and log an ALERT;
#                    they are thawed (SIGCONT) automatically once free space is back above HARD_GB + RESUME_MARGIN_GB
# usage: nohup bash scripts/disk_guard.sh >/dev/null 2>&1 &   (the queue scripts start it)   log: logs/disk_guard.log
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); cd "$ROOT"; mkdir -p logs; L=$ROOT/logs/disk_guard.log
SOFT_GB=${SOFT_GB:-150}; HARD_GB=${HARD_GB:-60}; RESUME_MARGIN_GB=${RESUME_MARGIN_GB:-30}; INTERVAL=${INTERVAL:-60}; CAP=${MAX_LOG_MB:-1024}
ISO=$ROOT/src/isolated_validation; frozen=0
echo "$(date -u +%FT%TZ) start soft=${SOFT_GB}G hard=${HARD_GB}G cap=${CAP}M pid=$$" >> "$L"
pipeline_pids () { pgrep -f "scripts/run_project[.]sh"; }
tree_pids () { local p; for p in "$@"; do echo "$p"; tree_pids $(pgrep -P "$p"); done; }
while true; do
  free=$(df -BG --output=avail "$ROOT" | tail -1 | tr -dc 0-9)
  if [ "$free" -lt "$SOFT_GB" ]; then
    n=0
    for f in $(find "$ISO" -maxdepth 2 -name '*.log' -size +"${CAP}"M 2>/dev/null; find "$ROOT/logs" -maxdepth 1 -name 'mockgen_*.log' -size +"${CAP}"M 2>/dev/null; find "${TMPDIR:-/tmp}/surefire" -maxdepth 1 -type f -size +"${CAP}"M 2>/dev/null); do : > "$f"; n=$((n+1)); done
    rm -rf "$ISO"/*__stability 2>/dev/null
    echo "$(date -u +%FT%TZ) free=${free}G < soft: truncated $n files" >> "$L"
  fi
  if [ "$free" -lt "$HARD_GB" ] && [ "$frozen" = 0 ]; then
    pids=$(tree_pids $(pipeline_pids) | sort -u); kill -STOP $pids 2>/dev/null; frozen=1
    echo "$(date -u +%FT%TZ) ALERT free=${free}G < hard: froze $(echo $pids | wc -w) pipeline processes" >> "$L"
  elif [ "$frozen" = 1 ] && [ "$free" -gt $((HARD_GB + RESUME_MARGIN_GB)) ]; then
    pids=$(tree_pids $(pipeline_pids) | sort -u); kill -CONT $pids 2>/dev/null; frozen=0
    echo "$(date -u +%FT%TZ) free=${free}G: thawed pipelines" >> "$L"
  fi
  sleep "$INTERVAL"
done
