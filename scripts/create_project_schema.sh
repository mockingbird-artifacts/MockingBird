#!/bin/bash

MODEL_NAME=$1
TEMPERATURE=$2
PROJECT_PATH=$3
SUFFIX=$4
PROJECT_NAME=$5

export PYTHONPATH=`pwd`;

echo "creating schema for $PROJECT_NAME"
bash scripts/extract_call_graph_evosuite.sh $PROJECT_NAME $PROJECT_PATH
python3 src/decomposition/create_schema.py --project_name=$PROJECT_NAME --suffix=$SUFFIX --model_name=$MODEL_NAME --temperature=$TEMPERATURE
