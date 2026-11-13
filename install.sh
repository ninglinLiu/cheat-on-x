#!/usr/bin/env bash
#
# cheat-on-x / install.sh
#
# Symlinks the cheat-on-x entry skill + the 15 cheatx-* sub-skills (slash commands) into
# Claude Code and/or Codex skill directories.
# Skill names are prefixed `cheatx-` so cheat-on-x can be installed side by side with
# upstream cheat-on-content (`cheat-*`) without collisions.
#
# After install: open your agent and say "启动 cheat-on-x" (or "start cheat-on-x").
# Agents can also do all of this themselves — see START.md.
#
# To uninstall: bash uninstall.sh
#
# Usage:
#   bash install.sh                    # Claude Code install, symlink mode (default)
#   bash install.sh --copy             # Claude Code install, copy mode
#   bash install.sh --codex            # Codex install into ~/.codex/skills/
#   bash install.sh --all              # install for Claude Code and Codex
#   bash install.sh --codex --copy     # Codex install, copy mode
#   bash install.sh --yes              # never prompt (overwrite existing links); for agents / CI
#   bash install.sh --reinstall-hooks <project-dir>
#                                      # rewrite hook scripts in an existing project's .cheatx-hooks/
#                                      # (use after git pull when CHANGELOG mentions hook changes;
#                                      #  does NOT touch .cheatx-state.json or any user data)

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

HOOK_FILES=(
  prediction-immutability.sh
  session-start.sh
  session_start.py
  log-event.sh
)

CLAUDE_SKILLS=(cheat-on-x "${SUB_SKILLS[@]}")
CODEX_SKILLS=(cheat-on-x "${SUB_SKILLS[@]}")

SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

MODE="symlink"
TARGET_AGENT="claude"
ASSUME_YES=0
FELL_BACK_TO_COPY=0

# --- --reinstall-hooks branch: rewrite a user project's hook scripts only ---
if [[ "${1:-}" == "--reinstall-hooks" ]]; then
  PROJECT_DIR="${2:-}"
  if [[ -z "$PROJECT_DIR" ]]; then
    echo "❌ Usage: bash install.sh --reinstall-hooks <path-to-x-project>"
    exit 1
  fi
  if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "❌ Project dir not found: $PROJECT_DIR"
    exit 1
  fi
  if [[ ! -f "$PROJECT_DIR/.cheatx-state.json" ]]; then
    echo "❌ $PROJECT_DIR is not a cheat-on-x project (no .cheatx-state.json)."
    echo "   Run /cheatx-init in that directory first."
    exit 1
  fi

  HOOK_DST="$PROJECT_DIR/.cheatx-hooks"
  mkdir -p "$HOOK_DST"

  echo ""
  echo "Reinstalling hook scripts in: $PROJECT_DIR"
  echo "  source: $SCRIPT_DIR/hooks/"
  echo ""

  for hook_file in "${HOOK_FILES[@]}"; do
    if [[ -f "$SCRIPT_DIR/hooks/$hook_file" ]]; then
      cp "$SCRIPT_DIR/hooks/$hook_file" "$HOOK_DST/$hook_file"
      chmod +x "$HOOK_DST/$hook_file"
      echo "  ✓ updated: .cheatx-hooks/$hook_file"
    else
      echo "  ⚠️  missing in source: hooks/$hook_file (skipped)"
    fi
  done

  echo ""
  echo "✅ Hook scripts reinstalled."
  echo ""
  echo "Note: this did NOT touch .cheatx-state.json, .claude/settings.json,"
  echo "      rubric_notes.md, predictions/ or posts/."
  echo "If the schema also changed (CHANGELOG marks BREAKING), run /cheatx-migrate."
  echo ""
  exit 0
fi

for arg in "$@"; do
  case "$arg" in
    --copy)   MODE="copy" ;;
    --claude) TARGET_AGENT="claude" ;;
    --codex)  TARGET_AGENT="codex" ;;
    --all)    TARGET_AGENT="all" ;;
    --yes|-y) ASSUME_YES=1 ;;
    --help|-h)
      sed -n '1,25p' "$0"
      exit 0
      ;;
    *)
      echo "❌ Unknown argument: $arg"
      echo "   Usage: bash install.sh [--copy] [--claude|--codex|--all] [--yes]"
      exit 1
      ;;
  esac
done

if [[ ! -f "$SCRIPT_DIR/SKILL.md" ]]; then
  echo "❌ Missing: $SCRIPT_DIR/SKILL.md — run install.sh from the cheat-on-x root."
  exit 1
fi

for s in "${SUB_SKILLS[@]}"; do
  if [[ ! -f "$SCRIPT_DIR/skills/$s/SKILL.md" ]]; then
    echo "❌ Missing: $SCRIPT_DIR/skills/$s/SKILL.md — run install.sh from the cheat-on-x root."
    exit 1
  fi
done

