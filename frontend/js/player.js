/**
 * VoxTube — Player: sincroniza video de YouTube con audio traducido.
 *
 * Usa la YouTube IFrame API para embeber el video y un <audio> nativo
 * para reproducir el audio traducido en paralelo.
 */

let ytPlayer = null;
let audioElement = null;
let syncInterval = null;

/**
 * Carga la YouTube IFrame API si no está cargada.
 */
function loadYouTubeAPI() {
  return new Promise((resolve) => {
    if (window.YT && window.YT.Player) {
      resolve();
      return;
    }

    const tag = document.createElement("script");
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);

    window.onYouTubeIframeAPIReady = () => resolve();
  });
}

/**
 * Inicializa el reproductor con video de YouTube y audio traducido.
 * @param {string} videoId - ID del video de YouTube
 * @param {string} audioUrl - URL del audio traducido
 * @param {HTMLElement} videoContainer - Contenedor del video
 * @param {HTMLElement} audioContainer - Contenedor de controles de audio
 */
export async function initPlayer(videoId, audioUrl, videoContainer, audioContainer) {
  await loadYouTubeAPI();

  // Limpiar reproductor anterior
  destroyPlayer();

  // ── Video de YouTube ──
  const videoDiv = document.createElement("div");
  videoDiv.id = "yt-player";
  videoContainer.innerHTML = "";
  videoContainer.appendChild(videoDiv);

  ytPlayer = new YT.Player("yt-player", {
    videoId: videoId,
    width: "100%",
    height: "100%",
    playerVars: {
      autoplay: 0,
      controls: 1,
      modestbranding: 1,
      rel: 0,
      playsinline: 1, // Importante para iOS
    },
    events: {
      onStateChange: onPlayerStateChange,
    },
  });

  // ── Audio traducido ──
  audioElement = new Audio(audioUrl);
  audioElement.preload = "auto";

  // Crear controles personalizados
  renderAudioControls(audioContainer);
}

/**
 * Sincroniza play/pause del video con el audio.
 */
function onPlayerStateChange(event) {
  if (!audioElement) return;

  switch (event.data) {
    case YT.PlayerState.PLAYING:
      syncAudioToVideo();
      audioElement.play().catch(() => {});
      startSync();
      break;

    case YT.PlayerState.PAUSED:
      audioElement.pause();
      stopSync();
      break;

    case YT.PlayerState.ENDED:
      audioElement.pause();
      audioElement.currentTime = 0;
      stopSync();
      break;

    case YT.PlayerState.BUFFERING:
      audioElement.pause();
      break;
  }
}

/**
 * Sincroniza la posición del audio con el video.
 */
function syncAudioToVideo() {
  if (!ytPlayer || !audioElement) return;

  const videoTime = ytPlayer.getCurrentTime();
  const diff = Math.abs(audioElement.currentTime - videoTime);

  // Solo corregir si la diferencia es mayor a 0.5s
  if (diff > 0.5) {
    audioElement.currentTime = videoTime;
  }
}

function startSync() {
  stopSync();
  syncInterval = setInterval(syncAudioToVideo, 1000);
}

function stopSync() {
  if (syncInterval) {
    clearInterval(syncInterval);
    syncInterval = null;
  }
}

/**
 * Renderiza los controles de audio traducido.
 */
function renderAudioControls(container) {
  container.innerHTML = `
    <div class="audio-controls">
      <div class="audio-controls__row">
        <button id="btn-play-all" class="btn-play" title="Reproducir todo">
          <svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28">
            <path d="M8 5v14l11-7z"/>
          </svg>
        </button>

        <div class="volume-control">
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
          </svg>
          <label for="volume-original" class="sr-only">Volumen original</label>
          <input type="range" id="volume-original" min="0" max="100" value="15"
                 class="volume-slider" title="Volumen video original" />
          <span class="volume-label">Original</span>
        </div>

        <div class="volume-control">
          <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
            <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
          </svg>
          <label for="volume-translated" class="sr-only">Volumen traducido</label>
          <input type="range" id="volume-translated" min="0" max="100" value="100"
                 class="volume-slider translated" title="Volumen audio traducido" />
          <span class="volume-label">Traducido</span>
        </div>
      </div>
    </div>
  `;

  // Event listeners
  const btnPlay = container.querySelector("#btn-play-all");
  const volOriginal = container.querySelector("#volume-original");
  const volTranslated = container.querySelector("#volume-translated");

  btnPlay.addEventListener("click", () => {
    if (ytPlayer && ytPlayer.getPlayerState() === YT.PlayerState.PLAYING) {
      ytPlayer.pauseVideo();
      if (audioElement) audioElement.pause();
      btnPlay.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28"><path d="M8 5v14l11-7z"/></svg>`;
    } else if (ytPlayer) {
      ytPlayer.playVideo();
      if (audioElement) audioElement.play().catch(e => console.error("Audio blocked:", e));
      btnPlay.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" width="28" height="28"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>`;
    }
  });

  volOriginal.addEventListener("input", (e) => {
    if (ytPlayer) ytPlayer.setVolume(parseInt(e.target.value));
  });

  volTranslated.addEventListener("input", (e) => {
    if (audioElement) audioElement.volume = parseInt(e.target.value) / 100;
  });

  // Volumen inicial: video bajo, traducción alto
  if (ytPlayer && typeof ytPlayer.setVolume === "function") {
    ytPlayer.setVolume(15);
  }
  if (audioElement) {
    audioElement.volume = 1.0;
  }
}

/**
 * Destruye el reproductor.
 */
export function destroyPlayer() {
  stopSync();

  if (ytPlayer && typeof ytPlayer.destroy === "function") {
    try { ytPlayer.destroy(); } catch (e) { /* ignore */ }
    ytPlayer = null;
  }

  if (audioElement) {
    audioElement.pause();
    audioElement.src = "";
    audioElement = null;
  }
}
