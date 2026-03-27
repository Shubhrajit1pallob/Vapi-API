import Vapi from "@vapi-ai/web";

// ── Config ──────────────────────────────────────────────────────────
const API_BASE = import.meta.env.VITE_API_BASE || "";
const PATIENT_ID = new URLSearchParams(window.location.search).get("patientId") || "123";

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

function setCallActive(active) {
  if (active) {
    btnStart.classList.add("hidden");
    btnEnd.classList.remove("hidden");
    statusArea.classList.remove("hidden");
  } else {
    btnStart.classList.remove("hidden");
    btnEnd.classList.add("hidden");
    statusArea.classList.add("hidden");
    transcript.textContent = "";
  }
}

// ── Fetch config from Python backend ────────────────────────────────
async function fetchVapiConfig() {
  const url = `${API_BASE}/get-vapi-config?patientId=${encodeURIComponent(PATIENT_ID)}`;

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
    config = await fetchVapiConfig();
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

    // 3. Build start options
    const startOptions = {};

    if (config.assistantId) {
      // Use an existing assistant with overrides
      startOptions.assistantId = config.assistantId;
      startOptions.assistantOverrides = config.assistantOverrides;
    } else {
      // Inline / transient assistant (no saved assistant)
      startOptions.assistant = {
        model: config.assistantOverrides.model,
        firstMessage:
          "Hello! I am your well-being assistant. Let's begin your check-in. Are you ready?",
        voice: {
          provider: "11labs",
          voiceId: "21m00Tcm4TlvDq8ikWAM", // "Rachel" – calm & clear
        },
        metadata: config.assistantOverrides.metadata,
        ...(config.assistantOverrides.serverUrl && {
          serverUrl: config.assistantOverrides.serverUrl,
        }),
      };
    }

    // 4. Show connecting state + start the call
    setCallActive(true);
    setStatus("connecting", "Connecting…");

    await vapi.start(startOptions.assistantId ? startOptions : startOptions.assistant);
  } catch (err) {
    showError(`Failed to start the call: ${err.message}`);
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
    showError(`Voice error: ${err.message || "An unexpected error occurred."}`);
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
btnStart.addEventListener("click", startCall);
btnEnd.addEventListener("click", endCall);
errorDismiss.addEventListener("click", hideError);
