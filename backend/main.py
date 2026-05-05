"""
VoxTube — FastAPI Backend.

Endpoints principales:
  POST /api/translate     → Inicia traducción, devuelve job_id
  GET  /api/status/{id}   → Consulta progreso
  GET  /api/audio/{id}    → Descarga audio traducido
  GET  /api/languages     → Lista idiomas soportados
"""
from __future__ import annotations

import shutil
import uuid
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from config import ALLOWED_ORIGINS, TEMP_DIR, SUPPORTED_LANGUAGES
from models import (
    TranslateRequest,
    TranslateResponse,
    JobStatus,
    JobStep,
    LanguageInfo,
    LanguagesResponse,
)

# ─── App ─────────────────────────────────────────────────
app = FastAPI(
    title="VoxTube API",
    description="Traduce videos de YouTube a cualquier idioma con voz sintetizada.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory job store ─────────────────────────────────
jobs: dict[str, JobStatus] = {}


def _update_job(job_id: str, **kwargs) -> None:
    """Actualiza el estado de un job."""
    if job_id in jobs:
        for key, value in kwargs.items():
            setattr(jobs[job_id], key, value)


# ─── Background processing pipeline ─────────────────────
def _process_translation(job_id: str, url: str, target_lang: str, gender: str) -> None:
    """Pipeline completo de traducción (se ejecuta en un thread)."""
    try:
        # ── Paso 1: Descargar audio ──
        _update_job(
            job_id,
            status=JobStep.DOWNLOADING,
            progress=10,
            step_label="Descargando audio del video...",
        )
        from services.youtube import extract_audio, YouTubeError
        try:
            video_info = extract_audio(url, job_id)
        except YouTubeError as e:
            _update_job(job_id, status=JobStep.FAILED, error=str(e))
            return

        _update_job(
            job_id,
            video_title=video_info["title"],
            video_thumbnail=video_info["thumbnail"],
            video_duration=video_info["duration"],
            progress=25,
        )

        # ── Paso 2: Transcribir ──
        _update_job(
            job_id,
            status=JobStep.TRANSCRIBING,
            progress=30,
            step_label="Transcribiendo audio...",
        )
        from services.transcriber import transcribe
        segments, detected_lang = transcribe(video_info["audio_path"])

        if not segments:
            _update_job(
                job_id,
                status=JobStep.FAILED,
                error="No se pudo detectar habla en el video.",
            )
            return

        _update_job(
            job_id,
            detected_language=detected_lang,
            progress=50,
        )

        # ── Paso 3: Traducir ──
        _update_job(
            job_id,
            status=JobStep.TRANSLATING,
            progress=55,
            step_label="Traduciendo texto...",
        )
        from services.translator import translate_segments
        translated_segments = translate_segments(segments, detected_lang, target_lang)
        _update_job(job_id, progress=65)

        # ── Paso 4: Sintetizar voz ──
        _update_job(
            job_id,
            status=JobStep.SYNTHESIZING,
            progress=70,
            step_label="Generando voz traducida...",
        )
        from services.synthesizer import synthesize_segments
        tts_results = synthesize_segments(translated_segments, target_lang, gender, job_id)
        _update_job(job_id, progress=85)

        # ── Paso 5: Mezclar audio ──
        _update_job(
            job_id,
            status=JobStep.MIXING,
            progress=90,
            step_label="Mezclando audio final...",
        )
        from services.audio_mixer import mix_audio
        audio_path = mix_audio(tts_results, video_info["duration"], job_id)

        # ── Completado ──
        _update_job(
            job_id,
            status=JobStep.COMPLETED,
            progress=100,
            step_label="¡Traducción completada!",
            audio_url=f"/api/audio/{job_id}",
        )

    except Exception as e:
        traceback.print_exc()
        _update_job(
            job_id,
            status=JobStep.FAILED,
            error=f"Error inesperado: {str(e)}",
        )


# ─── Endpoints ───────────────────────────────────────────

@app.post("/api/translate", response_model=TranslateResponse)
def start_translation(req: TranslateRequest):
    """Inicia la traducción de un video de YouTube."""
    # Validar idioma
    if req.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"Idioma '{req.target_language}' no soportado.")

    # Crear job
    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = JobStatus(
        job_id=job_id,
        status=JobStep.QUEUED,
        step_label="En cola de procesamiento...",
    )

    # Lanzar procesamiento en background thread
    thread = threading.Thread(
        target=_process_translation,
        args=(job_id, req.url, req.target_language, req.gender),
        daemon=True,
    )
    thread.start()

    return TranslateResponse(job_id=job_id)


