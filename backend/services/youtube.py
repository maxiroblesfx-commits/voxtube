"""
VoxTube — Servicio de extracción de audio de YouTube.
"""
from __future__ import annotations

import re
from pathlib import Path

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


def _try_ytdlp(url: str, video_id: str, output_dir: Path) -> dict | None:
    """Extrae el audio usando yt-dlp con client spoofing (Android/TV) para evadir bots."""
    import yt_dlp
    
    ydl_opts = {
        "format": "m4a/bestaudio/best",
        "outtmpl": str(output_dir / "audio.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        # Clave maestra para evadir el bloqueo de bot sin usar cookies
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "tv"],
                # NO ignorar formatos dash/hls (eso causaba el error de formato no disponible)
            }
        },
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if not info:
                raise YouTubeError("yt-dlp devolvió info vacía")
                
            duration = info.get("duration", 0)
            if duration > MAX_VIDEO_DURATION_SECONDS:
                raise YouTubeError(
                    f"El video dura {duration // 60}:{duration % 60:02d} min. "
                    f"Máximo permitido: {MAX_VIDEO_DURATION_SECONDS // 60} min."
                )

            # El post-processor asegura que el archivo final sea audio.mp3
            final_audio_path = output_dir / "audio.mp3"
            if not final_audio_path.exists():
                raise YouTubeError("El archivo MP3 final no se generó.")

            return {
                "audio_path": str(final_audio_path),
                "title": info.get("title", "Sin título"),
                "thumbnail": info.get("thumbnail", f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"),
                "duration": duration,
                "video_id": video_id,
            }
            
    except yt_dlp.utils.DownloadError as e:
        if "bot" in str(e).lower() or "sign in" in str(e).lower():
            raise YouTubeError("YouTube detectó el servidor como bot (client spoofing falló).")
        if "Requested format is not available" in str(e):
            raise YouTubeError("El formato de audio no está disponible para estos clientes (Android/iOS).")
        raise YouTubeError(f"Error de yt-dlp: {e}")
    except YouTubeError:
        raise
    except Exception as e:
        raise YouTubeError(f"Error inesperado con yt-dlp: {e}")


def extract_audio(url: str, job_id: str) -> dict:
    """
    Extrae el audio de un video de YouTube.
    """
    video_id = validate_youtube_url(url)
    output_dir = TEMP_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[YouTube] Intentando yt-dlp con client spoofing (Android/TV)...")
    try:
        result = _try_ytdlp(url, video_id, output_dir)
        if result:
            print(f"[YouTube] ✓ Descarga exitosa: {result['title']}")
            return result
    except YouTubeError as e:
        raise YouTubeError(f"No se pudo descargar el audio. Detalles: {str(e)}")
        
    raise YouTubeError("Método falló sin reportar error específico.")
