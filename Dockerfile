FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "yt-dlp[default,curl-cffi]" \
    fastapi \
    uvicorn \
    python-multipart

WORKDIR /app
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
