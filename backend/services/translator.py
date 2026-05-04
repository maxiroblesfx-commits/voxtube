"""
VoxTube — Servicio de traducción con deep-translator.
"""
from __future__ import annotations

from deep_translator import GoogleTranslator

from services.transcriber import Segment


def translate_segments(
    segments: list[Segment],
    source_lang: str,
    target_lang: str,
) -> list[Segment]:
    """
    Traduce una lista de segmentos manteniendo los timestamps originales.

    Args:
        segments: Segmentos con texto original
        source_lang: Código del idioma fuente (auto para auto-detectar)
        target_lang: Código del idioma destino

    Returns:
        Lista de segmentos con texto traducido
    """
    if source_lang == target_lang:
        return segments

    # Usar "auto" si el idioma fuente no se detectó bien
    src = source_lang if source_lang != "unknown" else "auto"

    translator = GoogleTranslator(source=src, target=target_lang)

    translated: list[Segment] = []

    # Traducir en batches de texto para eficiencia
    # deep-translator soporta batches, pero hacemos individual para mantener
    # la relación 1:1 con los timestamps
    batch_size = 20
    for i in range(0, len(segments), batch_size):
        batch = segments[i : i + batch_size]
        texts = [seg.text for seg in batch]

        try:
            results = translator.translate_batch(texts)
        except Exception:
            # Fallback: traducir uno a uno
            results = []
            for text in texts:
                try:
                    results.append(translator.translate(text))
                except Exception:
                    results.append(text)  # Mantener original si falla

        for seg, translated_text in zip(batch, results):
            translated.append(Segment(
                start=seg.start,
                end=seg.end,
                text=translated_text or seg.text,
            ))

    return translated
