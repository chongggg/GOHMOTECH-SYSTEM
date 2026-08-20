import logging
from typing import Any

import requests
from django.conf import settings
from django.core.cache import cache


logger = logging.getLogger(__name__)


WEATHER_CODE_LABELS = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _safe_float(raw: Any, default: float) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _weather_label(code: Any) -> str:
    try:
        return WEATHER_CODE_LABELS.get(int(code), "Unknown")
    except (TypeError, ValueError):
        return "Unknown"


def _fetch_open_meteo(latitude: float, longitude: float, timezone_name: str) -> dict[str, Any]:
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            # Request current weather block and hourly fields for humidity/precipitation
            "current_weather": True,
            "hourly": "relativehumidity_2m,precipitation_probability",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "forecast_days": 1,
            "timezone": timezone_name,
        },
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()

    # Open-Meteo returns a `current_weather` block and separate `hourly` / `daily` blocks.
    current = payload.get("current_weather") or {}
    hourly = payload.get("hourly") or {}
    daily = payload.get("daily") or {}

    weather_code = current.get("weathercode") or current.get("weather_code")

    # Try to pick humidity and precipitation probability from hourly that matches current time
    humidity = None
    precip_prob = None
    try:
        times = hourly.get("time") or []
        if times and current.get("time") in times:
            idx = times.index(current.get("time"))
            rh = hourly.get("relativehumidity_2m") or []
            pp = hourly.get("precipitation_probability") or []
            if idx < len(rh):
                humidity = rh[idx]
            if idx < len(pp):
                precip_prob = pp[idx]
        else:
            # Fallback to first available hourly values
            rh = hourly.get("relativehumidity_2m") or []
            pp = hourly.get("precipitation_probability") or []
            if rh:
                humidity = rh[0]
            if pp:
                precip_prob = pp[0]
    except Exception:
        humidity = None
        precip_prob = None

    return {
        "available": True,
        "provider": "Open-Meteo",
        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "updated_at": current.get("time"),
        "summary": _weather_label(weather_code),
        "weather_code": weather_code,
        "is_day": current.get("is_day"),
        # current weather fields
        "temperature_c": current.get("temperature") or current.get("temperature_2m"),
        "humidity_pct": humidity,
        "rain_mm": None,
        "rain_chance_pct": precip_prob,
        "wind_kph": current.get("windspeed") or current.get("wind_speed_10m"),
        "today_max_c": (daily.get("temperature_2m_max") or [None])[0],
        "today_min_c": (daily.get("temperature_2m_min") or [None])[0],
        "today_rain_chance_pct": (daily.get("precipitation_probability_max") or [None])[0],
        "stale": False,
    }


def get_farm_weather(force_refresh: bool = False) -> dict[str, Any]:
    """Return cached weather snapshot for farm coordinates.

    Uses Open-Meteo free endpoint, cached to reduce external calls and improve resilience.
    """
    if not getattr(settings, "WEATHER_ENABLED", True):
        return {"available": False, "provider": "Open-Meteo", "reason": "disabled"}

    latitude = _safe_float(getattr(settings, "WEATHER_LATITUDE", 14.5995), 14.5995)
    longitude = _safe_float(getattr(settings, "WEATHER_LONGITUDE", 120.9842), 120.9842)
    timezone_name = getattr(settings, "TIME_ZONE", "Asia/Manila")
    ttl_minutes = int(getattr(settings, "WEATHER_CACHE_TTL_MINUTES", 15))

    cache_key = f"farm_weather:{latitude:.4f}:{longitude:.4f}"
    last_success_key = f"{cache_key}:last_success"

    if not force_refresh:
        cached = cache.get(cache_key)
        if cached:
            return cached

    try:
        weather_info = _fetch_open_meteo(latitude, longitude, timezone_name)
        cache.set(cache_key, weather_info, timeout=ttl_minutes * 60)
        cache.set(last_success_key, weather_info, timeout=None)
        return weather_info
    except Exception as exc:
        logger.warning("Weather fetch failed: %s", exc)
        fallback = cache.get(last_success_key)
        if fallback:
            fallback_copy = dict(fallback)
            fallback_copy["stale"] = True
            return fallback_copy
        return {
            "available": False,
            "provider": "Open-Meteo",
            "reason": "fetch_failed",
            "summary": "Unavailable",
        }
