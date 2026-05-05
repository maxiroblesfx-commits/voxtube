"""
VoxTube — Servicio de extracción de audio de YouTube.

Usa Piped API (proxy público de YouTube) como método principal.
Piped descarga el video en sus servidores, evitando el bloqueo
de YouTube contra IPs de servidores cloud.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from urllib.request import Request, urlopen

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

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = Request(url)
    req.add_header("User-Agent", _UA)
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _download_file(url: str, dest: Path, timeout: int = 180) -> bool:
    """Descarga un archivo por streaming."""
    try:
        req = Request(url)
        req.add_header("User-Agent", _UA)
        with urlopen(req, timeout=timeout) as resp:
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(16384)
                    if not chunk:
                        break
                    f.write(chunk)
        return dest.exists() and dest.stat().st_size > 1000
    except Exception as e:
        print(f"  [Download] Error: {e}")
        return False


def _convert_to_mp3(input_path: Path, output_path: Path) -> bool:
    """Convierte cualquier audio a MP3 con FFmpeg."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(input_path), "-vn",
             "-acodec", "libmp3lame", "-q:a", "4", str(output_path)],
            capture_output=True, timeout=120
        )
        return output_path.exists() and output_path.stat().st_size > 1000
    except Exception as e:
        print(f"  [FFmpeg] Error: {e}")
        return False


def _get_thumbnail(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


def _get_metadata_oembed(video_id: str) -> dict:
    """Obtiene título via oEmbed (nunca requiere auth)."""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        raw = _http_get(url, timeout=10)
        data = json.loads(raw.decode("utf-8"))
        return {
            "title": data.get("title", "Sin título"),
            "thumbnail": data.get("thumbnail_url", _get_thumbnail(video_id)),
        }
    except Exception:
        return {"title": "Sin título", "thumbnail": _get_thumbnail(video_id)}


# ─── Piped Instances ────────────────────────────────────

# Instancia confirmada activa (05/2026)
PIPED_INSTANCES = [
    "https://api.piped.private.coffee",
]


def _fetch_live_piped_instances() -> list[str]:
    """Obtiene instancias Piped activas dinámicamente."""
    try:
        raw = _http_get("https://piped-instances.kavin.rocks/", timeout=10)
        data = json.loads(raw.decode("utf-8"))
        urls = []
        for inst in data:
            api_url = inst.get("api_url", "")
            uptime = inst.get("uptime_24h", 0)
            if api_url and uptime > 90:
                urls.append(api_url)
        print(f"  [Piped] Encontradas {len(urls)} instancias activas")
        return urls
    except Exception as e:
        print(f"  [Piped] No se pudo obtener lista dinámica: {e}")
        return []


def _get_piped_instances() -> list[str]:
    """Devuelve lista de instancias: hardcodeadas + dinámicas."""
    dynamic = _fetch_live_piped_instances()
    # Poner las hardcodeadas primero (sabemos que funcionan)
    all_instances = list(PIPED_INSTANCES)
    for url in dynamic:
        if url not in all_instances:
            all_instances.append(url)
    return all_instances


# ─── Descarga via Piped ─────────────────────────────────

def _try_piped(video_id: str, output_dir: Path) -> dict | None:
    """Descarga audio usando Piped (proxy público de YouTube)."""
    instances = _get_piped_instances()

    if not instances:
        raise YouTubeError("[Piped] No hay instancias disponibles")

    last_error = "Error desconocido"
    for instance in instances:
        try:
            print(f"  [Piped] Probando {instance}...")
            raw = _http_get(f"{instance}/streams/{video_id}", timeout=20)
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
                last_error = f"{instance}: sin audio streams"
                continue

            # Ordenar por bitrate (mejor calidad primero)
            audio_streams.sort(key=lambda s: s.get("bitrate", 0), reverse=True)

            # Intentar descargar el mejor stream disponible
            stream_success = False
            for stream in audio_streams[:3]:  # probar los 3 mejores
                stream_url = stream.get("url")
                if not stream_url:
                    continue

                mime = stream.get("mimeType", stream.get("type", ""))
                print(f"  [Piped] Descargando stream: {mime}, bitrate={stream.get('bitrate')}")

                raw_path = output_dir / "audio_raw"
                if not _download_file(stream_url, raw_path):
                    last_error = f"{instance}: Descarga de archivo HTTP falló"
                    continue

                # Convertir a MP3 con FFmpeg
                mp3_path = output_dir / "audio.mp3"
                if not _convert_to_mp3(raw_path, mp3_path):
                    last_error = f"{instance}: FFmpeg no pudo convertir el audio"
                    continue

                # Limpiar archivo temporal
                raw_path.unlink(missing_ok=True)

                print(f"  [Piped] ✓ Éxito con {instance}: {title}")
                return {
                    "audio_path": str(mp3_path),
                    "title": title,
                    "thumbnail": thumbnail,
                    "duration": duration,
                    "video_id": video_id,
                }
                
            if not stream_success:
                continue

        except YouTubeError:
            raise
        except Exception as e:
            last_error = f"{instance} falló: {e}"
            continue

    raise YouTubeError(last_error)


# ─── Fallback: pytubefix ────────────────────────────────

def _try_pytubefix(url: str, video_id: str, output_dir: Path) -> dict | None:
    """Último recurso: pytubefix directo a YouTube."""
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

        path = audio_stream.download(output_path=str(output_dir), filename="audio.mp3")

        if Path(path).exists() and Path(path).stat().st_size > 1000:
            print(f"  [pytubefix] ✓ Éxito: {yt.title}")
            return {
                "audio_path": path,
                "title": yt.title,
                "thumbnail": yt.thumbnail_url,
                "duration": duration,
                "video_id": video_id,
            }
        return None

    except YouTubeError:
        raise
    except Exception as e:
        print(f"  [pytubefix] Falló: {e}")
        return None


# ─── Main Entry Point ───────────────────────────────────

def extract_audio(url: str, job_id: str) -> dict:
    """
    Extrae el audio de un video de YouTube.
    Prueba Piped API primero, luego pytubefix como fallback.
    """
    video_id = validate_youtube_url(url)
    output_dir = TEMP_DIR / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    strategies = [
        ("Piped API", lambda: _try_piped(video_id, output_dir)),
        ("pytubefix", lambda: _try_pytubefix(url, video_id, output_dir)),
    ]

    errors = []
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
            else:
                errors.append(f"{name} devolvió None")
        except YouTubeError as e:
            errors.append(f"{name}: {str(e)}")
            if "dura" in str(e).lower():
                raise e
        except Exception as e:
            errors.append(f"{name}: {str(e)}")
            continue

    raise YouTubeError(
        f"No se pudo descargar el audio. Detalles: {' | '.join(errors)}"
    )
