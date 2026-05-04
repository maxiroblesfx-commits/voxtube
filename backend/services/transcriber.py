"""
VoxTube — Servicio de transcripción con faster-whisper.
"""
from __future__ import annotations

from dataclasses import dataclass

import whisper

from config import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE_TYPE

@dataclass
class Segment:
    """Un segmento transcrito con timestamps."""
    start: float
    end: float
    text: str

# Singleton del modelo (se carga una sola vez)
_model = None

def _get_model():
    """Carga lazy del modelo Whisper."""
    global _model
    if _model is None:
        # openai-whisper no usa compute_type directamente en load_model
        _model = whisper.load_model(WHISPER_MODEL, device=WHISPER_DEVICE)
    return _model

def transcribe(audio_path: str) -> tuple[list[Segment], str]:
    """
    Transcribe un archivo de audio.

    Returns:
        (segments, detected_language)
    """
    model = _get_model()

    result = model.transcribe(audio_path)

    segments: list[Segment] = []
    for seg in result["segments"]:
        text = seg["text"].strip()
        if text:
            segments.append(Segment(
                start=round(seg["start"], 2),
                end=round(seg["end"], 2),
                text=text,
            ))

    detected_lang = result.get("language", "unknown")
    return segments, detected_lang
