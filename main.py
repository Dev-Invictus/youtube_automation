"""
main.py
One command for the full pipeline:

    topic/script -> audio -> synced captions -> generated B-roll
    -> thumbnail -> video -> optional private YouTube upload

Usage:
    python main.py
    python main.py "What is CI/CD? Explained Simply"
    python main.py --force
    python main.py --publish
    python main.py --generate-script
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from assemble import assemble_video
from make_srt import build_srt

SCRIPT_PATH = Path("script_input.json")
CONFIG_PATH = Path("config.json")
CACHE_PATH = Path(".pipeline_cache.json")
AUDIO_PATH = "output.mp3"
SRT_PATH = "final_video.srt"
VIDEO_PATH = "final_video.mp4"
THUMB_PATH = "thumbnail.jpg"
TIMINGS_PATH = ".word_timings.json"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _normalize(data: dict) -> dict:
    if "script" not in data and "narration" in data:
        data["script"] = data["narration"]
    if "narration" not in data and "script" in data:
        data["narration"] = data["script"]
    for key in ("title", "script", "captions"):
        if key not in data:
            raise SystemExit(f"script_input.json is missing '{key}'")
    if not isinstance(data["captions"], list) or not data["captions"]:
        raise SystemExit("script_input.json captions must be a non-empty list")
    return data


def load_or_generate_script(topic: str, generate: bool, script_path: Path) -> dict:
    if generate:
        from script_gen import generate_script

        print(f"1/7 Generating script for: {topic}")
        data = _normalize(generate_script(topic))
        _save_json(script_path, data)
        return data

    if script_path.exists():
        print(f"1/7 Loading script from {script_path}")
        return _normalize(_load_json(script_path, {}))

    from script_gen import generate_script

    print(f"1/7 No {script_path}, generating for: {topic}")
    data = _normalize(generate_script(topic))
    _save_json(script_path, data)
    return data


def ensure_fonts() -> None:
    if not sys.platform.startswith("linux"):
        return
    marker = Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf")
    if marker.exists():
        print("0/7 Fonts already installed")
        return
    print("0/7 Installing Devanagari fonts (sudo)...")
    subprocess.run(["sudo", "apt-get", "update"], check=False)
    subprocess.run(["sudo", "apt-get", "install", "-y", "fonts-noto-core"], check=False)


def make_audio(script: str, force: bool, cache: dict, language: str | None) -> None:
    digest = _sha(script) + (language or "")
    audio = Path(AUDIO_PATH)
    if audio.exists() and not force:
        print("2/7 Reusing output.mp3")
        if not Path(TIMINGS_PATH).exists():
            print("   no voice-engine word timings alongside it;"
                  " rerun with --force to capture them for exact caption sync")
        cache["audio"] = digest
        return
    from tts import generate_audio

    print("2/7 Generating narration audio")
    generate_audio(script, AUDIO_PATH, language=language)
    cache["audio"] = digest


def make_captions(captions, force: bool, cache: dict, model: str, no_whisper: bool,
                  language: str | None, narration: str, script_path: Path,
                  allow_estimated: bool = False) -> None:
    digest = _file_sha(AUDIO_PATH) + _sha("\n".join(captions))
    if Path(SRT_PATH).exists() and not force:
        print("3/7 Reusing final_video.srt")
        cache["srt"] = digest
        return
    print("3/7 Aligning captions to audio")
    _, ratio = build_srt(
        audio_path=AUDIO_PATH,
        captions=captions,
        narration=narration,
        script_path=str(script_path),
        out_path=SRT_PATH,
        model=model,
        use_whisper=not no_whisper,
        show_report=True,
        language=language,
    )
    cache["srt"] = digest
    cache["srt_ratio"] = ratio

    if ratio is None and not (no_whisper or allow_estimated):
        Path(SRT_PATH).unlink(missing_ok=True)
        raise SystemExit(
            "Stopping: captions were NOT synced to the audio, so the video would lag.\n"
            "  The alignment error is printed just above this message.\n"
            "  Most likely fix:  pip install faster-whisper\n"
            "  Then rerun. To build anyway with guessed timings, pass --allow-estimated."
        )
    if ratio is not None and ratio < 0.6:
        print(f"   WARNING: only {ratio:.0%} of words anchored, timings may drift")


def make_clips(force: bool, cache: dict, title: str, clips_folder: str, script_path: Path, broll: str) -> None:
    folder = Path(clips_folder)
    existing = list(folder.glob("*.mp4")) if folder.exists() else []
    digest = _sha(title + broll)
    if existing and not force:
        print(f"4/7 Reusing {len(existing)} clips in {clips_folder}")
        cache["broll"] = digest
        return
    print(f"4/7 Generating B-roll ({broll})")
    if broll == "jagannath":
        from make_broll_jagannath import generate_broll as gen
    else:
        from make_broll import generate_broll as gen
    gen(script_path=str(script_path), out=clips_folder, preview=False)
    cache["broll"] = digest


def _hindi_font(size: int):
    for path, index in [
        ("C:/Windows/Fonts/Nirmala.ttc", 0),
        ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ]:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=index)
            except OSError:
                try:
                    return ImageFont.truetype(path, size=size)
                except OSError:
                    continue
    return ImageFont.load_default()


def make_thumbnail(title: str, force: bool, cache: dict) -> None:
    digest = _sha(title)
    if Path(THUMB_PATH).exists() and not force:
        print("5/7 Reusing thumbnail.jpg")
        cache["thumb"] = digest
        return
    print("5/7 Generating thumbnail")
    w, h = 1280, 720
    im = Image.new("RGB", (w, h), "#2A120C")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 18, h], fill="#C45C18")
    head, _, tail = title.partition("?")
    d.text((50, 200), (head or title).strip()[:40], font=_hindi_font(64), fill="#FFF4DC")
    d.text((50, 360), (tail.strip() or "")[:48], font=_hindi_font(40), fill="#E8C850")
    im.save(THUMB_PATH, quality=92)
    cache["thumb"] = digest


def make_video(captions, clips_folder: str) -> str:
    print("6/7 Assembling video")
    Path(VIDEO_PATH).unlink(missing_ok=True)
    return assemble_video(
        audio_path=AUDIO_PATH,
        clips_folder=clips_folder,
        captions=captions,
        output_path=VIDEO_PATH,
    )


def maybe_upload(title: str, topic: str, publish: bool, privacy: str) -> None:
    if not publish:
        print("7/7 Skipped upload (use --publish for a private YouTube draft)")
        return
    from upload import upload_video

    print("7/7 Uploading to YouTube")
    kwargs = dict(
        video_path=VIDEO_PATH,
        title=title,
        description=f"Auto-generated explainer: {topic}",
        privacy_status=privacy,
    )
    try:
        upload_video(**kwargs, thumbnail_path=THUMB_PATH)
    except TypeError:
        upload_video(**kwargs)


def run_pipeline(
    topic: str,
    publish: bool = False,
    generate_script: bool = False,
    force: bool = False,
    clips_folder: str = "clips/generated",
    whisper_model: str = "base",
    no_whisper: bool = False,
    privacy_status: str = "private",
    script_path: Path = SCRIPT_PATH,
    broll: str = "cicd",
    language: str | None = None,
    allow_estimated: bool = False,
) -> None:
    cache = _load_json(CACHE_PATH, {}) or {}
    ensure_fonts()
    result = load_or_generate_script(topic, generate_script, script_path)
    make_audio(result["script"], force, cache, language)
    make_captions(result["captions"], force, cache, whisper_model, no_whisper, language,
                  result["script"], script_path, allow_estimated)
    make_clips(force, cache, result["title"], clips_folder, script_path, broll)
    make_thumbnail(result["title"], force, cache)
    make_video(result["captions"], clips_folder)
    maybe_upload(result["title"], topic, publish, privacy_status)
    _save_json(CACHE_PATH, cache)
    print(f"Done. Video: {VIDEO_PATH}")


def main():
    cfg = _load_json(CONFIG_PATH, {}) or {}
    parser = argparse.ArgumentParser(description="Run the full YouTube automation pipeline.")
    parser.add_argument(
        "topic",
        nargs="?",
        default=cfg.get("topic", "What is CI/CD? Explained Simply"),
        help="Used for script generation and the YouTube description",
    )
    parser.add_argument("--generate-script", action="store_true",
                        help="Ignore existing script JSON and call script_gen.py")
    parser.add_argument("--script", default=cfg.get("script", "script_input.json"),
                        help="Path to title/narration/captions JSON")
    parser.add_argument("--broll", default=cfg.get("broll", "cicd"),
                        choices=["cicd", "jagannath"])
    parser.add_argument("--language", default=cfg.get("language"),
                        help="Whisper language, e.g. hi")
    parser.add_argument("--clips-folder", default=cfg.get("clips_folder", "clips/generated"))
    parser.add_argument("--whisper-model", default=cfg.get("whisper_model", "base"))
    parser.add_argument("--no-whisper", action="store_true")
    parser.add_argument("--allow-estimated", action="store_true",
                        help="Build the video even if captions could not be synced to the audio")
    parser.add_argument("--force", action="store_true", help="Rebuild audio, captions, B-roll, and thumbnail")
    parser.add_argument("--publish", action="store_true",
                        help="Upload as private after assemble (default: off)")
    parser.add_argument("--privacy", default=cfg.get("privacy_status", "private"),
                        choices=["private", "unlisted", "public"])
    args = parser.parse_args()

    run_pipeline(
        topic=args.topic,
        publish=args.publish or bool(cfg.get("publish")),
        generate_script=args.generate_script,
        force=args.force,
        clips_folder=args.clips_folder,
        whisper_model=args.whisper_model,
        no_whisper=args.no_whisper,
        privacy_status=args.privacy,
        script_path=Path(args.script),
        broll=args.broll,
        language=args.language,
        allow_estimated=args.allow_estimated,
    )


if __name__ == "__main__":
    main()
