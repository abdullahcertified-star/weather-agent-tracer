"""
Weather Tools Module
Provides integration with Open-Meteo free weather and geocoding APIs.
No API key required.
"""

from typing import Any, Dict, Optional
import requests

WMO_WEATHER_CODES = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤️",
    2: "Partly cloudy ⛅",
    3: "Overcast ☁️",
    45: "Fog 🌫️",
    48: "Depositing rime fog 🌫️",
    51: "Light drizzle 🌦️",
    53: "Moderate drizzle 🌦️",
    55: "Dense drizzle 🌧️",
    56: "Light freezing drizzle 🌧️❄️",
    57: "Dense freezing drizzle 🌧️❄️",
    61: "Slight rain 🌦️",
    63: "Moderate rain 🌧️",
    65: "Heavy rain 🌧️⛈️",
    66: "Light freezing rain 🌧️❄️",
    67: "Heavy freezing rain 🌧️❄️",
    71: "Slight snow fall 🌨️",
    73: "Moderate snow fall 🌨️",
    75: "Heavy snow fall ❄️🌨️",
    77: "Snow grains ❄️",
    80: "Slight rain showers 🌦️",
    81: "Moderate rain showers 🌧️",
    82: "Violent rain showers ⛈️",
    85: "Slight snow showers 🌨️",
    86: "Heavy snow showers ❄️🌨️",
    95: "Thunderstorm ⛈️",
    96: "Thunderstorm with slight hail ⛈️🌨️",
    99: "Thunderstorm with heavy hail ⛈️⚡",
}


def get_weather_description(code: int) -> str:
    """Translate WMO weather code to human readable description."""
    return WMO_WEATHER_CODES.get(code, f"Unknown weather condition (Code {code})")


