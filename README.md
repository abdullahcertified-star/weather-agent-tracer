# 🌤️ MeteoAgent AI — Real-Time Weather & Observability Tracing

An intelligent meteorological agent powered directly by **Open-Meteo's Free Global Weather API** (100% free with **zero API key required**), featuring an end-to-end **execution tracing and observability system** and a modern glassmorphic web dashboard.

---

## 🌟 Key Features

1. **100% Free & Zero-Key Architecture**:
   - **No API keys or accounts required**. Works straight out of the box immediately after cloning.
   - Runs directly on Open-Meteo's official high-resolution meteorological APIs.

2. **Real-Time Global Weather & Forecasts**:
   - **Current Conditions**: Temperature, apparent "feels like" temperature, relative humidity, wind speed, precipitation, day/night indicator, and WMO condition descriptions with dynamic weather emojis.
   - **Multi-Day Forecasts**: Daily temperature highs/lows, rain probabilities, and condition summaries.

3. **Smart Natural Language Understanding**:
   - **Intelligent Typo Tolerance**: Automatically corrects common typos (e.g. `Faisalabd` ➔ `Faisalabad`).
   - **Abbreviation & Acronym Resolution**: Recognizes common abbreviations (e.g. `NY`/`NYC` ➔ `New York`, `LA` ➔ `Los Angeles`, `SF` ➔ `San Francisco`).
   - **Temporal & Activity Queries**: Intelligently handles temporal queries like *"Should I carry an umbrella in London tomorrow evening?"* to provide rain probabilities and clothing advice.
   - **Multi-City Comparisons**: Handles comparisons like *"NY vs Paris"* or *"Compare London and Tokyo"* by dispatching tool calls for each location and rendering a side-by-side comparison.

4. **Complete Observability & Execution Tracing**:
   - **Visual Waterfall Timeline**: Tracks every step of the execution (intent analysis, tool calling, data retrieval, and answer synthesis).
   - **Performance Metrics**: Sub-millisecond latency measurements for each individual span and total run duration.
   - **Token Tracking**: Captures prompt, completion, and total tokens per execution.
   - **Trace Management**: View past traces, inspect raw JSON, download traces, and delete individual or all traces (`🗑️`).

5. **Modern Glassmorphic Web Dashboard**:
   - Atmospheric animated background with dark-mode glassmorphic cards.
   - Quick-prompt suggestion chips for instant one-click queries.
   - Interactive hero weather card and multi-day forecast carousel.

---

## 📁 Project Structure

```
Weather Agent/
├── server.py           # Web dashboard HTTP server & REST API endpoints
├── agent.py            # WeatherAgent orchestration, tool dispatching & tracing
├── weather_tools.py    # Open-Meteo Geocoding & Forecast API integrations
├── tracer.py           # Execution tracer with span waterfall & JSON exporter
├── main.py             # Interactive CLI & single-query command runner
├── tests.py            # Automated test suite (tools, tracer, agent)
├── requirements.txt    # Project dependencies
├── public/             # Glassmorphic web frontend
│   ├── index.html      # Dashboard layout & markup
│   ├── style.css       # Glassmorphic styling & animations
│   └── app.js          # Interactive frontend logic & trace rendering
└── traces/             # Persisted JSON execution traces
```

---

## 🚀 Quick Start

### 1. Installation

Ensure you have Python 3.10+ installed:

```bash
git clone https://github.com/abdullahcertified-star/weather-agent-tracer.git
cd weather-agent-tracer
pip install -r requirements.txt
```

### 2. Launch the Web Dashboard

Start the local server:

```bash
python server.py
```

Then open your browser at:

👉 **[http://localhost:8000](http://localhost:8000)**

*No API keys, setup modals, or configuration steps required — the dashboard is ready immediately!*

---

## 💻 Command-Line Interface (CLI)

### Interactive CLI Mode
```bash
python main.py
```
Type any question or choose from the built-in menu:
- *"What is the weather right now in Tokyo?"*
- *"What is the 3-day forecast for London?"*
- *"Should I carry an umbrella in London tomorrow evening?"*
- *"How is the weather in New York compared to Paris?"*

### Single Query Mode
```bash
python main.py "What is the weather in Tokyo right now?"
```

```bash
python main.py "How is the weather in New York compared to Paris?"
```

---

## 🔍 Tracing in Action

Every query records a complete trace with sub-millisecond timestamps, span hierarchy, and status badges:

```
🔍 EXECUTION TRACE DETAILS (trace_20260913_200542_a81f02)
┌─────────────────────────────── Trace Summary ───────────────────────────────┐
│   Metric           Value                                                    │
│   Status           SUCCESS                                                  │
│   Total Latency    1248.51 ms                                               │
│   Model            open-meteo                                               │
│   Tokens Used      Prompt: 42 | Completion: 18 | Total: 60                  │
│   Steps / Spans    3 events                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌───────────────────── Trace Execution Spans (Waterfall) ─────────────────────┐
│ Agent Run: "Should I carry an umbrella in London tomorrow evening?"         │
│ ├── 🟢 Step 1: Intent Analysis (0.86ms)                                      │
│ │   └── Decision: Call tool: get_weather_forecast                           │
│ ├── 🟢 Step 2: Tool 'get_weather_forecast' (1247.12ms)                      │
│ │   ├── Input: {"city": "London", "days": 3}                                │
│ │   └── Data: 3-day forecast fetched (Rain prob: 77%)                       │
│ └── 🟢 Step 3: Response Synthesis (0.53ms)                                  │
│     └── Advice: ☔ Carry an umbrella! Rain or showers expected.             │
└─────────────────────────────────────────────────────────────────────────────┘
```

All traces are accessible directly in the web UI under the **📜 Traces** button, where you can view past traces, inspect raw JSON, or delete them.

---

## 🧪 Running Automated Tests

Run the test suite to verify tool execution, geocoding, and trace generation:

```bash
python tests.py
```

---

## 🛡️ Privacy & Zero-Key Guarantee
This project connects exclusively to Open-Meteo's public meteorological API. It does not require or store any private API keys, and your `.env` file is protected via `.gitignore`.
