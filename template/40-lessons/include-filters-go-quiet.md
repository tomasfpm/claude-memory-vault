---
id: include-filters-go-quiet
type: lesson
status: active
updated: 2026-09-30
tags: [ci, checks]
---

# A check that filters IN goes quiet when something lands outside it

**Learned:** from this vault's own CI check (the example lesson that ships with the template).

The first version of `check-vault.sh` only checked "files inside a numbered folder". A note
that ended up at the vault root was therefore never checked at all. One sat there as a
**0-byte file with no `id:`** for its whole life, four notes linked to it, and CI stayed green
on every run. 70 of 76 notes were being checked, and the summary still said PASSED.

A filter that says *what to include* goes silent when something new appears outside it. A
filter that says *what to exclude* gets noisy instead — and noisy is the failure you notice.

## How to apply
- Write checks as exclude lists wherever you can.
- When a check says "all good", ask how many things it looked at, and whether that number is
  the number that exist.
