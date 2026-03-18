#!/bin/bash

set -e

if [ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]; then
  source "$HOME/.sdkman/bin/sdkman-init.sh"
else
  echo "SDKMAN is not installed or sdkman-init.sh not found"
  exit 1
fi

# For projects with Evosuitre dependency, use Java 11 for call graph extraction
sdk use java 11.0.26-amzn

bash scripts/extract_call_graph.sh "$1" "$2"

sdk use java 21.0.3-graal
