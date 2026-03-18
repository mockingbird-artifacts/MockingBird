#!/bin/bash

PROJECT=$1
TEMPERATURE=$2
MODEL=$3
SUFFIX=$4

python3 src/preprocessing/create_test_method_map.py --project_name=$PROJECT --model_name=$MODEL --suffix=$SUFFIX --temperature=$TEMPERATURE

export PYTHONPATH=$PYTHONPATH:`pwd`

MAX_RETRIES=3
RETRY_DELAY=5
LOG_FILE="${PROJECT}_${MODEL}_body.log"

for ((i=1; i<=MAX_RETRIES; i++)); do
    echo "Attempt $i of $MAX_RETRIES..." | tee -a "$LOG_FILE"
    
    python3 src/translation/compositional_translation_validation.py \
        --model_name=$MODEL \
        --project_name=$PROJECT \
        --from_lang=Java \
        --to_lang=Python \
        --debug \
        --fix_agent_simple \
        --fix_agent_advanced \
        --suffix=$SUFFIX \
        --validate_by_mocking \
        --temperature=$TEMPERATURE \
        --recursion_depth=2 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -eq 0 ]; then
        echo "All Fragment translations completed successfully." | tee -a "$LOG_FILE"
        break
    fi

    if [ $i -eq $MAX_RETRIES ]; then
        echo "Fragment Translation failed after $MAX_RETRIES attempts." | tee -a "$LOG_FILE"
        exit 1
    fi

    echo "Retrying after $RETRY_DELAY seconds..." | tee -a "$LOG_FILE"
    sleep $RETRY_DELAY
done

