"""
VoxTube — Modelo de datos de segmentos.
(Whisper ha sido removido de la arquitectura para ahorrar memoria y evitar bloqueos)
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Segment:
    """Un segmento de texto con timestamps (antes de Whisper, ahora de subtítulos)."""
    start: float
    end: float
    text: str
