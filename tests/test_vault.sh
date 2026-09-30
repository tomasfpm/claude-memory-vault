#!/usr/bin/env bash
# Tests for install.sh and the vault's check-vault.sh.
#
#   bash tests/test_vault.sh
#
# Everything happens in a temp folder, with CLAUDE_CONFIG_DIR pointed at it - so the skills
# are "installed" into a throwaway ~/.claude, never the real one.

set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
export CLAUDE_CONFIG_DIR="$T/claude"
pass=0; fail=0

check() {  # check <name> <expected-exit> <actual-exit>
  if [ "$2" = "$3" ]; then pass=$((pass+1)); printf '  ok    %s\n' "$1"
  else fail=$((fail+1)); printf '  FAIL  %s (expected exit %s, got %s)\n' "$1" "$2" "$3"; fi
}
has() {    # has <name> <text> <needle>
  if printf '%s' "$2" | grep -qF -- "$3"; then pass=$((pass+1)); printf '  ok    %s\n' "$1"
  else fail=$((fail+1)); printf '  FAIL  %s (output lacks: %s)\n' "$1" "$3"; fi
}
lacks() {  # lacks <name> <text> <needle>
  if printf '%s' "$2" | grep -qF -- "$3"; then fail=$((fail+1)); printf '  FAIL  %s (output contains: %s)\n' "$1" "$3"
  else pass=$((pass+1)); printf '  ok    %s\n' "$1"; fi
}
note() {   # note <path> <id> [extra frontmatter]
  mkdir -p "$(dirname "$1")"
  printf -- '---\nid: %s\ntype: lesson\nstatus: active\nupdated: 2026-01-01\n%s---\n\n# t\n' "$2" "${3:-}" > "$1"
}
fresh() {  # a new vault from the template, at $V
  V="$T/v$RANDOM$RANDOM"; bash "$HERE/install.sh" vault "$V" >/dev/null 2>&1
}
cv() { bash "$V/.github/scripts/check-vault.sh" 2>&1; }

echo "install.sh vault"
fresh; check "creates a vault" 0 $?
[ -d "$V/.git" ]; check "  ...as a git repo" 0 $?
out="$(bash "$HERE/install.sh" vault "$V" 2>&1)"; check "refuses an existing path" 1 $?
out="$(cv)"; check "a fresh vault passes its own check" 0 $?
has "  ...with no warnings" "$out" "0 warning(s)"

echo "check-vault.sh: what blocks"
fresh; note "$V/40-lessons/right-name.md" "wrong-name"
out="$(cv)"; check "id != filename blocks" 1 $?
has "  ...and says why" "$out" "unreachable"
fresh; printf -- '---\ntype: lesson\n---\n' > "$V/40-lessons/no-id.md"
cv >/dev/null; check "missing id blocks" 1 $?
fresh; tok="ghp_$(printf 'a%.0s' $(seq 36))"
note "$V/10-environment/oops.md" "oops"; printf 'token: %s\n' "$tok" >> "$V/10-environment/oops.md"
out="$(cv)"; check "a credential-shaped string blocks" 1 $?
has "  ...names the file and line" "$out" "oops.md:"
lacks "  ...but never prints the secret itself" "$out" "$tok"

echo "check-vault.sh: what only warns"
fresh; note "$V/stray.md" "stray"
out="$(cv)"; check "a note outside the numbered folders warns, not blocks" 0 $?
has "  ...and is still checked (the include-filter bug)" "$out" "stray.md is a note but sits outside"
fresh; note "$V/40-lessons/a.md" "a"; printf 'see [[not-written-yet]]\n' >> "$V/40-lessons/a.md"
out="$(cv)"; check "a forward link warns, not blocks" 0 $?
has "  ...and names it" "$out" "[[not-written-yet]]"
fresh; note "$V/40-lessons/b.md" "b"; printf 'write `[[example]]` like this\n' >> "$V/40-lessons/b.md"
out="$(cv)"; lacks "a link inside backticks is an example, not a link" "$out" "[[example]]"
fresh; printf -- '---\nid: c\ntype: lesson\nstatus: active\nupdated: last week\n---\n' > "$V/40-lessons/c.md"
out="$(cv)"; has "a relative date warns" "$out" "not an absolute YYYY-MM-DD date"
fresh; printf -- '- a pointer line that has somehow turned into a whole paragraph of prose, explaining things at length, which belongs in a note and not in the map\n' >> "$V/00-index.md"
out="$(cv)"; has "a paragraph in the index warns" "$out" "prose, not a pointer"

echo "install.sh skills"
bash "$HERE/install.sh" skills >/dev/null; check "installs" 0 $?
[ -f "$CLAUDE_CONFIG_DIR/skills/reel-to-idea/scripts/media-ingest.py" ]; check "  ...the scripts travel with the skill" 0 $?
bash "$HERE/install.sh" --check >/dev/null; check "--check: in sync" 0 $?
echo "local edit" >> "$CLAUDE_CONFIG_DIR/skills/vault-write/SKILL.md"
bash "$HERE/install.sh" --check >/dev/null; check "--check: notices drift" 1 $?
mkdir -p "$CLAUDE_CONFIG_DIR/skills/someone-elses"
bash "$HERE/install.sh" --remove >/dev/null; check "--remove" 0 $?
[ ! -e "$CLAUDE_CONFIG_DIR/skills/vault-write" ] && [ ! -e "$CLAUDE_CONFIG_DIR/skills/reel-to-idea" ]
check "  ...removes both" 0 $?
[ -d "$CLAUDE_CONFIG_DIR/skills/someone-elses" ]; check "  ...and nothing else" 0 $?

echo
echo "$pass passed, $fail failed"
[ "$fail" -eq 0 ]
