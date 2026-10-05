"""
make_srt.py
Builds final_video.srt so captions line up with the narration audio.

How it works:
  1. faster-whisper transcribes the narration with word-level timestamps.
  2. The script's words are aligned against the transcript with a sequence
     matcher, so every script word inherits a real start/end from the audio.
     The script text is kept verbatim - the transcript is used only for timing,
     never for wording, so no ASR mistake can change what is displayed.
  3. Words are regrouped into cues at clause punctuation and at genuine pauses
     in the audio. A cue's start is its first word's timestamp and its end is
     its last word's timestamp. No offsets are applied anywhere.

Timings always come from the narration audio file, never from the assembled
video, and everything is read and written as UTF-8.

Usage:
    pip install faster-whisper
    python make_srt.py --script script_jagannath.json --language hi --report
    python make_srt.py --model small      # better Hindi transcript, slower
    python make_srt.py --no-resegment     # keep the script's own caption lines
    python make_srt.py --no-whisper       # estimate only (not synced)
"""
import argparse
import difflib
import hashlib
import json
import subprocess
import unicodedata
from pathlib import Path

CLAUSE_END = ("।", "?", "!", ".", ",", ":", ";")
TRIM = '"\u201c\u201d\u2018\u2019()'

REPORT_PATH = ".caption_report.json"
TTS_TIMINGS = ".word_timings.json"
MAX_CHARS = 52
MIN_CHARS = 16
PAUSE = 0.32
MODEL_LADDER = ["tiny", "base", "small", "medium"]
RETRY_BELOW = 0.75


def _ts(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _audio_duration(path: str) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        text=True,
    )
    return float(out.strip())


def _norm(token: str) -> str:
    """Drop punctuation, keep letters, combining marks and digits in any script.
    A Latin-only filter emptied every Devanagari token, and \\w drops the matras
    that distinguish words like है from हैं."""
    kept = [ch for ch in token if unicodedata.category(ch)[0] in ("L", "M", "N")]
    return "".join(kept).lower()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tts_timings(narration: str, path: str = TTS_TIMINGS):
    """Word timings reported by the voice engine that produced the audio.

    These are exact by construction: the engine tells us when it said each word,
    so nothing has to be transcribed or guessed.
    """
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    if data.get("text_sha") and data["text_sha"] != _sha(narration):
        print("voice-engine timings are stale (narration changed), ignoring them")
        return None
    words = [
        (_norm(w["w"]), float(w["t"]), float(w["t"]) + float(w["d"]), 1.0)
        for w in data.get("words", [])
        if _norm(w["w"])
    ]
    if not words:
        return None
    return words, data.get("boundary", "word")


