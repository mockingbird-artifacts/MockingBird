#!/bin/bash
# Resume interrupted pipelines without wiping anything: each argument is <project>:<start_stage>[:<end_stage>] and is run as
# scripts/run_project.sh <project> <start_stage> <end_stage> (default end: results) when fewer than MAXC pipelines are running.
# Every stage resumes from what is already on disk (mock-test state, schema statuses). Launches go to logs/resume_launches.txt.
# usage: MAXC=4 bash scripts/resume_queue.sh JavaFastPFOR:translate commons-pool:mock jansi:mock:mock2
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); cd "$ROOT"; mkdir -p logs; MAXC=${MAXC:-4}; L=logs/resume_launches.txt
pgrep -f "scripts/orphan_reape[r].sh" > /dev/null || { nohup bash scripts/orphan_reaper.sh > /dev/null 2>&1 < /dev/null & }
pgrep -f "scripts/disk_guar[d].sh" > /dev/null || { nohup bash scripts/disk_guard.sh > /dev/null 2>&1 < /dev/null & }
for spec in "$@"; do
  IFS=: read -r P START END <<< "$spec"; END=${END:-results}
  while [ "$(pgrep -fc "run_project[.]sh")" -ge "$MAXC" ]; do sleep 120; done
  nohup bash scripts/run_project.sh "$P" "$START" "$END" > "logs/run_resume_${P}_${START}.out" 2>&1 < /dev/null &
  echo "$(date -u +%FT%TZ) $P: resumed at stage $START (to $END), pid $!" >> $L
  sleep 60
done
echo "$(date -u +%FT%TZ) resume queue: all launched" >> $L
