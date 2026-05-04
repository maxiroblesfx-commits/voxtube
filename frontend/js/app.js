/**
 * VoxTube — Main Application Logic
 */
import { startTranslation, pollJobStatus, getAudioUrl, getLanguages } from "./api.js";
import { initPlayer, destroyPlayer } from "./player.js";

// ─── State ──────────────────────────────────────────────
let currentJobId = null;
let stopPolling = null;

// ─── DOM refs ───────────────────────────────────────────
const viewHome       = document.getElementById("view-home");
const viewProcessing = document.getElementById("view-processing");
const viewPlayer     = document.getElementById("view-player");

const urlInput       = document.getElementById("url-input");
const langSelect     = document.getElementById("lang-select");
const genderSelect   = document.getElementById("gender-select");
const btnTranslate   = document.getElementById("btn-translate");
const errorMsg       = document.getElementById("error-msg");

const procThumbnail  = document.getElementById("proc-thumbnail");
const procTitle      = document.getElementById("proc-title");
const progressFill   = document.getElementById("progress-fill");
const progressStep   = document.getElementById("progress-step");
const progressPct    = document.getElementById("progress-pct");
const stepItems      = document.querySelectorAll(".steps-list__item");

const videoContainer  = document.getElementById("video-container");
const audioContainer  = document.getElementById("audio-controls-container");
const playerTitle     = document.getElementById("player-title");
const playerMeta      = document.getElementById("player-meta");
const btnNewVideo     = document.getElementById("btn-new-video");
const btnDownload     = document.getElementById("btn-download");

const installBanner   = document.getElementById("install-banner");
const btnInstall      = document.getElementById("btn-install");

// ─── Init ───────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await loadLanguages();
  loadHistory();
  registerServiceWorker();
  setupPWAInstall();
});

// ─── Load languages from API ────────────────────────────
async function loadLanguages() {
  // Fallback languages if API is not available
  const fallbackLangs = [
    { code: "es", name: "Español" },
    { code: "en", name: "English" },
    { code: "pt", name: "Português" },
    { code: "fr", name: "Français" },
    { code: "de", name: "Deutsch" },
    { code: "it", name: "Italiano" },
    { code: "ja", name: "日本語" },
    { code: "ko", name: "한국어" },
    { code: "zh", name: "中文" },
    { code: "ru", name: "Русский" },
    { code: "ar", name: "العربية" },
    { code: "hi", name: "हिन्दी" },
    { code: "tr", name: "Türkçe" },
    { code: "pl", name: "Polski" },
    { code: "nl", name: "Nederlands" },
  ];

  let langs = fallbackLangs;

  try {
    const data = await getLanguages();
    if (data.languages && data.languages.length > 0) {
      langs = data.languages;
    }
  } catch (e) {
    console.warn("Could not load languages from API, using fallback:", e);
  }

  langSelect.innerHTML = "";
  for (const lang of langs) {
    const opt = document.createElement("option");
    opt.value = lang.code;
    opt.textContent = lang.name;
    langSelect.appendChild(opt);
  }

  // Default: español
  langSelect.value = "es";
}

// ─── View switching ─────────────────────────────────────
function showView(view) {
  viewHome.classList.remove("active");
  viewProcessing.classList.remove("active");
  viewPlayer.classList.remove("active");
  view.classList.add("active");
}

// ─── Translate ──────────────────────────────────────────
btnTranslate.addEventListener("click", async () => {
  const url = urlInput.value.trim();
  const lang = langSelect.value;
  const gender = genderSelect.value;

  // Validate
  if (!url) {
    showError("Por favor pegá una URL de YouTube.");
    urlInput.classList.add("error");
    return;
  }

  if (!isYouTubeUrl(url)) {
    showError("Esa URL no parece ser de YouTube. Verificala e intentá de nuevo.");
    urlInput.classList.add("error");
    return;
  }

  hideError();
  urlInput.classList.remove("error");
  btnTranslate.disabled = true;
  btnTranslate.innerHTML = '<span class="spinner"></span> Iniciando...';

  try {
    const res = await startTranslation(url, lang, gender);
    currentJobId = res.job_id;

    // Reset processing view
    resetProcessingView();
    showView(viewProcessing);

    // Start polling
    stopPolling = pollJobStatus(res.job_id, handleStatusUpdate);

  } catch (err) {
    showError(err.message);
  } finally {
    btnTranslate.disabled = false;
    btnTranslate.textContent = "🎬 Traducir Video";
  }
});

// Remove error class on input
urlInput.addEventListener("input", () => {
  urlInput.classList.remove("error");
  hideError();
});

