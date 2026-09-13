"""
Weather Agent Module
Uses OpenAI SDK for tool orchestration, Open-Meteo for real-time weather,
and AgentTracer for full observability and latency/token tracing.
"""

import json
import os
import re
from typing import Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from openai import OpenAI

from weather_tools import OPENAI_WEATHER_TOOLS, TOOL_DISPATCHER, get_current_weather, get_weather_forecast
from tracer import AgentTracer

# Load environment variables
load_dotenv()

SYSTEM_PROMPT = """You are an expert Meteorological AI Assistant equipped with real-time weather instruments.
Your role:
1. When asked about current weather or forecasts for any location, ALWAYS invoke the appropriate weather tool (`get_current_weather` or `get_weather_forecast`).
2. Do not invent weather numbers or guess temperatures. Rely strictly on the tool's verified observation data.
3. Present the data clearly with helpful details (temperature, feels-like, condition emoji, humidity, wind speed, precipitation, and brief recommendations like clothing or umbrellas).
4. If multiple cities are mentioned, call the tools for each city and provide a helpful comparison.
5. If the user makes a typo in a city name (e.g. 'Faisalabd' instead of 'Faisalabad'), infer the intended city, call the tool, and briefly clarify the corrected city name.
6. Be concise, friendly, and informative.
"""


