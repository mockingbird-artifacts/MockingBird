#!/usr/bin/env bash
set -euo pipefail

# $1 = fully-qualified test class
# $2 = test method
mvn clean install \
    -Drat.skip \
    -Dgpg.skip \
    "-Dtest=${1}#${2}"
