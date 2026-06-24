#!/bin/bash

if [ $# -ne 2 ]; then
  echo "Usage: ./generate_cg.sh <project_name> <project_dir>"
  exit 1
fi

SCRIPT_DIR=$(dirname "$(realpath "$0")")

PROJECT_NAME="$1"
PROJECT_PATH="$2"
PROJECT_DIR="$PROJECT_PATH/$PROJECT_NAME"
OUTPUT_PATH="$PWD/data/call_graphs/$PROJECT_NAME"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Error: Directory '$PROJECT_DIR' does not exist."
  exit 1
fi

cd "$PROJECT_DIR" || exit 1

TARGET_DIR="target"

MAIN_JAR=$(find "$TARGET_DIR" -type f -name "*[^-tests].jar" | grep -v "merged" | head -n 1)

MERGED_JAR="$TARGET_DIR/$(basename "$MAIN_JAR" .jar)-merged.jar"

JAVACG_PATH="$SCRIPT_DIR/../misc/java-callgraph/target/javacg-0.1-SNAPSHOT-static.jar"

if [ ! -f "$JAVACG_PATH" ]; then
  echo "Error: javacg-0.1-SNAPSHOT-static.jar not found at $JAVACG_PATH."
  exit 1
fi

echo "Generating call graph for $MERGED_JAR..."
java -jar "$JAVACG_PATH" "$MERGED_JAR" > "$OUTPUT_PATH/callgraph.txt"

echo "Call graph saved to $OUTPUT_PATH/callgraph.txt."

