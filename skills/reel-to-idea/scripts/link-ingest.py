#!/usr/bin/env python3
"""
Put links in a file, get transcripts out.

    python link-ingest.py links.txt
    python link-ingest.py --url "https://www.youtube.com/watch?v=..."

Needs `python -m pip install yt-dlp`.

THE CHEAP PATH, TAKEN FIRST
Most YouTube videos already have captions. Fetching those needs no video download and no
Whisper at all - a 4-minute video's transcript is a couple of KB and arrives in a second.
Only fall through to downloading when there are no captions.

    captions available  ->  transcript, done. No video touched.
    no captions         ->  download the video, then run media-ingest.py on it
    login-walled        ->  reported as needing a screen recording. Not guessed at.

RUN IT FROM A HOME CONNECTION
YouTube blocks many datacentre IP addresses ("Sign in to confirm you're not a bot", HTTP
429). A cloud server often cannot fetch what your laptop can.

OUTPUT
    <out>/manifest.json     what happened to every link, with a status
    <out>/<slug>/transcript.md
    <out>/<slug>/video.mp4  only when captions were unavailable

PLATFORMS AND TERMS
YouTube captions are reliable. Public Instagram and TikTok posts often work; anything
login-walled will not, and no amount of retrying changes that - those are flagged for the
screen-recording route instead of failing silently. Automated fetching is against some
platforms' terms of service. This is for reading things you already have access to.
"""
import argparse, json, re, subprocess, sys
from datetime import date
from pathlib import Path


def have_ytdlp():
    try:
        subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                       capture_output=True, check=True)
        return True
    except Exception:
        return False


def ytdlp(args, url, timeout=180):
    # "--" so a "URL" that starts with "-" is a URL, never an option.
    return subprocess.run([sys.executable, "-m", "yt_dlp", *args, "--", url],
                          capture_output=True, text=True, timeout=timeout)


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s or "").strip().lower()
    return re.sub(r"[\s_-]+", "-", s)[:60].strip("-") or "untitled"


def parse_links(text):
    """One URL per line. A line starting with # is a comment, and so is ` # ...` after a URL.
    A bare # inside a URL is NOT a comment: https://youtu.be/x#t=30 keeps its fragment."""
    urls = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if line.startswith(("http://", "https://")):
            urls.append(line)
    return urls


def platform_of(url):
    u = url.lower()
    for name in ("youtube.com", "youtu.be"):
        if name in u:
            return "youtube"
    for name in ("instagram.com", "tiktok.com", "twitter.com", "x.com"):
        if name in u:
            return name.split(".")[0]
    return "other"


def probe(url):
    """Title and duration without downloading anything."""
    r = ytdlp(["--skip-download", "--print", "%(title)s\t%(duration)s\t%(id)s"], url, timeout=90)
    if r.returncode != 0:
        return None, r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "probe failed"
    line = (r.stdout.strip().splitlines() or [""])[0]
    parts = line.split("\t")
    if len(parts) < 3:
        return None, "unexpected probe output"
    title, dur, vid = parts[0], parts[1], parts[2]
    try:
        dur = float(dur)
    except ValueError:
        dur = 0.0
    return {"title": title, "duration": dur, "id": vid}, None


def vtt_to_markdown(text, title, url, duration):
    """WebVTT -> the same transcript.md shape media-ingest.py writes, so whatever reads it
    next does not care which route produced it. Auto-captions repeat each line as it scrolls,
    so exact repeats are dropped."""
    segs, cur_ts, seen = [], None, set()
    for line in text.splitlines():
        line = line.strip()
        if "-->" in line:
            cur_ts = line.split("-->")[0].strip()[:8]
            continue
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or line.isdigit():
            continue
        clean = re.sub(r"<[^>]+>", "", line).strip()
        if clean and clean not in seen:
            seen.add(clean)
            segs.append((cur_ts or "00:00:00", clean))
    out = [f"# {title}", "",
           f"- **Source:** {url}",
           f"- **Duration:** {duration:.0f}s",
           "- **Transcript:** platform captions (no video downloaded, no Whisper needed)",
           "", "## Transcript", ""]
    for ts, tx in segs:
        out.append(f"**[{ts[3:]}]** {tx}")
    return "\n".join(out), len(segs)


def classify_failure(err):
    low = (err or "").lower()
    if any(k in low for k in ("login", "sign in", "private", "cookies", "not a bot", "429")):
        return "needs_screen_recording"
    # A carousel of still images is not a failure, and retrying never fixes it: there is no
    # audio to transcribe, the content is entirely in the images.
    if "no video formats" in low:
        return "image_post"
    return "failed"


