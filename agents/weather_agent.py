"""
agents/weather_agent.py

LangChain "tool-calling" agent that:
- must use get_weather tool (Open-Meteo connector) before answering
- returns a friendly explanation grounded in the retrieved data

Notes for teaching:
- This file shows the "agent layer" separated from the API layer.
- Tools are how we connect LLM reasoning to real-world actions/data.

Environment:
- OPENAI_API_KEY must exist (loaded by dotenv in main.py)
"""

from __future__ import annotations

import os
from typing import Any, Dict

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain.agents import AgentExecutor, create_tool_calling_agent

from services.open_meteo import resolve_location_to_coords, get_weather_raw, adapt_open_meteo_response


@tool
def get_weather(location: str) -> Dict[str, Any]:
    """
    Get real weather data for a location.

    Input:
      location: City name (e.g., "Lima") OR "lat,lon" (e.g., "-33.45,-70.66")

    Output:
      A compact JSON dict with:
        - current conditions
        - today's min/max and precipitation sum
        - next_hours (6 entries)
    """
    coords = resolve_location_to_coords(location)
    provider_json = get_weather_raw(lat=coords["lat"], lon=coords["lon"], timezone="auto")
    adapted = adapt_open_meteo_response(provider_json)
    adapted["resolved_location"] = coords
    return adapted


def build_weather_agent() -> AgentExecutor:
    """
    Build and return an AgentExecutor that can call get_weather tool.

    The prompt enforces:
    - call get_weather at least once before answering
    - do not fabricate data
    - explain in plain language and include key numbers
    """
    model_name = os.getenv("OPENAI_MODEL", "gpt-5.1")

    llm = ChatOpenAI(
        model=model_name,
    )

    tools = [get_weather]

    system = (
        "You are a helpful weather assistant for business users.\n"
        "Rules:\n"
        "1) You MUST call the tool get_weather before answering.\n"
        "2) Use only the tool output for facts; do not invent weather.\n"
        "3) Explain simply for non-experts.\n"
        "4) Include key numbers (temperature, precipitation probability, wind) and a short recommendation.\n"
        "5) If the user question is unclear, ask one clarifying question.\n"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)
    executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return executor