@app.get("/api/status/{job_id}", response_model=JobStatus)
def get_status(job_id: str):
    """Consulta el estado de un job de traducción."""
    if job_id not in jobs:
        raise HTTPException(404, "Job no encontrado.")
    return jobs[job_id]


@app.get("/api/audio/{job_id}")
def get_audio(job_id: str):
    """Descarga el audio traducido."""
    if job_id not in jobs:
        raise HTTPException(404, "Job no encontrado.")

    job = jobs[job_id]
    if job.status != JobStep.COMPLETED:
        raise HTTPException(400, "El audio aún no está listo.")

    audio_path = TEMP_DIR / job_id / "translated_audio.mp3"
    if not audio_path.exists():
        raise HTTPException(404, "Archivo de audio no encontrado.")

    return FileResponse(
        str(audio_path),
        media_type="audio/mpeg",
        filename=f"voxtube_{job_id}.mp3",
    )


@app.get("/api/languages", response_model=LanguagesResponse)
def get_languages():
    """Devuelve la lista de idiomas soportados."""
    langs = [
        LanguageInfo(code=code, name=name)
        for code, name in SUPPORTED_LANGUAGES.items()
    ]
    return LanguagesResponse(languages=langs)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    """Elimina un job y sus archivos temporales."""
    if job_id in jobs:
        del jobs[job_id]
    job_dir = TEMP_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)
    return {"message": "Job eliminado."}


@app.get("/health")
def health():
    """Health check para Render."""
    return {"status": "ok", "service": "VoxTube API"}


@app.get("/api/debug-download")
def debug_download():
    """Diagnóstico: prueba cada método de descarga y reporta qué funciona."""
    import json as json_mod
    from urllib.request import Request, urlopen

    video_id = "dQw4w9WgXcQ"  # Rick Astley - video de prueba
    results = {}

    # Test 1: ¿Podemos resolver DNS de Piped?
    try:
        import socket
        ip = socket.getaddrinfo("api.piped.private.coffee", 443)[0][4][0]
        results["1_dns_piped"] = f"OK - IP: {ip}"
    except Exception as e:
        results["1_dns_piped"] = f"FAIL - {str(e)[:100]}"

    # Test 2: ¿Podemos obtener metadata de Piped?
    piped_data = None
    try:
        req = Request(f"https://api.piped.private.coffee/streams/{video_id}")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urlopen(req, timeout=15) as resp:
            piped_data = json_mod.loads(resp.read().decode())
        results["2_piped_metadata"] = f"OK - Title: {piped_data.get('title', '?')[:50]}"
    except Exception as e:
        results["2_piped_metadata"] = f"FAIL - {str(e)[:100]}"

    # Test 3: ¿Qué URLs de audio streams nos da Piped?
    if piped_data:
        streams = piped_data.get("audioStreams", [])
        results["3_audio_streams_count"] = len(streams)
        if streams:
            best = streams[0]
            stream_url = best.get("url", "")
            results["3_first_stream_url_preview"] = stream_url[:120] + "..."
            results["3_first_stream_type"] = best.get("mimeType", best.get("type", "?"))

            # Test 4: ¿Podemos descargar los primeros bytes del audio?
            try:
                req2 = Request(stream_url)
                req2.add_header("User-Agent", "Mozilla/5.0")
                req2.add_header("Range", "bytes=0-1023")
                with urlopen(req2, timeout=15) as resp2:
                    chunk = resp2.read(1024)
                    results["4_audio_download"] = f"OK - Got {len(chunk)} bytes, status={resp2.status}"
            except Exception as e:
                results["4_audio_download"] = f"FAIL - {str(e)[:150]}"
    else:
        results["3_audio_streams_count"] = "SKIP (metadata failed)"
        results["4_audio_download"] = "SKIP"

    # Test 5: ¿Podemos llegar a YouTube oEmbed?
    try:
        req3 = Request(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json")
        req3.add_header("User-Agent", "Mozilla/5.0")
        with urlopen(req3, timeout=10) as resp3:
            oembed = json_mod.loads(resp3.read().decode())
        results["5_youtube_oembed"] = f"OK - {oembed.get('title', '?')[:50]}"
    except Exception as e:
        results["5_youtube_oembed"] = f"FAIL - {str(e)[:100]}"

    # Test 6: ¿Podemos llegar a las instancias dinámicas de Piped?
    try:
        req4 = Request("https://piped-instances.kavin.rocks/")
        req4.add_header("User-Agent", "Mozilla/5.0")
        with urlopen(req4, timeout=10) as resp4:
            instances = json_mod.loads(resp4.read().decode())
        results["6_piped_instances_api"] = f"OK - {len(instances)} instances found"
    except Exception as e:
        results["6_piped_instances_api"] = f"FAIL - {str(e)[:100]}"

    return results
