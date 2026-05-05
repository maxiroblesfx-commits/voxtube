"""
VoxTube — Servicio de extracción de subtítulos de YouTube.

Utilizamos pytubefix directo (client='WEB') para extraer subtítulos (captions) 
ya que YouTube no bloquea la lectura de subtítulos a IPs de datacenters.
Esto evita 100% el problema de bloqueo antibot de descargas de medios.
"""
from __future__ import annotations

import re
from pathlib import Path

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


def _get_thumbnail(video_id: str) -> str:
    return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"


# ─── SRT Parser ─────────────────────────────────────────

def _srt_time_to_seconds(time_str: str) -> float | None:
    """Convierte '00:00:01,360' a segundos."""
    try:
        time_str = time_str.strip()
        parts = time_str.replace(",", ".").split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        pass
    return None


def _parse_srt(srt_text: str) -> list[Segment]:
    """Parsea un archivo SRT y devuelve una lista de Segments."""
    segments = []
    # YouTube SRT usa \n\n para separar bloques
    blocks = srt_text.strip().replace("\r\n", "\n").split("\n\n")
    
    for block in blocks:
        lines = block.split("\n")
        if len(lines) >= 3:
            time_line = lines[1]
            if "-->" in time_line:
                t_parts = time_line.split("-->")
                start = _srt_time_to_seconds(t_parts[0])
                end = _srt_time_to_seconds(t_parts[1])
                
                text = " ".join(lines[2:]).strip()
                # Limpiar tags de música como [♪♪♪] o [Música]
                text = re.sub(r"\[.*?\]", "", text).strip()
                text = re.sub(r"♪", "", text).strip()
                
                # Ignorar tags HTML (font, color, etc)
                text = re.sub(r"<[^>]+>", "", text).strip()
                
                if text and start is not None and end is not None:
                    segments.append(Segment(
                        start=round(start, 2),
                        end=round(end, 2),
                        text=text
                    ))
                    
    # Eliminar duplicados consecutivos si los hubiera
    cleaned = []
    for seg in segments:
        if not cleaned or seg.text != cleaned[-1].text:
            cleaned.append(seg)

    return cleaned


# ─── Main Functions ──────────────────────────────────────

def extract_subtitles(url: str, job_id: str) -> dict:
    """
    Extrae los subtítulos de un video de YouTube vía pytubefix.
    
    Returns:
        dict con: segments, detected_lang, title, thumbnail, duration, video_id
    """
    video_id = validate_youtube_url(url)
    
    from pytubefix import YouTube
    try:
        yt = YouTube(url, client='WEB')
        
        title = yt.title or "Sin título"
        thumbnail = yt.thumbnail_url or _get_thumbnail(video_id)
        duration = yt.length or 0

        # Verificar duración
        if duration > MAX_VIDEO_DURATION_SECONDS:
            raise YouTubeError(
                f"El video dura {duration // 60}:{duration % 60:02d} min. "
                f"Máximo permitido: {MAX_VIDEO_DURATION_SECONDS // 60} min."
            )

        if not yt.captions:
            raise YouTubeError(
                "Este video no tiene subtítulos disponibles. "
                "Probá con otro video que tenga subtítulos o CC activados."
            )
            
        print(f"[YouTube] Captions disponibles: {list(yt.captions.keys())}")

        # Priorizar: auto-generated inglés primero (más preciso), luego español, etc
        best_cap = None
        detected_lang = "en"
        
        # Buscar en orden de preferencia
        prefs = ['a.en', 'en', 'a.es', 'es']
        for pref in prefs:
            if pref in yt.captions:
                best_cap = yt.captions[pref]
                detected_lang = pref.replace('a.', '')
                break
                
        # Si no encontramos preferidos, tomamos el primero
        if best_cap is None:
            first_key = list(yt.captions.keys())[0]
            best_cap = yt.captions[first_key]
            detected_lang = first_key.replace('a.', '')[:2] # truncar 'en-GB' a 'en'

        print(f"[YouTube] Seleccionado caption: {best_cap.code}")
        
        # Generar texto SRT
        srt_text = best_cap.generate_srt_captions()
        
        # Parsear a segmentos
        segments = _parse_srt(srt_text)
        if not segments:
            raise YouTubeError("Los subtítulos están vacíos o no se pudieron leer.")

        print(f"[YouTube] ✓ Subtítulos extraídos: {len(segments)} segmentos, idioma base: {detected_lang}")
        
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
        raise YouTubeError(f"Error interno al obtener subtítulos: {str(e)}")
