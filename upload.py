"""
upload.py
Uploads a finished video to YouTube via the YouTube Data API v3.

One-time setup (do this in a browser, not in code):
1. Go to console.cloud.google.com -> create a project -> enable "YouTube Data API v3"
2. Create OAuth 2.0 credentials (type: Desktop app) -> download as client_secret.json
   -> upload it into your Codespace (drag into the file explorer)
3. First run prints a URL -> open it, sign in, approve access. Google redirects to
   localhost:8080, which will likely show "site can't be reached" in Codespaces -
   that's expected and fine. Copy the FULL URL from the address bar at that point
   (it contains the authorization code) and paste it back into the terminal.
   This creates token.json so future runs don't need re-approval.
"""
import os
import pickle

# oauthlib blocks non-https redirect URIs by default as a safety precaution.
# http://localhost is a standard, accepted exception for desktop OAuth apps -
# this line just tells the library that's expected here.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_PATH = "token.json"
CLIENT_SECRET_PATH = "client_secret.json"
REDIRECT_URI = "http://localhost:8080/"


def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_PATH, SCOPES, redirect_uri=REDIRECT_URI
            )
            auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")

            print("\nOpen this URL in your browser, sign in, and approve access:\n")
            print(auth_url)
            print(
                "\nAfter approving, the browser will try to load localhost:8080 and "
                "likely show 'site can't be reached' - that's expected. Copy the FULL "
                "URL from the address bar at that point (it contains '?code=...') and "
                "paste it below.\n"
            )
            redirect_response = input("Paste the full redirect URL here: ").strip()
            flow.fetch_token(authorization_response=redirect_response)
            creds = flow.credentials

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
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Upload a video to YouTube.")
    parser.add_argument("video_path", nargs="?", default="final_video.mp4",
                         help="Path to the video file (default: final_video.mp4)")
    parser.add_argument("--title", default="Untitled video", help="Video title")
    parser.add_argument("--description", default="", help="Video description")
    parser.add_argument("--tags", default="", help="Comma-separated tags, e.g. 'docker,tech,tutorial'")
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"],
                         help="Privacy status (default: private)")
    args = parser.parse_args()

    tags_list = [t.strip() for t in args.tags.split(",") if t.strip()]

    upload_video(
        video_path=args.video_path,
        title=args.title,
        description=args.description or f"Auto-generated video: {args.title}",
        tags=tags_list,
        privacy_status=args.privacy,
    )
