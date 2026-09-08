"""
main.py
Runs the full pipeline for one topic: script -> audio -> video -> upload.

Usage:
    python main.py "3 surprising facts about Docker"
"""
import sys
from script_gen import generate_script
from tts import generate_audio
from assemble import assemble_video
from upload import upload_video


def run_pipeline(topic: str, background_image: str = "background.jpg",
                  publish: bool = False):
    print(f"1/4 Generating script for: {topic}")
    result = generate_script(topic)
    print(f"    Title: {result['title']}")

    print("2/4 Generating narration audio")
    audio_path = generate_audio(result["script"], "output.mp3")

    print("3/4 Assembling video")
    video_path = assemble_video(
        audio_path=audio_path,
        background_path=background_image,
        captions=result["captions"],
        output_path="final_video.mp4",
    )

    if publish:
        print("4/4 Uploading to YouTube (private, for review)")
        upload_video(
            video_path=video_path,
            title=result["title"],
            description=f"Auto-generated video about: {topic}",
            privacy_status="private",
        )
    else:
        print("4/4 Skipped upload — pass publish=True in run_pipeline() to upload")

    print("Done.")


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "3 surprising facts about Docker"
    run_pipeline(topic, publish=False)
