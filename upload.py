"""
upload.py
Uploads a finished video to YouTube via the YouTube Data API v3.

One-time setup (do this in a browser, not in code):
1. Go to console.cloud.google.com -> create a project -> enable "YouTube Data API v3"
2. Create OAuth 2.0 credentials (type: Desktop app) -> download as client_secret.json
   -> upload it into your Codespace (drag into the file explorer)
3. First run will print a URL -> open it, approve access, paste the code back.
   This creates token.json so future runs don't need re-approval.
"""
import os
import pickle
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = "token.json"
CLIENT_SECRET_PATH = "client_secret.json"


def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            # run_console works headlessly (Codespaces has no local browser popup)
            creds = flow.run_console()
        with open(TOKEN_PATH, "wb") as f:
            pickle.dump(creds, f)

    return build("youtube", "v3", credentials=creds)


def upload_video(video_path: str, title: str, description: str,
                  tags: list[str] = None, category_id: str = "27",  # 27 = Education
                  privacy_status: str = "private") -> str:
    """privacy_status: 'private', 'unlisted', or 'public'. Start with 'private' to review."""
    youtube = get_authenticated_service()

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {"privacyStatus": privacy_status},
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Upload complete: https://youtube.com/watch?v={video_id}")
    return video_id


if __name__ == "__main__":
    upload_video(
        video_path="final_video.mp4",
        title="Test upload",
        description="Uploaded via automated pipeline.",
        tags=["test"],
        privacy_status="private",
    )
