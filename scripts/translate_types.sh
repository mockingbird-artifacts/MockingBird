#!/bin/bash

PROJECT_NAME=$1
MODEL_NAME=$2
TEMPERATURE=$3
SUFFIX=$4
PROMPT_TYPE=$5
SOURCE_LANGUAGE=$6
TARGET_LANGUAGE=$7


echo "translating types [project=$PROJECT_NAME, model=$MODEL_NAME, temperature=$TEMPERATURE, suffix=$SUFFIX, prompt_type=$PROMPT_TYPE, source_language=$SOURCE_LANGUAGE, target_language=$TARGET_LANGUAGE]"
python3 -m src.type_resolution.translate_type \
            --project_name=$PROJECT_NAME \
            --model_name=$MODEL_NAME \
            --temperature=$TEMPERATURE \
            --suffix=$SUFFIX \
            --debug \
            --prompt_type=$PROMPT_TYPE \
            --source_language=$SOURCE_LANGUAGE \
            --target_language=$TARGET_LANGUAGE \
            --budget=2 | tee ${PROJECT_NAME}_${MODEL_NAME}_${TEMPERATURE}_type_translation.log
