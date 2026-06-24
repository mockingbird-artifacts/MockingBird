#!/bin/bash

suffix=$1
model=$2
temperature=$3
project=$4
pwd=$(pwd)

export PYTHONPATH=`pwd`;

echo "creating skeleton for $project"
python3 src/preprocessing/create_skeleton.py --project_name=$project --model_name=$model --suffix=$suffix --temperature=$temperature 2>&1 | tee create_skeleton_${project}_${model}_${temperature}_${suffix}.log; [ ${PIPESTATUS[0]} -eq 0 ] || echo "ERROR: Python script failed with exit code ${PIPESTATUS[0]}" >> create_skeleton_${project}_${model}_${temperature}_${suffix}.log
