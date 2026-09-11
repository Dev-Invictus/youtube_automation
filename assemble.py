"""
assemble.py
Combines narration audio + a folder of stock video clips + burned-in captions
into a final .mp4 using ffmpeg.

HOW TO USE:
1. Create a folder called "clips" in this directory.
2. Download 3-6 short (5-15 sec) free video clips relevant to your topic from
   pexels.com or pixabay.com (search their Videos tab, not Photos), and drop
   them into clips/ as .mp4 files.
3. Run main.py as usual - assemble_video() will cycle through the clips,
   cutting to the next one every few seconds, looping the list if the
   narration runs longer than the clips combined.

Falls back to the old single-image Ken Burns zoom if you pass an image path
instead of a clips folder (see assemble_video_from_image below), so you're
not blocked if you don't have clips yet.
"""
import glob
import json
import os
import subprocess
from mutagen.mp3 import MP3


def get_audio_duration(audio_path: str) -> float:
    return MP3(audio_path).info.length


def get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", video_path],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


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


def assemble_video(audio_path: str, clips_folder: str, captions: list[str],
                    output_path: str, resolution: str = "1080x1920") -> str:
    """
    clips_folder: a folder containing .mp4 clips (e.g. "clips"). They'll be
    cycled through, cutting to the next one every few seconds, looping the
    list as needed until the total covers the narration length.
    resolution: "1080x1920" for Shorts (vertical), "1920x1080" for standard
    """
    duration = get_audio_duration(audio_path)
    srt_path = output_path.replace(".mp4", ".srt")
    write_srt(captions, duration, srt_path)
    w, h = resolution.split("x")

    clip_files = sorted(glob.glob(os.path.join(clips_folder, "*.mp4")))
    if not clip_files:
        raise FileNotFoundError(
            f"No .mp4 files found in '{clips_folder}/'. Download a few short "
            f"clips from pexels.com or pixabay.com and drop them in that folder."
        )

    # Build a playlist of clips (looping the list) until total duration
    # covers the narration, trimming each clip to a max of 6 seconds so cuts
    # happen at a reasonable pace.
    max_clip_len = 6.0
    playlist = []
    covered = 0.0
    i = 0
    while covered < duration:
        clip = clip_files[i % len(clip_files)]
        clip_len = min(get_video_duration(clip), max_clip_len)
        playlist.append((clip, clip_len))
        covered += clip_len
        i += 1

    # ffmpeg inputs: one -i per playlist entry (duplicates allowed)
    cmd = ["ffmpeg", "-y"]
    for clip, _ in playlist:
        cmd += ["-i", clip]
    cmd += ["-i", audio_path]  # audio is the last input

    filter_parts = []
    for idx, (_, clip_len) in enumerate(playlist):
        filter_parts.append(
            f"[{idx}:v]trim=0:{clip_len},setpts=PTS-STARTPTS,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps=25,setsar=1[v{idx}]"
        )
    concat_inputs = "".join(f"[v{idx}]" for idx in range(len(playlist)))
    filter_parts.append(f"{concat_inputs}concat=n={len(playlist)}:v=1:a=0[vout]")
    filter_parts.append(f"[vout]subtitles={srt_path}[vfinal]")
    filter_complex = ";".join(filter_parts)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[vfinal]", "-map", f"{len(playlist)}:a",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    return output_path


def assemble_video_from_image(audio_path: str, background_path: str, captions: list[str],
                               output_path: str, resolution: str = "1080x1920") -> str:
    """Fallback: single static image with a Ken Burns zoom, if you don't have clips yet."""
    duration = get_audio_duration(audio_path)
    srt_path = output_path.replace(".mp4", ".srt")
    write_srt(captions, duration, srt_path)

    w, h = resolution.split("x")
    fps = 25
    total_frames = int(duration * fps) + fps

    zoompan = (
        f"scale=8000:-1,"
        f"zoompan=z='min(zoom+0.0007,1.4)':d={total_frames}:s={w}x{h}:fps={fps}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", background_path,
        "-i", audio_path,
        "-vf", f"{zoompan},subtitles={srt_path}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path,
    ]
    subprocess.run(cmd, check=True)
    return output_path


if __name__ == "__main__":
    assemble_video(
        audio_path="output.mp3",
        clips_folder="clips",
        captions=["This is caption one.", "This is caption two."],
        output_path="final_video.mp4",
    )
