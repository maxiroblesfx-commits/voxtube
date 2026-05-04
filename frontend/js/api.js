/**
 * VoxTube — API Communication Layer
 */
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://localhost:8000"
  : "https://voxtube-api.onrender.com"; // Cambiar a tu URL de Render

/**
 * Inicia la traducción de un video.
 * @param {string} url - URL del video de YouTube
 * @param {string} targetLang - Código del idioma destino
 * @param {string} gender - Género de la voz (female/male)
 * @returns {Promise<{job_id: string}>}
 */
export async function startTranslation(url, targetLang, gender = "female") {
  const res = await fetch(`${API_BASE}/api/translate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, target_language: targetLang, gender }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Error de conexión con el servidor." }));
    throw new Error(err.detail || "Error al iniciar la traducción.");
  }

  return res.json();
}

/**
 * Consulta el estado de un job.
 * @param {string} jobId
 * @returns {Promise<Object>} JobStatus
 */
export async function getJobStatus(jobId) {
  const res = await fetch(`${API_BASE}/api/status/${jobId}`);

  if (!res.ok) {
    throw new Error("No se pudo obtener el estado del job.");
  }

  return res.json();
}

/**
 * Obtiene la URL completa del audio traducido.
 * @param {string} jobId
 * @returns {string}
 */
export function getAudioUrl(jobId) {
  return `${API_BASE}/api/audio/${jobId}`;
}

/**
 * Obtiene la lista de idiomas soportados.
 * @returns {Promise<{languages: Array<{code: string, name: string}>}>}
 */
export async function getLanguages() {
  const res = await fetch(`${API_BASE}/api/languages`);
  if (!res.ok) throw new Error("No se pudieron obtener los idiomas.");
  return res.json();
}

/**
 * Polling de estado con callback.
 * @param {string} jobId
 * @param {function} onUpdate - Callback con el estado actual
 * @param {number} intervalMs - Intervalo de polling en ms
 * @returns {function} Función para detener el polling
 */
export function pollJobStatus(jobId, onUpdate, intervalMs = 3000) {
  let active = true;

  const poll = async () => {
    while (active) {
      try {
        const status = await getJobStatus(jobId);
        onUpdate(status);

        if (status.status === "completed" || status.status === "failed") {
          break;
        }
      } catch (err) {
        onUpdate({ status: "failed", error: err.message });
        break;
      }

      await new Promise((r) => setTimeout(r, intervalMs));
    }
  };

  poll();

  return () => { active = false; };
}
