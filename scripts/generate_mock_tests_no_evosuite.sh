#!/bin/bash

if [ -z "$1" ]; then
  echo "Usage: $0 <project_name>"
  exit 1
fi

PROJECT="$1"
DATA_DIR="../../data/mock_tests"
DEST_DIR="../../java_projects/cleaned_final_projects_no_evosuite_cleaned"

cd src/isolated_validation || exit 1

source "$HOME/.sdkman/bin/sdkman-init.sh"

# Use Java 8 for mock test generation
sdk use java 8.0.432-kona

python3 generate_logs_no_evosuite.py "$PROJECT" 400 executed_tests

mkdir -p "$DATA_DIR/$PROJECT"
rsync -a --ignore-existing "${PROJECT}-python/" "$DATA_DIR/$PROJECT/"

rm -rf "$DEST_DIR/$PROJECT/evosuite-tests"

# Switch back to Java 21
sdk use java 21.0.3-graal

cd ../../
