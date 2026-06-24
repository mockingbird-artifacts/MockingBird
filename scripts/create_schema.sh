#!/bin/bash

MODEL_NAME=$1
TEMPERATURE=$2
PROJECT_PATH=$3
SUFFIX=$4

export PYTHONPATH=`pwd`;

for PROJECT in 'commons-cli' 'commons-codec' 'commons-csv' 'commons-exec' 'JavaFastPFOR' 'commons-fileupload' 'commons-graph' 'jansi' 'commons-pool' 'commons-validator';
do
    echo "creating schema for $PROJECT"
    bash scripts/extract_call_graph.sh $PROJECT $PROJECT_PATH
    python3 src/decomposition/create_schema.py --project_name=$PROJECT --suffix=$SUFFIX --model_name=$MODEL_NAME --temperature=$TEMPERATURE
done
