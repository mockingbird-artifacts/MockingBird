#!/bin/bash
# From-scratch end-to-end runs (scripts/run_project.sh <P> mock results) for the given projects, at most MAXC at a time.
# Per project: previous logs are archived with a .prev suffix, every generated artifact of the project is removed, then the
# pipeline is launched in the background. Launches are recorded in logs/e2e_launches.txt; progress: scripts/e2e_status.sh.
# usage: MAXC=2 SHARDS=3 bash scripts/e2e_queue.sh commons-cli commons-csv ...   (all ten projects when none are given)
# env defaults mirror the reference run: MOCKINGBIRD_STABILITY_RUNS=2 SHARDS=4 MAX_LOG_MB=1024 MOCKGEN_QUIET=1 MOCKINGBIRD_RESUME=1
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); cd "$ROOT"; mkdir -p logs
MAXC=${MAXC:-2}; M=${MODEL:-deepseek-coder-33b-instruct}/${TEMP:-0.0}; ISO=src/isolated_validation; L=logs
export MOCKINGBIRD_STABILITY_RUNS=${MOCKINGBIRD_STABILITY_RUNS:-2} SHARDS=${SHARDS:-4} MAX_LOG_MB=${MAX_LOG_MB:-1024} MOCKGEN_QUIET=${MOCKGEN_QUIET:-1} MOCKINGBIRD_RESUME=${MOCKINGBIRD_RESUME:-1}
PROJECTS=("$@"); [ ${#PROJECTS[@]} -eq 0 ] && PROJECTS=(commons-codec JavaFastPFOR commons-validator commons-graph commons-csv commons-pool jansi commons-cli commons-exec commons-fileupload)
pgrep -f "scripts/orphan_reape[r].sh" > /dev/null || { nohup bash scripts/orphan_reaper.sh > /dev/null 2>&1 < /dev/null & }
pgrep -f "scripts/disk_guar[d].sh" > /dev/null || { nohup bash scripts/disk_guard.sh > /dev/null 2>&1 < /dev/null & }
for P in "${PROJECTS[@]}"; do
  while [ "$(pgrep -fc "run_project[.]sh")" -ge "$MAXC" ]; do sleep 120; done
  raw=java_projects/cleaned_final_projects_evosuite/$P/src/test/java
  find "$raw" -name '*DrivenTest.java' -delete 2>/dev/null
  echo "$(date -u +%FT%TZ) $P: raw EvoSuite tree has $(find "$raw" -name '*_ESTest.java' 2>/dev/null | wc -l) *_ESTest classes ($(find "$raw" -name '*ES[0-9]_ESTest.java' 2>/dev/null | wc -l) topped up)" >> $L/e2e_launches.txt
  rm -rf "data/mock_tests/${P:?}" "data/schemas_evosuite_cleaned/$M/${P:?}" "data/type_resolution/${P:?}" "data/recomposed_projects/$M/${P:?}"
  rm -f $ISO/executed_tests/${P}.json $ISO/executed_tests/${P}__s*.json; for d in $ISO/${P} $ISO/${P}__s* $ISO/${P}-python*; do [ -d "$d" ] && rm -rf "${d:?}"; done
  for f in stages_$P.txt pipeline_$P.log results_$P.txt; do [ -f $L/$f ] && mv $L/$f $L/${f}.prev; done
  nohup bash scripts/run_project.sh "$P" mock results > $L/run_e2e_$P.out 2>&1 < /dev/null &
  echo "$(date -u +%FT%TZ) $P: launched pid $! (STABILITY_RUNS=$MOCKINGBIRD_STABILITY_RUNS SHARDS=$SHARDS MAX_LOG_MB=$MAX_LOG_MB)" >> $L/e2e_launches.txt
  sleep 300
done
echo "$(date -u +%FT%TZ) queue: all projects launched" >> $L/e2e_launches.txt
