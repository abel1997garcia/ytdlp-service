from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess, uuid, os

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
    raw_path = f"/tmp/{file_id}.mp3"
    final_path = f"/tmp/{file_id}_final.mp3"

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--no-playlist",
        "--no-part",
        "--retries", "10",
        "--fragment-retries", "10",
        "--extractor-retries", "5",
        "--no-abort-on-error",
        "--impersonate", "chrome",
        "--embed-metadata",
    ]

    if needs_youtube_cookies(req.url) and os.path.exists(COOKIES_YOUTUBE):
        cmd.extend(["--cookies", COOKIES_YOUTUBE])
    elif needs_tiktok_cookies(req.url) and os.path.exists(COOKIES_TIKTOK):
        cmd.extend(["--cookies", COOKIES_TIKTOK])
    elif needs_instagram_cookies(req.url) and os.path.exists(COOKIES_INSTAGRAM):
        cmd.extend(["--cookies", COOKIES_INSTAGRAM])

    cmd.extend(["-o", raw_path, req.url])

    try:
        result = subprocess.run(cmd, timeout=900, capture_output=True)

        if not os.path.exists(raw_path):
            raise HTTPException(500, f"Error yt-dlp: {result.stderr.decode()[:500]}")

        output_path = raw_path

        if req.normalize:
            ff = subprocess.run([
                "ffmpeg", "-y", "-i", raw_path,
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                "-codec:a", "libmp3lame",
                "-b:a", "128k",
                final_path,
            ], capture_output=True, timeout=600)

            if ff.returncode != 0:
                cleanup_file(raw_path)
                cleanup_file(final_path)
                raise HTTPException(500, f"Error ffmpeg: {ff.stderr.decode()[:500]}")

            cleanup_file(raw_path)
            output_path = final_path

        background_tasks.add_task(cleanup_file, output_path)
        return FileResponse(output_path, media_type="audio/mpeg", filename=f"{file_id}.mp3")

    except subprocess.TimeoutExpired:
        cleanup_file(raw_path)
        cleanup_file(final_path)
        raise HTTPException(504, "Timeout descargando audio")
