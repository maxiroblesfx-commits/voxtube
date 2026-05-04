"""
VoxTube — Configuración centralizada del backend.
"""
import os
from pathlib import Path

# ─── Rutas ───────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# ─── Whisper ─────────────────────────────────────────────
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

# ─── Límites ─────────────────────────────────────────────
MAX_VIDEO_DURATION_SECONDS = int(os.getenv("MAX_VIDEO_DURATION", "600"))  # 10 min
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "3"))

# ─── CORS ────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000"
).split(",")

# ─── Edge-TTS — Voces por idioma (las mejores disponibles) ─
VOICE_MAP: dict[str, dict[str, str]] = {
    "es":    {"female": "es-MX-DaliaNeural", "male": "es-MX-JorgeNeural"},
    "en":    {"female": "en-US-JennyNeural", "male": "en-US-GuyNeural"},
    "pt":    {"female": "pt-BR-FranciscaNeural", "male": "pt-BR-AntonioNeural"},
    "fr":    {"female": "fr-FR-DeniseNeural", "male": "fr-FR-HenriNeural"},
    "de":    {"female": "de-DE-KatjaNeural", "male": "de-DE-KillianNeural"},
    "it":    {"female": "it-IT-ElsaNeural", "male": "it-IT-DiegoNeural"},
    "ja":    {"female": "ja-JP-NanamiNeural", "male": "ja-JP-KeitaNeural"},
    "ko":    {"female": "ko-KR-SunHiNeural", "male": "ko-KR-InJoonNeural"},
    "zh":    {"female": "zh-CN-XiaoxiaoNeural", "male": "zh-CN-YunxiNeural"},
    "ru":    {"female": "ru-RU-SvetlanaNeural", "male": "ru-RU-DmitryNeural"},
    "ar":    {"female": "ar-SA-ZariyahNeural", "male": "ar-SA-HamedNeural"},
    "hi":    {"female": "hi-IN-SwaraNeural", "male": "hi-IN-MadhurNeural"},
    "tr":    {"female": "tr-TR-EmelNeural", "male": "tr-TR-AhmetNeural"},
    "pl":    {"female": "pl-PL-ZofiaNeural", "male": "pl-PL-MarekNeural"},
    "nl":    {"female": "nl-NL-ColetteNeural", "male": "nl-NL-MaartenNeural"},
    "sv":    {"female": "sv-SE-SofieNeural", "male": "sv-SE-MattiasNeural"},
    "da":    {"female": "da-DK-ChristelNeural", "male": "da-DK-JeppeNeural"},
    "fi":    {"female": "fi-FI-NooraNeural", "male": "fi-FI-HarriNeural"},
    "el":    {"female": "el-GR-AthinaNeural", "male": "el-GR-NestorasNeural"},
    "he":    {"female": "he-IL-HilaNeural", "male": "he-IL-AvriNeural"},
    "id":    {"female": "id-ID-GadisNeural", "male": "id-ID-ArdiNeural"},
    "ms":    {"female": "ms-MY-YasminNeural", "male": "ms-MY-OsmanNeural"},
    "th":    {"female": "th-TH-PremwadeeNeural", "male": "th-TH-NiwatNeural"},
    "vi":    {"female": "vi-VN-HoaiMyNeural", "male": "vi-VN-NamMinhNeural"},
    "uk":    {"female": "uk-UA-PolinaNeural", "male": "uk-UA-OstapNeural"},
    "cs":    {"female": "cs-CZ-VlastaNeural", "male": "cs-CZ-AntoninNeural"},
    "ro":    {"female": "ro-RO-AlinaNeural", "male": "ro-RO-EmilNeural"},
    "hu":    {"female": "hu-HU-NoemiNeural", "male": "hu-HU-TamasNeural"},
    "bg":    {"female": "bg-BG-KalinaNeural", "male": "bg-BG-BorislavNeural"},
    "hr":    {"female": "hr-HR-GabrijelaNeural", "male": "hr-HR-SreckoNeural"},
    "sk":    {"female": "sk-SK-ViktoriaNeural", "male": "sk-SK-LukasNeural"},
    "ca":    {"female": "ca-ES-JoanaNeural", "male": "ca-ES-EnricNeural"},
    "fil":   {"female": "fil-PH-BlessicaNeural", "male": "fil-PH-AngeloNeural"},
}

# ─── Idiomas soportados (label para frontend) ───────────
SUPPORTED_LANGUAGES: dict[str, str] = {
    "es":   "Español",
    "en":   "English",
    "pt":   "Português",
    "fr":   "Français",
    "de":   "Deutsch",
    "it":   "Italiano",
    "ja":   "日本語",
    "ko":   "한국어",
    "zh":   "中文",
    "ru":   "Русский",
    "ar":   "العربية",
    "hi":   "हिन्दी",
    "tr":   "Türkçe",
    "pl":   "Polski",
    "nl":   "Nederlands",
    "sv":   "Svenska",
    "da":   "Dansk",
    "fi":   "Suomi",
    "el":   "Ελληνικά",
    "he":   "עברית",
    "id":   "Bahasa Indonesia",
    "ms":   "Bahasa Melayu",
    "th":   "ไทย",
    "vi":   "Tiếng Việt",
    "uk":   "Українська",
    "cs":   "Čeština",
    "ro":   "Română",
    "hu":   "Magyar",
    "bg":   "Български",
    "hr":   "Hrvatski",
    "sk":   "Slovenčina",
    "ca":   "Català",
    "fil":  "Filipino",
}