skill_source() {
  local skill="$1"
  if [[ "$skill" == "cheat-on-x" ]]; then
    echo "$SCRIPT_DIR"
  else
    echo "$SCRIPT_DIR/skills/$skill"
  fi
}

detect_conflicts() {
  local target_dir="$1"
  shift
  local warned=0
  for s in "$@"; do
    local src target
    src=$(skill_source "$s")
    target="$target_dir/$s"
    if [[ -e "$target" || -L "$target" ]]; then
      if [[ -L "$target" ]]; then
        local existing
        existing=$(readlink "$target")
        if [[ "$existing" != "$src" ]]; then
          echo "⚠️  $target already symlinked to: $existing"
          warned=1
        fi
      else
        echo "⚠️  $target exists (not a symlink) — will be overwritten"
        warned=1
      fi
    fi
  done
  return "$warned"
}

install_skills() {
  local label="$1"
  local target_dir="$2"
  shift 2
  mkdir -p "$target_dir"
  echo ""
  echo "Installing cheat-on-x for $label (mode: $MODE)"
  echo "  source: $SCRIPT_DIR"
  echo "  target: $target_dir/"
  echo ""
  for s in "$@"; do
    local src dst
    src=$(skill_source "$s")
    dst="$target_dir/$s"
    if [[ -e "$dst" || -L "$dst" ]]; then
      rm -rf "$dst"
    fi
    if [[ "$MODE" == "symlink" ]]; then
      # Git Bash on Windows silently deep-copies on `ln -s` unless native symlinks are allowed
      # (Developer Mode / admin). Ask for a native link; if we did not get one, copy explicitly.
      if MSYS=winsymlinks:nativestrict ln -s "$src" "$dst" 2>/dev/null && [[ -L "$dst" ]]; then
        echo "  ✓ symlinked: $s"
      else
        rm -rf "$dst"
        cp -R "$src" "$dst"
        if [[ "$s" == "cheat-on-x" ]]; then
          rm -rf "$dst/.git"
        fi
        FELL_BACK_TO_COPY=1
        echo "  ✓ copied:    $s (symlinks not available here)"
      fi
    else
      cp -R "$src" "$dst"
      if [[ "$s" == "cheat-on-x" ]]; then
        rm -rf "$dst/.git"
      fi
      echo "  ✓ copied:    $s"
    fi
  done
}

WARNED=0
if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  detect_conflicts "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}" || WARNED=1
fi
if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  detect_conflicts "$HOME/.codex/skills" "${CODEX_SKILLS[@]}" || WARNED=1
fi

if [[ $WARNED -eq 1 && $ASSUME_YES -eq 1 ]]; then
  echo "(--yes: overwriting)"
elif [[ $WARNED -eq 1 && ! -t 0 ]]; then
  echo ""
  echo "Not a terminal, so I cannot ask. Re-run with --yes to overwrite."
  exit 1
elif [[ $WARNED -eq 1 ]]; then
  echo ""
  read -p "Continue and overwrite? (y/N) " -n 1 -r
  echo ""
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
  fi
fi

if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  install_skills "Claude Code" "$HOME/.claude/skills" "${CLAUDE_SKILLS[@]}"
fi
if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  install_skills "Codex" "$HOME/.codex/skills" "${CODEX_SKILLS[@]}"
fi

echo ""
echo "✅ Install complete!"
echo ""
echo "Next steps:"
echo "  1. Open Claude Code or Codex (a new session, so the skills load)"
echo "  2. Say:  启动 cheat-on-x   (or: start cheat-on-x)"
echo "     It sets up a workspace (default ~/x-posts), asks 3 questions, and from then on"
echo "     you just talk: paste drafts, say \"posting now\", paste the link, ask \"how did it do\"."
echo ""
echo "  Data export (default, free): install userscripts/cheatx-exporter.user.js"
echo "  in Tampermonkey / Violentmonkey — see userscripts/README.md"
echo ""
if [[ "$TARGET_AGENT" == "claude" || "$TARGET_AGENT" == "all" ]]; then
  echo "Verify Claude install: ls -la ~/.claude/skills/ | grep cheatx"
fi
if [[ "$TARGET_AGENT" == "codex" || "$TARGET_AGENT" == "all" ]]; then
  echo "Verify Codex install:  ls -la ~/.codex/skills/ | grep cheat"
  echo "Note: restart Codex if the new skills do not appear in the current session."
fi
echo ""
if [[ "$MODE" == "symlink" && $FELL_BACK_TO_COPY -eq 1 ]]; then
  echo "ℹ️  Mode: copy (this system could not create symlinks — e.g. Windows without Developer Mode)."
  echo "   Re-run install.sh after updating the source to refresh the installed copy."
elif [[ "$MODE" == "symlink" ]]; then
  echo "ℹ️  Mode: symlink — edits to source SKILL.md files take effect immediately."
else
  echo "ℹ️  Mode: copy — frozen at install time. Re-run install.sh to update."
fi
echo ""