def handle(url, outdir, langs):
    plat = platform_of(url)
    meta, err = probe(url)
    if meta is None:
        status = classify_failure(err)
        reason = ("carousel of images, no video - screenshot the slides instead"
                  if status == "image_post" else err)
        return {"url": url, "platform": plat, "status": status, "reason": reason}

    # Some platforms title every post "Video by <author>", so the title alone collides and
    # one video silently overwrites another. The platform id is the unique part - and it is
    # slugified too, because it becomes a folder name.
    d = outdir / f'{slugify(meta["title"])}-{slugify(meta["id"])}'
    d.mkdir(parents=True, exist_ok=True)

    # --- cheap path: captions ---
    ytdlp(["--skip-download", "--write-auto-sub", "--write-sub",
           "--sub-lang", langs, "--sub-format", "vtt",
           "-o", str(d / "cap.%(ext)s")], url)
    vtts = sorted(d.glob("cap*.vtt"), key=lambda p: p.stat().st_size, reverse=True)
    if vtts:
        md, n = vtt_to_markdown(vtts[0].read_text(encoding="utf-8", errors="replace"),
                                meta["title"], url, meta["duration"])
        (d / "transcript.md").write_text(md, encoding="utf-8")
        for v in vtts:
            v.unlink()
        return {"url": url, "platform": plat, "status": "captions",
                "title": meta["title"], "duration": meta["duration"],
                "dir": str(d), "segments": n}

    # --- fallback: download the video for media-ingest.py ---
    r = ytdlp(["-f", "mp4/best[height<=1080]", "-o", str(d / "video.%(ext)s")], url, timeout=600)
    vids = list(d.glob("video.*"))
    if r.returncode != 0 or not vids:
        return {"url": url, "platform": plat, "status": "needs_screen_recording",
                "title": meta["title"],
                "reason": (r.stderr.strip().splitlines() or ["download failed"])[-1]}
    return {"url": url, "platform": plat, "status": "downloaded",
            "title": meta["title"], "duration": meta["duration"],
            "dir": str(d), "video": str(vids[0]),
            "next": "python media-ingest.py \"%s\"" % vids[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("linkfile", nargs="?", help="text file, one URL per line, # for comments")
    ap.add_argument("--url", action="append", default=[])
    # Not a constant on purpose. With a fixed default, a second batch run without --out
    # wrote its manifest.json straight over the first one's - no video was lost, but the
    # only record of which links had been login-walled was, and the run printed OK. A dated
    # folder per run, and --force as the only way to overwrite a manifest.
    ap.add_argument("--out", default=None,
                    help="output dir (default: ~/media-in/<linkfile name>-<today>)")
    ap.add_argument("--langs", default="en.*",
                    help="caption languages for yt-dlp, e.g. 'en.*,pt.*' (default: en.*)")
    ap.add_argument("--force", action="store_true",
                    help="allow overwriting an existing manifest.json")
    a = ap.parse_args()

    urls = list(a.url)
    if a.linkfile:
        urls += parse_links(Path(a.linkfile).read_text(encoding="utf-8"))
    if not urls:
        sys.exit("no URLs given")
    if not have_ytdlp():
        sys.exit("yt-dlp not installed. Run: python -m pip install yt-dlp")

    if a.out:
        out = Path(a.out).expanduser()
    else:
        stem = Path(a.linkfile).stem if a.linkfile else "links"
        out = Path.home() / "media-in" / ("%s-%s" % (stem, date.today().isoformat()))
    out.mkdir(parents=True, exist_ok=True)

    # Refuse before downloading anything, not after. The manifest is the only record of
    # what a batch CONTAINED; the videos alone do not carry that.
    existing = out / "manifest.json"
    if existing.is_file() and not a.force:
        sys.exit("refusing to overwrite %s\n"
                 "That file is the record of a previous run. Pass --out <dir> for a new\n"
                 "batch, or --force if you really mean to replace it." % existing)
    print("  writing to %s" % out)
    results = []
    for i, u in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {u[:70]}")
        try:
            res = handle(u, out, a.langs)
        except subprocess.TimeoutExpired:
            res = {"url": u, "status": "failed", "reason": "timed out"}
        results.append(res)
        mark = {"captions": "OK  captions", "downloaded": "OK  downloaded",
                "needs_screen_recording": "->  screen-record this one",
                "image_post": "->  image carousel, screenshot it",
                "failed": "!!  failed"}.get(res["status"], res["status"])
        print(f"      {mark}" + (f" - {res.get('title','')[:50]}" if res.get("title") else ""))
        if res.get("reason"):
            print(f"      {res['reason'][:100]}")

    (out / "manifest.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    by = {}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"\n  {out}/manifest.json")
    for k, v in sorted(by.items()):
        print(f"    {k:24} {v}")


if __name__ == "__main__":
    main()
