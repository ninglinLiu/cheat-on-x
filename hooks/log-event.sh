#!/usr/bin/env bash
#
# cheat-on-x / meta-logging hook
#
# Passive event recorder: one JSON line per event in .cheatx-cache/usage.jsonl.
# Stores event type, tool name, file path, success flag, and prompt presence/length only —
# never prompt text. Async fire-and-forget; never blocks.
#
# Used by /cheatx-status (e.g. "predictions since last bump", rough x-api call count).
#
# Usage: log-event.sh <tool_use|user_prompt|session_start|session_end>   (payload on stdin)

set -uo pipefail

event_type="${1:-unknown}"
cache_dir="${CLAUDE_PROJECT_DIR:-.}/.cheatx-cache"
log_file="${cache_dir}/usage.jsonl"

[[ -f "${CLAUDE_PROJECT_DIR:-.}/.cheatx-state.json" ]] || exit 0
mkdir -p "$cache_dir" 2>/dev/null || exit 0

input=$(cat 2>/dev/null || echo "{}")
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

case "$event_type" in
  tool_use|user_prompt|session_start|session_end) ;;
  *) event_type="unknown" ;;
esac

event_json=""
if command -v jq >/dev/null 2>&1; then
  event_json=$(printf '%s' "$input" | jq -c --arg ts "$ts" --arg type "$event_type" '
    {
      ts: $ts,
      event: $type,
      tool: (.tool_name // null),
      file: (.tool_input.file_path // null),
      command_head: ((.tool_input.command // "") | tostring | .[0:80] | if test("xapi\\.py|import_csv\\.py|calib_pool\\.py|rank_check\\.py") then . else null end),
      success: (.tool_response.success // null),
      prompt_present: ((.prompt // .user_prompt // null) != null),
      prompt_chars: ((.prompt // .user_prompt // "" | tostring) | length)
    }' 2>/dev/null || echo "")
fi
[[ -z "$event_json" ]] && event_json=$(printf '{"ts":"%s","event":"%s"}' "$ts" "$event_type")

printf '%s\n' "$event_json" >> "$log_file" 2>/dev/null || true
exit 0