def transcribe(audio_path: str, model_size: str, language=None, prompt=None):
    """Word-level timestamps straight from the model, with no text rewriting."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        audio_path,
        language=language,
        word_timestamps=True,
        vad_filter=False,
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
        initial_prompt=prompt,
    )

    words = []
    for seg in segments:
        for word in seg.words or []:
            norm = _norm(word.word)
            if norm:
                prob = getattr(word, "probability", None)
                words.append((norm, float(word.start), float(word.end),
                              1.0 if prob is None else float(prob)))
    if not words:
        raise RuntimeError("whisper returned no word timestamps")
    return words


def align_words(tokens, hyp, duration):
    """Give every script token a start/end taken from the transcript.

    Matched words are anchors; unmatched runs are interpolated between their
    neighbours, so a mis-heard word cannot shift anything after it.
    """
    norms = [_norm(t) for t in tokens]
    ref_idx = [i for i, n in enumerate(norms) if n]
    if not ref_idx:
        raise RuntimeError("script contains no usable words")
    ref = [norms[i] for i in ref_idx]

    matcher = difflib.SequenceMatcher(a=ref, b=[w[0] for w in hyp], autojunk=False)
    starts = [None] * len(ref)
    ends = [None] * len(ref)
    anchored = 0
    for i, j, size in matcher.get_matching_blocks():
        for k in range(size):
            starts[i + k] = hyp[j + k][1]
            ends[i + k] = hyp[j + k][2]
            anchored += 1

    known = [i for i, s in enumerate(starts) if s is not None]
    if not known:
        raise RuntimeError("no script words matched the transcript")

    first, last = known[0], known[-1]
    pace = (ends[last] - starts[first]) / max(1, last - first)
    for i in range(first - 1, -1, -1):
        ends[i] = starts[i + 1]
        starts[i] = max(0.0, ends[i] - pace)
    for i in range(last + 1, len(ref)):
        starts[i] = ends[i - 1]
        ends[i] = min(duration, starts[i] + pace)

    gap = None
    for i in range(len(ref)):
        if starts[i] is None:
            gap = i if gap is None else gap
            continue
        if gap is not None:
            left, right = ends[gap - 1], starts[i]
            step = (right - left) / (i - gap + 1)
            for k in range(i - gap):
                starts[gap + k] = left + step * k
                ends[gap + k] = left + step * (k + 1)
            gap = None

    timed = [None] * len(tokens)
    for pos, i in enumerate(ref_idx):
        timed[i] = (starts[pos], ends[pos], True)
    for i, slot in enumerate(timed):
        if slot is not None:
            continue
        prev = next((timed[j] for j in range(i - 1, -1, -1) if timed[j]), None)
        nxt = next((timed[j] for j in range(i + 1, len(timed)) if timed[j]), None)
        start = prev[1] if prev else 0.0
        end = nxt[0] if nxt else duration
        timed[i] = (start, max(start, end), False)

    return timed, anchored / len(ref)


def regroup(tokens, timed, max_chars=MAX_CHARS, min_chars=MIN_CHARS, pause=PAUSE):
    """Cut cues at clause punctuation and at real silences in the audio."""
    cues = []
    current = []
    for i, token in enumerate(tokens):
        current.append(i)
        text = " ".join(tokens[j] for j in current)
        if i + 1 >= len(tokens):
            break
        gap = timed[i + 1][0] - timed[i][1]
        clause = token.rstrip(TRIM).endswith(CLAUSE_END)
        width = len(text) + 1 + len(tokens[i + 1])
        if (clause and len(text) >= min_chars) or gap >= pause or width > max_chars:
            cues.append(current)
            current = []
    if current:
        cues.append(current)

    out = []
    for group in cues:
        text = " ".join(tokens[j] for j in group).strip().strip("—").strip()
        if not text:
            continue
        start = timed[group[0]][0]
        end = timed[group[-1]][1]
        confident = sum(1 for j in group if timed[j][2])
        out.append((text, start, end, confident / len(group)))
    return out


def cues_from_captions(captions, tokens, timed):
    """Keep the script's own caption lines, timed by their first/last word."""
    out = []
    cursor = 0
    for caption in captions:
        count = len(caption.split())
        group = list(range(cursor, min(cursor + count, len(tokens))))
        cursor += count
        if not group:
            continue
        confident = sum(1 for j in group if timed[j][2])
        out.append((caption, timed[group[0]][0], timed[group[-1]][1],
                    confident / len(group)))
    return out


def tidy(cues, duration):
    """Keep cues in order and non-overlapping without inventing any offset."""
    out = []
    for i, (text, start, end, conf) in enumerate(cues):
        if out and start < out[-1][2]:
            start = out[-1][2]
        if i + 1 < len(cues):
            end = min(end, cues[i + 1][1])
        end = min(max(end, start + 0.08), duration)
        out.append((text, start, end, conf))
    return out


def weighted(cues_text, duration):
    def weight(text):
        w = len(text)
        if text.rstrip().endswith(("।", ".", "!", "?")):
            w += 12
        elif text.rstrip().endswith((",", ":", ";")):
            w += 5
        return w

    weights = [weight(c) for c in cues_text]
    total = sum(weights) or 1.0
    out = []
    cursor = 0.0
    for text, w in zip(cues_text, weights):
        span = duration * (w / total)
        out.append((text, cursor, cursor + span, 0.0))
        cursor += span
    return out


def write_srt(cues, path: Path):
    blocks = []
    for i, (text, start, end, _) in enumerate(cues, start=1):
        blocks.append(f"{i}\n{_ts(start)} --> {_ts(end)}\n{text}\n")
    path.write_text("\n".join(blocks), encoding="utf-8")


def report(cues, duration, mean_prob=None):
    print("\nspot-check these against the audio:")
    for target in (5, 60, 180, 330, 480, 570):
        for text, start, end, _ in cues:
            if start >= target:
                print(f"  {_ts(start)} -> {_ts(end)}  {text}")
                break
    shaky = sorted(cues, key=lambda c: c[3])[:3]
    if shaky and shaky[0][3] < 1.0:
        print("\nweakest timings (interpolated, verify these):")
        for text, start, _, conf in shaky:
            print(f"  {_ts(start)}  {conf:.0%} anchored  {text}")
    if mean_prob is not None:
        print(f"\ntranscript confidence: {mean_prob:.0%} mean word probability")
    print(f"last cue ends at {_ts(cues[-1][2])}, audio is {_ts(duration)}")


