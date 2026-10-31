#!/bin/bash
# Optional safety net for mock-test generation: kills surefire-forked test JVMs that outlived their Maven parent (ppid 1)
# and are older than 3 minutes. generate_logs.py reaps each run's process group itself; this loop covers generation runs
# started with an older generate_logs.py or JVMs left behind by any other means. Each such JVM otherwise keeps its cores
# and heap (tens of GB) indefinitely. usage: nohup bash scripts/orphan_reaper.sh >/dev/null 2>&1 &   (log: logs/orphan_reaper.log)
ROOT=$(pwd); mkdir -p "$ROOT/logs"; L=$ROOT/logs/orphan_reaper.log; echo "$(date -u +%FT%TZ) start pid=$$" >> "$L"
while true; do
  ps -eo pid,ppid,etimes,rss,args | awk '$2==1 && $3>180 && /surefirebooter/ {print $1, $3, int($4/1048576)}' | while read -r pid et gb; do
    kill -9 "$pid" 2>/dev/null && echo "$(date -u +%FT%TZ) killed $pid age=${et}s rss=${gb}GB" >> "$L"
  done
  sleep 60
done
