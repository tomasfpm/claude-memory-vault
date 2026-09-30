---
name: reel-to-idea
description: "Turn a saved video - an Instagram reel, a TikTok, a YouTube clip, a screen recording - or a list of video links into a structured idea note in the knowledge vault's 60-inbox, then file it. Use whenever the user drops a video file or links and wants them watched, transcribed, summarised, or turned into something actionable, or mentions a reel they saved."
---

# reel-to-idea

Many good ideas arrive as 30-second videos, and most saved videos are never opened again. This
turns one into a note that can be acted on weeks later.

**Split of labour, and it matters:** a script does the mechanical extraction, you do the
interpretation. Do not try to reason about a video file directly — run the script first.
Scripts are good at work with one right answer; you are good at deciding what it means.

The scripts live next to this file: `~/.claude/skills/reel-to-idea/scripts/`.

## 0. Where the video comes from

| Route | Use when | How |
|---|---|---|
| **Links** | YouTube, public Instagram/TikTok | `python ~/.claude/skills/reel-to-idea/scripts/link-ingest.py links.txt` |
| **A file** | anything login-walled | the user saves or screen-records it, and gives you the path |

`link-ingest.py` takes the cheap path first: **if the platform already has captions, no video
is downloaded and Whisper never runs.** A transcript arrives in about a second. It falls back to
downloading only when there are none, and reports anything login-walled as needing a screen
recording rather than failing silently. Run it from a home connection: YouTube blocks many
cloud servers.

## 1. Extract

```bash
python ~/.claude/skills/reel-to-idea/scripts/media-ingest.py <video> [--frames 8] [--model small]
```

Needs `ffmpeg`, and `faster-whisper` if the video has speech. It writes `~/media-in/<name>/`:

| File | What it is |
|---|---|
| `transcript.md` | timestamped speech, with the detected language |
| `frames/` | evenly sampled stills — **look at these; they are images you can read** |
| `meta.json` | duration, resolution, model, segment count |

**Models:** `small` is the sweet spot on a CPU. Use `medium` only if `small` produces obvious
nonsense; it is roughly 3× slower. `tiny` or `base` for a quick triage of a long video.

If the video is over ~10 minutes, say so and ask before transcribing — it is a different cost
from a 30-second reel.

## 2. Read both halves

**Read the transcript AND look at the frames.** Short videos are often visual — the transcript
alone misses the app being demonstrated, the diagram, the code on screen. A frame alone misses
the argument. Neither is enough.

If the transcript says "no speech detected", the video is visual-only. That is normal for demos;
work entirely from the frames.

## 3. Write the note

Write to `60-inbox/` in the vault — **the inbox, never straight into a topic folder.** It is an
idea until the user decides otherwise. Filename: `idea-<short-slug>.md`.

```markdown
---
id: idea-<short-slug>
type: reference
status: active
updated: YYYY-MM-DD
tags: [inbox, idea]
---

# <what it is, in the user's words, not the creator's>

**Source:** <file or URL> · <duration> · captured YYYY-MM-DD

## The claim
One paragraph. What is this actually proposing? Strip the hype — short videos overstate.

## What is concretely shown
Only what is genuinely on screen or said. Tools, commands, numbers, names.

## Why it might matter here
Tie it to something real: a project, an open problem, something in the vault. If it connects
to nothing, say that — it is a valid conclusion.

## What it would take
The honest cost. What would need installing, learning, or paying for.

## Verdict
TWO verdicts, never one. They are different questions and they often disagree.

**The idea:** worth trying / worth knowing / worth researching / skip.
**The method the video showed:** trust it / do not trust it / it never actually showed one.

Justify each in a sentence. A distrusted method does not demote the idea — see §4.
```

## 4. The rules that make this useful rather than noise

- **⚠️ Judge the idea separately from the video's execution. This is the rule that gets
  broken.** A short video is an advert made by someone selling attention; it is a **pointer to
  a topic**, not a design document. The sloppy, unmeasured or plain wrong *method* it shows is
  a finding about the video — not a reason to bin the *idea*. If the idea is interesting and the
  execution is not, the idea goes forward as something to research properly: find the real
  repos, the real docs, the people actually doing it.
- **Be sceptical of the method.** If a claim is unmeasured — "10x faster", "replaces your whole
  workflow" — say so explicitly. A note that repeats marketing uncritically is worse than no note.
- **Say when it duplicates something already in the vault.** Check before writing. An idea that
  was already rejected should link to the decision that rejected it.
- **`skip` is for the idea being wrong** — already decided against, a duplicate, or against a
  standing decision. It is **not** for "the video was bad". If your reason is about the
  presenter, the production or the proof, the verdict is `worth researching`.
- **Never invent detail the video did not contain.** If it names a tool but never shows it
  working, the note says exactly that.

## 5. ⚠️ File it — an inbox that only fills is a graveyard

A note in `60-inbox/` is not finished work. Every idea ends up in exactly one of these places,
decided **in the same session that wrote it**:

| Verdict | Where it goes |
|---|---|
| **Worth trying** | the user's backlog or the relevant project note, written as a task with a success criterion — not "look at X" |
| **Worth knowing** | merged into the project or stack note it affects. **Merged, not appended**: edit at the source so the note reads as one coherent thing |
| **Worth researching** | the backlog as a **research** task: "find out how X is actually done, then decide". Its success criterion is a decision, and it names what the video failed to prove |
| **Skip** | say so in the note and leave it in the inbox as a tombstone, so the same idea is not evaluated again in three months. Link the decision that rejects it |

Then **delete the inbox note** if its content moved somewhere else — a copy in two places is two
things to keep in sync. Keep only tombstones.

**Say which one you did.** "Written to the inbox" is not a finished report; "merged into the
project note as two next actions" is.

## 6. Finish

Commit with the `vault-write` skill's rules: pull first, run the check, commit, push. Then give
the verdict in one line, not the whole note.

## 7. Boundaries

- Prefer files to scraping. Login-walled platforms are fragile to scrape and it is against their
  terms; save the video and use the file.
- Never delete the user's source video.
