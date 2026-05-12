FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y ffmpeg curl unzip && \
    rm -rf /var/lib/apt/lists/*

# Deno: JS runtime requerido por yt-dlp para resolver el "n challenge" de YouTube
RUN curl -fsSL -o /tmp/deno.zip \
    "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip" && \
    unzip /tmp/deno.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/deno && \
    rm /tmp/deno.zip

RUN pip install --no-cache-dir \
    "yt-dlp[default,curl-cffi]" \
    fastapi \
    uvicorn \
    python-multipart

WORKDIR /app
COPY main.py .
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
