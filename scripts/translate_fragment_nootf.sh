#!/bin/bash
# w/o-OTF arm: translate with NO on-the-fly mocking validation; mocking is applied
# only as a final verdict pass afterwards (scripts/revalidate_fragments_isolated.py).
PROJECT=$1
TEMPERATURE=$2
MODEL=$3
SUFFIX=$4

python3 src/preprocessing/create_test_method_map.py --project_name=$PROJECT --model_name=$MODEL --suffix=$SUFFIX --temperature=$TEMPERATURE
export PYTHONPATH=$PYTHONPATH:`pwd`

MAX_RETRIES=3
LOG_FILE="${PROJECT}_${MODEL}_body.log"
for ((i=1; i<=MAX_RETRIES; i++)); do
    python3 src/translation/compositional_translation_validation.py \
        --model_name=$MODEL --project_name=$PROJECT --from_lang=Java --to_lang=Python \
        --debug --fix_agent_simple --fix_agent_advanced \
        --suffix=$SUFFIX --temperature=$TEMPERATURE --recursion_depth=2 | tee -a "$LOG_FILE"
    [ ${PIPESTATUS[0]} -eq 0 ] && break
    [ $i -eq $MAX_RETRIES ] && exit 1
    sleep 5
done
