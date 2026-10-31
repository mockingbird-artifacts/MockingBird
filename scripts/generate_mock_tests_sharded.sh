#!/bin/bash
# env: TEST_TIMEOUT (seconds per test method, default 900), MAX_MOCK_TEST_MB (mock tests above this size are set aside, default 10),
#      MAX_LOG_MB (aspect logs above this size are truncated in flight and discarded, default 2048)
# Same as generate_mock_tests.sh but runs SHARDS independent workers per project (each with its own project copy),
# then merges their mock tests. usage: SHARDS=4 bash scripts/generate_mock_tests_sharded.sh <project>
if [ -z "$1" ]; then
  echo "Usage: $0 <project_name>"
  exit 1
fi
PROJECT="$1"; SHARDS=${SHARDS:-4}
DATA_DIR="../../data/mock_tests"
DEST_DIR="../../java_projects/cleaned_final_projects_evosuite_cleaned"
bash scripts/log_cap_guard.sh "$PROJECT" > /dev/null 2>&1 &   # keeps aspect logs under MAX_LOG_MB while tests run
GUARD_PID=$!; trap 'kill $GUARD_PID 2>/dev/null' EXIT
cd src/isolated_validation || exit 1
source "$HOME/.sdkman/bin/sdkman-init.sh"
sdk use java 8.0.432-kona
pids=()
for ((i=0; i<SHARDS; i++)); do
  python3 generate_logs.py "$PROJECT" "${TEST_TIMEOUT:-900}" executed_tests True --shards $SHARDS --shard $i > "../../logs/mockgen_${PROJECT}_s${i}.log" 2>&1 &
  pids+=($!)
  sleep 20   # let shard 0 create the shared cleaned copy first
done
for pid in "${pids[@]}"; do wait $pid; done
mkdir -p "$DATA_DIR/$PROJECT"
for ((i=0; i<SHARDS; i++)); do
  [ -d "${PROJECT}-python__s${i}" ] && rsync -a --ignore-existing "${PROJECT}-python__s${i}/" "$DATA_DIR/$PROJECT/"
done
# the merged mock tests now live in data/mock_tests/<project>; the per-shard project copies, outputs and set-aside
# directories are no longer needed (the resume state is in executed_tests/, so a later pass re-creates what it needs)
# and would otherwise double the project's disk footprint
[ "${KEEP_SHARD_DIRS:-0}" = "1" ] || rm -rf "${PROJECT}-python__s"[0-9]* "${PROJECT}__s"[0-9]*
rm -rf "$DEST_DIR/$PROJECT/evosuite-tests"
sdk use java 21.0.3-graal
cd ../../
