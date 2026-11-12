#!/usr/bin/env bash
#
# cheat-on-x / prediction-immutability hook  (PreToolUse: Edit|Write|MultiEdit)
#
# Locks the body of every predictions/*.md that has a '## 预测…' section: everything from the
# first '## ' heading (输入快照, 预测 v1/v2, 推理因素, 锚点对比, 反事实场景, 关键校准假设) up to the
# '## 复盘' heading. (Upstream cheat-on-content only locked the '## 预测' heading's own section,
# which left reasoning / anchors / counterfactuals / the scores editable after the fact.)
#
# Allows:
#   - creating a brand-new prediction file (Write to a path that does not exist yet)
#   - editing the metadata header (above the first '## ') — cheatx-publish writes there
#   - inserting '## 预测 v2' right before '## 复盘' (old_string starting at '## 复盘')
#   - appending inside / after '## 复盘' / '## Retrospective'
#   - files outside predictions/
# Blocks:
#   - any Edit / MultiEdit whose old_string overlaps the locked body
#   - Write that would overwrite an existing prediction file
#
# Exit codes (Claude Code PreToolUse contract):
#   0 = allow
#   2 = BLOCK — stderr is fed back to Claude. (Exit 1 would NOT block: Claude Code treats
#       any non-2 non-zero exit as a non-blocking error and runs the tool anyway.)
#
# Bypass (pure markdown-formatting fixes only, visible in git history):
#   CHEATX_BYPASS_IMMUTABILITY=1
#
# Needs python3/python (preferred, exact overlap check) or jq + awk + grep (conservative fallback).

set -uo pipefail

if [[ "${CHEATX_BYPASS_IMMUTABILITY:-0}" == "1" ]]; then
  echo "[cheat-on-x] ⚠️  IMMUTABILITY BYPASS active (CHEATX_BYPASS_IMMUTABILITY=1) — formatting fixes only." >&2
  exit 0
fi

input=$(cat)
[[ -z "$input" ]] && exit 0

block_msg() {
  cat >&2 <<EOF

[cheat-on-x] 🚫 BLOCKED: $1
  $2

预测是 immutable 的（原则 #1）。写完之后预测段一个字都不能改，只能往 '## 复盘' 追加。

要做的是：
  • 想基于新信息重做预测 → 新建 ${2%.md}_redo.md，原文件保留
  • 发现看过数据后才意识到的错误 → 在 '## 复盘' 段写更正说明
  • 纯 markdown 排版修复 → 单次设置 CHEATX_BYPASS_IMMUTABILITY=1（git 里留痕）

See: shared-references/blind-prediction-protocol.md
EOF
}

# ---------------------------------------------------------------- preferred path: Python
PY=""
for cand in python3 python; do
  # skip the Windows Store "python" stub (it can hang or open the Store instead of running)
  [[ "$(command -v "$cand" 2>/dev/null)" == *WindowsApps* ]] && continue
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "import sys; sys.exit(0 if sys.version_info >= (3, 6) else 1)" >/dev/null 2>&1; then
    PY="$cand"
    break
  fi
done