def geocode_city(city_name: str) -> Optional[Dict[str, Any]]:
    """
    Geocode a city name into latitude, longitude, and metadata using Open-Meteo Geocoding API.
    Includes intelligent typo-tolerance and prefix matching.
    """
    import difflib
    import re

    # Remove conversational / temporal words that might be attached
    cleaned = re.sub(r"(?i)\b(morning|afternoon|evening|night|tonight|today|tomorrow|weekend|weather|forecast|right now|currently|umbrella)\b", "", city_name).strip()
    city_cleaned = cleaned if cleaned else city_name.strip()
    city_cleaned = re.sub(r"[^A-Za-z\s\-\']", "", city_cleaned).strip()
    
    if not city_cleaned:
        return None

    # Common aliases & abbreviations
    aliases = {
        "ny": "New York",
        "nyc": "New York",
        "la": "Los Angeles",
        "sf": "San Francisco",
        "dc": "Washington",
        "kl": "Kuala Lumpur",
        "faisalabd": "Faisalabad"
    }
    city_cleaned = aliases.get(city_cleaned.lower(), city_cleaned)

    url = "https://geocoding-api.open-meteo.com/v1/search"
    
    # 1. Exact / direct query
    try:
        response = requests.get(url, params={"name": city_cleaned, "count": 5, "language": "en", "format": "json"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = data.get("results") or []
        
        if results:
            # Pick highest population or exact match
            res = results[0]
            for r in results:
                if r.get("name", "").lower() == city_cleaned.lower():
                    res = r
                    break
            return {
                "name": res.get("name"),
                "latitude": res.get("latitude"),
                "longitude": res.get("longitude"),
                "country": res.get("country"),
                "admin1": res.get("admin1", ""),
                "timezone": res.get("timezone", "UTC")
            }
    except Exception as e:
        return {"error": f"Failed to geocode location '{city_name}': {str(e)}"}

    # 2. Fuzzy / Typo tolerance: try prefix variations if >= 4 characters
    if len(city_cleaned) >= 4:
        for prefix_len in [len(city_cleaned) - 1, len(city_cleaned) - 2, max(4, len(city_cleaned) - 3)]:
            prefix = city_cleaned[:prefix_len]
            try:
                resp = requests.get(url, params={"name": prefix, "count": 10, "language": "en", "format": "json"}, timeout=8)
                if resp.status_code == 200:
                    cand_results = resp.json().get("results") or []
                    if cand_results:
                        names_map = {r.get("name"): r for r in cand_results if r.get("name")}
                        matches = difflib.get_close_matches(city_cleaned, list(names_map.keys()), n=1, cutoff=0.55)
                        if matches:
                            matched_res = names_map[matches[0]]
                            return {
                                "name": matched_res.get("name"),
                                "latitude": matched_res.get("latitude"),
                                "longitude": matched_res.get("longitude"),
                                "country": matched_res.get("country"),
                                "admin1": matched_res.get("admin1", ""),
                                "timezone": matched_res.get("timezone", "UTC"),
                                "auto_corrected_from": city_cleaned
                            }
            except Exception:
                continue

    return None


def get_current_weather(city: str) -> Dict[str, Any]:
    """
    Get real-time current weather for a city including temperature, feels-like,
    humidity, precipitation, wind speed, and conditions.
    """
    geo = geocode_city(city)
    if not geo:
        return {"error": f"City '{city}' could not be located. Please check the spelling."}
    if "error" in geo:
        return geo

    lat = geo["latitude"]
    lon = geo["longitude"]
    timezone = geo.get("timezone", "auto")

    forecast_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": [
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "is_day",
            "precipitation",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m"
        ],
        "timezone": timezone
    }

    try:
        resp = requests.get(forecast_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        current = data.get("current", {})
        current_units = data.get("current_units", {})
        weather_code = current.get("weather_code", 0)

        return {
            "status": "success",
            "location": {
                "city": geo["name"],
                "region": geo["admin1"],
                "country": geo["country"],
                "latitude": lat,
                "longitude": lon,
                "timezone": timezone
            },
            "current_weather": {
                "temperature": f"{current.get('temperature_2m')} {current_units.get('temperature_2m', '°C')}",
                "feels_like": f"{current.get('apparent_temperature')} {current_units.get('apparent_temperature', '°C')}",
                "humidity": f"{current.get('relative_humidity_2m')} {current_units.get('relative_humidity_2m', '%')}",
                "condition": get_weather_description(weather_code),
                "weather_code": weather_code,
                "is_day": "Day" if current.get("is_day") == 1 else "Night",
                "precipitation": f"{current.get('precipitation', 0)} {current_units.get('precipitation', 'mm')}",
                "wind_speed": f"{current.get('wind_speed_10m')} {current_units.get('wind_speed_10m', 'km/h')}",
                "time": current.get("time")
            }
        }
    except Exception as e:
        return {"error": f"Error retrieving weather data for '{city}': {str(e)}"}


def get_weather_forecast(city: str, days: int = 3) -> Dict[str, Any]:
    """
    Get weather forecast for a specified number of days (1 to 7) for a city.
    """
    days = max(1, min(days, 7))
    geo = geocode_city(city)
    if not geo:
        return {"error": f"City '{city}' could not be located."}
    if "error" in geo:
        return geo

    lat = geo["latitude"]
    lon = geo["longitude"]
    timezone = geo.get("timezone", "auto")

    forecast_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "apparent_temperature_max",
            "apparent_temperature_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "wind_speed_10m_max"
        ],
        "timezone": timezone,
        "forecast_days": days
    }

    try:
        resp = requests.get(forecast_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        daily = data.get("daily", {})
        units = data.get("daily_units", {})

        forecast_list = []
        times = daily.get("time", [])
        for i, day_date in enumerate(times):
            code = daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else 0
            forecast_list.append({
                "date": day_date,
                "condition": get_weather_description(code),
                "max_temp": f"{daily.get('temperature_2m_max', [])[i]} {units.get('temperature_2m_max', '°C')}",
                "min_temp": f"{daily.get('temperature_2m_min', [])[i]} {units.get('temperature_2m_min', '°C')}",
                "precipitation_probability": f"{daily.get('precipitation_probability_max', [])[i]} {units.get('precipitation_probability_max', '%')}",
                "precipitation_sum": f"{daily.get('precipitation_sum', [])[i]} {units.get('precipitation_sum', 'mm')}",
                "max_wind": f"{daily.get('wind_speed_10m_max', [])[i]} {units.get('wind_speed_10m_max', 'km/h')}"
            })

        return {
            "status": "success",
            "location": {
                "city": geo["name"],
                "region": geo["admin1"],
                "country": geo["country"],
                "timezone": timezone
            },
            "forecast_days": days,
            "forecast": forecast_list
        }
    except Exception as e:
        return {"error": f"Error retrieving forecast for '{city}': {str(e)}"}


# OpenAI Function Calling Tool Definitions
OPENAI_WEATHER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_weather",
            "description": "Get real-time current weather conditions, temperature, humidity, precipitation, and wind for any city worldwide using Open-Meteo free API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Name of the city (e.g. 'Tokyo', 'London', 'New York', 'Paris', 'Lahore')"
                    }
                },
                "required": ["city"],
                "additionalProperties": False
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": "Get multi-day weather forecast (up to 7 days) including maximum/minimum temperatures, rain probability, and conditions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Name of the city"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of forecast days (between 1 and 7, default is 3)",
                        "default": 3
                    }
                },
                "required": ["city"],
                "additionalProperties": False
            }
        }
    }
]

TOOL_DISPATCHER = {
    "get_current_weather": get_current_weather,
    "get_weather_forecast": get_weather_forecast
}
