"""
Weather Explainer API (FastAPI + Open-Meteo + LangChain Agent)

This project is designed for a guided lab (Session 2: APIs & connectors for LLMs).
It demonstrates how to:
- consume an external REST API (Open-Meteo) as a connector,
- normalize/adapt third‑party data into a stable contract,
- expose your own API endpoints with FastAPI,
- and add an LLM agent layer (LangChain + OpenAI) that explains the data in natural language.

Files:
- main.py                     -> FastAPI app (endpoints + wiring)
- services/open_meteo.py       -> Open-Meteo client + data adapter
- agents/weather_agent.py      -> LangChain tool + agent executor
- .env.example                 -> environment variables template
"""

from __future__ import annotations

import os
from typing import Optional, Literal, Dict, Any

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from services.open_meteo import (
    resolve_location_to_coords,
    get_weather_raw,
    adapt_open_meteo_response,
)
from agents.weather_agent import build_weather_agent

# Load environment variables from .env (only in local dev; in production use real env vars)
load_dotenv()

app = FastAPI(
    title="Weather Explainer API",
    version="1.0.0",
    description=(
        "A teaching API that integrates an external data provider (Open-Meteo) "
        "and an LLM agent (LangChain + OpenAI) to explain the weather."
    ),
)


# -----------------------------
# Models
# -----------------------------
class WeatherRawResponse(BaseModel):
    provider: str = "open-meteo"
    location: Dict[str, Any]
    data: Dict[str, Any]


class WeatherAskRequest(BaseModel):
    question: str = Field(..., description="User question in natural language (e.g., 'Do I need an umbrella today?').")
    location: Optional[str] = Field(None, description="City name (e.g., 'Lima') OR 'lat,lon' string (e.g., '-33.45,-70.66').")
    units: Literal["metric", "imperial"] = Field("metric", description="Units to present. Open-Meteo returns metric by default.")


class WeatherAskResponse(BaseModel):
    answer: str
    used_location: Dict[str, Any]
    raw_summary: Dict[str, Any]


# -----------------------------
# Helpers
# -----------------------------
def _validate_lat_lon(lat: float, lon: float) -> None:
    if not (-90.0 <= lat <= 90.0):
        raise HTTPException(status_code=422, detail="lat must be between -90 and 90")
    if not (-180.0 <= lon <= 180.0):
        raise HTTPException(status_code=422, detail="lon must be between -180 and 180")


# -----------------------------
# Endpoints
# -----------------------------
@app.get("/")
def root():
    """Redirect to the chat UI."""
    return RedirectResponse(url="/chat/chat.html")


app.mount("/chat", StaticFiles(directory=Path(__file__).parent / "static"), name="chat")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/weather/raw", response_model=WeatherRawResponse)
def weather_raw(
    lat: float = Query(..., description="Latitude (e.g., -33.45)"),
    lon: float = Query(..., description="Longitude (e.g., -70.66)"),
    timezone: str = Query("auto", description="Timezone for Open-Meteo (default: auto)"),
):
    """
    Returns adapted/normalized raw weather data from Open-Meteo.

    Why this endpoint exists:
    - It shows how to integrate an external REST API.
    - It produces a stable contract (adapter pattern), so your clients depend on YOUR schema, not the provider's.
    """
    _validate_lat_lon(lat, lon)

    try:
        provider_json = get_weather_raw(lat=lat, lon=lon, timezone=timezone)
        adapted = adapt_open_meteo_response(provider_json)
        return WeatherRawResponse(
            location={"lat": lat, "lon": lon, "timezone": timezone},
            data=adapted,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Open-Meteo request failed: {e}") from e


@app.post("/weather/ask", response_model=WeatherAskResponse)
def weather_ask(req: WeatherAskRequest):
    """
    Conversational endpoint:
    - Accepts a natural language question.
    - Resolves the location.
    - Uses a LangChain tool-calling agent that MUST call get_weather to answer.
    - Returns a friendly explanation grounded in real weather data.
    """
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is missing. Create a .env file from .env.example")

    # Resolve location:
    # - If user provided "lat,lon", use it
    # - Otherwise geocode city name via Open-Meteo geocoding
    if not req.location:
        raise HTTPException(
            status_code=422,
            detail="location is required for this lab. Provide a city name (e.g., 'Lima') or 'lat,lon' (e.g., '-33.45,-70.66').",
        )

    try:
        coords = resolve_location_to_coords(req.location)
        _validate_lat_lon(coords["lat"], coords["lon"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not resolve location: {e}") from e

    # Build the agent (LLM + tools)
    agent = build_weather_agent()

    # Provide context to the agent as a short, structured instruction.
    # The agent can call tools to fetch data, then explain it.
    user_prompt = (
        f"User location: {coords['name']} (lat={coords['lat']}, lon={coords['lon']}).\n"
        f"Units: {req.units}.\n"
        f"Question: {req.question}\n"
        f"Please answer clearly for a non-expert and cite the key numbers (temp, precipitation, wind)."
    )

    try:
        result = agent.invoke({"input": user_prompt})
        answer = result.get("output", "").strip()

        # For transparency in teaching: also return a compact summary of the raw adapted weather.
        provider_json = get_weather_raw(lat=coords["lat"], lon=coords["lon"], timezone="auto")
        adapted = adapt_open_meteo_response(provider_json)

        return WeatherAskResponse(
            answer=answer,
            used_location=coords,
            raw_summary=adapted,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {e}") from e
