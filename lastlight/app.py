from __future__ import annotations

import hashlib
import os
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from lastlight.climate import features_from_request, foliage_index
from lastlight.copy import recipes, write_copy
from lastlight.places import CITIES, get_city
from lastlight.predict import load_engine, verdict
from lastlight.sun import heading_name, solar_day

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"

app = FastAPI(title="Last Light", version="1.0.0")


class TicketRequest(BaseModel):
    city_id: str | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    offset_hours: float | None = Field(default=None, ge=-14, le=14)
    duration_min: int = Field(default=20, ge=12, le=60)
    sky: str = Field(default="thin")
    ground: str = Field(default="mixed")
    urban: bool | None = None
    temp_c: float | None = Field(default=None, ge=-50, le=60)
    when: str | None = None  # ISO date, default today in that offset


class SpeakRequest(BaseModel):
    text: str = Field(min_length=8, max_length=1200)


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=load_engine, daemon=True).start()


@app.get("/api/health")
def health():
    from lastlight import predict as pred

    if pred._engine is None:
        return {"ok": True, "engine": "loading"}
    engine = pred._engine
    bt = engine.backtest
    return {
        "ok": True,
        "engine": engine.backend,
        "backtest": {
            "n_test": bt.n_test,
            "tabpfn_mae": bt.tabpfn_mae,
            "ridge_mae": round(bt.ridge_mae, 3),
            "mean_mae": round(bt.mean_mae, 3),
            "tabpfn_wins": bt.tabpfn_wins,
            "fit_seconds": round(bt.fit_seconds, 2),
        },
        "gemma": {
            "ollama": os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
            "groq_configured": bool(os.environ.get("GROQ_API_KEY")),
            "google_configured": bool(
                os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            ),
        },
        "voice": bool(os.environ.get("ELEVENLABS_API_KEY")),
    }


@app.get("/api/places")
def places():
    return {"places": CITIES}


