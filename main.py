from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess, uuid, os, glob

app = FastAPI()

COOKIES_INSTAGRAM = "/cookies/instagram_cookies.txt"
COOKIES_YOUTUBE = "/cookies/youtube_cookies.txt"
COOKIES_TIKTOK = "/cookies/tiktok_cookies.txt"

class DownloadRequest(BaseModel):
    url: str
    normalize: bool = False

@app.get("/")
def root():
    return {"status": "ok", "service": "ytdlp-audio-downloader"}

def cleanup_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def needs_instagram_cookies(url: str) -> bool:
    return "instagram.com" in url.lower()

def needs_youtube_cookies(url: str) -> bool:
    return any(x in url.lower() for x in ["youtube.com", "youtu.be"])

def needs_tiktok_cookies(url: str) -> bool:
    return any(x in url.lower() for x in ["tiktok.com", "vm.tiktok.com"])

@app.post("/download-audio")
def download_audio(req: DownloadRequest, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    raw_template = f"/tmp/{file_id}.%(ext)s"
    mp3_path = f"/tmp/{file_id}.mp3"

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-part",
        "--retries", "10",
        "--fragment-retries", "10",
        "--extractor-retries", "5",
        "--no-abort-on-error",
        "--impersonate", "chrome",
        "-f", "bestaudio/best",
        "-o", raw_template,
    ]

    if needs_youtube_cookies(req.url) and os.path.exists(COOKIES_YOUTUBE):
        cmd.extend(["--cookies", COOKIES_YOUTUBE])
    elif needs_tiktok_cookies(req.url) and os.path.exists(COOKIES_TIKTOK):
        cmd.extend(["--cookies", COOKIES_TIKTOK])
    elif needs_instagram_cookies(req.url) and os.path.exists(COOKIES_INSTAGRAM):
        cmd.extend(["--cookies", COOKIES_INSTAGRAM])

    cmd.append(req.url)

    try:
        result = subprocess.run(cmd, timeout=900, capture_output=True)

        downloaded = glob.glob(f"/tmp/{file_id}.*")
        downloaded = [f for f in downloaded if not f.endswith(".mp3")]

        if not downloaded:
            raise HTTPException(500, f"Error yt-dlp: {result.stderr.decode()[:500]}")

        input_file = downloaded[0]

        ff = subprocess.run([
            "ffmpeg", "-y", "-i", input_file,
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            mp3_path,
        ], capture_output=True, timeout=600)

        cleanup_file(input_file)

        if ff.returncode != 0 or not os.path.exists(mp3_path):
            raise HTTPException(500, f"Error ffmpeg: {ff.stderr.decode()[:300]}")

        background_tasks.add_task(cleanup_file, mp3_path)
        return FileResponse(mp3_path, media_type="audio/mpeg", filename=f"{file_id}.mp3")

    except subprocess.TimeoutExpired:
        for f in glob.glob(f"/tmp/{file_id}.*"):
            cleanup_file(f)
        raise HTTPException(504, "Timeout descargando audio")
