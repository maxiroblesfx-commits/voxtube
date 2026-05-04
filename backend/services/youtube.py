"""
VoxTube — Servicio de extracción de audio de YouTube con yt-dlp.
"""
from __future__ import annotations

import re
from pathlib import Path

import yt_dlp

from config import TEMP_DIR, MAX_VIDEO_DURATION_SECONDS


class YouTubeError(Exception):
    """Error específico de extracción de YouTube."""


def validate_youtube_url(url: str) -> str:
    """Valida y normaliza una URL de YouTube. Devuelve el video ID."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise YouTubeError("URL de YouTube inválida. Por favor verificá el enlace.")


def extract_audio(url: str, job_id: str) -> dict:
    """
    Extrae el audio de un video de YouTube.

    Returns:
        dict con keys: audio_path, title, thumbnail, duration, video_id
    """
    video_id = validate_youtube_url(url)
    output_path = TEMP_DIR / job_id / "audio.%(ext)s"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_path),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        # Bypass bot detection
        "noprogress": True,
        "cookiefile": "cookies.txt",  # Forzado en el root del Docker
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "web_creator", "web"],
            }
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        # Verificar duración
        duration = info.get("duration", 0)
        if duration > MAX_VIDEO_DURATION_SECONDS:
            raise YouTubeError(
                f"El video dura {duration // 60}:{duration % 60:02d} min. "
                f"El máximo permitido es {MAX_VIDEO_DURATION_SECONDS // 60} minutos."
            )

        # Descargar
        ydl.download([url])

    audio_file = TEMP_DIR / job_id / "audio.mp3"
    if not audio_file.exists():
        # Buscar cualquier archivo de audio generado
        for f in (TEMP_DIR / job_id).iterdir():
            if f.suffix in (".mp3", ".m4a", ".webm", ".wav", ".opus"):
                audio_file = f
                break
        else:
            raise YouTubeError("No se pudo extraer el audio del video.")

    return {
        "audio_path": str(audio_file),
        "title": info.get("title", "Sin título"),
        "thumbnail": info.get("thumbnail", ""),
        "duration": duration,
        "video_id": video_id,
    }
