# 🌤️ OpenAI Weather Agent with Real-Time Data & Tracing

An intelligent meteorological agent built using the official **OpenAI SDK**, integrating **Open-Meteo's Free Global Weather API** (no API key required), and featuring an end-to-end **execution tracing and observability system**.

---

## 🌟 Key Features

1. **OpenAI SDK Tool Calling**:
   - Uses OpenAI's official function-calling interface (`tools` definition and auto-dispatch loop).
   - Multi-turn conversation handling and meteorological reasoning.

2. **Real-Time Weather Data (100% Free & No API Key Needed)**:
   - Integrates Open-Meteo Geocoding & Weather Forecast APIs.
   - Live temperature, apparent "feels like" temperature, humidity, precipitation, wind speed, and WMO weather condition descriptions with visual emojis.
   - Multi-day forecasts (up to 7 days) with temperature highs/lows and rain probabilities.

3. **Complete Execution Tracing & Observability**:
   - **Step-by-step waterfall**: Visualizes LLM inferences, tool calls, and data synthesis.
   - **Performance metrics**: Sub-millisecond latency measurements for each span and total run duration.
   - **Token tracking**: Captures prompt, completion, and total tokens per LLM turn.
   - **Inspectable artifacts**: Every session automatically generates a structured JSON trace in the `traces/` folder.
   - **Rich Terminal UI**: Beautiful formatted tables, status badges (🟢 🔴 ⏳), and expandable trees.

4. **Zero-Friction Testing (Zero-Key Mode)**:
   - If an `OPENAI_API_KEY` is not yet configured, the agent runs in **Live Weather Mode with Local Runner**, fetching real live data from Open-Meteo and outputting complete execution traces immediately.

---

## 📁 Project Structure

```
Weather Agent/
├── agent.py            # OpenAI WeatherAgent orchestration & tool dispatch loop
├── weather_tools.py    # Open-Meteo API integrations & OpenAI tool definitions
├── tracer.py           # Session & Span tracer with Rich UI and JSON exporter
├── main.py             # Interactive CLI and single-query runner
├── tests.py            # Automated test suite (tools, tracer, agent)
├── requirements.txt    # Project dependencies
├── .env.example        # Environment configuration template
└── traces/             # Generated JSON trace logs (created on run)
```

---

## 🚀 Quick Start

### 1. Installation

Ensure you have Python 3.10+ installed:

```bash
pip install -r requirements.txt
```

### 2. Configure Environment (Optional for Live OpenAI API)

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` to include your OpenAI API key:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

> **Note**: Even without an OpenAI API key, you can run and test the live weather queries and tracing system right away!

---

## 🌐 Web Frontend Dashboard

A modern, glassmorphic dark-mode web application is included!

### Starting the Web Dashboard:
```bash
python server.py
```
Open your browser at **[http://localhost:8000](http://localhost:8000)**.

### Web Dashboard Features:
1. **Gemini & OpenAI API Key Onboarding**:
   - Easily paste your Gemini or OpenAI key directly in the web UI or continue with your pre-configured `.env`.
   - Includes a **Demo Mode** button to test live weather data without an API key.
2. **Interactive Weather Search & Prompt Chips**:
   - Natural language input (*"What's the weather in Tokyo right now?"*, *"London 3-day forecast"*, *"Compare NY and Paris"*).
   - Quick-click suggestion chips for instant answers.
3. **Hero Weather Display & Forecast Carousel**:
   - Dynamic real-time weather card (temperature, feels-like, humidity, wind, precipitation, condition emoji, day/night).
   - Multi-day forecast cards with high/low temperature bars and rain probability.
4. **AI Reasoning Card**:
   - Markdown-rendered AI assistant response with meteorological context and clothing/travel advice.
5. **Interactive Execution Tracing Inspector**:
   - Visual waterfall timeline for every run.
   - LLM inference latency, token metrics (prompt, completion, total), and tool execution time.
   - Expandable raw JSON viewer with one-click **Copy JSON** and **Download Trace** buttons.
   - History drawer to inspect past runs.

---

### Interactive Mode

Start the interactive assistant:

```bash
python main.py
```

You can choose from the quick sample menu or type any custom natural language question:
- *"What is the weather right now in Tokyo?"*
- *"What is the 3-day forecast for London?"*
- *"How is the weather in New York compared to Paris?"*
- *"Will it rain in Lahore tomorrow?"*

### Single Query Command-Line Mode

You can also pass a query directly as a command-line argument:

```bash
python main.py "What is the weather in Tokyo right now?"
```

```bash
python main.py "What is the 3-day forecast for London?"
```

---

## 🔍 Tracing in Action

Every agent execution produces both a **live terminal waterfall** and an exported **JSON trace file**:

### 1. Console Trace View
```
🔍 EXECUTION TRACE DETAILS (trace_20260912_203019_39ebdd)
┌─────────────────────────────── Trace Summary ───────────────────────────────┐
│   Metric           Value                                                    │
│   Status           SUCCESS                                                  │
│   Total Latency    1653.62 ms                                               │
│   Model            gpt-4o-mini                                              │
│   Tokens Used      Prompt: 127 | Completion: 138 | Total: 265               │
│   Steps / Spans    3 events                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
┌───────────────────── Trace Execution Spans (Waterfall) ─────────────────────┐
│ Agent Run: "What is the weather in Tokyo right now?"                        │
│ ├── 🟢 Step 1: LLM Inference (0.86ms)                                       │
│ │   ├── Tokens: 60 (Prompt: 42, Compl: 18)                                  │
│ │   └── Decision: Call 1 tool(s): get_current_weather                       │
│ ├── 🟢 Step 2: Tool 'get_current_weather' (1652.56ms)                       │
│ │   ├── Input: {"city": "Tokyo"}                                            │
│ │   └── Data fetched for Tokyo, Japan: Weather: 21.7 °C, Partly cloudy ⛅   │
│ └── 🟢 Step 3: LLM Inference (0.03ms)                                       │
│     ├── Tokens: 205 (Prompt: 85, Compl: 120)                                │
│     └── Generated final answer preview                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Exported JSON Traces
Traces are saved in `traces/trace_<timestamp>_<id>.json` containing exact timestamps, duration down to milliseconds, input arguments, raw API outputs, and token counts.

---

## 🧪 Running Tests

Run the test suite to verify weather APIs, tracing, and agent loops:

```bash
python tests.py
```