// ─── Handle status updates ──────────────────────────────
function handleStatusUpdate(status) {
  if (!status) return;

  // Update thumbnail & title
  if (status.video_thumbnail) {
    procThumbnail.src = status.video_thumbnail;
    procThumbnail.style.display = "block";
  }
  if (status.video_title) {
    procTitle.textContent = status.video_title;
  }

  // Update progress
  progressFill.style.width = `${status.progress}%`;
  progressPct.textContent = `${status.progress}%`;
  progressStep.textContent = status.step_label || "";

  // Update step indicators
  updateStepIndicators(status.status);

  // Handle completion
  if (status.status === "completed") {
    showPlayerView(status);
    saveToHistory(status);
  }

  // Handle failure
  if (status.status === "failed") {
    showView(viewHome);
    showError(status.error || "Error desconocido durante el procesamiento.");
  }
}

function updateStepIndicators(currentStep) {
  const stepOrder = ["downloading", "transcribing", "translating", "synthesizing", "mixing"];
  const currentIdx = stepOrder.indexOf(currentStep);

  stepItems.forEach((item, i) => {
    const itemStep = item.dataset.step;
    const itemIdx = stepOrder.indexOf(itemStep);

    item.classList.remove("active", "done");
    const icon = item.querySelector(".step-icon");

    if (itemIdx < currentIdx) {
      item.classList.add("done");
      icon.textContent = "✓";
    } else if (itemIdx === currentIdx) {
      item.classList.add("active");
      icon.textContent = "⏳";
    } else {
      icon.textContent = "○";
    }
  });
}

// ─── Player View ────────────────────────────────────────
function showPlayerView(status) {
  const videoId = extractVideoId(urlInput.value.trim());
  const audioUrl = getAudioUrl(status.job_id);

  playerTitle.textContent = status.video_title || "Video traducido";
  playerMeta.textContent = `Idioma detectado: ${status.detected_language || "?"} → ${langSelect.options[langSelect.selectedIndex].text}`;

  showView(viewPlayer);

  // Initialize player
  initPlayer(videoId, audioUrl, videoContainer, audioContainer);
}

// ─── New video button ───────────────────────────────────
btnNewVideo.addEventListener("click", () => {
  destroyPlayer();
  urlInput.value = "";
  currentJobId = null;
  if (stopPolling) { stopPolling(); stopPolling = null; }
  showView(viewHome);
});

// ─── Download button ────────────────────────────────────
btnDownload.addEventListener("click", () => {
  if (currentJobId) {
    const a = document.createElement("a");
    a.href = getAudioUrl(currentJobId);
    a.download = `voxtube_${currentJobId}.mp3`;
    a.click();
  }
});

// ─── History ────────────────────────────────────────────
function saveToHistory(status) {
  const history = getHistory();
  history.unshift({
    jobId: status.job_id,
    title: status.video_title,
    thumbnail: status.video_thumbnail,
    lang: langSelect.options[langSelect.selectedIndex].text,
    url: urlInput.value.trim(),
    date: new Date().toISOString(),
  });

  // Keep last 10
  localStorage.setItem("voxtube_history", JSON.stringify(history.slice(0, 10)));
  loadHistory();
}

function getHistory() {
  try {
    return JSON.parse(localStorage.getItem("voxtube_history") || "[]");
  } catch { return []; }
}

function loadHistory() {
  const historyList = document.getElementById("history-list");
  const historySection = document.getElementById("history-section");
  const history = getHistory();

  if (history.length === 0) {
    historySection.style.display = "none";
    return;
  }

  historySection.style.display = "block";
  historyList.innerHTML = "";

  for (const item of history) {
    const el = document.createElement("div");
    el.className = "history-item";
    el.innerHTML = `
      <img class="history-item__thumb" src="${item.thumbnail}" alt="" loading="lazy" />
      <div class="history-item__info">
        <div class="history-item__title">${item.title}</div>
        <div class="history-item__lang">→ ${item.lang}</div>
      </div>
    `;
    el.addEventListener("click", () => {
      urlInput.value = item.url;
      langSelect.value = item.lang;
      showView(viewHome);
    });
    historyList.appendChild(el);
  }
}

// ─── Helpers ────────────────────────────────────────────
function isYouTubeUrl(url) {
  return /(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)/.test(url);
}

function extractVideoId(url) {
  const match = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/shorts\/)([a-zA-Z0-9_-]{11})/);
  return match ? match[1] : "";
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.classList.add("visible");
}

function hideError() {
  errorMsg.classList.remove("visible");
}

function resetProcessingView() {
  procThumbnail.style.display = "none";
  procTitle.textContent = "Preparando traducción...";
  progressFill.style.width = "0%";
  progressPct.textContent = "0%";
  progressStep.textContent = "En cola...";
  stepItems.forEach((item) => {
    item.classList.remove("active", "done");
    item.querySelector(".step-icon").textContent = "○";
  });
}

// ─── PWA Service Worker ─────────────────────────────────
function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js").catch((err) =>
      console.warn("SW registration failed:", err)
    );
  }
}

// ─── PWA Install Prompt ─────────────────────────────────
let deferredPrompt = null;

function setupPWAInstall() {
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installBanner.classList.add("visible");
  });

  btnInstall?.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    deferredPrompt = null;
    installBanner.classList.remove("visible");
  });
}