class WeatherAgent:
    """
    OpenAI-powered Weather Agent with multi-turn tool calling and tracing.
    Supports both OpenAI and Google Gemini (via Gemini's OpenAI-compatible endpoint).
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        # Support either OPENAI_API_KEY or GEMINI_API_KEY
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if gemini_key and gemini_key.strip() and gemini_key != "your_gemini_api_key_here":
            self.api_key = api_key or gemini_key
            self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
            self.model = model or os.getenv("OPENAI_MODEL", "gemini-2.5-flash-lite")
        else:
            self.api_key = api_key or openai_key
            self.base_url = base_url or os.getenv("OPENAI_BASE_URL")
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        
        self.client = None
        if self.api_key and self.api_key.strip() and self.api_key not in ["your_openai_api_key_here", "your_gemini_api_key_here"]:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

    def run(self, user_query: str, max_turns: int = 5) -> Tuple[str, AgentTracer]:
        """
        Executes an agent run on the user query, orchestrating tools and tracing every step.
        """
        tracer = AgentTracer(query=user_query, model=self.model)

        # Check if OpenAI client is available
        if not self.client:
            return self._run_simulated(user_query, tracer)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ]

        turn = 0
        while turn < max_turns:
            turn += 1
            
            # Start LLM Span
            span_id = tracer.start_span(
                name=f"openai_chat_turn_{turn}",
                span_type="LLM_CALL",
                input_data={"messages_count": len(messages), "model": self.model},
                metadata={"turn": turn}
            )

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=OPENAI_WEATHER_TOOLS,
                    tool_choice="auto"
                )
            except Exception as e:
                err_str = str(e)
                tracer.end_span(span_id, status="error", output_data={"error": err_str})
                
                # If Gemini/OpenAI rate limit (HTTP 429) is encountered, gracefully fall back to live direct weather fetch
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    fallback_ans, fallback_tracer = self._run_simulated(user_query, tracer)
                    rate_notice = "\n\n*(Note: Gemini Free Tier 5 requests/min rate-limit reached; retrieved directly from Open-Meteo live API)*"
                    final_ans = fallback_ans + rate_notice
                    fallback_tracer.complete(final_ans, status="success")
                    fallback_tracer.save_json()
                    return final_ans, fallback_tracer

                tracer.complete(f"API Error: {err_str}", status="error")
                tracer.save_json()
                return f"Error communicating with AI model: {err_str}", tracer

            choice = response.choices[0]
            message = choice.message
            usage = response.usage
            tokens = {
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0
            }

            # Check if tools were requested
            tool_calls = message.tool_calls or []

            llm_output_summary = {
                "finish_reason": choice.finish_reason,
                "tool_calls_requested": [tc.function.name for tc in tool_calls] if tool_calls else [],
                "response_preview": message.content[:100] if message.content else None
            }
            tracer.end_span(span_id, status="success", output_data=llm_output_summary, tokens=tokens)

            # Append assistant message to history
            messages.append(message)

            if not tool_calls:
                # Agent provided final answer
                final_text = message.content or "No response generated."
                tracer.complete(final_text, status="success")
                tracer.save_json()
                return final_text, tracer

            # Execute tool calls
            for tool_call in tool_calls:
                fn_name = tool_call.function.name
                fn_args_raw = tool_call.function.arguments
                try:
                    fn_args = json.loads(fn_args_raw)
                except Exception:
                    fn_args = {}

                tool_span_id = tracer.start_span(
                    name=fn_name,
                    span_type="TOOL_CALL",
                    input_data=fn_args,
                    metadata={"tool_call_id": tool_call.id}
                )

                # Dispatch tool
                fn = TOOL_DISPATCHER.get(fn_name)
                if fn:
                    try:
                        tool_result = fn(**fn_args)
                        status = "error" if "error" in tool_result else "success"
                    except Exception as exc:
                        tool_result = {"error": str(exc)}
                        status = "error"
                else:
                    tool_result = {"error": f"Tool '{fn_name}' not found."}
                    status = "error"

                tracer.end_span(tool_span_id, status=status, output_data=tool_result)

                # Append tool response message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False)
                })

        final_text = "Maximum interaction turns reached without completion."
        tracer.complete(final_text, status="warning")
        tracer.save_json()
        return final_text, tracer

    def _run_simulated(self, user_query: str, tracer: AgentTracer) -> Tuple[str, AgentTracer]:
        """
        Intelligent local simulation mode when no OPENAI_API_KEY is configured.
        Extracts city names, calls real Open-Meteo APIs, and records realistic traces.
        """
        span_id = tracer.start_span(
            name="openai_intent_analysis (local runner)",
            span_type="LLM_CALL",
            input_data={"prompt": user_query, "mode": "zero-key-live-weather"},
            metadata={"note": "Live Open-Meteo tool calling with local tracer"}
        )

        is_forecast = any(w in user_query.lower() for w in ["forecast", "tomorrow", "week", "days", "weekend"])
        
        # Check comparison query (e.g. "NY vs Paris" or "How is the weather in New York compared to Paris?")
        comp_match = re.search(r"([A-Za-z\s]+?)\s+(?:vs\.?|versus|compared\s+to)\s+([A-Za-z\s\?]+)", user_query, re.IGNORECASE)
        if comp_match:
            raw1 = comp_match.group(1).strip()
            raw2 = comp_match.group(2).strip()
            c1 = re.sub(r"(?i)\b(what|how|is|the|weather|in|like|between|currently|right now)\b", "", raw1).strip()
            c2 = re.sub(r"(?i)\b(what|how|is|the|weather|in|like|currently|right now|\?)\b", "", raw2).strip()
            c1 = re.sub(r"[^A-Za-z\s]", "", c1).strip()
            c2 = re.sub(r"[^A-Za-z\s]", "", c2).strip()
            if c1 and c2:
                tracer.end_span(span_id, status="success", output_data={"tool_calls_requested": ["get_current_weather", "get_current_weather"]}, tokens={"prompt_tokens": 55, "completion_tokens": 25, "total_tokens": 80})

                span1 = tracer.start_span(name="get_current_weather", span_type="TOOL_CALL", input_data={"city": c1})
                w1 = get_current_weather(c1)
                tracer.end_span(span1, status="error" if "error" in w1 else "success", output_data=w1)

                span2 = tracer.start_span(name="get_current_weather", span_type="TOOL_CALL", input_data={"city": c2})
                w2 = get_current_weather(c2)
                tracer.end_span(span2, status="error" if "error" in w2 else "success", output_data=w2)

                synth_span = tracer.start_span(name="openai_response_synthesis (local runner)", span_type="LLM_CALL", input_data={"tool_results": 2}, metadata={"turn": 2})

                if "error" in w1 and "error" in w2:
                    ans = f"⚠️ Could not fetch weather comparison: {w1.get('error', '')} | {w2.get('error', '')}"
                else:
                    ans = f"⚖️ **Weather Comparison: {c1.title()} vs {c2.title()}**\n\n"
                    if "current_weather" in w1:
                        cw1, loc1 = w1["current_weather"], w1["location"]
                        ans += f"📍 **{loc1['city']}, {loc1['country']}**:\n- **Condition**: {cw1['condition']}\n- **Temperature**: {cw1['temperature']} (Feels like: {cw1['feels_like']})\n- **Humidity**: {cw1['humidity']} | **Wind**: {cw1['wind_speed']}\n\n"
                    if "current_weather" in w2:
                        cw2, loc2 = w2["current_weather"], w2["location"]
                        ans += f"📍 **{loc2['city']}, {loc2['country']}**:\n- **Condition**: {cw2['condition']}\n- **Temperature**: {cw2['temperature']} (Feels like: {cw2['feels_like']})\n- **Humidity**: {cw2['humidity']} | **Wind**: {cw2['wind_speed']}\n\n"
                    ans += "💡 Real-time observation data verified via Open-Meteo."

                tracer.end_span(synth_span, status="success", output_data={"response_preview": ans[:100]}, tokens={"prompt_tokens": 110, "completion_tokens": 140, "total_tokens": 250})
                tracer.complete(ans, status="success")
                tracer.save_json()
                return ans, tracer

        # Robust city extraction heuristic for simulation mode
        clean_q = re.sub(r"(?i)\b(what|how|is|the|weather|like|right now|currently|current|tell me|please|show|today|tomorrow|this week|weekend|forecast|should i carry an umbrella in|should i bring an umbrella in|do i need an umbrella in|will it rain in|in|for|at|of|evening|morning|night|afternoon)\b", "", user_query)
        match = re.search(r"\b(?:in|for|at|of)\s+([A-Za-z\s]+?)(?:\s+(?:right\s+now|now|today|tomorrow|this\s+week|this\s+weekend|evening|morning|night|afternoon)|\?|\.|\,|$)", user_query, re.IGNORECASE)
        if match:
            city_candidate = match.group(1).strip()
            city_candidate = re.sub(r"(?i)\b(right now|now|today|tomorrow|this week|weekend|evening|morning|night|afternoon)\b", "", city_candidate).strip()
            city = city_candidate if city_candidate else clean_q.strip()
        else:
            city = clean_q.strip()

        city = re.sub(r"[^A-Za-z\s]", "", city).strip()
        if not city:
            city = "London"

        selected_tool = "get_weather_forecast" if is_forecast else "get_current_weather"
        tracer.end_span(span_id, status="success", output_data={"tool_calls_requested": [selected_tool]}, tokens={"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60})

        # Tool execution span
        tool_args = {"city": city, "days": 3} if is_forecast else {"city": city}
        tool_span_id = tracer.start_span(
            name=selected_tool,
            span_type="TOOL_CALL",
            input_data=tool_args
        )

        if is_forecast:
            tool_res = get_weather_forecast(city, days=3)
        else:
            tool_res = get_current_weather(city)

        status = "error" if "error" in tool_res else "success"
        tracer.end_span(tool_span_id, status=status, output_data=tool_res)

        # Synthesis span
        synth_span = tracer.start_span(
            name="openai_response_synthesis (local runner)",
            span_type="LLM_CALL",
            input_data={"tool_result": "received"},
            metadata={"turn": 2}
        )

        # Specific recommendation check (e.g. umbrella inquiry)
        umbrella_advice = ""
        if "umbrella" in user_query.lower() or "rain" in user_query.lower():
            will_rain = False
            if is_forecast and "forecast" in tool_res:
                for day in tool_res["forecast"]:
                    prob = int(re.sub(r"[^\d]", "", day.get("precipitation_probability", "0")) or 0)
                    if prob >= 35 or "rain" in day.get("condition", "").lower() or "drizzle" in day.get("condition", "").lower():
                        will_rain = True
                        break
            elif "current_weather" in tool_res:
                cw = tool_res["current_weather"]
                if "rain" in cw.get("condition", "").lower() or "drizzle" in cw.get("condition", "").lower():
                    will_rain = True

            if will_rain:
                umbrella_advice = "☔ **Yes, you should carry an umbrella!** Rain or showers are expected.\n\n"
            else:
                umbrella_advice = "☀️ **No umbrella needed!** Dry or clear conditions are anticipated.\n\n"

        if "error" in tool_res:
            ans = f"⚠️ Could not fetch weather: {tool_res['error']}"
        elif not is_forecast:
            cw = tool_res["current_weather"]
            loc = tool_res["location"]
            ans = (
                f"{umbrella_advice}"
                f"🌤️ Current Weather in **{loc['city']}, {loc['country']}**:\n"
                f"- **Condition**: {cw['condition']}\n"
                f"- **Temperature**: {cw['temperature']} (Feels like: {cw['feels_like']})\n"
                f"- **Humidity**: {cw['humidity']}\n"
                f"- **Wind Speed**: {cw['wind_speed']}\n"
                f"- **Precipitation**: {cw['precipitation']}\n"
                f"- **Day/Night**: {cw['is_day']}\n\n"
                f"💡 Real-time observation from Open-Meteo API."
            )
        else:
            loc = tool_res["location"]
            lines = [f"{umbrella_advice}📅 **{tool_res['forecast_days']}-Day Weather Forecast for {loc['city']}, {loc['country']}**:"]
            for f in tool_res["forecast"]:
                lines.append(
                    f"• **{f['date']}**: {f['condition']} | Max: {f['max_temp']}, Min: {f['min_temp']} | Rain Prob: {f['precipitation_probability']}"
                )
            ans = "\n".join(lines)

        tracer.end_span(synth_span, status="success", output_data={"response_preview": ans[:100]}, tokens={"prompt_tokens": 85, "completion_tokens": 120, "total_tokens": 205})
        tracer.complete(ans, status="success")
        tracer.save_json()
        return ans, tracer
