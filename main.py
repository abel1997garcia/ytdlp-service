from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess, uuid, os

app = FastAPI()

class DownloadRequest(BaseModel):
    url: str

@app.get("/")
def root():
    return {"status": "ok", "service": "ytdlp-audio-downloader"}

@app.post("/download-audio")
def download_audio(req: DownloadRequest):
    file_id = str(uuid.uuid4())
    output_path = f"/tmp/{file_id}.mp3"
    try:
        subprocess.run(
            [
                "yt-dlp",
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "5",
                "--no-playlist",
                "--impersonate", "chrome",
                "-o", output_path,
                req.url,
            ],
            check=True,
            timeout=180,
            capture_output=True,
        )
        if not os.path.exists(output_path):
            raise HTTPException(500, "El archivo no se generó")
        return FileResponse(
            output_path,
            media_type="audio/mpeg",
            filename=f"{file_id}.mp3",
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Error yt-dlp: {e.stderr.decode()[:500]}")
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "Timeout descargando audio")
