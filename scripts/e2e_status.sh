#!/bin/bash
# One line per project: last stage marker, mock tests so far, disk and model-server state. usage: bash scripts/e2e_status.sh
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd); cd "$ROOT"
date -u +%FT%TZ; echo "disk: $(df -h . | tail -1 | awk '{print $4" free of "$2}')  pipelines running: $(pgrep -fc "run_project[.]sh")"
for f in logs/stages_*.txt; do [ -f "$f" ] || continue; P=${f#logs/stages_}; P=${P%.txt}
  printf "%-20s %-70s mock tests=%s\n" "$P" "$(tail -n 1 "$f" | cut -c1-70)" "$(find "data/mock_tests/$P" -name '*_mocker_*.py' 2>/dev/null | wc -l)"; done
echo "model server: $(curl -s -m 3 "${OLLAMA_URL:-http://127.0.0.1:11434}/api/ps" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(", ".join(f"{m[\"name\"]} {m[\"size_vram\"]/1e9:.0f} GB VRAM" for m in d.get("models",[])) or "idle")' 2>/dev/null || echo unreachable)"
