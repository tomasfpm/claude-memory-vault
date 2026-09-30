#!/usr/bin/env bash
# Vault integrity check.
#
# Runs in CI on every push, and locally with:  bash .github/scripts/check-vault.sh
# One source of truth for both, so the two cannot drift. The vault-write skill runs this
# exact script rather than carrying its own copy of the checks: two copies of a check drift
# apart, and each grows its own blind spot.
#
# FAIL (exit 1) only for things that are unambiguously broken and silent:
#   - a note whose `id` != its filename  -> every [[link]] to it breaks, with no error
#   - a credential-shaped string          -> git history is permanent
#
# WARN (exit 0) for things that need a human to judge:
#   - forward links to notes that do not exist yet   (allowed by design)
#   - missing frontmatter fields
#   - notes outside the numbered folders
#   - 00-index.md over its size budget
#
# A check that cries wolf gets ignored, so the FAIL list is deliberately short.

set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 2

fails=0
warns=0
notes=0

if [ -t 1 ]; then
  red() { printf '\033[31m%s\033[0m\n' "$*"; }
  ylw() { printf '\033[33m%s\033[0m\n' "$*"; }
  grn() { printf '\033[32m%s\033[0m\n' "$*"; }
else
  red() { printf '%s\n' "$*"; }; ylw() { printf '%s\n' "$*"; }; grn() { printf '%s\n' "$*"; }
fi

note_files() {
  # Every .md is a note EXCEPT the map, the repo docs and the templates.
  #
  # Written as an EXCLUDE list on purpose. An earlier version filtered *in* - "only files
  # inside a numbered folder" - so a note at the vault root was never checked at all. One
  # sat there as a 0-byte file with no `id:` for its whole life, four notes linked to it,
  # and CI stayed green. 70 of 76 notes were checked and the summary still said PASSED.
  #
  # An include-filter goes quiet when something lands outside it; an exclude-filter gets
  # noisy when something new appears. Prefer the one that gets noisier.
  find . -type f -name '*.md' \
    -not -path './.git/*' -not -path './.github/*' -not -path './.obsidian/*' \
    -not -name '_template.md' \
    -not -name '00-index.md' -not -name 'CLAUDE.md' \
    -not -name 'README.md'   -not -name 'SETUP.md' \
    | sort
}

# Wiki links that Obsidian would actually resolve. Anything inside `backticks` is a syntax
# example in prose, not a link - Obsidian does not render links in inline code, so neither
# should this check. Missing that produced 3 false positives on the first run.
real_links() {
  grep -rh --include='*.md' \
    --exclude-dir=.git --exclude-dir=.github --exclude-dir=.obsidian '' . 2>/dev/null \
    | sed 's/`[^`]*`//g' \
    | grep -oE '\[\[[A-Za-z0-9_-]+\]\]' | tr -d '[]' | sort -u
}

echo "== 1. id must equal filename =="
while IFS= read -r f; do
  [ -z "$f" ] && continue
  notes=$((notes + 1))
  want="$(basename "$f" .md)"
  got="$(grep -m1 '^id:' "$f" | sed 's/^id:[[:space:]]*//; s/[[:space:]]*$//')"
  if [ -z "$got" ]; then
    red "FAIL  $f — no 'id:' in frontmatter"
    fails=$((fails + 1))
  elif [ "$want" != "$got" ]; then
    red "FAIL  $f — id='$got' but filename='$want'"
    red "        Obsidian resolves [[links]] by FILENAME. This note is unreachable."
    fails=$((fails + 1))
  fi
done < <(note_files)
[ "$fails" -eq 0 ] && grn "      ok — $notes notes, every id matches its filename"

echo
echo "== 2. no credential-shaped strings =="
# Shape-based, not word-based: a vault discusses tokens constantly in prose.
patterns='ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,}'
patterns="$patterns"'|sk-ant-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9]{32,}|AKIA[0-9A-Z]{16}'
patterns="$patterns"'|-----BEGIN [A-Z ]*PRIVATE KEY-----|[0-9]{8,10}:[A-Za-z0-9_-]{35}'
hits="$(grep -rInE "$patterns" . \
        --include='*.md' --include='*.json' --include='*.yml' --include='*.yaml' --include='*.txt' \
        --exclude-dir=.git --exclude-dir=.github --exclude-dir=.obsidian 2>/dev/null || true)"
