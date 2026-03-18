#!/bin/bash

# Usage: ./copy_schema.sh MODEL_NAME

if [ $# -ne 1 ]; then
  echo "Usage: $0 MODEL_NAME"
  exit 1
fi

MODEL_NAME="$1"

cp -r data/schemas_evosuite/llama-3-3-70b-instruct "data/schemas_evosuite/${MODEL_NAME}"
