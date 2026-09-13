/**
 * MeteoAgent AI — Interactive Frontend Logic
 */

let currentTrace = null;
let appConfig = {
  configured: false,
  provider: "gemini",
  model: "gemini-2.5-flash"
};

// Simple Markdown parser for AI responses
function parseMarkdown(md) {
  if (!md) return "";
  let html = md
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^### (.*$)/gim, '<h3 style="margin: 10px 0 5px; color: #38bdf8;">$1</h3>')
    .replace(/^## (.*$)/gim, '<h2 style="margin: 14px 0 6px; color: #38bdf8;">$1</h2>')
    .replace(/^# (.*$)/gim, '<h1 style="margin: 16px 0 8px; color: #38bdf8;">$1</h1>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.1); padding: 2px 5px; border-radius: 4px; font-family: monospace;">$1</code>')
    .replace(/^\s*[-•]\s+(.*$)/gim, '<li style="margin-left: 18px; margin-bottom: 4px;">$1</li>')
    .replace(/\n\n/g, '<br><br>')
    .replace(/\n/g, '<br>');
  return html;
}

// Map WMO Weather Codes to Emojis
function getWeatherEmoji(conditionText) {
  if (!conditionText) return "🌤️";
  const lower = conditionText.toLowerCase();
  if (lower.includes("clear") || lower.includes("sun")) return "☀️";
  if (lower.includes("thunder")) return "⛈️";
  if (lower.includes("snow") || lower.includes("grain") || lower.includes("ice")) return "❄️";
  if (lower.includes("heavy rain") || lower.includes("violent")) return "🌧️⛈️";
  if (lower.includes("rain") || lower.includes("drizzle") || lower.includes("shower")) return "🌦️";
  if (lower.includes("fog") || lower.includes("rime")) return "🌫️";
  if (lower.includes("overcast")) return "☁️";
  if (lower.includes("partly") || lower.includes("cloud")) return "⛅";
  return "🌤️";
}

// Initial check on load
document.addEventListener("DOMContentLoaded", () => {
  checkStatus();
  fetchTraceList();
});

async function checkStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    appConfig = data;

    updateHeaderStatus();

    if (data.configured) {
      document.getElementById("keyModal").classList.add("hidden");
      // Initial demo query to populate the dashboard right away!
      submitPrompt("What is the weather right now in Tokyo?", false);
    } else {
      document.getElementById("keyModal").classList.remove("hidden");
    }
  } catch (err) {
    console.warn("Could not connect to /api/status, running in offline mode:", err);
  }
}

function updateHeaderStatus() {
  const pill = document.getElementById("providerLabel");
  const modelText = appConfig.model || "gemini-2.5-flash";
  pill.textContent = `${appConfig.provider === "gemini" ? "Gemini" : "OpenAI"}: ${modelText}`;
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  input.type = input.type === "password" ? "text" : "password";
}

function openKeyModal() {
  const modal = document.getElementById("keyModal");
  modal.classList.remove("hidden");

  const hint = document.getElementById("apiKeyStatusHint");
  if (appConfig.configured && appConfig.masked_key) {
    hint.innerHTML = `<span style="color: #34d399;">✓ Active key in use: <strong>${appConfig.masked_key}</strong></span>. Enter a new key to change, or click <em>Go Back</em>.`;
  } else {
    hint.innerHTML = `Don't have one? Get a free key at <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noopener">Google AI Studio</a>.`;
  }
}

function closeKeyModal() {
  document.getElementById("keyModal").classList.add("hidden");
}

function continueInDemoMode() {
  closeKeyModal();
  appConfig.configured = true;
  appConfig.provider = "simulation";
  appConfig.model = "zero-key-live-weather";
  document.getElementById("providerLabel").textContent = "Live Demo (Open-Meteo)";
  submitPrompt("What is the weather right now in Tokyo?", false);
}

// Close modals when clicking the dark backdrop
document.addEventListener("DOMContentLoaded", () => {
  const keyModal = document.getElementById("keyModal");
  if (keyModal) {
    keyModal.addEventListener("click", (e) => {
      if (e.target.id === "keyModal") closeKeyModal();
    });
  }

  const tracesModal = document.getElementById("tracesModal");
  if (tracesModal) {
    tracesModal.addEventListener("click", (e) => {
      if (e.target.id === "tracesModal") closeTracesModal();
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeKeyModal();
      closeTracesModal();
    }
  });
});

