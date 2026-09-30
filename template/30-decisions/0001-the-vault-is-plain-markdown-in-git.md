---
id: 0001-the-vault-is-plain-markdown-in-git
type: decision
status: active
updated: 2026-09-30
tags: [vault, memory]
---

# 0001 — The vault is plain Markdown in git

**Decision:** Claude's long-term memory is a folder of Markdown notes in a git repo, with one
small index loaded into every session. Not a database, not a vector store, not a memory server.

**Date:** 2026-09-30 (this is the example decision that ships with the template — edit it or
replace it with your own).

## Context
Sessions need to remember what was decided and why, across days and across machines. Claude
Code already loads a `CLAUDE.md` into every session, and that file can import another file.

## Options considered
- **A memory server (MCP) or a database** — lost. It adds a running process to keep alive, and
  the memory becomes something you query rather than something you can read, diff and fix.
- **Vector search over notes** — lost, for now. It finds *similar* text, which is not the same
  as the *right* note; a small hand-kept index points at the right note directly.
- **Markdown in git** — won. Every change is a diff you can read. Two machines conflicting is a
  merge you can do by hand. It works offline, it works in Obsidian, and it survives any one
  machine being wiped.

## Consequences
- Easy: reading, correcting and reviewing memory; seeing what changed and when.
- Hard: nothing enforces the rules by itself — hence the CI check (`.github/scripts/check-vault.sh`)
  and the `vault-write` skill.
- The index must stay small enough to *skim*. It is a map; detail lives in notes.

## Revisit when
The vault is too big to navigate from the index plus a `grep`. Measure that before assuming it.
