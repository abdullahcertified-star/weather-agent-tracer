"""
Unit and Integration Tests for Weather Agent & Tracing System
"""

import os
import sys
import unittest

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from weather_tools import (
    OPENAI_WEATHER_TOOLS,
    TOOL_DISPATCHER,
    geocode_city,
    get_current_weather,
    get_weather_forecast,
)
from tracer import AgentTracer
from agent import WeatherAgent


class TestWeatherTools(unittest.TestCase):
    def test_geocode_valid_city(self):
        result = geocode_city("Paris")
        self.assertIsNotNone(result)
        self.assertNotIn("error", result)
        self.assertEqual(result["name"], "Paris")
        self.assertIn("latitude", result)
        self.assertIn("longitude", result)

    def test_geocode_invalid_city(self):
        result = geocode_city("ThisCityDoesNotExist123xyz")
        self.assertIsNone(result)

    def test_get_current_weather_valid(self):
        res = get_current_weather("Berlin")
        self.assertEqual(res["status"], "success")
        self.assertIn("current_weather", res)
        cw = res["current_weather"]
        self.assertIn("temperature", cw)
        self.assertIn("humidity", cw)
        self.assertIn("condition", cw)

    def test_get_current_weather_invalid(self):
        res = get_current_weather("InvalidCity999XYZ")
        self.assertIn("error", res)

    def test_get_weather_forecast(self):
        res = get_weather_forecast("Rome", days=2)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["forecast_days"], 2)
        self.assertEqual(len(res["forecast"]), 2)
        self.assertIn("max_temp", res["forecast"][0])

    def test_openai_tool_definitions(self):
        self.assertEqual(len(OPENAI_WEATHER_TOOLS), 2)
        tool_names = [t["function"]["name"] for t in OPENAI_WEATHER_TOOLS]
        self.assertIn("get_current_weather", tool_names)
        self.assertIn("get_weather_forecast", tool_names)
        for name in tool_names:
            self.assertIn(name, TOOL_DISPATCHER)


class TestAgentTracer(unittest.TestCase):
    def test_tracer_lifecycle(self):
        tracer = AgentTracer(query="Test query", model="gpt-4o-mini")
        self.assertTrue(tracer.trace_id.startswith("trace_"))
        
        span_id = tracer.start_span("test_llm", "LLM_CALL", input_data={"q": 1})
        tracer.end_span(span_id, status="success", tokens={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        
        tracer.complete("Final result", status="success")
        
        self.assertEqual(tracer.token_usage["total_tokens"], 15)
        self.assertEqual(tracer.status, "success")
        self.assertIsNotNone(tracer.total_duration_ms)
        self.assertGreaterEqual(tracer.total_duration_ms, 0)
        
        # Test JSON export
        filepath = tracer.save_json(directory="traces")
        self.assertTrue(os.path.exists(filepath))


class TestWeatherAgent(unittest.TestCase):
    def test_agent_run(self):
        agent = WeatherAgent()
        response, tracer = agent.run("What is the weather in New York?")
        self.assertIsNotNone(response)
        self.assertIn("New York", response)
        self.assertEqual(tracer.status, "success")
        self.assertGreater(len(tracer.spans), 0)


if __name__ == "__main__":
    unittest.main()
