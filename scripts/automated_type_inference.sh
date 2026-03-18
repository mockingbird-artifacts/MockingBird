#!/bin/bash

MODEL_NAME=$1
TEMPERATURE=$2
SUFFIX=$3

for PROJECT in 'commons-cli' 'commons-codec' 'commons-csv' 'commons-exec' 'JavaFastPFOR' 'commons-fileupload' 'commons-graph' 'jansi' 'commons-pool' 'commons-validator';
do
    echo "inferencing type map for $PROJECT"
    python3 src/type_resolution/automated_type_inference.py --project_name=$PROJECT --model_name=$MODEL_NAME --temperature=$TEMPERATURE --suffix=$SUFFIX
done
