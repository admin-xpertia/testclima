# Weather Explainer API (FastAPI + Open‑Meteo + LangChain + OpenAI)

This lab project corresponds to **Session 2: APIs and connectors for LLMs**.  
You will build a small **integration API** that:

1) Calls a real external provider (**Open‑Meteo**) to fetch weather (connector)  
2) Adapts the provider response to a stable internal contract (adapter pattern)  
3) Exposes your own endpoints via **FastAPI**  
4) Adds an **LLM agent** (LangChain + OpenAI) to explain the weather in natural language

---

## Project structure

```
weather_explainer_api/
  main.py
  services/
    open_meteo.py
  agents/
    weather_agent.py
  .env.example
  requirements.txt
```

---

## Requirements

- Python 3.10+ recommended
- An OpenAI API key

---

## Setup in VS Code (step-by-step)

### 1) Open the folder
- Open VS Code
- `File → Open Folder…`
- Select the folder `weather_explainer_api`

### 2) Create a virtual environment
In VS Code Terminal:

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell)**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3) Install dependencies
```bash
pip install -r requirements.txt
```

### 4) Configure environment variables
Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Then open `.env` and set:
- `OPENAI_API_KEY=...`
- optionally `OPENAI_MODEL=gpt-4o-mini`

### 5) Run the API
```bash
uvicorn main:app --reload
```

You should see something like:
- `Uvicorn running on http://127.0.0.1:8000`

### 6) Try the Swagger UI
Open in browser:
- http://127.0.0.1:8000/docs

---

## Endpoints

### Health
- `GET /health`

### Raw weather (adapter demo)
- `GET /weather/raw?lat=-33.45&lon=-70.66`

Returns a normalized JSON with:
- `current` (temp, wind, precipitation, cloud cover)
- `today` (min/max and precipitation sum)
- `next_hours` (6 hours)

### Conversational weather (agent)
- `POST /weather/ask`

Body example:
```json
{
  "question": "¿Necesito paraguas hoy? Explica con números.",
  "location": "Santiago",
  "units": "metric"
}
```

Notes:
- `location` can be a city name (uses Open‑Meteo geocoding) **or** `"lat,lon"` string.

---

## Teaching notes (what to discuss)

- **Connector pattern**: `services/open_meteo.py` is the external integration layer.
- **Adapter pattern**: `adapt_open_meteo_response()` creates a stable contract.
- **Tool calling**: the agent MUST call `get_weather()` tool before answering.
- **Separation of concerns**:
  - API layer (FastAPI) vs Integration layer (Open‑Meteo) vs Agent layer (LangChain)

---

## Troubleshooting

**1) OPENAI_API_KEY is missing**
- Ensure you created `.env` and placed it at the project root
- Ensure `OPENAI_API_KEY` is set

**2) Import errors with LangChain**
- Upgrade packages:
```bash
pip install -U langchain langchain-openai langchain-core
```

**3) Open‑Meteo errors**
- Check your internet connection
- Try calling `/weather/raw` first to validate the provider connection
