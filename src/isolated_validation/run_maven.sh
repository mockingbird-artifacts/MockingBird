#!/usr/bin/env bash
set -euo pipefail

# $1 = fully-qualified test class
# $2 = test method
# the project was fully built (and woven with the logging aspect) once by generate_logs.py; per-test runs only need the
# test phase on the existing build, which avoids a full clean+compile for each of the thousands of test methods
mvn test \
    -q \
    -Drat.skip \
    -Dgpg.skip \
    -Dmoditect.skip \
    -Dcheckstyle.skip \
    -Dmaven.javadoc.skip \
    -DfailIfNoTests=false \
    "-Dtest=${1}${2:+#${2}}"   # an empty method runs the whole class (inherited test methods)