if [ -n "$hits" ]; then
  # Report where, never what: printing the match would put the secret in the CI log too.
  red "FAIL  credential-shaped string(s) found at:"
  echo "$hits" | cut -d: -f1,2 | sed 's/^/        /'
  red "        git history is permanent — deleting it in a later commit does NOT remove it."
  red "        Rotate the credential first, then rewrite history."
  fails=$((fails + 1))
else
  grn "      ok — nothing matching a credential shape"
fi

echo
echo "== 3. frontmatter completeness (warn) =="
while IFS= read -r f; do
  [ -z "$f" ] && continue
  for field in type status updated; do
    grep -qm1 "^${field}:" "$f" || { ylw "WARN  $f — missing '${field}:'"; warns=$((warns + 1)); }
  done
  d="$(grep -m1 '^updated:' "$f" | sed 's/^updated:[[:space:]]*//; s/[[:space:]]*$//')"
  if [ -n "$d" ] && ! printf '%s' "$d" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
    ylw "WARN  $f — 'updated: $d' is not an absolute YYYY-MM-DD date"
    warns=$((warns + 1))
  fi
done < <(note_files)

echo
echo "== 4. forward links (warn — allowed by design) =="
dangling=0
while IFS= read -r link; do
  [ -z "$link" ] && continue
  if ! find . -name "${link}.md" -not -path './.git/*' | grep -q .; then
    ylw "WARN  [[${link}]] has no note yet"
    dangling=$((dangling + 1)); warns=$((warns + 1))
  fi
done < <(real_links)
[ "$dangling" -eq 0 ] && grn "      ok — every [[link]] resolves"

echo
echo "== 4b. notes live in numbered folders (warn) =="
stray=0
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in
    ./[0-9][0-9]-*) ;;
    *) ylw "WARN  $f is a note but sits outside the numbered folders"
       ylw "        Root notes get missed by every tool that assumes the NN-folder layout."
       stray=$((stray + 1)); warns=$((warns + 1)) ;;
  esac
done < <(note_files)
[ "$stray" -eq 0 ] && grn "      ok - every note is filed"

echo
echo "== 5. index: is it still a map? (warn) =="
# Not a cost limit. Measured over a real week of heavy use: a 16 KB index cost under 1% of
# usage. The reason to keep it small is legibility. The index is a MAP - one line per
# thing, pointing at the note that holds the detail - and a map you skim instead of read
# has stopped working.
#
# So check the two things that actually indicate rot:
#   1. Size RELATIVE TO NOTE COUNT. The budget grows as the vault does.
#   2. Long lines - the real symptom of content creeping into the map.
if [ -f 00-index.md ]; then
  bytes="$(wc -c < 00-index.md | tr -d ' ')"
  budget=$(( 1500 + 70 * notes ))
  if [ "$bytes" -gt "$budget" ]; then
    ylw "WARN  00-index.md is ${bytes} bytes; budget for ${notes} notes is ${budget}."
    ylw "        Either it holds content that belongs in a note, or a section has outgrown"
    ylw "        the index and wants its own sub-index (like 40-lessons/00-lessons-index.md)."
    warns=$((warns + 1))
  else
    grn "      ok — ${bytes} bytes, budget ${budget} for ${notes} notes"
  fi

  long=$(awk 'length > 130 && !/^\|/ {c++} END {print c+0}' 00-index.md)
  if [ "$long" -gt 0 ]; then
    ylw "WARN  ${long} line(s) over 130 chars in 00-index.md — that is prose, not a pointer."
    awk 'length > 130 && !/^\|/ {printf "        L%d: %.70s...\n", NR, $0}' 00-index.md
    warns=$((warns + 1))
  else
    grn "      ok — every line is a pointer, not a paragraph"
  fi
fi

echo
echo "────────────────────────────────────────────"
if [ "$fails" -gt 0 ]; then
  red "FAILED — $fails blocking problem(s), $warns warning(s)"
  exit 1
fi
grn "PASSED — $notes notes checked, 0 blocking problems, $warns warning(s)"
exit 0
