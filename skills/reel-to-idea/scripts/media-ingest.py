#!/usr/bin/env python3
"""
Turn a video into something an agent can actually read: a transcript and a handful of frames.

    python media-ingest.py <video> [--out DIR] [--frames N] [--model SIZE]

Needs ffmpeg/ffprobe on PATH, and `pip install faster-whisper` for the speech. A video with
no audio track needs only ffmpeg.

WHY A SCRIPT AND NOT AN AGENT
Extracting audio, transcribing it and sampling frames is deterministic work with an exactly
correct answer. Agents are bad at that and good at the step after: deciding what the content
MEANS. So this script does the mechanical half and stops. The reel-to-idea skill reads its
output and writes the note.

WHY FILES AND NOT URLS
Some platforms are login-walled, and scraping them is fragile and against their terms. Save
the video (or screen-record it), drop the file in, and this keeps working with nothing to
break. For public links, link-ingest.py tries captions first.

OUTPUT
    <out>/<name>/
        transcript.md    what was said, with timestamps
        frames/          evenly sampled stills the agent can look at
        meta.json        duration, resolution, model used, language detected
"""
import argparse, json, subprocess, sys, shutil
from pathlib import Path


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        # ffmpeg's own message, not a bare CalledProcessError - it is the only useful part.
        sys.exit("%s failed:\n%s" % (cmd[0], (p.stderr or p.stdout).strip()[-800:]))
    return p


def probe(video):
    out = run(["ffprobe", "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", str(video)]).stdout
    d = json.loads(out)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in d.get("streams", []))
    return {
        "duration": float(d.get("format", {}).get("duration", 0) or 0),
        "width": v.get("width"), "height": v.get("height"),
        "fps": v.get("r_frame_rate"), "has_audio": has_audio,
        "size_bytes": int(d.get("format", {}).get("size", 0) or 0),
    }


def frame_times(duration, n):
    """Evenly spaced, skipping the very first and last frames - openers and end cards are
    usually a logo or a black frame and tell you nothing."""
    return [duration * (i + 1) / (n + 1) for i in range(n)]


def extract_audio(video, wav):
    # 16 kHz mono is what Whisper wants; anything more is wasted work.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(wav)])


def extract_frames(video, outdir, n, duration):
    outdir.mkdir(parents=True, exist_ok=True)
    for i, t in enumerate(frame_times(duration, n)):
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", "scale=768:-1",
             str(outdir / f"frame_{i+1:02d}_at_{t:.0f}s.jpg")])


def transcribe(wav, model_size):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("This video has speech, and transcribing it needs faster-whisper:\n"
                 "    python -m pip install faster-whisper\n"
                 "(The frames were already extracted.)")
    # int8 on CPU: roughly 4x faster than float32, with negligible quality loss at this size.
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(wav), beam_size=5, vad_filter=True)
    segs = [(s.start, s.end, s.text.strip()) for s in segments]
    return segs, info.language, info.language_probability


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default=str(Path.home() / "media-in"))
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--model", default="small",
                    help="tiny|base|small|medium. small is the CPU sweet spot.")
    a = ap.parse_args()

    video = Path(a.video).expanduser().resolve()
    if not video.is_file():
        sys.exit(f"not a file: {video}")
    if a.frames < 1:
        sys.exit("--frames must be at least 1")
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not on PATH - install ffmpeg first")

    out = Path(a.out).expanduser() / video.stem
    out.mkdir(parents=True, exist_ok=True)

    meta = probe(video)
    print(f"  {video.name}: {meta['duration']:.1f}s, "
          f"{meta['width']}x{meta['height']}, audio={meta['has_audio']}")

    print(f"  sampling {a.frames} frames...")
    extract_frames(video, out / "frames", a.frames, meta["duration"])

    segs, lang, prob = [], None, 0.0
    if meta["has_audio"]:
        wav = out / "audio.wav"
        print("  extracting audio...")
        extract_audio(video, wav)
        print(f"  transcribing with whisper-{a.model} (cpu/int8)...")
        try:
            segs, lang, prob = transcribe(wav, a.model)
        finally:
            wav.unlink(missing_ok=True)      # the transcript is the artifact; the wav is not
    else:
        print("  no audio track - frames only")

    lines = [f"# {video.stem}", ""]
    lines.append(f"- **Duration:** {meta['duration']:.1f}s")
    lines.append(f"- **Resolution:** {meta['width']}x{meta['height']}")
    if lang:
        lines.append(f"- **Language detected:** {lang} ({prob:.0%} confidence)")
    lines.append(f"- **Frames:** `frames/` ({a.frames} stills)")
    lines.append("")
    lines.append("## Transcript")
    lines.append("")
    if segs:
        for st, en, tx in segs:
            if tx:
                lines.append(f"**[{int(st//60)}:{int(st%60):02d}]** {tx}")
    else:
        lines.append("_No speech detected._")
    (out / "transcript.md").write_text("\n".join(lines), encoding="utf-8")

    meta.update({"model": a.model, "language": lang, "language_probability": prob,
                 "segments": len(segs), "frames": a.frames})
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    words = sum(len(t.split()) for _, _, t in segs)
    print(f"\n  -> {out}")
    print(f"     transcript.md ({len(segs)} segments, ~{words} words)")
    print(f"     frames/ ({a.frames} stills)")


if __name__ == "__main__":
    main()
