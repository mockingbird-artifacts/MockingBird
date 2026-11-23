#!/bin/bash
# Load the MockingBird artifact image from the Zenodo tarball (a flattened
# root filesystem produced by `docker export`, so it is loaded via `docker import`
# with the runtime configuration restored below).
# Usage: bash scripts/load_image.sh mockingbird.tar.gz
set -e
TARBALL=${1:-mockingbird.tar.gz}
docker import \
  --change 'ENV OLLAMA_KEEP_ALIVE=-1' \
  --change 'ENV OLLAMA_NUM_PARALLEL=2' \
  --change 'ENV OLLAMA_FLASH_ATTENTION=1' \
  --change 'ENV PATH=/root/.sdkman/candidates/java/current/bin:/home/apache-maven-3.9.9/bin:/root/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' \
  --change 'ENV JAVA_HOME=/root/.sdkman/candidates/java/current' \
  --change 'WORKDIR /home/tmp/MockingBird' \
  --change 'CMD ["sleep","infinity"]' \
  "$TARBALL" mockingbird:latest
echo "Loaded image mockingbird:latest"
