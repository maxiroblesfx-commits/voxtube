"""
VoxTube — Schemas Pydantic para request/response.
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


class JobStep(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    TRANSLATING = "translating"
    SYNTHESIZING = "synthesizing"
    MIXING = "mixing"
    COMPLETED = "completed"
    FAILED = "failed"


class TranslateRequest(BaseModel):
    """Payload que envía el frontend."""
    url: str = Field(..., description="URL del video de YouTube")
    target_language: str = Field(..., description="Código de idioma destino (es, en, pt, ...)")
    gender: str = Field("female", description="Género de la voz (female o male)")


class TranslateResponse(BaseModel):
    """Respuesta inmediata al iniciar traducción."""
    job_id: str
    status: JobStep = JobStep.QUEUED
    message: str = "Traducción en cola de procesamiento"


class JobStatus(BaseModel):
    """Estado completo de un job de traducción."""
    job_id: str
    status: JobStep
    progress: int = Field(0, ge=0, le=100, description="Porcentaje de progreso")
    step_label: str = ""
    video_title: str = ""
    video_thumbnail: str = ""
    video_duration: float = 0
    detected_language: str = ""
    audio_url: str | None = None
    error: str | None = None


class LanguageInfo(BaseModel):
    """Info de un idioma soportado."""
    code: str
    name: str


class LanguagesResponse(BaseModel):
    """Lista de idiomas disponibles."""
    languages: list[LanguageInfo]
