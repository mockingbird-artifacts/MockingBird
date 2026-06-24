#!/bin/bash

project=$1
temperature=$2
model=$3
results_dir=$4
suffix=$5

echo "results for $project [temperature=$temperature, model=$model]"

output=$(python3 src/postprocessing/print_results.py --project_name=$project --results_dir=$results_dir --temperature=$temperature --model=$model | tee /dev/tty)

total_main=$(echo "$output" | grep -oP 'main methods: \K[0-9]+')
interface_methods=$(echo "$output" | grep -oP 'interface methods: \K[0-9]+')

echo "main methods: $total_main"
echo "interface methods: $interface_methods"

target_dir="java_projects/cleaned_final_projects${suffix}/${project}"
cp src/utils/count_missed_methods.py "$target_dir"

(
  cd "$target_dir" || exit
  mvn clean test jacoco:report \
    -Drat.skip=true \
    -Dgpg.skip=true \
    -Dmoditect.skip=true \
    -Dcheckstyle.skip=true \
    -Dmaven.javadoc.skip=true \
    -Dmaven.test.failure.ignore=true \
    > /dev/null 2>&1
)

orig_dir=$(pwd)

missed_output=$(cd "$target_dir" && python3 count_missed_methods.py; cd "$orig_dir")

missed_count=$(echo "$missed_output" | grep -oP 'missed: \K[0-9]+')

covered=$((total_main - interface_methods - missed_count))

coverage=$(awk "BEGIN { printf \"%.2f\", ($covered/$total_main)*100 }")

echo "Covered methods: $covered"
echo "Test coverage: $coverage% ($covered / $total_main)"
