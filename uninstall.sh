#!/usr/bin/env bash
#
# cheat-on-x / uninstall.sh
#
# Removes the cheatx-* skills from Claude Code and/or Codex skill dirs.
# Does NOT touch upstream cheat-on-content (cheat-*) skills, and does NOT touch any
# X content project's data (.cheatx-state.json, predictions/, posts/, rubric_notes.md …).
#
# Usage:
#   bash uninstall.sh          # remove Claude Code install (default)
#   bash uninstall.sh --codex  # remove Codex install
#   bash uninstall.sh --all    # remove both

set -euo pipefail

SUB_SKILLS=(
  cheatx-init
  cheatx-learn-from
  cheatx-seed
  cheatx-score
  cheatx-score-blind
  cheatx-predict
  cheatx-queue
  cheatx-publish
  cheatx-retro
  cheatx-persona
  cheatx-bump
  cheatx-recommend
  cheatx-trends
  cheatx-status
  cheatx-migrate
)

CLAUDE_SKILLS=("${SUB_SKILLS[@]}")
CODEX_SKILLS=(cheat-on-x "${SUB_SKILLS[@]}")

TARGET_AGENT="claude"
for arg in "$@"; do
  case "$arg" in
    --claude) TARGET_AGENT="claude" ;;
    --codex)  TARGET_AGENT="codex" ;;
    --all)    TARGET_AGENT="all" ;;
    --help|-h)
      sed -n '1,14p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $arg"
      echo "   Usage: bash uninstall.sh [--claude|--codex|--all]"
      exit 1
      ;;
  esac
done

REMOVED=0

remove_skills() {
  local label="$1"
  local target_dir="$2"
  shift 2
  echo ""
  echo "Removing cheat-on-x from $label:"
  echo "  target: $target_dir/"
  echo ""
  for s in "$@"; do
    local target="$target_dir/$s"
    if [[ -L "$target" ]]; then
      rm "$target"
      echo "  ✓ removed symlink:   $s"
      REMOVED=$((REMOVED + 1))
    elif [[ -d "$target" ]]; then
      rm -rf "$target"
      echo "  ✓ removed directory: $s"
      REMOVED=$((REMOVED + 1))
    else
      echo "  · not found:         $s (skipped)"
    fi
  done
}

if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  remove_skills "Claude Code" "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}"
fi
if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  remove_skills "Codex" "$HOME/.codex/skills" "${CODEX_SKILLS[@]}"
fi

echo ""
if [[ $REMOVED -gt 0 ]]; then
  echo "✅ Uninstalled $REMOVED skill(s)."
else
  echo "ℹ️  Nothing to uninstall."
fi
echo ""
echo "Note: your X projects' data (predictions/, posts/, rubric_notes.md, .cheatx-state.json,"
echo "      .cheatx-hooks/, candidates.md …) are NOT touched."
echo ""
echo "To re-install: bash install.sh [--codex|--all] (from the cheat-on-x source root)"
echo ""
