"""
diagnose.py
Tells you whether final_video.srt is really synced to the audio, and what is
on screen at any moment.

The length-based fallback lays cues end to end with no gaps, because it just
divides the runtime by text length. Real word timings leave silence between
cues wherever the speaker pauses, so the absence of any gap is proof that the
timings were guessed rather than measured from the audio.

Usage:
    python diagnose.py
    python diagnose.py 56 120 300      # what is on screen at these seconds
"""
import json
import subprocess
import sys
from pathlib import Path

SRT = Path("final_video.srt")
REPORT = Path(".caption_report.json")
AUDIO = "output.mp3"
DEFAULT_PROBES = [5, 56, 120, 300, 480, 570]


def parse_srt(path: Path):
    cues = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3:
            continue
        start, _, end = lines[1].partition(" --> ")
        cues.append((_secs(start), _secs(end), " ".join(lines[2:])))
    return cues


def _secs(stamp: str) -> float:
    h, m, rest = stamp.strip().split(":")
    s, _, ms = rest.replace(",", ".").partition(".")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def _audio_seconds(path: str):
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            text=True,
        )
        return float(out.strip())
    except Exception:
        return None


def _pearson(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if not SRT.exists():
        print(f"{SRT} is missing - run the pipeline first")
        return

    cues = parse_srt(SRT)
    audio = _audio_seconds(AUDIO)
    print(f"{SRT}: {len(cues)} cues, first starts {cues[0][0]:.2f}s, last ends {cues[-1][1]:.2f}s")
    if audio:
        print(f"{AUDIO}: {audio:.2f}s  (gap at end: {audio - cues[-1][1]:+.2f}s)")

    chars = [len(c[2]) for c in cues]
    durs = [c[1] - c[0] for c in cues]
    gaps = [cues[i + 1][0] - cues[i][1] for i in range(len(cues) - 1)]
    silent = sum(1 for g in gaps if g > 0.1)
    share = silent / len(gaps) if gaps else 0.0

    print(f"\npauses between cues: {silent} of {len(gaps)} ({share:.0%}) have a real gap")
    print(f"correlation between cue length and duration: r = {_pearson(chars, durs):.4f}")
    if share < 0.05:
        print("  VERDICT: timings were GUESSED from text length, not the audio.")
        print("  Cues run end to end with no silence, which only the fallback does.")
        print("  Whisper alignment did not run or it failed - check the pipeline log.")
    else:
        print("  VERDICT: cues start and stop on real speech boundaries,")
        print("  which is what word-level timings from the audio look like.")

    if REPORT.exists():
        data = json.loads(REPORT.read_text(encoding="utf-8"))
        print("\nwhat the last caption run recorded:")
        for key in ("estimated", "model", "anchored", "mean_word_confidence", "cues"):
            if key in data:
                value = data[key]
                if isinstance(value, float):
                    value = f"{value:.3f}"
                print(f"  {key}: {value}")
    else:
        print(f"\n{REPORT} not found - rerun the caption step to record one")

    probes = [float(a) for a in sys.argv[1:]] or DEFAULT_PROBES
    print("\nplay the video at each time below and check the words match:")
    for t in probes:
        hit = next(((s, e, txt) for s, e, txt in cues if s <= t <= e), None)
        if hit is None:
            hit = min(cues, key=lambda c: abs(c[0] - t))
            print(f"  {t:6.1f}s  (no cue; nearest starts {hit[0]:.1f}s)  {hit[2]}")
        else:
            print(f"  {t:6.1f}s  [{hit[0]:.1f}-{hit[1]:.1f}]  {hit[2]}")


if __name__ == "__main__":
    main()
