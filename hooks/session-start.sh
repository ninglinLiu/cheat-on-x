#!/usr/bin/env bash
#
# cheat-on-x SessionStart hook — thin wrapper around session_start.py.
# Prints a short status block (due retros, today's posts, queue, candidates, confidence, warnings)
# into Claude's context before the first reply. Read-only. Silent outside cheat-on-x projects.

set -uo pipefail

HOOK_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

[[ -f "$PROJECT_DIR/.cheatx-state.json" ]] || exit 0

for cand in python3 python; do
  [[ "$(command -v "$cand" 2>/dev/null)" == *WindowsApps* ]] && continue   # Windows Store stub
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >/dev/null 2>&1; then
    exec "$cand" "$HOOK_DIR/session_start.py" "$PROJECT_DIR"
  fi
done

echo "[cheat-on-x] SessionStart：没找到 Python 3.8+，跳过自动报告。说 \"X 状态\" 看完整看板。"
exit 0