if [[ -n "$PY" ]]; then
  verdict=$(CHEATX_HOOK_INPUT="$input" "$PY" - <<'PY'
import json, os, re, sys

try:
    data = json.loads(os.environ.get("CHEATX_HOOK_INPUT") or "{}")
except ValueError:
    print("allow"); sys.exit(0)
tool = data.get("tool_name") or ""
ti = data.get("tool_input") or {}
fp = (ti.get("file_path") or "").replace("\\", "/")
if tool not in ("Edit", "Write", "MultiEdit") or not re.search(r"(^|/)predictions/[^/]+\.md$", fp):
    print("allow"); sys.exit(0)
path = fp
if not os.path.isabs(path) and not re.match(r"^[A-Za-z]:/", path):
    path = os.path.join(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd(), path)
if not os.path.isfile(path):
    print("allow"); sys.exit(0)          # creating a new prediction file
with open(path, encoding="utf-8", errors="replace") as f:
    text = f.read().replace("\r\n", "\n")

# Locked region = from the first '## ' heading (输入快照 / 预测 vN / 推理因素 / 锚点 / 反事实 / 校准假设)
# up to the '## 复盘' / '## Retrospective' heading (exclusive). The header above the first '## '
# stays editable (publish metadata), and so does everything from '## 复盘' on.
retro_head = re.compile(r"^## (复盘|Retrospective)(?![A-Za-z])")
pred_head = re.compile(r"^## (预测|Prediction)(?![A-Za-z])")
first, retro, offset, has_pred = None, None, 0, False
for line in text.splitlines(keepends=True):
    if line.startswith("## "):
        if retro_head.match(line):
            retro = offset
            break
        if first is None:
            first = offset
        if pred_head.match(line):
            has_pred = True
    offset += len(line)
if first is None or not has_pred:
    print("allow"); sys.exit(0)          # not a prediction file (no '## 预测' section)
ranges = [(first, retro if retro is not None else len(text))]
if tool == "Write":
    print("block-write"); sys.exit(0)
olds = [ti.get("old_string")] if tool == "Edit" else [e.get("old_string") for e in (ti.get("edits") or [])]
for old in olds:
    if not old:
        continue
    old = old.replace("\r\n", "\n")
    i = text.find(old)
    while i >= 0:
        j = i + len(old)
        if any(i < b and j > a for a, b in ranges):
            print("block-edit"); sys.exit(0)
        i = text.find(old, i + 1)
print("allow")
PY
)
  case "$verdict" in
    block-edit)
      file_path=$(CHEATX_HOOK_INPUT="$input" "$PY" -c "import json,os;print(json.loads(os.environ['CHEATX_HOOK_INPUT'])['tool_input']['file_path'])" 2>/dev/null)
      block_msg "edit touches the '## 预测' section of" "$file_path"
      exit 2 ;;
    block-write)
      file_path=$(CHEATX_HOOK_INPUT="$input" "$PY" -c "import json,os;print(json.loads(os.environ['CHEATX_HOOK_INPUT'])['tool_input']['file_path'])" 2>/dev/null)
      block_msg "Write would overwrite an existing prediction file (use Edit to append to '## 复盘')" "$file_path"
      exit 2 ;;
    *) exit 0 ;;
  esac
fi

# ---------------------------------------------------------------- fallback: jq + awk + grep
if ! command -v jq >/dev/null 2>&1; then
  echo "[cheat-on-x] ⚠️  prediction-immutability hook 无法检查：没有 python3/python，也没有 jq。预测锁当前不生效。" >&2
  exit 1   # non-blocking: surfaces the warning without stopping the tool
fi

tool_name=$(printf '%s' "$input" | jq -r '.tool_name // empty')
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' | tr '\\' '/')
case "$tool_name" in Edit|Write|MultiEdit) ;; *) exit 0 ;; esac
case "$file_path" in */predictions/*.md|predictions/*.md) ;; *) exit 0 ;; esac
[[ -f "$file_path" ]] || exit 0

grep -qE '^## (预测|Prediction)' "$file_path" 2>/dev/null || exit 0
# locked region: first '## ' heading up to (not including) '## 复盘' / '## Retrospective'
section=$(awk '
  /^## (复盘|Retrospective)/ { exit }
  /^## / { inp=1 }
  inp { print }
' "$file_path" 2>/dev/null)
[[ -z "$section" ]] && exit 0

if [[ "$tool_name" == "Write" ]]; then
  block_msg "Write would overwrite an existing prediction file (use Edit to append to '## 复盘')" "$file_path"
  exit 2
fi

tmp_sec=$(mktemp); tmp_pat=$(mktemp)
trap 'rm -f "$tmp_sec" "$tmp_pat"' EXIT
printf '%s\n' "$section" > "$tmp_sec"
# Conservative: block if any non-blank line of any old_string appears inside the prediction sections.
# (Blank lines are dropped — an empty pattern would match every line.)
printf '%s' "$input" | jq -r '(.tool_input.old_string // empty), (.tool_input.edits // [] | .[].old_string)' \
  | grep -v '^[[:space:]]*$' | grep -v '^## ' > "$tmp_pat" || true
if [[ -s "$tmp_pat" ]] && grep -qF -f "$tmp_pat" "$tmp_sec"; then
  block_msg "edit touches the '## 预测' section of (fallback check — install python for an exact check)" "$file_path"
  exit 2
fi
exit 0
