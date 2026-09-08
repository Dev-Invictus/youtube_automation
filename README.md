# YouTube Automation Pipeline

A minimal, swappable pipeline: **topic → script → voiceover → captioned video → YouTube upload.**
Built to run entirely in GitHub Codespaces — no local machine needed, same workflow as the
`ml-api-portfolio` project.

## Pipeline stages
| Stage | File | Service used | Swap it for |
|---|---|---|---|
| Script | `script_gen.py` | Anthropic API | any LLM |
| Voice | `tts.py` | ElevenLabs | Play.ht, Google Cloud TTS |
| Assembly | `assemble.py` | ffmpeg (local, free) | InVideo/Pictory if you want a GUI |
| Upload | `upload.py` | YouTube Data API v3 | — |

## Setup (in a new or existing Codespace)

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install mutagen           # audio duration helper used by assemble.py
   sudo apt-get update && sudo apt-get install -y ffmpeg
   ```

2. **Set API keys as Codespaces secrets** (Settings -> Secrets and variables -> Codespaces,
   on your GitHub repo) so they're injected automatically as environment variables:
   - `ANTHROPIC_API_KEY`
   - `ELEVENLABS_API_KEY`
   - `ELEVENLABS_VOICE_ID` (optional, defaults to a preset voice)

3. **YouTube API access** — one-time, done from inside the Codespace browser tab:
   - Create a project + OAuth credentials at console.cloud.google.com (see `upload.py` docstring)
   - Upload `client_secret.json` into the Codespace
   - First run of `upload.py` prints a URL — open it, approve, paste the code back
   - This saves `token.json` so future runs are automatic

4. **Add a background image** — drop a `background.jpg` (or point `main.py` at a video clip)
   into this folder. Free sources: Pexels, Pixabay (no attribution required).

## Run it

```bash
python main.py "3 surprising facts about Docker"
```

This generates the script, audio, and video, then stops before uploading so you can review
`final_video.mp4` first. Once you're happy with the output quality, flip `publish=True` in
`main.py`'s `run_pipeline()` call to upload (videos upload as **private** by default — review
in YouTube Studio, then switch to public yourself).

## Scaling up
- Loop `run_pipeline()` over a list of topics to batch-produce a week's content at once.
- Add a GitHub Actions workflow (you already have one for CI on the ML API project) to run
  `main.py` on a schedule — e.g. daily at 8am — using `workflow_dispatch` + `schedule` triggers.
- Once volume grows, replace the single background image in `assemble.py` with a rotation of
  stock clips for more visual variety.

## Notes
- Keep `privacy_status="private"` until you've reviewed a handful of outputs — AI voice glitches
  or factual errors are the main failure mode, and reviewing before publishing catches them.
- Category ID 27 = Education; see YouTube's category list if your niche fits elsewhere.
