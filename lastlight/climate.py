"""A dusk-walk climate table that never leaves the machine.

Rows are generated from a known physical recipe (temperature, rain, wind,
day of year, latitude, minutes-to-sunset). TabPFN has to rediscover the
recipe from the table. The recipe itself is not used at prediction time.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "lat",
    "abs_lat",
    "day_of_year",
    "minutes_to_sunset",
    "duration_min",
    "temp_c",
    "cloud",
    "precip_mm",
    "wind_ms",
    "humidity",
    "foliage",
    "urban",
]

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "dusk_walks.csv"


def foliage_index(lat: float, day_of_year: int) -> float:
    """Peak color roughly late September–October in the mid-latitudes."""
    peak = 278 - abs(lat) * 0.15  # slightly earlier farther north
    width = 22 + abs(lat) * 0.08
    if abs(lat) < 18:
        return 0.08  # tropics: not a foliage story
    return float(np.exp(-0.5 * ((day_of_year - peak) / width) ** 2))


def climatology_temp(lat: float, day_of_year: int) -> float:
    seasonal = np.cos(2 * np.pi * (day_of_year - 200) / 365)
    if lat < 0:
        seasonal = -seasonal
    return float(18 - 0.28 * abs(lat) + 11 * seasonal * np.cos(np.radians(lat * 0.65)))


def hidden_score(row: dict, rng: np.random.Generator | None = None) -> float:
    """Ground-truth walk quality. Hidden from the model."""
    temp = row["temp_c"]
    comfort = np.exp(-0.5 * ((temp - 14) / 9) ** 2)
    rain = np.exp(-row["precip_mm"] / 2.2)
    cloud = 1 - 0.55 * row["cloud"]
    wind = np.exp(-max(0, row["wind_ms"] - 6) / 5)
    light = np.exp(-0.5 * ((row["minutes_to_sunset"] - 22) / 18) ** 2)
    foliage = 0.55 + 0.45 * row["foliage"]
    duration = 1 - abs(row["duration_min"] - 22) / 80
    urban_penalty = 0.92 if row["urban"] else 1.0
    humidity_pen = 1 - 0.25 * max(0, row["humidity"] - 0.75)
    raw = (
        0.28 * comfort
        + 0.22 * rain
        + 0.12 * cloud
        + 0.10 * wind
        + 0.16 * light
        + 0.08 * foliage
        + 0.04 * duration
    ) * urban_penalty * humidity_pen
    noise = 0.0 if rng is None else rng.normal(0, 0.04)
    return float(np.clip(100 * (raw + noise), 1, 99))


def generate_dataset(n: int = 1400, seed: int = 26) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        lat = float(rng.uniform(-55, 65))
        doy = int(rng.integers(1, 366))
        temp = climatology_temp(lat, doy) + float(rng.normal(0, 3.5))
        cloud = float(np.clip(rng.beta(2.2, 2.4), 0, 1))
        precip = float(max(0, rng.exponential(1.1) - 0.7))
        if rng.random() < 0.62:
            precip = 0.0
        wind = float(np.clip(rng.gamma(2.1, 1.4), 0, 18))
        humidity = float(np.clip(rng.beta(5, 3), 0.2, 0.98))
        minutes = float(rng.uniform(-10, 55))
        duration = float(rng.choice([15, 20, 25, 30, 40, 45]))
        urban = int(rng.random() < 0.55)
        row = {
            "lat": lat,
            "abs_lat": abs(lat),
            "day_of_year": doy,
            "minutes_to_sunset": minutes,
            "duration_min": duration,
            "temp_c": temp,
            "cloud": cloud,
            "precip_mm": precip,
            "wind_ms": wind,
            "humidity": humidity,
            "foliage": foliage_index(lat, doy),
            "urban": urban,
        }
        row["walk_score"] = hidden_score(row, rng)
        rows.append(row)
    return pd.DataFrame(rows)


def load_or_build(path: Path | None = None) -> pd.DataFrame:
    path = path or DATA_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return pd.read_csv(path)
    df = generate_dataset()
    df.to_csv(path, index=False)
    return df


SKY_PRESETS = {
    "clear": {"cloud": 0.08, "precip_mm": 0.0, "humidity": 0.48, "wind_ms": 2.4},
    "thin": {"cloud": 0.38, "precip_mm": 0.0, "humidity": 0.58, "wind_ms": 3.1},
    "heavy": {"cloud": 0.82, "precip_mm": 0.4, "humidity": 0.74, "wind_ms": 4.8},
    "rain": {"cloud": 0.95, "precip_mm": 4.2, "humidity": 0.88, "wind_ms": 5.5},
    "wind": {"cloud": 0.45, "precip_mm": 0.0, "humidity": 0.50, "wind_ms": 9.5},
}


def features_from_request(
    *,
    lat: float,
    day_of_year: int,
    minutes_to_sunset: float,
    duration_min: float,
    sky: str,
    urban: bool,
    temp_c: float | None = None,
) -> dict:
    preset = SKY_PRESETS.get(sky, SKY_PRESETS["thin"])
    temp = temp_c if temp_c is not None else climatology_temp(lat, day_of_year)
    return {
        "lat": lat,
        "abs_lat": abs(lat),
        "day_of_year": day_of_year,
        "minutes_to_sunset": minutes_to_sunset,
        "duration_min": duration_min,
        "temp_c": temp,
        "cloud": preset["cloud"],
        "precip_mm": preset["precip_mm"],
        "wind_ms": preset["wind_ms"],
        "humidity": preset["humidity"],
        "foliage": foliage_index(lat, day_of_year),
        "urban": int(urban),
    }
