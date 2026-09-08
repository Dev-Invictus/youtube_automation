"""
assemble.py
Combines narration audio + a background image/video + burned-in captions
into a final .mp4 using ffmpeg (already installed on most Codespaces images;
run `sudo apt-get install -y ffmpeg` if not).

This is intentionally simple: one static background + captions. Swap the
background for a looping stock clip, or a slideshow of images, once the
basic pipeline works end to end.
"""
import subprocess
import wave
import contextlib
from mutagen.mp3 import MP3


def get_audio_duration(audio_path: str) -> float:
    return MP3(audio_path).info.length


def write_srt(captions: list[str], total_duration: float, srt_path: str) -> str:
    """Splits total_duration evenly across captions and writes an .srt file."""
    per_caption = total_duration / len(captions)

    def fmt(t: float) -> str:
        h, rem = divmod(t, 3600)
        m, s = divmod(rem, 60)
        ms = (s - int(s)) * 1000
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(ms):03d}"

    with open(srt_path, "w") as f:
        for i, cap in enumerate(captions):
            start = i * per_caption
            end = (i + 1) * per_caption
            f.write(f"{i+1}\n{fmt(start)} --> {fmt(end)}\n{cap}\n\n")
    return srt_path


def assemble_video(audio_path: str, background_path: str, captions: list[str],
                    output_path: str, resolution: str = "1080x1920") -> str:
    """
    background_path: a static image (.jpg/.png) or a looping video clip (.mp4)
    resolution: "1080x1920" for Shorts (vertical), "1920x1080" for standard
    """
    duration = get_audio_duration(audio_path)
    srt_path = output_path.replace(".mp4", ".srt")
    write_srt(captions, duration, srt_path)

    w, h = resolution.split("x")
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", background_path,   # background image (drop -loop 1 if using a video clip)
        "-i", audio_path,
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},subtitles={srt_path}",
        "-c:v", "libx264", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    return output_path


if __name__ == "__main__":
    assemble_video(
        audio_path="output.mp3",
        background_path="background.jpg",
        captions=["This is caption one.", "This is caption two."],
        output_path="final_video.mp4",
    )
