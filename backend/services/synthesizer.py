"""
VoxTube — Servicio de síntesis de voz con edge-tts.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts

from config import VOICE_MAP, TEMP_DIR
from services.transcriber import Segment


def get_voice_for_language(lang_code: str, gender: str = "female") -> str:
    """Obtiene la voz Edge-TTS para un idioma dado y género."""
    voice_options = VOICE_MAP.get(lang_code)
    if isinstance(voice_options, dict):
        return voice_options.get(gender, voice_options.get("female", "en-US-JennyNeural"))
    elif isinstance(voice_options, str):
        return voice_options
    return "en-US-JennyNeural"


async def _synthesize_segment(
    text: str,
    voice: str,
    output_path: Path,
) -> None:
    """Sintetiza un segmento de texto a audio."""
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(output_path))


async def _synthesize_all(
    segments: list[Segment],
    voice: str,
    job_dir: Path,
) -> list[dict]:
    """Sintetiza todos los segmentos de forma secuencial."""
    tts_dir = job_dir / "tts_segments"
    tts_dir.mkdir(exist_ok=True)

    results: list[dict] = []

    for i, seg in enumerate(segments):
        output_path = tts_dir / f"seg_{i:04d}.mp3"
        try:
            await _synthesize_segment(seg.text, voice, output_path)
            # Verify file was actually written
            file_size = output_path.stat().st_size if output_path.exists() else 0
            if file_size == 0:
                print(f"  [TTS] WARNING: Segment {i} produced empty file for text: {seg.text[:50]}...")
                results.append({
                    "index": i,
                    "path": "",
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "success": False,
                    "error": "TTS produced empty file",
                })
            else:
                print(f"  [TTS] OK: Segment {i} = {file_size} bytes")
                results.append({
                    "index": i,
                    "path": str(output_path),
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "success": True,
                })
        except Exception as e:
            print(f"  [TTS] ERROR: Segment {i}: {e}")
            results.append({
                "index": i,
                "path": "",
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "success": False,
                "error": str(e),
            })

    return results


def synthesize_segments(
    segments: list[Segment],
    target_lang: str,
    gender: str,
    job_id: str,
) -> list[dict]:
    """
    Genera audio TTS para cada segmento traducido.

    Returns:
        Lista de dicts con path, start, end, success para cada segmento.
    """
    voice = get_voice_for_language(target_lang, gender)
    job_dir = TEMP_DIR / job_id

    # edge-tts es async, lo ejecutamos en un event loop
    loop = asyncio.new_event_loop()
    try:
        results = loop.run_until_complete(
            _synthesize_all(segments, voice, job_dir)
        )
    finally:
        loop.close()

    return results
