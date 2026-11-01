#!/usr/bin/env bash
set -euo pipefail

# $1 = fully-qualified test class
# $2 = test method
# the project was fully built (and woven with the logging aspect) once by generate_logs.py; per-test runs only need the
# test phase on the existing build, which avoids a full clean+compile for each of the thousands of test methods
# cap the heap of the surefire-forked test JVM (and of Maven itself): the projects set no -Xmx, so each fork defaults to a
# quarter of the machine's RAM and a few concurrent huge-array tests can exhaust it; an explicit -Xmx in a project's own
# argLine still wins over this default
export JAVA_TOOL_OPTIONS="-Xmx${SUREFIRE_XMX:-16g} ${JAVA_TOOL_OPTIONS:-}"
mvn test \
    -q \
    -Drat.skip \
    -Dgpg.skip \
    -Dmoditect.skip \
    -Dcheckstyle.skip \
    -Dmaven.javadoc.skip \
    -DfailIfNoTests=false \
    -Djacoco.skip=true \
    "-Dtest=${1}${2:+#${2}}"   # an empty method runs the whole class (inherited test methods)
# -Djacoco.skip: coverage instrumentation is not needed for mock-test generation, and a test JVM killed by the timeout
# leaves a truncated target/jacoco.exec that makes the jacoco report goal fail every later Maven run of the shard
