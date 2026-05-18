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

def is_youtube(url: str) -> bool:
    return any(x in url.lower() for x in ["youtube.com", "youtu.be"])

def is_tiktok(url: str) -> bool:
    return any(x in url.lower() for x in ["tiktok.com", "vm.tiktok.com"])

def is_instagram(url: str) -> bool:
    return "instagram.com" in url.lower()

@app.post("/download-audio")
def download_audio(req: DownloadRequest, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    input_file = f"/tmp/{file_id}.mp4"
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
        "--merge-output-format", "mp4",
        "-o", input_file,
    ]

    if is_youtube(req.url):
        # YouTube tiene streams de audio separados
        cmd.extend(["-f", "bestaudio/best"])
        if os.path.exists(COOKIES_YOUTUBE):
            cmd.extend(["--cookies", COOKIES_YOUTUBE])
    elif is_tiktok(req.url):
        # TikTok solo tiene video+audio combinado
        cmd.extend(["-f", "b"])
        if os.path.exists(COOKIES_TIKTOK):
            cmd.extend(["--cookies", COOKIES_TIKTOK])
    elif is_instagram(req.url):
        # Instagram solo tiene video+audio combinado
        cmd.extend(["-f", "b"])
        if os.path.exists(COOKIES_INSTAGRAM):
            cmd.extend(["--cookies", COOKIES_INSTAGRAM])
    else:
        # Facebook y cualquier otra plataforma
        cmd.extend(["-f", "b"])

    cmd.append(req.url)

    try:
        result = subprocess.run(cmd, timeout=900, capture_output=True)

        if not os.path.exists(input_file):
            raise HTTPException(500, f"Error yt-dlp: {result.stderr.decode()[:500]}")

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
        cleanup_file(input_file)
        cleanup_file(mp3_path)
        raise HTTPException(504, "Timeout descargando audio")
