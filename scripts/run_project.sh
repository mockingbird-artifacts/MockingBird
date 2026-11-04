#!/bin/bash
# Full MockingBird pipeline for one project with stage markers, run from the repository root (or anywhere: the script
# locates the root itself). usage: scripts/run_project.sh <project> [start_stage] [end_stage]
#   stages: mock schema augment mock2 types typemap infer skeleton translate results
#   mock     sharded mock-test generation from the EvoSuite + developer tests (SHARDS, TEST_TIMEOUT, MAX_LOG_MB, MOCKINGBIRD_STABILITY_RUNS)
#   augment  EvoSuite top-up for classes still without mock tests (ES_BUDGET seconds per class, ES_PAR parallel runs)
#   mock2    second generation pass that records the topped-up tests (resume keeps everything from the first pass)
# env: MODEL (deepseek-coder-33b-instruct) TEMP (0.0) SUFFIX (_evosuite_cleaned); markers in logs/stages_<project>.txt
set -u
P=$1; START=${2:-mock}; END=${3:-results}
MODEL=${MODEL:-deepseek-coder-33b-instruct}; TEMP=${TEMP:-0.0}; SUFFIX=${SUFFIX:-_evosuite_cleaned}
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); cd "$ROOT"; mkdir -p logs
for c in /root/miniconda3 "$HOME/miniconda3" "$HOME/anaconda3" /opt/conda; do [ -f "$c/etc/profile.d/conda.sh" ] && { source "$c/etc/profile.d/conda.sh"; break; }; done
conda activate mockingbird 2>/dev/null || true
set +u; [ -f "$HOME/.sdkman/bin/sdkman-init.sh" ] && source "$HOME/.sdkman/bin/sdkman-init.sh"; set -u
export PYTHONPATH=":$ROOT${PYTHONPATH:+:$PYTHONPATH}"   # leading empty entry = cwd: validation executes translated files from inside the recomposed project, which imports its own src.main.* modules
export MOCKINGBIRD_ROOT="$ROOT" MOCKINGBIRD_PROJECT="$P"
export MOCKINGBIRD_TYPE_MAP_LOG="${MOCKINGBIRD_TYPE_MAP_LOG:-/dev/null}"   # per-resolution jsonl diagnostic (set a path to keep it; it reached 15 GB on one project)
export TOKENIZERS_PARALLELISM=false
LOG=logs/pipeline_$P.log; MARK=logs/stages_$P.txt
mark () { echo "$(date -u +%FT%TZ) $P $1" | tee -a "$MARK"; }
ORDER="mock schema augment mock2 types typemap infer skeleton translate results"
stage_on () { local s started=0; for s in $ORDER; do [ "$s" = "$START" ] && started=1; if [ "$s" = "$1" ]; then [ $started = 1 ] && return 0 || return 1; fi; [ "$s" = "$END" ] && [ $started = 1 ] && [ "$s" != "$1" ] && return 1; done; return 1; }
mock_count () { find "data/mock_tests/$P" -name '*_mocker_*.py' 2>/dev/null | wc -l; }

if stage_on mock; then
  mark "mock START"; SHARDS=${SHARDS:-4} bash scripts/generate_mock_tests_sharded.sh "$P" >> "$LOG" 2>&1; mark "mock DONE rc=$? tests=$(mock_count)"
  if [ "$(mock_count)" -eq 0 ]; then mark "mock ABORTED: no mock tests generated (build or generation failure, see logs/mockgen_${P}_s*.log); pipeline stopped"; exit 1; fi
fi
if stage_on schema; then
  mark "schema START"; bash scripts/create_project_schema.sh "$MODEL" "$TEMP" "java_projects/cleaned_final_projects$SUFFIX" "$SUFFIX" "$P" >> "$LOG" 2>&1; mark "schema DONE rc=$? schemas=$(ls "data/schemas$SUFFIX/$MODEL/$TEMP/$P" 2>/dev/null | wc -l)"
fi
if stage_on augment; then
  mark "augment START"; BUDGET=${ES_BUDGET:-180} PAR=${ES_PAR:-4} bash scripts/augment_evosuite.sh "$P" "$MODEL" "$TEMP" "$SUFFIX" >> "$LOG" 2>&1; mark "augment DONE rc=$? ES2 classes=$(find "java_projects/cleaned_final_projects_evosuite/$P/src/test/java" -name '*ES2_ESTest.java' 2>/dev/null | wc -l)"
fi
if stage_on mock2; then
  mark "mock2 START"; before=$(mock_count); SHARDS=${SHARDS:-4} bash scripts/generate_mock_tests_sharded.sh "$P" >> "$LOG" 2>&1; mark "mock2 DONE rc=$? tests=$(mock_count) (+$(( $(mock_count) - before )))"
fi
if stage_on types; then
  mark "types START"; bash scripts/translate_types.sh "$P" "$MODEL" "$TEMP" "$SUFFIX" description Java Python >> "$LOG" 2>&1; mark "types DONE rc=$?"
fi
if stage_on typemap; then
  mark "typemap START"; bash scripts/create_project_type_map.sh "$MODEL" "$TEMP" "$SUFFIX" "$P" >> "$LOG" 2>&1; mark "typemap DONE rc=$? $(grep -h 'type mapping success' "logs/type_map_${P}_${SUFFIX}.log" 2>/dev/null | tail -1)"
fi
if stage_on infer; then
  mark "infer START"; bash scripts/automated_project_type_inference.sh "$MODEL" "$TEMP" "$SUFFIX" "$P" >> "$LOG" 2>&1; mark "infer DONE rc=$? $(grep -h 'type mapping success' "logs/infer_type_map_${P}_${SUFFIX}.log" 2>/dev/null | tail -1)"
fi
if stage_on skeleton; then
  mark "skeleton START"; bash scripts/create_project_skeleton.sh "$SUFFIX" "$MODEL" "$TEMP" "$P" >> "$LOG" 2>&1; mark "skeleton DONE rc=$?"
fi
if stage_on translate; then
  mark "translate START"; bash scripts/translate_fragment.sh "$P" "$TEMP" "$MODEL" "$SUFFIX" >> "$LOG" 2>&1; mark "translate DONE rc=$?"
fi
if stage_on results; then
  mark "results START"; bash scripts/print_results.sh "$P" "$TEMP" "$MODEL" "data/schemas$SUFFIX" "$SUFFIX" > "logs/results_$P.txt" 2>&1; mark "results DONE rc=$?"
fi
mark "PIPELINE END"
