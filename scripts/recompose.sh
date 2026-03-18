#!/bin/bash

PROJECT=$1
TEMPERATURE=$2
MODEL=$3
SUFFIX=$4

export PYTHONPATH=$PYTHONPATH:`pwd`
python3 src/postprocessing/recompose.py --project_name=$PROJECT \
                                        --model_name=$MODEL \
                                        --output_dir=data/recomposed_projects \
                                        --temperature=$TEMPERATURE \
                                        --suffix=$SUFFIX \
