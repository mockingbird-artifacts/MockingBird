#!/bin/bash

MODEL_NAME=$1
TEMPERATURE=$2
SUFFIX=$3

for PROJECT in 'commons-cli' 'commons-codec' 'commons-csv' 'commons-exec' 'JavaFastPFOR' 'commons-fileupload' 'commons-graph' 'jansi' 'commons-pool' 'commons-validator';
do
    echo "creating type map for $PROJECT [model: $MODEL_NAME, temperature: $TEMPERATURE, suffix: $SUFFIX]"
    python3 src/type_resolution/create_type_map.py --project_name=$PROJECT --model_name=$MODEL_NAME --temperature=$TEMPERATURE --suffix=$SUFFIX
done
