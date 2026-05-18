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

def has_audio_stream(filepath: str) -> bool:
    result = subprocess.run([
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        filepath
    ], capture_output=True, timeout=30)
    return b"audio" in result.stdout

def download_file(url: str, output: str, fmt: str, cookies: str = None) -> subprocess.CompletedProcess:
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
        "-f", fmt,
        "-o", output,
    ]
    if cookies and os.path.exists(cookies):
        cmd.extend(["--cookies", cookies])
    cmd.append(url)
    return subprocess.run(cmd, timeout=900, capture_output=True)

@app.post("/download-audio")
def download_audio(req: DownloadRequest, background_tasks: BackgroundTasks):
    file_id = str(uuid.uuid4())
    input_file = f"/tmp/{file_id}.mp4"
    mp3_path = f"/tmp/{file_id}.mp3"

    # Determinar cookies y formatos a intentar según plataforma
    if is_youtube(req.url):
        formats = ["bestaudio/best"]
        cookies = COOKIES_YOUTUBE
    elif is_tiktok(req.url):
        formats = ["h264/bestaudio", "b"]
        cookies = COOKIES_TIKTOK
    elif is_instagram(req.url):
        formats = ["b"]
        cookies = COOKIES_INSTAGRAM
    else:
        formats = ["b"]
        cookies = None

    try:
        # Intentar cada formato hasta que el archivo tenga audio
        downloaded = False
        for fmt in formats:
            cleanup_file(input_file)
            download_file(req.url, input_file, fmt, cookies)
            if os.path.exists(input_file) and has_audio_stream(input_file):
                downloaded = True
                break

        if not downloaded:
            raise HTTPException(500, "No se pudo descargar audio válido")

        ff = subprocess.run([
            "ffmpeg", "-y", "-i", input_file,
            "-vn",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            mp3_path,
        ], capture_output=True, timeout=600)

        cleanup_file(input_file)

        if ff.returncode != 0 or not os.path.exists(mp3_path):
            raise HTTPException(500, f"Error ffmpeg: {ff.stderr.decode()[-500:]}")

        background_tasks.add_task(cleanup_file, mp3_path)
        return FileResponse(mp3_path, media_type="audio/mpeg", filename=f"{file_id}.mp3")

    except subprocess.TimeoutExpired:
        cleanup_file(input_file)
        cleanup_file(mp3_path)
        raise HTTPException(504, "Timeout descargando audio")