def build_srt(
    audio_path="output.mp3",
    captions=None,
    script_path="script_input.json",
    out_path="final_video.srt",
    model="base",
    use_whisper=True,
    show_report=False,
    language=None,
    resegment=True,
    narration=None,
):
    data = None
    if captions is None or narration is None:
        path = Path(script_path)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
    if captions is None:
        captions = data["captions"]
    if narration is None:
        narration = (data or {}).get("narration") or (data or {}).get("script") or " ".join(captions)

    duration = _audio_duration(audio_path)
    tokens = narration.split()
    cues = None
    ratio = None
    mean_prob = None
    used_model = None

    engine = tts_timings(narration)
    if engine:
        hyp, grain = engine
        print(f"using {len(hyp)} {grain} timings from the voice engine (exact, no transcription)")
        try:
            timed, ratio = align_words(tokens, hyp, duration)
            print(f"matched {ratio:.0%} of script words to spoken words")
            if ratio >= 0.8:
                cues = regroup(tokens, timed) if resegment else cues_from_captions(captions, tokens, timed)
                used_model = f"edge-tts {grain} boundaries"
            else:
                print("  match too low, falling back to whisper")
                ratio = None
        except Exception as exc:
            print(f"voice-engine timings unusable ({exc}), falling back to whisper")
            ratio = None

    if cues is None and use_whisper:
        ladder = MODEL_LADDER[MODEL_LADDER.index(model):] if model in MODEL_LADDER else [model]
        for attempt, size in enumerate(ladder):
            try:
                print(f"transcribing with faster-whisper ({size}), this takes a few minutes")
                hyp = transcribe(audio_path, size, language=language,
                                 prompt=narration[:600])
                mean_prob = sum(w[3] for w in hyp) / len(hyp)
                print(f"transcript has {len(hyp)} words, mean confidence {mean_prob:.0%}")
                timed, ratio = align_words(tokens, hyp, duration)
                print(f"alignment done, {ratio:.0%} of script words anchored to real timings")
                if ratio < RETRY_BELOW and attempt + 1 < len(ladder):
                    print(f"  below {RETRY_BELOW:.0%}, retrying with '{ladder[attempt + 1]}'")
                    continue
                cues = regroup(tokens, timed) if resegment else cues_from_captions(captions, tokens, timed)
                used_model = size
                break
            except ImportError:
                print("faster-whisper not installed, falling back to weighted estimate")
                break
            except Exception as exc:
                print(f"alignment failed ({exc})")
                if attempt + 1 < len(ladder):
                    print(f"  retrying with '{ladder[attempt + 1]}'")

    if cues is None:
        print("!! captions are ESTIMATED from text length, not synced to the audio")
        cues = weighted(captions, duration)

    cues = tidy(cues, duration)
    out = Path(out_path)
    write_srt(cues, out)

    Path(REPORT_PATH).write_text(json.dumps({
        "estimated": ratio is None,
        "model": used_model,
        "anchored": ratio,
        "mean_word_confidence": mean_prob,
        "cues": len(cues),
        "audio_seconds": duration,
        "resegmented": resegment,
    }, indent=2), encoding="utf-8")

    print(f"wrote {out} ({len(cues)} cues, UTF-8)")
    if show_report:
        report(cues, duration, mean_prob)
    return str(out), ratio


def main():
    ap = argparse.ArgumentParser(description="Generate a synced subtitle file.")
    ap.add_argument("--audio", default="output.mp3")
    ap.add_argument("--script", default="script_input.json")
    ap.add_argument("--out", default="final_video.srt")
    ap.add_argument("--model", default="base", help="tiny, base, small, medium")
    ap.add_argument("--language", default=None, help="whisper language code, e.g. hi")
    ap.add_argument("--report", action="store_true", help="print sample timings")
    ap.add_argument("--no-resegment", action="store_true",
                    help="keep the script's caption lines instead of cutting at pauses")
    ap.add_argument("--no-whisper", action="store_true", help="skip alignment, estimate only")
    args = ap.parse_args()
    build_srt(
        audio_path=args.audio,
        script_path=args.script,
        out_path=args.out,
        model=args.model,
        use_whisper=not args.no_whisper,
        show_report=args.report,
        language=args.language,
        resegment=not args.no_resegment,
    )


if __name__ == "__main__":
    main()
