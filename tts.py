"""
tts.py — edge-tts, no API key.

Streams the synthesis instead of using save(), so the WordBoundary events the
engine emits can be captured. Those give the exact start and duration of every
spoken word, which makes caption timing exact instead of transcribed and
guessed. Timings are written next to the audio as .word_timings.json.

Voice is chosen from:
  1. explicit voice= argument
  2. language= ("hi", "en", ...)
  3. Devanagari characters in the text
  4. DEFAULT_VOICE
"""
import asyncio
import hashlib
import json
import re
from pathlib import Path

import edge_tts

DEFAULT_VOICE = "en-US-GuyNeural"
TIMINGS_PATH = ".word_timings.json"
TICKS_PER_SECOND = 10_000_000

VOICES = {
    "hi": "hi-IN-SwaraNeural",
    "en": "en-US-GuyNeural",
    "en-gb": "en-GB-RyanNeural",
}


def pick_voice(text: str, language: str | None = None, voice: str | None = None) -> str:
    if voice:
        return voice
    if language:
        return VOICES.get(language.lower(), DEFAULT_VOICE)
    if re.search(r"[\u0900-\u097F]", text):
        return VOICES["hi"]
    return DEFAULT_VOICE


def text_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _communicate(text: str, voice: str):
    """Word boundaries are opt-in; older versions have no boundary argument
    and emit them by default."""
    try:
        return edge_tts.Communicate(text, voice, boundary="WordBoundary")
    except TypeError:
        return edge_tts.Communicate(text, voice)


async def _stream(text: str, output_path: str, voice: str):
    communicate = _communicate(text, voice)
    words = []
    with open(output_path, "wb") as audio:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio.write(chunk["data"])
            elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
                words.append({
                    "w": chunk["text"],
                    "t": chunk["offset"] / TICKS_PER_SECOND,
                    "d": chunk["duration"] / TICKS_PER_SECOND,
                    "kind": chunk["type"],
                })
    return words


def generate_audio(
    text: str,
    output_path: str,
    voice: str | None = None,
    language: str | None = None,
    timings_path: str = TIMINGS_PATH,
) -> str:
    chosen = pick_voice(text, language=language, voice=voice)
    print(f"   TTS voice: {chosen}")
    words = asyncio.run(_stream(text, output_path, chosen))

    path = Path(timings_path)
    if words:
        kinds = {w["kind"] for w in words}
        path.write_text(json.dumps({
            "voice": chosen,
            "text_sha": text_sha(text),
            "boundary": "word" if "WordBoundary" in kinds else "sentence",
            "words": words,
        }, ensure_ascii=False), encoding="utf-8")
        grain = "word" if "WordBoundary" in kinds else "sentence-level"
        print(f"   captured {len(words)} {grain} timings from the voice engine")
    else:
        path.unlink(missing_ok=True)
        print("   voice engine sent no word timings, captions will fall back to whisper")
    return output_path


if __name__ == "__main__":
    import sys

    text = sys.argv[1] if len(sys.argv) > 1 else "This is a test of the automated pipeline."
    path = generate_audio(text, "output.mp3")
    print(f"Saved audio to {path}")
