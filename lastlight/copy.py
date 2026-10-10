"""Ticket copy: Gemma if a local/open endpoint is up, otherwise field recipes.

The recipes are not a joke fallback. They are the offline voice of the
product — a park bulletin, not a chatbot.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import httpx

from lastlight.sun import heading_name

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass
class TicketCopy:
    title: str
    lede: str
    cues: list[str]
    rule: str
    route: str
    writer: str
    model: str


def _month_name(day_of_year: int) -> str:
    # Approximate month from day-of-year
    cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    m = 11
    for i, c in enumerate(cum):
        if day_of_year <= c + 31:
            m = i
            break
    return MONTHS[min(m, 11)]


def recipes(
    *,
    heading_deg: float,
    day_of_year: int,
    lat: float,
    duration: int,
    sky: str,
    ground: str,
    foliage: float,
    urban: bool,
) -> TicketCopy:
    heading = heading_name(heading_deg)
    month = _month_name(day_of_year)
    hemi = "north" if lat >= 0 else "south"
    autumn = foliage > 0.35

    titles = {
        "clear": "Walk into the sun",
        "thin": "Thin cloud, still go",
        "heavy": "Low light, short loop",
        "rain": "Wet pavement, anyway",
        "wind": "Lean into it",
    }
    sky_lede = {
        "clear": "The sun will sit on the horizon like a coin. You do not need a photograph of it.",
        "thin": "The light will go milk-coloured before it goes. That is still the hour.",
        "heavy": "No colour tonight. Go for the air, and for the fact of leaving the room.",
        "rain": "Rain on a street is still weather. Hood up. Twenty minutes.",
        "wind": "The wind will do the talking. Keep your hands out of your pockets long enough to feel it.",
    }

    if autumn and hemi == "north":
        look = f"Look {heading}: which trees have dropped and which are still holding."
        notice = "Notice where the light is coming from without checking a compass. You already know."
    elif month in ("April", "May") and hemi == "north":
        look = f"Look {heading}: new leaves are a different green than the ones that wintered."
        notice = "Notice the first warm wall. Stand there for ten seconds."
    elif month in ("June", "July") and hemi == "north":
        look = f"Look {heading}: the sun is taking its time. You do not have to."
        notice = "Notice how late it still is, and leave anyway before the screen finds you."
    else:
        look = f"Look {heading} until you can say what colour the sky is without using the word nice."
        notice = "Notice one thing you have walked past a hundred times."

    listen = {
        "pavement": "Listen for a bird you cannot name. Do not open an app to name it.",
        "park": "Listen under the traffic. There is always something under the traffic.",
        "mixed": "Listen for the moment the pavement gives way to dirt, even if it is only a strip.",
    }[ground]
    touch = {
        "pavement": "Touch a railing or a wall that has been in the sun. Then one that has not.",
        "park": "Touch something living that is not a person. Bark is enough.",
        "mixed": "Touch the first unpaved thing you find. Dust, grass, a planter.",
    }[ground]
    if sky == "rain":
        touch = "Let one hand get wet. Then put it back in your pocket."

    where = "from your own door" if urban else "from wherever you are standing"
    route = (
        f"Step {where}. Walk {heading} for about {duration} minutes, "
        f"turning only when a street or a fence makes you. Do not pick a destination."
    )
    if ground == "park":
        route = (
            f"Walk to the nearest patch of unpaved ground, then {heading} along its edge "
            f"for {duration} minutes. If you cannot find a park, a tree in a median counts."
        )

    rule = "Phone in a pocket that is not your hand. If it buzzes, it can wait until the door."
    return TicketCopy(
        title=titles.get(sky, "Go anyway"),
        lede=sky_lede.get(sky, sky_lede["thin"]),
        cues=[look, listen, touch, notice],
        rule=rule,
        route=route,
        writer="field recipes",
        model="offline",
    )


def _parse_json_object(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _validate(data: dict) -> TicketCopy | None:
    title = str(data.get("title") or "").strip()
    lede = str(data.get("lede") or "").strip()
    cues = data.get("cues") or []
    rule = str(data.get("rule") or "").strip()
    route = str(data.get("route") or "").strip()
    if not (title and lede and rule and route):
        return None
    if not isinstance(cues, list) or len(cues) < 4:
        return None
    cues = [str(c).strip() for c in cues[:4]]
    banned = ("embrace", "journey", "unlock", "dive in", "leverage", "game-changer")
    blob = " ".join([title, lede, rule, route] + cues).lower()
    if any(b in blob for b in banned):
        return None
    if any(ch in title for ch in "!😀🌿✨"):
        return None
    return TicketCopy(
        title=title[:48],
        lede=lede[:240],
        cues=cues,
        rule=rule[:200],
        route=route[:280],
        writer="gemma",
        model="",
    )


async def _chat(url: str, model: str, messages: list[dict], extra_headers: dict | None = None) -> str:
    headers = {"Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 500,
    }
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]


def _prompt(facts: dict) -> list[dict]:
    system = (
        "You write park-bulletin copy for a 20-minute dusk walk. "
        "Plain English. No emoji, no hashtags, no motivational language. "
        "Never invent street names, distances in kilometres, or weather facts "
        "that are not in the user message. Return JSON only."
    )
    user = (
        "Facts:\n"
        f"{json.dumps(facts, indent=2)}\n\n"
        "Return JSON with keys: title (3-6 words), lede (one sentence), "
        "cues (array of exactly 4 sensory instructions: look, listen, touch, notice), "
        "rule (one sentence: phone stays in pocket), "
        "route (two sentences, from the door, toward the heading, no destination)."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def write_copy(facts: dict, fallback: TicketCopy) -> TicketCopy:
    ollama = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
    ollama_model = os.environ.get("OLLAMA_MODEL", "gemma3:4b")
    groq_key = os.environ.get("GROQ_API_KEY", "")
    groq_model = os.environ.get("GROQ_MODEL", "gemma2-9b-it")
    google_key = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")

    attempts: list[tuple[str, str, str, dict | None]] = []
    attempts.append(
        (
            f"{ollama}/v1/chat/completions",
            os.environ.get("OLLAMA_MODEL", ollama_model),
            "gemma / ollama",
            None,
        )
    )
    if groq_key:
        attempts.append(
            (
                "https://api.groq.com/openai/v1/chat/completions",
                groq_model,
                "gemma / groq",
                {"Authorization": f"Bearer {groq_key}"},
            )
        )

    messages = _prompt(facts)
    for url, model, label, headers in attempts:
        try:
            text = await _chat(url, model, messages, headers)
            parsed = _parse_json_object(text)
            if not parsed:
                continue
            copy = _validate(parsed)
            if copy:
                copy.writer = "gemma"
                copy.model = f"{label} · {model}"
                return copy
        except Exception:
            continue

    if google_key:
        try:
            copy = await _gemma_google(facts, google_key)
            if copy:
                return copy
        except Exception:
            pass

    return fallback


async def _gemma_google(facts: dict, key: str) -> TicketCopy | None:
    model = os.environ.get("GEMMA_MODEL", "gemma-3-4b-it")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    messages = _prompt(facts)
    body = {
        "system_instruction": {"parts": [{"text": messages[0]["content"]}]},
        "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 500},
    }
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    parsed = _parse_json_object(text)
    if not parsed:
        return None
    copy = _validate(parsed)
    if copy:
        copy.model = f"gemma / google · {model}"
    return copy