async function handleKeySubmit() {
  const apiKey = document.getElementById("apiKeyInput").value.trim();
  const model = document.getElementById("modelSelect").value;
  const saveToEnv = document.getElementById("saveLocalEnv").checked;

  // If no new key entered but one is already configured in .env/session, simply close
  if (!apiKey && appConfig.configured) {
    appConfig.model = model;
    updateHeaderStatus();
    closeKeyModal();
    return;
  }

  if (!apiKey) {
    alert("Please enter a valid Gemini or OpenAI API Key, or click '← Go Back'.");
    return;
  }

  const btn = document.getElementById("saveKeyBtn");
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner-small"></span> Connecting...`;

  const provider = apiKey.startsWith("AIza") ? "gemini" : (apiKey.startsWith("sk-") ? "openai" : "gemini");

  try {
    const res = await fetch("/api/set-key", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        api_key: apiKey,
        provider: provider,
        model: model,
        save_to_env: saveToEnv
      })
    });

    const result = await res.json();
    if (res.ok) {
      appConfig.configured = true;
      appConfig.provider = provider;
      appConfig.model = model;
      appConfig.masked_key = apiKey.slice(0, 4) + "..." + apiKey.slice(-4);
      updateHeaderStatus();
      closeKeyModal();

      // Trigger initial query
      submitPrompt("What is the weather right now in Tokyo?", false);
    } else {
      alert("Error: " + (result.error || "Failed to set API key."));
    }
  } catch (err) {
    alert("Network error communicating with server.");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>Save & Enter Dashboard</span> 🚀`;
  }
}

function applyQuickPrompt(text) {
  document.getElementById("promptInput").value = text;
  submitPrompt(text);
}

async function submitPrompt(customPrompt = null, scrollIntoView = true) {
  const promptInput = document.getElementById("promptInput");
  const query = (customPrompt || promptInput.value).trim();
  if (!query) return;

  promptInput.value = query;

  // UI state updates
  const submitBtn = document.getElementById("btnSubmitQuery");
  const submitText = document.getElementById("btnQueryText");
  const submitSpinner = document.getElementById("btnQuerySpinner");
  const executingBanner = document.getElementById("executingBanner");

  submitBtn.disabled = true;
  submitText.textContent = "Processing...";
  submitSpinner.classList.remove("hidden");
  executingBanner.classList.remove("hidden");

  // Show immediate visual feedback on weather card
  const heroLocation = document.getElementById("heroLocationBadge");
  const previousLocationText = heroLocation.textContent;
  heroLocation.textContent = `🔍 Fetching data for "${query}"...`;
  document.getElementById("heroConditionPill").textContent = "Analyzing query...";

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query })
    });

    const data = await response.json();

    if (!response.ok) {
      alert("Error: " + (data.error || "Agent execution failed."));
      heroLocation.textContent = previousLocationText;
      return;
    }

    // 1. Render AI Markdown Answer
    const aiAnswerBody = document.getElementById("aiAnswerBody");
    aiAnswerBody.innerHTML = parseMarkdown(data.answer);

    // 2. Render Structured Weather if available
    if (data.weather_data && data.weather_data.current_weather) {
      renderCurrentWeather(data.weather_data);
    } else {
      // Clear or update hero card so old city data is not lingering!
      renderWeatherNotFound(query);
    }

    // 3. Render Forecast if available
    if (data.forecast_data && data.forecast_data.forecast) {
      renderForecast(data.forecast_data);
    } else {
      document.getElementById("forecastSection").classList.add("hidden");
    }

    // 4. Render Execution Trace Waterfall
    if (data.trace) {
      currentTrace = data.trace;
      renderTrace(data.trace);
      fetchTraceList(); // update history count
    }

    if (scrollIntoView) {
      document.getElementById("weatherWidgetsArea").scrollIntoView({ behavior: "smooth" });
    }
  } catch (err) {
    console.error("Agent error:", err);
    heroLocation.textContent = previousLocationText;
    alert("Connection to server failed. Is server.py running?");
  } finally {
    submitBtn.disabled = false;
    submitText.textContent = "Ask Agent";
    submitSpinner.classList.add("hidden");
    executingBanner.classList.add("hidden");
  }
}

function renderWeatherNotFound(query) {
  document.getElementById("heroLocationBadge").textContent = `📍 Location Not Found`;
  document.getElementById("heroLocalTime").textContent = `Query: "${query}"`;
  document.getElementById("heroTemp").textContent = `--`;
  document.getElementById("heroFeelsLike").textContent = `No real-time data`;
  document.getElementById("heroConditionPill").textContent = `Check city spelling`;
  document.getElementById("heroConditionEmoji").textContent = `❓`;

  document.getElementById("metricHumidity").textContent = `--`;
  document.getElementById("metricWind").textContent = `--`;
  document.getElementById("metricPrecip").textContent = `--`;
  document.getElementById("metricDayNight").textContent = `--`;
}

function renderCurrentWeather(data) {
  const loc = data.location;
  const cw = data.current_weather;

  document.getElementById("heroLocationBadge").textContent = `📍 ${loc.city}, ${loc.country}`;
  document.getElementById("heroLocalTime").textContent = `Observed: ${cw.time ? cw.time.replace('T', ' ') : 'Just now'} (${loc.timezone})`;
  document.getElementById("heroTemp").textContent = cw.temperature;
  document.getElementById("heroFeelsLike").textContent = `Feels like ${cw.feels_like}`;
  document.getElementById("heroConditionPill").textContent = cw.condition;
  document.getElementById("heroConditionEmoji").textContent = getWeatherEmoji(cw.condition);

  document.getElementById("metricHumidity").textContent = cw.humidity;
  document.getElementById("metricWind").textContent = cw.wind_speed;
  document.getElementById("metricPrecip").textContent = cw.precipitation;
  document.getElementById("metricDayNight").textContent = cw.is_day;
}

function renderForecast(data) {
  const container = document.getElementById("forecastCardsContainer");
  const section = document.getElementById("forecastSection");
  const badge = document.getElementById("forecastCountBadge");

  container.innerHTML = "";
  badge.textContent = `${data.forecast_days} Days`;
  document.getElementById("forecastTitle").textContent = `${data.forecast_days}-Day Forecast for ${data.location.city}`;

  data.forecast.forEach(day => {
    const card = document.createElement("div");
    card.className = "f-card";
    card.innerHTML = `
      <div class="f-date">${day.date}</div>
      <div class="f-condition-icon">${getWeatherEmoji(day.condition)}</div>
      <div class="f-condition-name">${day.condition}</div>
      <div class="f-temp-range">
        <span class="f-temp-max">${day.max_temp}</span>
        <span class="f-temp-min">${day.min_temp}</span>
      </div>
      <div class="f-rain">💧 ${day.precipitation_probability} rain</div>
    `;
    container.appendChild(card);
  });

  section.classList.remove("hidden");
}

function renderTrace(trace) {
  document.getElementById("traceIdBadge").textContent = trace.trace_id;
  document.getElementById("traceStatStatus").textContent = (trace.status || "SUCCESS").toUpperCase();
  document.getElementById("traceStatStatus").className = `t-val ${trace.status === 'error' ? 'text-rose' : 'text-green'}`;
  document.getElementById("traceStatDuration").textContent = `${trace.total_duration_ms} ms`;
  document.getElementById("traceStatModel").textContent = trace.model;
  
  const tok = trace.token_usage || {};
  document.getElementById("traceStatTokens").textContent = `${tok.prompt_tokens || 0} / ${tok.completion_tokens || 0}`;
  document.getElementById("traceStatTotalTokens").textContent = tok.total_tokens || 0;

  const container = document.getElementById("traceTimelineContainer");
  container.innerHTML = "";

  if (!trace.spans || trace.spans.length === 0) {
    container.innerHTML = `<div class="timeline-empty">No spans recorded for this trace.</div>`;
    return;
  }

  trace.spans.forEach((span, i) => {
    const row = document.createElement("div");
    row.className = "span-row";

    const isLlm = span.span_type === "LLM_CALL";
    const badgeClass = isLlm ? "badge-llm" : "badge-tool";
    const statusIcon = span.status === "success" ? "🟢" : (span.status === "error" ? "🔴" : "⏳");
    const dur = span.duration_ms ? `${span.duration_ms} ms` : "in progress";

    const drawerId = `json_drawer_${i}`;

    let summaryNote = "";
    if (span.output_data && span.output_data.tool_calls_requested) {
      summaryNote = `<span style="color: #34d399; font-size: 0.8rem;">Decision: Call tool(s) [${span.output_data.tool_calls_requested.join(", ")}]</span>`;
    } else if (span.output_data && span.output_data.current_weather) {
      summaryNote = `<span style="color: #38bdf8; font-size: 0.8rem;">Returned: ${span.output_data.current_weather.condition}, ${span.output_data.current_weather.temperature}</span>`;
    }

    row.innerHTML = `
      <div class="span-row-header">
        <div class="span-title-group">
          <span class="span-status-indicator">${statusIcon}</span>
          <span class="span-type-badge ${badgeClass}">${span.span_type}</span>
          <span class="span-name">Step ${i + 1}: ${span.name}</span>
          ${summaryNote}
        </div>
        <div class="span-meta-right">
          <span class="span-duration">${dur}</span>
          <span class="span-details-toggle" onclick="toggleDrawer('${drawerId}')">View JSON</span>
        </div>
      </div>
      <div id="${drawerId}" class="span-json-drawer hidden">
        <pre>${JSON.stringify({ input: span.input_data, output: span.output_data, metadata: span.metadata }, null, 2)}</pre>
      </div>
    `;

    container.appendChild(row);
  });
}

function toggleDrawer(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("hidden");
}

function copyTraceJson() {
  if (!currentTrace) {
    alert("No active trace to copy.");
    return;
  }
  navigator.clipboard.writeText(JSON.stringify(currentTrace, null, 2))
    .then(() => alert("Trace JSON copied to clipboard! 📋"))
    .catch(() => alert("Failed to copy to clipboard."));
}

function downloadTraceJson() {
  if (!currentTrace) {
    alert("No active trace to download.");
    return;
  }
  const blob = new Blob([JSON.stringify(currentTrace, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${currentTrace.trace_id}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// Past Traces Modal
async function fetchTraceList() {
  try {
    const res = await fetch("/api/traces");
    const data = await res.json();
    const countBadge = document.getElementById("traceCounterBadge");
    if (data.traces) {
      countBadge.textContent = data.traces.length;
    }
  } catch (err) {
    console.warn("Could not fetch traces list:", err);
  }
}

async function openTracesModal() {
  const modal = document.getElementById("tracesModal");
  const container = document.getElementById("tracesListContainer");
  modal.classList.remove("hidden");
  container.innerHTML = `<div class="spinner-small"></div> Loading traces...`;

  try {
    const res = await fetch("/api/traces");
    const data = await res.json();

    if (!data.traces || data.traces.length === 0) {
      container.innerHTML = `<div class="timeline-empty">No past traces recorded yet. Run some queries!</div>`;
      return;
    }

    container.innerHTML = "";
    data.traces.forEach(t => {
      const item = document.createElement("div");
      item.className = "trace-item-row";
      item.innerHTML = `
        <div style="flex: 1; cursor: pointer;" onclick="loadPastTrace('${t.trace_id}')">
          <div class="trace-item-q">"${t.query}"</div>
          <div class="trace-item-meta">${t.trace_id} • ${new Date(t.created_at).toLocaleTimeString()}</div>
        </div>
        <div class="trace-item-actions">
          <div style="text-align: right; cursor: pointer;" onclick="loadPastTrace('${t.trace_id}')">
            <div style="color: #fbbf24; font-family: monospace; font-size: 0.85rem;">${t.total_duration_ms} ms</div>
            <div style="color: #94a3b8; font-size: 0.75rem;">${t.total_tokens} tokens</div>
          </div>
          <button type="button" class="btn-icon-danger" onclick="deleteTrace('${t.trace_id}', event)" title="Delete this trace">🗑️</button>
        </div>
      `;
      container.appendChild(item);
    });
  } catch (err) {
    container.innerHTML = `<div style="color: #f87171;">Failed to load traces history.</div>`;
  }
}

async function deleteTrace(traceId, event) {
  if (event) event.stopPropagation();
  if (!confirm(`Are you sure you want to delete trace "${traceId}"?`)) return;

  try {
    const res = await fetch(`/api/traces/${traceId}`, { method: "DELETE" });
    if (res.ok) {
      if (currentTrace && currentTrace.trace_id === traceId) {
        resetTraceInspector();
      }
      await fetchTraceList();
      const modal = document.getElementById("tracesModal");
      if (!modal.classList.contains("hidden")) {
        await openTracesModal();
      }
    } else {
      alert("Failed to delete trace.");
    }
  } catch (err) {
    alert("Error deleting trace: " + err.message);
  }
}

async function clearAllTraces() {
  if (!confirm("Are you sure you want to delete ALL past saved traces? This cannot be undone.")) return;

  try {
    const res = await fetch("/api/traces/clear", { method: "POST" });
    if (res.ok) {
      resetTraceInspector();
      await fetchTraceList();
      await openTracesModal();
    } else {
      alert("Failed to clear traces.");
    }
  } catch (err) {
    alert("Error clearing traces.");
  }
}

async function deleteCurrentTrace() {
  if (!currentTrace || !currentTrace.trace_id) {
    alert("No active trace to delete.");
    return;
  }
  await deleteTrace(currentTrace.trace_id);
}

function resetTraceInspector() {
  currentTrace = null;
  document.getElementById("traceIdBadge").textContent = "trace_cleared";
  document.getElementById("traceStatStatus").textContent = "--";
  document.getElementById("traceStatStatus").className = "t-val";
  document.getElementById("traceStatDuration").textContent = "0 ms";
  document.getElementById("traceStatTokens").textContent = "0 / 0";
  document.getElementById("traceStatTotalTokens").textContent = "0";
  document.getElementById("traceTimelineContainer").innerHTML = `<div class="timeline-empty">Trace deleted. Run a new query to generate a trace.</div>`;
}

function closeTracesModal() {
  document.getElementById("tracesModal").classList.add("hidden");
}

async function loadPastTrace(traceId) {
  closeTracesModal();
  try {
    const res = await fetch(`/api/traces/${traceId}`);
    const data = await res.json();
    currentTrace = data;
    renderTrace(data);

    if (data.final_response) {
      document.getElementById("aiAnswerBody").innerHTML = parseMarkdown(data.final_response);
    }
    document.getElementById("traceInspector").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("Could not load trace details.");
  }
}
