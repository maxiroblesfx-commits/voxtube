"""
VoxTube — Servicio de extracción de audio de YouTube con pytubefix.
"""
from __future__ import annotations

import re
from pathlib import Path
from pytubefix import YouTube
from pytubefix.cli import on_progress

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
    Extrae el audio de un video de YouTube usando pytubefix.
    """
    try:
        video_id = validate_youtube_url(url)
        output_dir = TEMP_DIR / job_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Usar pytubefix que es más resistente a bloqueos
        yt = YouTube(url, on_progress_callback=on_progress)
        
        # Verificar duración
        duration = yt.length
        if duration > MAX_VIDEO_DURATION_SECONDS:
            raise YouTubeError(
                f"El video dura {duration // 60}:{duration % 60:02d} min. "
                f"El máximo permitido es {MAX_VIDEO_DURATION_SECONDS // 60} minutos."
            )

        # Buscar el mejor stream de audio
        audio_stream = yt.streams.get_audio_only()
        if not audio_stream:
            raise YouTubeError("No se encontró una pista de audio para este video.")

        # Descargar
        print(f"[YouTube] Descargando: {yt.title}")
        audio_file_path = audio_stream.download(
            output_path=str(output_dir),
            filename="audio.mp3"
        )

        return {
            "audio_path": str(audio_file_path),
            "title": yt.title,
            "thumbnail": yt.thumbnail_url,
            "duration": duration,
            "video_id": video_id,
        }

    except Exception as e:
        print(f"[YouTube ERROR] {str(e)}")
        if "bot" in str(e).lower() or "sign in" in str(e).lower():
            raise YouTubeError("YouTube bloqueó la conexión por bot. Reintentando con otro método...")
        raise YouTubeError(f"Error al extraer audio: {str(e)}")
