import Vapi from "@vapi-ai/web";

// ── Config ──────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "";
const INITIAL_PATIENT_ID = new URLSearchParams(window.location.search).get("patientId") || "";
// const INLINE_VOICE_PROVIDER = import.meta.env.VITE_VOICE_PROVIDER || "";
// const INLINE_VOICE_ID = import.meta.env.VITE_VOICE_ID || "";

// ── DOM refs ────────────────────────────────────────────────────────
const btnStart = document.getElementById("btn-start");
const btnEnd = document.getElementById("btn-end");
const statusArea = document.getElementById("status-area");
const statusIndicator = document.getElementById("status-indicator");
const statusText = document.getElementById("status-text");
const transcript = document.getElementById("transcript");
const errorBanner = document.getElementById("error-banner");
const errorMessage = document.getElementById("error-message");
const errorDismiss = document.getElementById("error-dismiss");
const patientIdInput = document.getElementById("patient-id");

// ── State ───────────────────────────────────────────────────────────
let vapi = null;

// ── Helpers ─────────────────────────────────────────────────────────
function setStatus(state, label) {
  statusIndicator.setAttribute("data-state", state);
  statusText.textContent = label;
}

function showError(msg) {
  errorMessage.textContent = msg;
  errorBanner.classList.remove("hidden");
}

function hideError() {
  errorBanner.classList.add("hidden");
}

function formatError(err) {
  if (!err) return "Unknown error";
  if (typeof err === "string") return err;
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "object") {
    const obj = err;
    if (obj.message) return String(obj.message);
    if (obj.error) return typeof obj.error === "string" ? obj.error : JSON.stringify(obj.error);
    if (obj.details) return typeof obj.details === "string" ? obj.details : JSON.stringify(obj.details);
    try {
      return JSON.stringify(obj);
    } catch {
      return String(obj);
    }
  }
  return String(err);
}

function setCallActive(active) {
  if (active) {
    btnStart.classList.add("hidden");
    btnEnd.classList.remove("hidden");
    statusArea.classList.remove("hidden");
    patientIdInput.disabled = true;
  } else {
    btnStart.classList.remove("hidden");
    btnEnd.classList.add("hidden");
    statusArea.classList.add("hidden");
    transcript.textContent = "";
    patientIdInput.disabled = false;
  }
}



// ── Fetch config from Python backend ────────────────────────────────
async function fetchVapiConfig(patientId) {
  const url = `${API_BASE}/start-session/${encodeURIComponent(patientId)}`;

  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail || res.statusText;
    throw new Error(`Backend error (${res.status}): ${detail}`);
  }
  const json = await res.json();
  return json.data; // { vapiApiKey, assistantId, assistantOverrides }
}



// ── Start call ──────────────────────────────────────────────────────
async function startCall() {
  hideError();

  const patientId = patientIdInput.value.trim();
  if (!patientId) {
    showError("Please enter a Patient ID before starting the survey.");
    patientIdInput.focus();
    return;
  }

  // Keep the current patient ID in the URL so refresh/share preserves context.
  const currentUrl = new URL(window.location.href);
  currentUrl.searchParams.set("patientId", patientId);
  window.history.replaceState(null, "", currentUrl);

  btnStart.disabled = true;
  btnStart.textContent = "Loading…";

  try {
    // 1. Check microphone permission early
    await navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      // Release the test stream immediately
      stream.getTracks().forEach((t) => t.stop());
    });
  } catch {
    showError(
      "Microphone access was denied. Please allow microphone permission in your browser settings and try again."
    );
    btnStart.disabled = false;
    btnStart.textContent = "Start Check-In";
    return;
  }

  let config;
  try {
    config = await fetchVapiConfig(patientId);
  } catch (err) {
    showError(
      `Could not reach the server. Please check your connection and try again. (${err.message})`
    );
    btnStart.disabled = false;
    btnStart.textContent = "Start Check-In";
    return;
  }

  try {
    // 2. Initialise Vapi with the API key from the backend
    vapi = new Vapi(config.vapiApiKey);
    bindVapiEvents(vapi);

    // 3. Show connecting state before starting the call
    setCallActive(true);
    setStatus("connecting", "Connecting…");

    // Use SDK signature: start(assistantId, assistantOverrides) for saved assistants.
    if (config.assistantId) {
      await vapi.start(config.assistantId, config.assistantOverrides);
    } else {
      // Inline / transient assistant (no saved assistant)
      // const voiceConfig = INLINE_VOICE_PROVIDER && INLINE_VOICE_ID
      //   ? {
      //       voice: {
      //         provider: INLINE_VOICE_PROVIDER,
      //         voiceId: INLINE_VOICE_ID,
      //       },
      //     }
      //   : {};

      await vapi.start({
        model: config.assistantOverrides.model,
        firstMessage:
          "Hello! I am your well-being assistant. Let's begin your survey. Are you ready?",
        metadata: config.assistantOverrides.metadata,
        // ...voiceConfig,
        ...(config.assistantOverrides.serverUrl && {
          serverUrl: config.assistantOverrides.serverUrl,
        }),
      });
    }
  } catch (err) {
    const details = formatError(err);
    showError(`Failed to start the call: ${details}`);
    setCallActive(false);
  } finally {
    btnStart.disabled = false;
    btnStart.textContent = "Start Check-In";
  }
}

// ── Vapi event bindings ─────────────────────────────────────────────
function bindVapiEvents(instance) {
  instance.on("call-start", () => {
    setStatus("listening", "Listening…");
  });

  instance.on("call-end", () => {
    setCallActive(false);
  });

  instance.on("speech-start", () => {
    setStatus("speaking", "Speaking…");
  });

  instance.on("speech-end", () => {
    setStatus("listening", "Listening…");
  });

  instance.on("volume-level", () => {
    // Keep listening state visible when user is talking
    if (statusIndicator.getAttribute("data-state") !== "speaking") {
      setStatus("listening", "Listening…");
    }
  });

  instance.on("message", (msg) => {
    // Show the latest partial/final transcript
    if (msg.type === "transcript") {
      transcript.textContent = msg.transcript || "";
    }
  });

  instance.on("error", (err) => {
    console.error("[Vapi error]", err);
    const details = formatError(err);
    showError(`Voice error: ${details || "An unexpected error occurred."}`);
    setCallActive(false);
  });
}

// ── End call ────────────────────────────────────────────────────────
function endCall() {
  if (vapi) {
    vapi.stop();
  }
  setCallActive(false);
}

// ── Event listeners ─────────────────────────────────────────────────
patientIdInput.value = INITIAL_PATIENT_ID;
btnStart.addEventListener("click", startCall);
btnEnd.addEventListener("click", endCall);
errorDismiss.addEventListener("click", hideError);
