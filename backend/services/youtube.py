"""
VoxTube — Servicio de extracción de subtítulos de YouTube.

En lugar de descargar el audio (bloqueado por YouTube en servidores cloud),
extraemos los subtítulos auto-generados vía Piped API.
Esto elimina la necesidad de descargar audio Y de transcribir con Whisper.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from config import TEMP_DIR, MAX_VIDEO_DURATION_SECONDS
from services.transcriber import Segment


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


def _get_thumbnail(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


# ─── Piped Instances ────────────────────────────────────

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
        return urls
    except Exception:
        return []


def _get_piped_instances() -> list[str]:
    dynamic = _fetch_live_piped_instances()
    all_instances = list(PIPED_INSTANCES)
    for url in dynamic:
        if url not in all_instances:
            all_instances.append(url)
    return all_instances


# ─── VTT Parser ─────────────────────────────────────────

def _parse_vtt(vtt_text: str) -> list[Segment]:
    """Parsea un archivo VTT y devuelve una lista de Segments."""
    segments = []
    lines = vtt_text.strip().split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Buscar línea de timestamp: 00:00:01.234 --> 00:00:05.678
        if "-->" in line:
            parts = line.split("-->")
            if len(parts) == 2:
                start = _vtt_time_to_seconds(parts[0].strip())
                end = _vtt_time_to_seconds(parts[1].strip())

                # Recoger texto de las líneas siguientes
                text_lines = []
                i += 1
                while i < len(lines) and lines[i].strip() and "-->" not in lines[i]:
                    text_line = lines[i].strip()
                    # Remover tags HTML de VTT (<c>, </c>, etc.)
                    text_line = re.sub(r"<[^>]+>", "", text_line)
                    if text_line:
                        text_lines.append(text_line)
                    i += 1

                text = " ".join(text_lines).strip()
                if text and start is not None and end is not None:
                    segments.append(Segment(
                        start=round(start, 2),
                        end=round(end, 2),
                        text=text,
                    ))
                continue
        i += 1

    # Eliminar duplicados consecutivos (YouTube VTT repite líneas)
    cleaned = []
    for seg in segments:
        if not cleaned or seg.text != cleaned[-1].text:
            cleaned.append(seg)

    return cleaned


def _vtt_time_to_seconds(time_str: str) -> float | None:
    """Convierte '00:01:23.456' o '01:23.456' a segundos."""
    try:
        # Remover posibles posiciones de caracteres extra
        time_str = time_str.split(" ")[0]
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except (ValueError, IndexError):
        pass
    return None


# ─── Main Functions ──────────────────────────────────────

def extract_subtitles(url: str, job_id: str) -> dict:
    """
    Extrae los subtítulos de un video de YouTube vía Piped API.
    
    Returns:
        dict con: segments, detected_lang, title, thumbnail, duration, video_id
    """
    video_id = validate_youtube_url(url)
    instances = _get_piped_instances()

    if not instances:
        raise YouTubeError("No hay instancias Piped disponibles.")

    last_error = ""
    for instance in instances:
        try:
            print(f"[YouTube] Probando {instance} para subtítulos...")
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

            # Buscar subtítulos
            subtitles = data.get("subtitles", [])
            if not subtitles:
                raise YouTubeError(
                    "Este video no tiene subtítulos disponibles. "
                    "Probá con otro video que tenga subtítulos o CC activados."
                )

            # Priorizar: auto-generated primero (más común), luego manuales
            best_sub = None
            detected_lang = "en"

            for sub in subtitles:
                code = sub.get("code", "")
                is_auto = sub.get("autoGenerated", False)
                sub_url = sub.get("url", "")
                if sub_url:
                    if best_sub is None or is_auto:
                        best_sub = sub
                        detected_lang = code

            if not best_sub or not best_sub.get("url"):
                raise YouTubeError("No se encontró un archivo de subtítulos descargable.")

            # Descargar el archivo de subtítulos (VTT)
            sub_url = best_sub["url"]
            print(f"[YouTube] Descargando subtítulos ({best_sub.get('name', '?')})...")
            vtt_raw = _http_get(sub_url, timeout=15)
            vtt_text = vtt_raw.decode("utf-8")

            # Parsear VTT
            segments = _parse_vtt(vtt_text)
            if not segments:
                raise YouTubeError("Los subtítulos no contienen texto.")

            print(f"[YouTube] ✓ Subtítulos extraídos: {len(segments)} segmentos, idioma: {detected_lang}")
            return {
                "segments": segments,
                "detected_lang": detected_lang,
                "title": title,
                "thumbnail": thumbnail,
                "duration": duration,
                "video_id": video_id,
            }

        except YouTubeError:
            raise
        except Exception as e:
            last_error = f"{instance}: {str(e)}"
            print(f"[YouTube] {last_error}")
            continue

    raise YouTubeError(
        f"No se pudieron obtener los subtítulos. Último error: {last_error}"
    )
