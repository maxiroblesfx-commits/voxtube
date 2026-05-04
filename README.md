# VoxTube 🌐

**Traducí videos de YouTube a cualquier idioma con voz sintetizada.**

VoxTube es una Progressive Web App (PWA) mobile-first que permite traducir videos de YouTube y reproducirlos con audio en el idioma que elijas.

## 🚀 Stack Tecnológico

### Frontend (PWA)
- HTML5 / CSS3 / JavaScript Vanilla
- Service Worker para funcionalidad offline
- Diseño mobile-first con glassmorphism

### Backend (API)
- **Python 3.11 + FastAPI** — API REST
- **yt-dlp** — Extracción de audio de YouTube
- **faster-whisper** — Transcripción Speech-to-Text
- **deep-translator** — Traducción de texto
- **edge-tts** — Síntesis de voz (Text-to-Speech)
- **pydub + FFmpeg** — Mezcla y sincronización de audio

## 📦 Instalación Local

### Requisitos
- Python 3.11+
- FFmpeg instalado y en PATH
- Node.js (opcional, para servir el frontend)

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
# Opción 1: Python
python -m http.server 5500

# Opción 2: npx
npx serve -l 5500
```

Abrí `http://localhost:5500` en tu navegador.

## 🌍 Deploy

### Backend → Render.com (Gratis)
1. Conectá tu repo de GitHub en [render.com](https://render.com)
2. Render detectará el `render.yaml` automáticamente
3. Deploy automático con cada push

### Frontend → Vercel (Gratis)
1. Conectá tu repo en [vercel.com](https://vercel.com)
2. Root directory: `frontend/`
3. Deploy automático con cada push

## 📱 Idiomas Soportados

Español, English, Português, Français, Deutsch, Italiano, 日本語, 한국어, 中文, Русский, العربية, हिन्दी, Türkçe, Polski, Nederlands, y más (33 idiomas).

## 📄 Licencia

MIT
