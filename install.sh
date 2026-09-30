#!/usr/bin/env bash
# Set up a knowledge vault and install the two skills.
#
#   ./install.sh vault <path>     create a new vault at <path> from template/ (refuses if it exists)
#   ./install.sh skills           install / refresh the skills into ~/.claude/skills/
#   ./install.sh --check          report whether the installed skills match this repo
#   ./install.sh --remove         uninstall the skills (the vault is never touched)
#
# ⚠️ ~/.claude/skills/ affects EVERY Claude Code session on the machine. --remove is the
# complete undo for that part.
#
# It never edits ~/.claude/CLAUDE.md: that file is yours and shapes every session, so it
# prints the one line to add instead.
#
# Why the skills are COPIED, not symlinked: on Windows, symlinks need admin or developer
# mode, and `ln -s` under Git Bash exits 0 while silently making a copy - it reports success
# for something it did not do. A copy that is scripted and checkable (--check) beats a link
# that lies. The cost: edit a skill here and you must re-run this. The repo is the source;
# ~/.claude/skills/ is a build output.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills"
SKILLS=(vault-write reel-to-idea)

case "${1:-}" in
  vault)
    target="${2:-}"
    [ -n "$target" ] || { echo "usage: $0 vault <path>" >&2; exit 2; }
    if [ -e "$target" ]; then
      echo "refusing: $target already exists. Pick a new path - this never merges into a folder." >&2
      exit 1
    fi
    cp -r "$SRC/template" "$target"
    git -C "$target" init -q -b main
    git -C "$target" add -A
    git -C "$target" -c user.name="${GIT_AUTHOR_NAME:-vault}" -c user.email="${GIT_AUTHOR_EMAIL:-vault@localhost}" \
      commit -qm "New vault from claude-memory-vault template" 2>/dev/null || true
    abs="$(cd "$target" && pwd)"
    echo "Created a vault at $abs"
    echo
    bash "$abs/.github/scripts/check-vault.sh" | tail -1
    echo
    echo "Last step, yours: add this line to ~/.claude/CLAUDE.md so every session loads the map:"
    echo
    echo "    @$abs/00-index.md"
    echo
    echo "Then push the vault to a PRIVATE remote if you want it on more than one machine."
    ;;
  skills)
    mkdir -p "$DEST"
    for s in "${SKILLS[@]}"; do
      rm -rf "${DEST:?}/$s"
      cp -r "$SRC/skills/$s" "$DEST/$s"
      echo "installed $s -> $DEST/$s"
    done
    echo
    echo "These load in every Claude Code session on this machine. Undo: $0 --remove"
    ;;
  --check)
    rc=0
    for s in "${SKILLS[@]}"; do
      if [ ! -d "$DEST/$s" ]; then
        echo "MISSING  $s"; rc=1
      elif diff -rq "$SRC/skills/$s" "$DEST/$s" >/dev/null 2>&1; then
        echo "in sync  $s"
      else
        echo "DRIFTED  $s  (run: $0 skills)"; rc=1
      fi
    done
    exit $rc
    ;;
  --remove)
    for s in "${SKILLS[@]}"; do
      if [ -d "$DEST/$s" ]; then rm -rf "${DEST:?}/$s" && echo "removed  $s"; fi
    done
    ;;
  *)
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2
    exit 2
    ;;
esac
