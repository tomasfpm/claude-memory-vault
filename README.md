# claude-memory-vault

Long-term memory for Claude Code, made of plain Markdown files in a git repo. A starter vault,
a CI check that catches its silent failures, and two skills: one that writes knowledge back at
the end of a session, and one that turns saved videos into notes you'll actually use.

## In plain words

Every Claude Code session starts with a blank memory. It doesn't know what you decided last
week, why, or what went wrong the last time you tried something. You end up explaining the
same things again, or worse, it confidently repeats a mistake you already paid for.

The fix here is deliberately boring: **a notebook.** A folder of short notes, one fact each,
kept in git so every machine has the same copy. Each session reads one small page, the
**index**, which works like the contents page of a book. It then opens only the notes that
matter for the task at hand. At the end of a session, anything worth keeping gets written back.

No database, no memory server, nothing running in the background. You can read every memory,
fix any wrong one by hand, and see exactly what changed and when.

## How it works

Claude Code reads `~/.claude/CLAUDE.md` at the start of every session, and that file can
**import** another one with a line like `@/path/to/file.md`. So:

```text
~/.claude/CLAUDE.md
   └── @~/brain/00-index.md        ← the map, loaded into every session
          ├── [[0001-some-decision]]    ← opened only when relevant
          ├── [[00-lessons-index]]      ← what went wrong before, grouped by kind
          └── ...
```

The index is small on purpose. It's a map, one line per thing, pointing at the note that holds
the detail. The size limit isn't about cost: on one heavy week of real use, a 16 KB index cost
under 1% of total usage. It's about **legibility**: a map you skim instead of read has stopped
working. So the CI check measures the index against the number of notes, and flags lines long
enough to be paragraphs.

## What's in it

| | What it is |
|---|---|
| `template/` | an empty vault: numbered folders, a template for each kind of note, the rules (`CLAUDE.md`), one example decision and one example lesson |
| `template/.github/scripts/check-vault.sh` | the integrity check, run by CI on every push and by the skill before every commit |
| `skills/vault-write/` | the end-of-session write-back: what's worth keeping, where it goes, frontmatter, index, check, commit, push |
| `skills/reel-to-idea/` | turns a saved video or a list of links into a note, then *files* it. Includes the two scripts that do the extraction |
| `install.sh` | creates a vault, and installs, checks or removes the skills |

### The folders

| Folder | Holds |
|---|---|
| `10-environment/` | machines, accounts, what runs where: facts the code can't tell you |
| `20-projects/` | one note per project: state, next actions, open questions |
| `30-decisions/` | numbered decisions with their reasons, so they don't get argued again |
| `40-lessons/` | things that went wrong and the correction each one forced |
| `50-stack/` | tools you're evaluating, and the verdict |
| `60-inbox/` | capture now, file later; a week at most |
| `70-learning/` | concepts you now understand well enough to explain |

## The four rules that matter

These are in `template/CLAUDE.md`, and the check enforces what it can.

1. **One fact per note.** If a note needs "meanwhile, separately", it's two notes.
2. **Edit at the source; never append a correction.** When a decision is reversed, the original
   note is edited and marked `superseded`. A correction written somewhere else leaves the wrong
   version looking authoritative, which is the exact failure a memory is supposed to prevent.
3. **`id` must equal the filename.** Obsidian resolves `[[links]]` by filename. A mismatch makes a
   note unreachable from every link pointing at it, with no error anywhere. The check **blocks**
   on this.
4. **Absolute dates only.** "Last week" means nothing to the session that reads it next month.

## The check

`check-vault.sh` blocks on only two things: a note whose `id` doesn't match its filename, and a
string shaped like a credential. Everything else is a warning. A check that cries wolf gets
ignored, so the blocking list is kept short.

Two details came from real failures, and the tests hold both of them:

- **It checks by *excluding*, not including.** An earlier version checked only "notes inside a
  numbered folder". A broken note at the root went unchecked for its whole life while CI said
  PASSED. That story ships as the template's example lesson.
- **When it finds a credential, it prints the file and line, never the value.** Printing the
  match would copy the secret into the CI log as well.

## The skills

**`vault-write`** is the procedure for writing knowledge back. It's a skill rather than part of
`CLAUDE.md` because it's long, easy to get subtly wrong, and only relevant at the end of a
session. Only a skill's short description sits in every session; the full procedure loads when
it's needed. It runs the same check CI runs, rather than carrying its own copy, because two
copies of one check drift apart.

**`reel-to-idea`** is for the ideas that arrive as 30-second videos. A script does the
mechanical part: captions if the platform has them, otherwise ffmpeg frames and a Whisper
transcript. Claude does the judging. Its main rule: **judge the idea separately from the
video.** A reel is an advert, not a design document. A sloppy demo is a reason to research the
idea properly, not to throw it away. It also won't leave the note sitting in the inbox. Every
idea gets filed: into the backlog, merged into a project note, or kept as a "skip" tombstone
so it isn't evaluated again.

## Quick start

```bash
git clone https://github.com/<you>/claude-memory-vault
cd claude-memory-vault
./install.sh vault ~/brain        # creates the vault, checks it, and prints one line to add
./install.sh skills               # optional: the two skills
```

Then add the printed line (`@/home/you/brain/00-index.md`) to `~/.claude/CLAUDE.md`. The
installer never edits that file itself: it shapes every session you run, so that edit is yours.

To use the vault on more than one machine, push it to a **private** remote.

⚠️ Skills in `~/.claude/skills/` load in **every** Claude Code session on the machine.
`./install.sh --remove` removes exactly the two installed here and nothing else.
`./install.sh --check` tells you if an installed copy has drifted from this repo.

For `reel-to-idea`: Python 3.8+, `ffmpeg`, `pip install faster-whisper` for speech, and
`pip install yt-dlp` for links.

## Goes well with

[claude-code-guardrails](https://github.com/tomasfpm/claude-code-guardrails) has two hooks built
for this vault. One pulls it at the start of every session. The other refuses to let a session
end while the vault has uncommitted notes. Hooks are the part that can't be forgotten, whatever
the model decides.

## What it is not

- **Not automatic.** Nothing gets remembered unless a session writes it down. The skill and the
  hooks make that the default; they can't make it happen for you.
- **Not search.** The index points at the right note. There's no semantic search, on purpose
  (see the example decision). If the vault ever outgrows the index plus `grep`, measure that
  before adding one.
- **Not a place for other people's data.** Your own learnings and code, yes. Your employer's
  data, no.

## Tests

```bash
bash tests/test_vault.sh            # 25 checks: the template, check-vault.sh, install.sh
python -m unittest discover tests   # 9 tests: both capture scripts
```

Everything runs in a temp folder, with a throwaway `~/.claude`. Nothing touches the network.
The one end-to-end video test needs `ffmpeg` and skips itself without it. GitHub Actions
installs ffmpeg, so it runs there on every push.

## Licence

MIT. See `LICENSE`.
