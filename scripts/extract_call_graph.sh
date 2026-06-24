#!/bin/bash

PROJECT=$1
PROJECT_PATH=$2

mkdir -p data/call_graphs/$PROJECT
echo "extracting call graph for $PROJECT"
bash scripts/add_plugin.sh $PROJECT $PROJECT_PATH
bash scripts/merge_jar.sh $PROJECT $PROJECT_PATH
bash scripts/generate_cg.sh $PROJECT $PROJECT_PATH
echo "done extracting call graph for $PROJECT"
