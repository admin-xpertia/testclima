from fastapi.testclient import TestClient

from main import app
from services.open_meteo import adapt_open_meteo_response, resolve_location_to_coords


client = TestClient(app)


# --- Endpoint tests ---

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_redirects():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307


def test_weather_raw_invalid_lat():
    response = client.get("/weather/raw", params={"lat": 999, "lon": 0})
    assert response.status_code == 422


def test_weather_raw_missing_params():
    response = client.get("/weather/raw")
    assert response.status_code == 422


# --- Adapter tests ---

def test_adapt_open_meteo_response_empty():
    result = adapt_open_meteo_response({})
    assert "current" in result
    assert "today" in result
    assert "next_hours" in result
    assert result["next_hours"] == []


def test_adapt_open_meteo_response_with_data():
    fake_provider = {
        "current": {
            "time": "2026-01-01T12:00",
            "temperature_2m": 22.5,
            "wind_speed_10m": 10.0,
            "precipitation": 0.0,
            "cloud_cover": 30,
        },
        "daily": {
            "time": ["2026-01-01"],
            "temperature_2m_min": [15.0],
            "temperature_2m_max": [25.0],
            "precipitation_sum": [0.0],
        },
        "hourly": {
            "time": ["2026-01-01T12:00", "2026-01-01T13:00"],
            "temperature_2m": [22.5, 23.0],
            "precipitation_probability": [10, 20],
            "precipitation": [0.0, 0.0],
            "wind_speed_10m": [10.0, 11.0],
        },
    }

    result = adapt_open_meteo_response(fake_provider)

    assert result["current"]["temp_c"] == 22.5
    assert result["today"]["temp_max_c"] == 25.0
    assert len(result["next_hours"]) == 2
    assert result["next_hours"][0]["precip_prob_pct"] == 10


# --- Location resolver tests ---

def test_resolve_location_lat_lon():
    result = resolve_location_to_coords("-33.45,-70.66")
    assert result["lat"] == -33.45
    assert result["lon"] == -70.66
