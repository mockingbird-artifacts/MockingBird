
#!/bin/bash

PROJECT=$1
TEMPERATURE=$2
MODEL=$3
SUFFIX=$4

export PYTHONPATH=$PYTHONPATH:`pwd`
bash scripts/recompose.sh $PROJECT $TEMPERATURE $MODEL
python3 src/translation/verify_translation_results.py --model_name=$MODEL --project_name=$PROJECT --temperature=$TEMPERATURE --suffix=$SUFFIX
