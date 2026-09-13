"""
Weather Agent Web Server
Serves static frontend files and provides REST API endpoints for agent execution,
API key management, and execution trace retrieval.
"""

import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Ensure UTF-8 output encoding
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv
from agent import WeatherAgent
from weather_tools import get_current_weather, get_weather_forecast

load_dotenv()

PORT = int(os.getenv("PORT", 8000))
PUBLIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
TRACES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traces")
os.makedirs(PUBLIC_DIR, exist_ok=True)
os.makedirs(TRACES_DIR, exist_ok=True)

# In-memory session key if user provides via frontend
RUNTIME_CONFIG = {
    "gemini_api_key": os.getenv("GEMINI_API_KEY") if os.getenv("GEMINI_API_KEY") != "your_gemini_api_key_here" else None,
    "openai_api_key": os.getenv("OPENAI_API_KEY") if os.getenv("OPENAI_API_KEY") != "your_openai_api_key_here" else None,
    "model": os.getenv("OPENAI_MODEL", "gemini-2.5-flash-lite")
}


class WeatherAgentHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def _send_json(self, data, status=HTTPStatus.OK):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/status":
            has_gemini = bool(RUNTIME_CONFIG["gemini_api_key"] and RUNTIME_CONFIG["gemini_api_key"].strip())
            has_openai = bool(RUNTIME_CONFIG["openai_api_key"] and RUNTIME_CONFIG["openai_api_key"].strip())
            
            masked_key = ""
            if has_gemini:
                k = RUNTIME_CONFIG["gemini_api_key"]
                masked_key = f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "***"
            elif has_openai:
                k = RUNTIME_CONFIG["openai_api_key"]
                masked_key = f"{k[:4]}...{k[-4:]}" if len(k) > 8 else "***"

            self._send_json({
                "configured": has_gemini or has_openai,
                "provider": "gemini" if has_gemini else ("openai" if has_openai else "simulation"),
                "model": RUNTIME_CONFIG["model"],
                "masked_key": masked_key
            })
            return

        elif path == "/api/traces":
            try:
                files = os.listdir(TRACES_DIR)
                json_files = [f for f in files if f.endswith(".json")]
                json_files.sort(key=lambda x: os.path.getmtime(os.path.join(TRACES_DIR, x)), reverse=True)
                
                recent_traces = []
                for fname in json_files[:15]:
                    fpath = os.path.join(TRACES_DIR, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        tdata = json.load(f)
                        recent_traces.append({
                            "trace_id": tdata.get("trace_id"),
                            "query": tdata.get("query"),
                            "status": tdata.get("status"),
                            "created_at": tdata.get("created_at"),
                            "total_duration_ms": tdata.get("total_duration_ms"),
                            "total_tokens": tdata.get("token_usage", {}).get("total_tokens", 0),
                            "file": fname
                        })
                self._send_json({"traces": recent_traces})
            except Exception as e:
                self._send_json({"error": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        elif path.startswith("/api/traces/"):
            trace_id = path.replace("/api/traces/", "").replace(".json", "")
            fname = f"{trace_id}.json"
            fpath = os.path.join(TRACES_DIR, fname)
            if os.path.exists(fpath):
                with open(fpath, "r", encoding="utf-8") as f:
                    self._send_json(json.load(f))
            else:
                self._send_json({"error": "Trace not found"}, status=HTTPStatus.NOT_FOUND)
            return

        # Serve static assets
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/traces" or path == "/api/traces/clear":
                files = [f for f in os.listdir(TRACES_DIR) if f.endswith(".json")]
                for f in files:
                    try:
                        os.remove(os.path.join(TRACES_DIR, f))
                    except Exception:
                        pass
                self._send_json({"status": "success", "message": f"Deleted {len(files)} traces."})
                return
            elif path == "/api/key" or path == "/api/delete-key":
                RUNTIME_CONFIG["gemini_api_key"] = None
                RUNTIME_CONFIG["openai_api_key"] = None
                os.environ.pop("GEMINI_API_KEY", None)
                os.environ.pop("OPENAI_API_KEY", None)
                try:
                    with open(".env", "w", encoding="utf-8") as env_f:
                        env_f.write("# API Keys removed\nOPENAI_MODEL=gemini-2.5-flash\n")
                except Exception:
                    pass
                self._send_json({"status": "success", "message": "API key successfully removed."})
                return
            elif path.startswith("/api/traces/"):
                trace_id = path.replace("/api/traces/", "").replace(".json", "")
                fpath = os.path.join(TRACES_DIR, f"{trace_id}.json")
                if os.path.exists(fpath):
                    os.remove(fpath)
                    self._send_json({"status": "success", "message": f"Deleted trace {trace_id}."})
                else:
                    self._send_json({"error": "Trace not found"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            content_len = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_len).decode("utf-8")
            data = json.loads(body) if body else {}

            if path == "/api/traces/clear":
                files = [f for f in os.listdir(TRACES_DIR) if f.endswith(".json")]
                for f in files:
                    try:
                        os.remove(os.path.join(TRACES_DIR, f))
                    except Exception:
                        pass
                self._send_json({"status": "success", "message": f"Deleted {len(files)} traces."})
                return

            elif path == "/api/traces/delete":
                trace_id = data.get("trace_id", "").replace(".json", "")
                fpath = os.path.join(TRACES_DIR, f"{trace_id}.json")
                if os.path.exists(fpath):
                    os.remove(fpath)
                    self._send_json({"status": "success", "message": f"Deleted trace {trace_id}."})
                else:
                    self._send_json({"error": "Trace not found"}, status=HTTPStatus.NOT_FOUND)
                return

            elif path == "/api/delete-key":
                RUNTIME_CONFIG["gemini_api_key"] = None
                RUNTIME_CONFIG["openai_api_key"] = None
                os.environ.pop("GEMINI_API_KEY", None)
                os.environ.pop("OPENAI_API_KEY", None)
                try:
                    with open(".env", "w", encoding="utf-8") as env_f:
                        env_f.write("# API Keys removed\nOPENAI_MODEL=gemini-2.5-flash\n")
                except Exception:
                    pass
                self._send_json({"status": "success", "message": "API key successfully removed."})
                return

            if path == "/api/set-key":
                key = data.get("api_key", "").strip()
                provider = data.get("provider", "gemini").lower()
                model = data.get("model", "").strip()

                if not key:
                    self._send_json({"error": "API Key cannot be empty."}, status=HTTPStatus.BAD_REQUEST)
                    return

                if provider == "gemini":
                    RUNTIME_CONFIG["gemini_api_key"] = key
                    RUNTIME_CONFIG["model"] = model or "gemini-2.5-flash"
                    os.environ["GEMINI_API_KEY"] = key
                    os.environ["OPENAI_MODEL"] = RUNTIME_CONFIG["model"]
                else:
                    RUNTIME_CONFIG["openai_api_key"] = key
                    RUNTIME_CONFIG["model"] = model or "gpt-4o-mini"
                    os.environ["OPENAI_API_KEY"] = key
                    os.environ["OPENAI_MODEL"] = RUNTIME_CONFIG["model"]

                # Save to local .env optionally
                if data.get("save_to_env", False):
                    try:
                        with open(".env", "w", encoding="utf-8") as env_f:
                            if provider == "gemini":
                                env_f.write(f"GEMINI_API_KEY={key}\nOPENAI_MODEL={RUNTIME_CONFIG['model']}\n")
                            else:
                                env_f.write(f"OPENAI_API_KEY={key}\nOPENAI_MODEL={RUNTIME_CONFIG['model']}\n")
                    except Exception:
                        pass

                self._send_json({
                    "status": "success",
                    "message": f"Successfully activated {provider.title()} API Key!",
                    "provider": provider,
                    "model": RUNTIME_CONFIG["model"]
                })
                return

            elif path == "/api/chat":
                query = data.get("query", "").strip()
                if not query:
                    self._send_json({"error": "Query cannot be empty."}, status=HTTPStatus.BAD_REQUEST)
                    return

                # Check if user sent a one-time key in request
                custom_key = data.get("api_key")
                custom_model = data.get("model")

                active_key = custom_key or RUNTIME_CONFIG["gemini_api_key"] or RUNTIME_CONFIG["openai_api_key"]
                active_model = custom_model or RUNTIME_CONFIG["model"]

                # Instantiate Agent
                base_url = None
                if RUNTIME_CONFIG["gemini_api_key"] or (custom_key and "AIza" in custom_key):
                    base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

                agent = WeatherAgent(api_key=active_key, model=active_model, base_url=base_url)

                # Run agent with tracing
                answer, tracer = agent.run(query)

                # Extract structured weather data from tool spans for rich frontend cards
                weather_payload = None
                forecast_payload = None
                for span in tracer.spans:
                    if span.span_type == "TOOL_CALL" and span.output_data and span.output_data.get("status") == "success":
                        if "current_weather" in span.output_data:
                            weather_payload = span.output_data
                        elif "forecast" in span.output_data:
                            forecast_payload = span.output_data

                self._send_json({
                    "status": "success",
                    "query": query,
                    "answer": answer,
                    "trace": tracer.to_dict(),
                    "weather_data": weather_payload,
                    "forecast_data": forecast_payload
                })
                return

            self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self._send_json({"error": f"Internal Server Error: {str(exc)}"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)


def run_server():
    server_address = ("", PORT)
    httpd = ThreadingHTTPServer(server_address, WeatherAgentHandler)
    print(f"==================================================")
    print(f"🌤️  Weather Agent Web Dashboard Running!")
    print(f"🔗  URL: http://localhost:{PORT}")
    print(f"==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    run_server()
