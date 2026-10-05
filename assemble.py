import random
import subprocess
from pathlib import Path

SRT_PATH = Path("final_video.srt")


def _duration(path: str) -> float:
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        text=True,
    )
    return float(out.strip())


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _weight(caption: str) -> float:
    w = len(caption)
    if caption.rstrip().endswith((".", "!", "?")):
        w += 12
    elif caption.rstrip().endswith((",", ":", ";")):
        w += 5
    return w


def _write_srt(captions, duration, path: Path) -> None:
    """Length-weighted fallback. Run make_srt.py for real word-level timings."""
    weights = [_weight(c) for c in captions]
    total = sum(weights) or 1.0
    blocks = []
    cursor = 0.0
    for i, caption in enumerate(captions, start=1):
        span = duration * (weights[i - 1] / total)
        blocks.append(f"{i}\n{_ts(cursor)} --> {_ts(cursor + span)}\n{caption}\n")
        cursor += span
    path.write_text("\n".join(blocks), encoding="utf-8")


def _subtitle_font(captions) -> str:
    """libass picks a Latin font by default, which renders Devanagari as boxes."""
    text = "".join(captions)
    if any("\u0900" <= ch <= "\u097F" for ch in text):
        return "Noto Sans Devanagari"
    return "DejaVu Sans"


def _clip_order(clips, audio_dur, seed=7):
    """Shuffle in passes so the same clip never plays twice in a row."""
    rng = random.Random(seed)
    order = []
    covered = 0.0
    last = None
    while covered < audio_dur + 1 and len(order) < 400:
        batch = clips[:]
        rng.shuffle(batch)
        if last is not None and len(batch) > 1 and batch[0] == last:
            batch[0], batch[-1] = batch[-1], batch[0]
        for clip in batch:
            order.append(clip)
            covered += _duration(str(clip))
            last = clip
            if covered >= audio_dur + 1:
                break
    return order


def assemble_video(
    audio_path: str,
    clips_folder: str = "clips",
    captions=None,
    output_path: str = "final_video.mp4",
):
    captions = captions or []
    audio_dur = _duration(audio_path)
    clips = sorted(
        p
        for p in Path(clips_folder).iterdir()
        if p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}
    )
    if not clips:
        raise SystemExit(f"No clips found in {clips_folder}")

    if SRT_PATH.exists() and SRT_PATH.stat().st_size > 0:
        print(f"   using existing {SRT_PATH}")
    else:
        _write_srt(captions, audio_dur, SRT_PATH)

    concat_list = Path("_concat.txt")
    entries = [f"file '{c.resolve().as_posix()}'" for c in _clip_order(clips, audio_dur)]
    concat_list.write_text("\n".join(entries) + "\n", encoding="utf-8")

    font = _subtitle_font(captions)
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", audio_path,
        "-map", "0:v:0", "-map", "1:a:0",
        "-vf",
        "scale=1920:1080:force_original_aspect_ratio=decrease,"
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p,"
        f"subtitles={SRT_PATH.name}:force_style="
        f"'FontName={font},FontSize=22,Outline=2,Shadow=0,MarginV=60,Alignment=2'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        output_path,
    ]
    subprocess.check_call(cmd)
    return output_path
