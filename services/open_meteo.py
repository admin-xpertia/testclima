"""
services/open_meteo.py

Open-Meteo connector + adapter for a stable, teaching-friendly contract.

Open-Meteo APIs used:
1) Geocoding (city -> lat/lon)
   https://geocoding-api.open-meteo.com/v1/search?name=Lima&count=1&language=en&format=json

2) Forecast
   https://api.open-meteo.com/v1/forecast?... (current + hourly + daily fields)

We keep it simple but "enterprise-ish":
- one function that calls the provider (connector)
- one function that adapts/normalizes the provider response (adapter pattern)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import json

import httpx


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def resolve_location_to_coords(location: str) -> Dict[str, Any]:
    """
    Resolve a location to coordinates.

    Accepted formats:
    - "lat,lon" string (e.g. "-33.45,-70.66")
    - City name (e.g. "Lima") via Open-Meteo geocoding

    Returns:
    {
      "name": "Lima, PE",
      "lat": -12.0464,
      "lon": -77.0428
    }
    """
    # Case 1: "lat,lon"
    if "," in location:
        parts = [p.strip() for p in location.split(",")]
        if len(parts) == 2:
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                return {"name": f"{lat},{lon}", "lat": lat, "lon": lon}
            except ValueError:
                pass  # fall through to geocoding

    # Case 2: geocode city
    with httpx.Client(timeout=15.0) as client:
        r = client.get(
            GEOCODING_URL,
            params={"name": location, "count": 1, "language": "en", "format": "json"},
        )
        r.raise_for_status()
        payload = r.json()

    results = payload.get("results") or []
    if not results:
        raise ValueError(f"No geocoding results for '{location}'")

    top = results[0]
    name_bits = [top.get("name"), top.get("admin1"), top.get("country_code")]
    clean_name = ", ".join([b for b in name_bits if b])
    return {"name": clean_name, "lat": float(top["latitude"]), "lon": float(top["longitude"])}


def get_weather_raw(lat: float, lon: float, timezone: str = "auto") -> Dict[str, Any]:
    """
    Calls Open-Meteo forecast endpoint and returns the provider JSON response.

    We request:
    - current weather summary
    - hourly: temperature, precipitation probability, precipitation, wind
    - daily: min/max temperature and precipitation sum (useful for "today")
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": timezone,
        "current": ["temperature_2m", "wind_speed_10m", "precipitation", "cloud_cover"],
        "hourly": ["temperature_2m", "precipitation_probability", "precipitation", "wind_speed_10m"],
        "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_sum"],
        "forecast_days": 2,
    }

    with httpx.Client(timeout=20.0) as client:
        r = client.get(FORECAST_URL, params=params)
        r.raise_for_status()
        return r.json()


def adapt_open_meteo_response(provider_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Adapter: normalize Open-Meteo response into a stable, small schema.

    Output shape:
    {
      "current": {...},
      "today": {...},
      "next_hours": [
         {"time": "...", "temp_c": 18.2, "precip_prob_pct": 40, "wind_kmh": 12.3, "precip_mm": 0.0},
         ...
      ]
    }
    """
    current = provider_json.get("current", {}) or {}
    daily = provider_json.get("daily", {}) or {}
    hourly = provider_json.get("hourly", {}) or {}

    # Current snapshot
    out_current = {
        "time": current.get("time"),
        "temp_c": current.get("temperature_2m"),
        "wind_kmh": current.get("wind_speed_10m"),
        "precip_mm": current.get("precipitation"),
        "cloud_cover_pct": current.get("cloud_cover"),
    }

    # Today's daily summary is index 0
    def _safe_first(arr: Any) -> Any:
        return arr[0] if isinstance(arr, list) and arr else None

    out_today = {
        "date": _safe_first(daily.get("time")),
        "temp_min_c": _safe_first(daily.get("temperature_2m_min")),
        "temp_max_c": _safe_first(daily.get("temperature_2m_max")),
        "precip_sum_mm": _safe_first(daily.get("precipitation_sum")),
    }

    # Next 6 hours summary from hourly arrays (index alignment)
    times: List[str] = hourly.get("time") or []
    temps: List[float] = hourly.get("temperature_2m") or []
    pprob: List[int] = hourly.get("precipitation_probability") or []
    precip: List[float] = hourly.get("precipitation") or []
    wind: List[float] = hourly.get("wind_speed_10m") or []

    next_hours = []
    n = min(len(times), len(temps), len(pprob), len(precip), len(wind))
    for i in range(min(n, 6)):
        next_hours.append(
            {
                "time": times[i],
                "temp_c": temps[i],
                "precip_prob_pct": pprob[i],
                "precip_mm": precip[i],
                "wind_kmh": wind[i],
            }
        )

    return {"current": out_current, "today": out_today, "next_hours": next_hours}
