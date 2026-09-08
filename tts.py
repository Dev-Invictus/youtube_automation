"""
tts.py (FREE VERSION - no API key needed)

Uses edge-tts, a free wrapper around Microsoft Edge's text-to-speech engine.
No signup, no API key, no character limits.

Install: pip install edge-tts
List available voices: edge-tts --list-voices
"""
import asyncio
import edge_tts

DEFAULT_VOICE = "en-US-GuyNeural"  # try en-US-JennyNeural, en-GB-RyanNeural, etc.


async def _generate(text: str, output_path: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_audio(text: str, output_path: str, voice: str = DEFAULT_VOICE) -> str:
    asyncio.run(_generate(text, output_path, voice))
    return output_path


if __name__ == "__main__":
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else "This is a test of the automated pipeline."
    path = generate_audio(text, "output.mp3")
    print(f"Saved audio to {path}")
