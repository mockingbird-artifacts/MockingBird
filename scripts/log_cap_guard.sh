#!/bin/bash
# In-flight aspect-log cap. generate_logs.py discards an aspect log above MAX_LOG_MB only after its test ends; while a runaway
# test runs it can append several GB per minute until TEST_TIMEOUT, and a few such tests in parallel fill the disk. This loop
# truncates any aspect log above the cap every INTERVAL seconds. No process is touched: the aspect appends to the file, the
# test ends on its own timeout, and generate_logs.py then handles the log as usual.
# usage: bash scripts/log_cap_guard.sh [project]   (run from the repository root; the generate_mock_tests*.sh scripts start it
#        for the duration of a run)   env: MAX_LOG_MB (default 2048), INTERVAL (seconds between passes, default 20)
ROOT=$(pwd); ISO=$ROOT/src/isolated_validation; CAP=${MAX_LOG_MB:-2048}; INTERVAL=${INTERVAL:-20}
mkdir -p "$ROOT/logs"; L=$ROOT/logs/log_cap_guard.log
echo "$(date -u +%FT%TZ) start project=${1:-all} cap=${CAP}M interval=${INTERVAL}s pid=$$" >> "$L"
while true; do
  find "$ISO" -maxdepth 2 -path "$ISO/${1:-}*/*.log" -size +"${CAP}"M 2>/dev/null | while read -r f; do
    echo "$(date -u +%FT%TZ) truncated $(du -m "$f" | cut -f1)MB $f" >> "$L"; : > "$f"
  done
  # surefire spools a test's console output to <tmpdir>/surefire/stdout-*deferred when it grows large; a looping test fills the disk there
  find "${TMPDIR:-/tmp}/surefire" -maxdepth 1 -type f -size +"${CAP}"M 2>/dev/null | while read -r f; do
    echo "$(date -u +%FT%TZ) truncated $(du -m "$f" | cut -f1)MB $f" >> "$L"; : > "$f"
  done
  sleep "$INTERVAL"
done