@app.post("/api/ticket")
async def issue_ticket(req: TicketRequest):
    if req.sky not in {"clear", "thin", "heavy", "rain", "wind"}:
        raise HTTPException(400, "sky must be clear, thin, heavy, rain, or wind")
    if req.ground not in {"pavement", "park", "mixed"}:
        raise HTTPException(400, "ground must be pavement, park, or mixed")

    city = get_city(req.city_id) if req.city_id else None
    if city:
        lat, lon = city["lat"], city["lon"]
        offset = req.offset_hours if req.offset_hours is not None else city["offset"]
        urban = city["urban"] if req.urban is None else req.urban
        place_name = city["name"]
    elif req.lat is not None and req.lon is not None:
        lat, lon = req.lat, req.lon
        offset = req.offset_hours if req.offset_hours is not None else round(lon / 15)
        urban = True if req.urban is None else req.urban
        place_name = f"{lat:.2f}°, {lon:.2f}°"
    else:
        raise HTTPException(400, "Pick a city or send lat and lon.")

    tz = timezone(timedelta(hours=offset))
    if req.when:
        try:
            day = date.fromisoformat(req.when[:10])
        except ValueError as exc:
            raise HTTPException(400, "when must be YYYY-MM-DD") from exc
    else:
        day = datetime.now(tz).date()

    solar = solar_day(lat, lon, day, offset)
    now = datetime.now(tz)
    minutes_to_sunset = (solar.sunset - now).total_seconds() / 60
    features = features_from_request(
        lat=lat,
        day_of_year=int(day.strftime("%j")),
        minutes_to_sunset=minutes_to_sunset,
        duration_min=float(req.duration_min),
        sky=req.sky,
        urban=urban,
        temp_c=req.temp_c,
    )
    engine = load_engine()
    score, score_src = engine.predict_one(features)

    leave_by = solar.sunset - timedelta(minutes=req.duration_min)
    if leave_by < solar.golden_start:
        leave_by = solar.golden_start
    return_by = solar.civil_dusk

    heading = heading_name(solar.sunset_azimuth_deg)
    serial = hashlib.sha1(
        f"{day.isoformat()}|{lat:.3f}|{lon:.3f}|{req.duration_min}".encode()
    ).hexdigest()[:6].upper()

    fallback = recipes(
        heading_deg=solar.sunset_azimuth_deg,
        day_of_year=int(day.strftime("%j")),
        lat=lat,
        duration=req.duration_min,
        sky=req.sky,
        ground=req.ground,
        foliage=features["foliage"],
        urban=urban,
    )
    facts = {
        "place": place_name,
        "date": day.isoformat(),
        "heading": heading,
        "heading_deg": round(solar.sunset_azimuth_deg, 1),
        "duration_min": req.duration_min,
        "sky": req.sky,
        "ground": req.ground,
        "urban": urban,
        "foliage": round(features["foliage"], 3),
        "walk_score": round(score, 1),
        "verdict": verdict(score, minutes_to_sunset, req.sky),
        "sunset": solar.sunset.strftime("%H:%M"),
        "leave_by": leave_by.strftime("%H:%M"),
        "temp_c_estimate": round(features["temp_c"], 1),
        "polar_night": solar.is_polar_night,
        "polar_day": solar.is_polar_day,
    }
    copy = await write_copy(facts, fallback)

    pace_kmh = 4.4
    metres = int(pace_kmh * 1000 * (req.duration_min / 60))

    return {
        "serial": serial,
        "place": place_name,
        "date": day.isoformat(),
        "lat": lat,
        "lon": lon,
        "urban": urban,
        "duration_min": req.duration_min,
        "sky": req.sky,
        "ground": req.ground,
        "sun": {
            "sunrise": solar.sunrise.isoformat(),
            "sunset": solar.sunset.isoformat(),
            "golden_start": solar.golden_start.isoformat(),
            "civil_dusk": solar.civil_dusk.isoformat(),
            "sunset_azimuth_deg": round(solar.sunset_azimuth_deg, 1),
            "heading": heading,
            "day_length_min": int(solar.day_length.total_seconds() // 60),
            "is_polar_night": solar.is_polar_night,
            "is_polar_day": solar.is_polar_day,
        },
        "leave_by": leave_by.isoformat(),
        "return_by": return_by.isoformat(),
        "minutes_to_sunset": round(minutes_to_sunset, 1),
        "distance_m": metres,
        "score": round(score, 1),
        "score_source": score_src,
        "verdict": verdict(score, minutes_to_sunset, req.sky),
        "foliage": round(features["foliage"], 3),
        "foliage_note": _foliage_note(lat, int(day.strftime("%j"))),
        "copy": {
            "title": copy.title,
            "lede": copy.lede,
            "cues": copy.cues,
            "rule": copy.rule,
            "route": copy.route,
            "writer": copy.writer,
            "model": copy.model,
        },
        "engine": {
            "backend": engine.backend,
            "tabpfn_mae": engine.backtest.tabpfn_mae,
            "ridge_mae": engine.backtest.ridge_mae,
        },
    }


def _foliage_note(lat: float, doy: int) -> str:
    f = foliage_index(lat, doy)
    if abs(lat) < 18:
        return "No foliage season here. The light is the event."
    if f > 0.7:
        return "Peak colour, if the trees around you play along."
    if f > 0.35:
        return "Colour is moving. Walk while it lasts."
    if f > 0.12:
        return "Early or late colour. Look anyway."
    return "Not a foliage week. Go for the hour, not the leaves."


@app.post("/api/speak")
async def speak(req: SpeakRequest):
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise HTTPException(501, "No ElevenLabs key. The browser can still read the ticket aloud.")
    voice = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
    import httpx

    async with httpx.AsyncClient(timeout=45) as client:
        r = await client.post(
            url,
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": req.text,
                "model_id": os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
            },
        )
    if r.status_code >= 400:
        raise HTTPException(502, f"ElevenLabs refused the read ({r.status_code}).")
    return Response(content=r.content, media_type="audio/mpeg")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")
