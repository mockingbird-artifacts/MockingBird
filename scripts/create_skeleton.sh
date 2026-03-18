#!/bin/bash

suffix=$1
model=$2
pwd=$(pwd)

export PYTHONPATH=`pwd`;

for temperature in 0.0;
do
    for project in 'commons-cli' 'commons-codec' 'commons-csv' 'commons-exec' 'JavaFastPFOR' 'commons-fileupload' 'commons-graph' 'jansi' 'commons-pool' 'commons-validator';
    do
        echo "creating skeleton for $project"
        python3 src/preprocessing/create_skeleton.py --project_name=$project --model_name=$model --suffix=$suffix --temperature=$temperature 2>&1 | tee create_skeleton_${project}_${model}_${temperature}_${suffix}.log; [ ${PIPESTATUS[0]} -eq 0 ] || echo "ERROR: Python script failed with exit code ${PIPESTATUS[0]}" >> create_skeleton_${project}_${model}_${temperature}_${suffix}.log
    done
done
