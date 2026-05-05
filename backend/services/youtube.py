"""
VoxTube — Servicio de extracción de audio de YouTube.

Usa múltiples estrategias para evitar el bloqueo por bot:
  1. Piped API (proxy público de YouTube)
  2. Cobalt API (servicio de descarga)
  3. pytubefix (librería Python como último recurso)
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

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


# ─── Helpers ─────────────────────────────────────────────

def _http_get(url: str, timeout: int = 15) -> bytes:
    """GET request con User-Agent."""
    req = Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_post_json(url: str, data: dict, timeout: int = 30) -> dict:
    """POST JSON request."""
    body = json.dumps(data).encode("utf-8")
    req = Request(url, data=body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download_file(url: str, dest: Path, timeout: int = 180) -> bool:
    """Descarga un archivo grande por streaming."""
    try:
        req = Request(url)
        req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        with urlopen(req, timeout=timeout) as resp:
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(16384)
                    if not chunk:
                        break
                    f.write(chunk)
        return dest.exists() and dest.stat().st_size > 0
    except Exception as e:
        print(f"  [Download] Error: {e}")
        return False


def _convert_to_mp3(input_path: Path, output_path: Path) -> bool:
    """Convierte cualquier audio a MP3 con FFmpeg."""
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path), "-vn",
             "-acodec", "libmp3lame", "-q:a", "4", str(output_path)],
            capture_output=True, timeout=120
        )
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception as e:
        print(f"  [FFmpeg] Error: {e}")
        return False


def _get_thumbnail(video_id: str) -> str:
    """Devuelve la URL de thumbnail de YouTube (nunca falla)."""
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


# ─── Strategy 1: Piped API ──────────────────────────────

PIPED_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi.adminforge.de",
    "https://api.piped.projectsegfau.lt",
    "https://pipedapi.in.projectsegfau.lt",
    "https://pipedapi.r4fo.com",
]


def _try_piped(video_id: str, output_dir: Path) -> dict | None:
    """Descarga audio usando Piped (proxy público de YouTube)."""
    for instance in PIPED_INSTANCES:
        try:
            print(f"  [Piped] Probando {instance}...")
            raw = _http_get(f"{instance}/streams/{video_id}", timeout=15)
            data = json.loads(raw.decode("utf-8"))

            title = data.get("title", "Sin título")
            thumbnail = data.get("thumbnailUrl", _get_thumbnail(video_id))
            duration = data.get("duration", 0)

            # Verificar duración
            if duration > MAX_VIDEO_DURATION_SECONDS:
                raise YouTubeError(
                    f"El video dura {duration // 60}:{duration % 60:02d} min. "
                    f"Máximo permitido: {MAX_VIDEO_DURATION_SECONDS // 60} min."
                )

            # Buscar streams de audio
            audio_streams = data.get("audioStreams", [])
            if not audio_streams:
                print(f"  [Piped] {instance}: no audio streams")
                continue

            # Ordenar por bitrate (mejor primero)
            audio_streams.sort(key=lambda s: s.get("bitrate", 0), reverse=True)
            stream_url = audio_streams[0].get("url")

            if not stream_url:
                continue

            # Descargar
            raw_path = output_dir / "audio_raw"
            if not _download_file(stream_url, raw_path):
                continue

            # Convertir a MP3
            mp3_path = output_dir / "audio.mp3"
            if not _convert_to_mp3(raw_path, mp3_path):
                continue

            # Limpiar archivo temporal
            raw_path.unlink(missing_ok=True)

            print(f"  [Piped] ✓ Éxito con {instance}")
            return {
                "audio_path": str(mp3_path),
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "video_id": video_id,
            }

        except YouTubeError:
            raise
        except Exception as e:
            print(f"  [Piped] {instance} falló: {e}")
            continue

    return None


# ─── Strategy 2: Cobalt API ─────────────────────────────

COBALT_INSTANCES = [
    "https://api.cobalt.tools",
    "https://cobalt-api.kwiatekmiki.com",
]


def _try_cobalt(url: str, video_id: str, output_dir: Path) -> dict | None:
    """Descarga audio usando Cobalt (servicio de descarga de videos)."""
    for instance in COBALT_INSTANCES:
        try:
            print(f"  [Cobalt] Probando {instance}...")
            body = json.dumps({
                "url": url,
                "downloadMode": "audio",
                "audioFormat": "mp3",
            }).encode("utf-8")

            req = Request(f"{instance}/", data=body)
            req.add_header("Content-Type", "application/json")
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "Mozilla/5.0")

            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            status = data.get("status", "")
            download_url = data.get("url", "")

            if status not in ("tunnel", "redirect", "stream") or not download_url:
                print(f"  [Cobalt] {instance}: respuesta inesperada: {data}")
                continue

            mp3_path = output_dir / "audio.mp3"
            if not _download_file(download_url, mp3_path):
                continue

            print(f"  [Cobalt] ✓ Éxito con {instance}")
            return {
                "audio_path": str(mp3_path),
                "title": f"Video de YouTube",
                "thumbnail": _get_thumbnail(video_id),
                "duration": 0,
                "video_id": video_id,
            }

        except Exception as e:
            print(f"  [Cobalt] {instance} falló: {e}")
            continue

    return None


# ─── Strategy 3: pytubefix ──────────────────────────────

def _try_pytubefix(url: str, video_id: str, output_dir: Path) -> dict | None:
    """Descarga audio usando pytubefix (acceso directo a YouTube)."""
    try:
        print("  [pytubefix] Probando...")
        from pytubefix import YouTube

        yt = YouTube(url)

        duration = yt.length or 0
        if duration > MAX_VIDEO_DURATION_SECONDS:
            raise YouTubeError(
                f"El video dura {duration // 60}:{duration % 60:02d} min. "
                f"Máximo permitido: {MAX_VIDEO_DURATION_SECONDS // 60} min."
            )

        audio_stream = yt.streams.get_audio_only()
        if not audio_stream:
            print("  [pytubefix] No se encontró stream de audio")
            return None

        path = audio_stream.download(
            output_path=str(output_dir), filename="audio.mp3"
        )

        print(f"  [pytubefix] ✓ Éxito: {yt.title}")
        return {
            "audio_path": path,
            "title": yt.title,
            "thumbnail": yt.thumbnail_url,
            "duration": duration,
            "video_id": video_id,
        }

    except YouTubeError:
        raise
    except Exception as e:
        print(f"  [pytubefix] Falló: {e}")
        return None


# ─── Metadata Fallback ───────────────────────────────────

def _get_metadata_oembed(video_id: str) -> dict:
    """Obtiene título y thumbnail via oEmbed (nunca requiere auth)."""
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        raw = _http_get(oembed_url, timeout=10)
        data = json.loads(raw.decode("utf-8"))
        return {
            "title": data.get("title", "Sin título"),
            "thumbnail": data.get("thumbnail_url", _get_thumbnail(video_id)),
        }
    except Exception:
        return {
            "title": "Sin título",
            "thumbnail": _get_thumbnail(video_id),
        }


# ─── Main Entry Point ───────────────────────────────────

def extract_audio(url: str, job_id: str) -> dict:
    """
    Extrae el audio de un video de YouTube.
    Prueba múltiples estrategias en orden hasta que una funcione.
    """
    video_id = validate_youtube_url(url)
    output_dir = TEMP_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    strategies = [
        ("Piped API", lambda: _try_piped(video_id, output_dir)),
        ("Cobalt API", lambda: _try_cobalt(url, video_id, output_dir)),
        ("pytubefix", lambda: _try_pytubefix(url, video_id, output_dir)),
    ]

    for name, strategy in strategies:
        print(f"[YouTube] Intentando con {name}...")
        try:
            result = strategy()
            if result:
                # Completar metadata si falta
                if result.get("title") in (None, "", "Video de YouTube", "Sin título"):
                    meta = _get_metadata_oembed(video_id)
                    result["title"] = meta["title"]
                    result["thumbnail"] = meta["thumbnail"]
                print(f"[YouTube] ✓ Descarga exitosa via {name}: {result['title']}")
                return result
        except YouTubeError:
            raise
        except Exception as e:
            print(f"[YouTube] {name} falló: {e}")
            continue

    raise YouTubeError(
        "No se pudo descargar el audio del video. "
        "YouTube está bloqueando todos los métodos de descarga. "
        "Por favor intentá con otro video o esperá unos minutos."
    )
