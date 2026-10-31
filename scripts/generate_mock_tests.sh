#!/bin/bash
# env: TEST_TIMEOUT (seconds per test method, default 900), MAX_MOCK_TEST_MB (mock tests above this size are set aside, default 10),
#      MAX_LOG_MB (aspect logs above this size are truncated in flight and discarded, default 2048)

if [ -z "$1" ]; then
  echo "Usage: $0 <project_name>"
  exit 1
fi

PROJECT="$1"
DATA_DIR="../../data/mock_tests"
DEST_DIR="../../java_projects/cleaned_final_projects_evosuite_cleaned"

bash scripts/log_cap_guard.sh "$PROJECT" > /dev/null 2>&1 &   # keeps aspect logs under MAX_LOG_MB while tests run
GUARD_PID=$!; trap 'kill $GUARD_PID 2>/dev/null' EXIT
cd src/isolated_validation || exit 1

source "$HOME/.sdkman/bin/sdkman-init.sh"

# Use Java 8 for mock test generation
sdk use java 8.0.432-kona

python3 generate_logs.py "$PROJECT" "${TEST_TIMEOUT:-900}" executed_tests True
mkdir -p "$DATA_DIR/$PROJECT"
rsync -a --ignore-existing "${PROJECT}-python/" "$DATA_DIR/$PROJECT/"

rm -rf "$DEST_DIR/$PROJECT/evosuite-tests"

# Switch back to Java 21
sdk use java 21.0.3-graal

cd ../../
