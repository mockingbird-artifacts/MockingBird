#!/bin/bash
# Top up the EvoSuite test suite of a project for the classes whose public/protected methods still have no mock test after a
# first `generate_mock_tests.sh` run: build the project unwoven, run EvoSuite 1.2.0 (runtime mocking and sandbox off, so the
# tests survive clean_evosuite_tests.py), rename the classes to <X>ES2_ESTest and place the raw files next to the archive's
# EvoSuite tests. Re-run `generate_mock_tests.sh <project>` afterwards to clean, build and record them.
# usage: BUDGET=180 PAR=8 bash scripts/augment_evosuite.sh <project> <model> <temperature> <suffix>
# needs Java 8; misc/evosuite-1.2.0.jar and misc/evosuite-standalone-runtime-1.2.0.jar are downloaded from the EvoSuite 1.2.0 release when missing
set -u; P=$1; MODEL=${2:-deepseek-coder-33b-instruct}; TEMP=${3:-0.0}; SUFFIX=${4:-_evosuite_cleaned}; BUDGET=${BUDGET:-180}; PAR=${PAR:-8}
ROOT=$(pwd); JAR=$ROOT/misc/evosuite-1.2.0.jar; WORK=$ROOT/logs/evosuite/$P; mkdir -p $WORK
set +u; source "$HOME/.sdkman/bin/sdkman-init.sh"; sdk use java 8.0.432-kona; set -u   # sdkman-init is not set -u clean
[ -f $JAR ] || curl -sL -o $JAR https://github.com/EvoSuite/evosuite/releases/download/v1.2.0/evosuite-1.2.0.jar
RT=$ROOT/misc/evosuite-standalone-runtime-1.2.0.jar; [ -f $RT ] || curl -sL -o $RT https://github.com/EvoSuite/evosuite/releases/download/v1.2.0/evosuite-standalone-runtime-1.2.0.jar   # evosuite_place_tests.py compiles the scaffolding against it
rm -rf $WORK/proj && cp -r java_projects/cleaned_final_projects$SUFFIX/$P $WORK/proj && (cd $WORK/proj && mvn -q clean compile -Drat.skip -Dgpg.skip -Dmoditect.skip -Dcheckstyle.skip -Dmaven.javadoc.skip && mvn -q dependency:build-classpath -Dmdep.outputFile=$WORK/cp.txt -Drat.skip)
echo "$WORK/proj/target/classes:$(cat $WORK/cp.txt)" > $WORK/cp_full.txt
python3 src/isolated_validation/evosuite_targets.py $P data/schemas$SUFFIX/$MODEL/$TEMP/$P data/mock_tests/$P > $WORK/targets.txt
rm -rf $WORK/out $WORK/report; mkdir -p $WORK/out $WORK/report $WORK/runs
export ES_CP=$(cat $WORK/cp_full.txt) ES_BUDGET=$BUDGET ES_OUT=$WORK/out ES_REPORT=$WORK/report ES_RUNS=$WORK/runs ES_JAR=$JAR
run_one () { timeout $((ES_BUDGET*3)) java -Xmx3g -jar $ES_JAR -class "$1" -projectCP "$ES_CP" -Dsearch_budget=$ES_BUDGET -Dtest_dir=$ES_OUT -Dreport_dir=$ES_REPORT -Dsandbox=false -Dvirtual_fs=false -Dreplace_calls=false -Dreplace_system_in=false -Dvirtual_net=false -Dminimize=true > "$ES_RUNS/$1.log" 2>&1; }
export -f run_one
xargs -P $PAR -I{} bash -c 'run_one "$1"' _ {} < $WORK/targets.txt
echo "EvoSuite generated $(find $WORK/out -name '*_ESTest.java' | wc -l) test classes for $(wc -l < $WORK/targets.txt) target classes"
python3 src/isolated_validation/evosuite_place_tests.py $WORK/out java_projects/cleaned_final_projects_evosuite/$P $WORK/cp_full.txt
set +u; sdk use java 21.0.3-graal
