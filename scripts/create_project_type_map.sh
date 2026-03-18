#!/bin/bash

MODEL_NAME=$1
TEMPERATURE=$2
SUFFIX=$3
PROJECT=$4

echo "creating type map for $PROJECT [model: $MODEL_NAME, temperature: $TEMPERATURE, suffix: $SUFFIX]"

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/type_map_${PROJECT}_${SUFFIX}.log"

python3 src/type_resolution/create_type_map.py \
  --project_name="$PROJECT" \
  --model_name="$MODEL_NAME" \
  --temperature="$TEMPERATURE" \
  --suffix="$SUFFIX" \
  > "$LOG_FILE" 2>&1
