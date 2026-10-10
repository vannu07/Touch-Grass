"""Local solar times. No weather API, no map tiles, no network.

NOAA-style solar geometry so a walk ticket can say "leave by 17:42"
from latitude, longitude, and the date alone.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone


@dataclass(frozen=True)
class SolarDay:
    sunrise: datetime
    sunset: datetime
    solar_noon: datetime
    golden_start: datetime
    golden_end: datetime
    civil_dusk: datetime
    sunset_azimuth_deg: float
    day_length: timedelta
    is_polar_night: bool = False
    is_polar_day: bool = False


CARDINALS = (
    (0, "north"),
    (45, "northeast"),
    (90, "east"),
    (135, "southeast"),
    (180, "south"),
    (225, "southwest"),
    (270, "west"),
    (315, "northwest"),
    (360, "north"),
)


def heading_name(azimuth_deg: float) -> str:
    az = azimuth_deg % 360
    return min(CARDINALS, key=lambda c: abs(c[0] - az))[1]


def _julian_day(dt: datetime) -> float:
    utc = dt.astimezone(timezone.utc)
    y, m, d = utc.year, utc.month, utc.day
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    jd = math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5
    return jd + hour / 24


def _solar_position(lat: float, lon: float, dt: datetime) -> tuple[float, float]:
    """Return (altitude_deg, azimuth_deg clockwise from north)."""
    jd = _julian_day(dt)
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    ep = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(ep) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(ep) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    lst = (gmst + lon / 15) % 24
    ha = math.radians(lst * 15) - ra
    lat_r = math.radians(lat)
    alt = math.asin(
        math.sin(lat_r) * math.sin(dec) + math.cos(lat_r) * math.cos(dec) * math.cos(ha)
    )
    az = math.atan2(
        -math.sin(ha),
        math.tan(dec) * math.cos(lat_r) - math.sin(lat_r) * math.cos(ha),
    )
    az_deg = (math.degrees(az) + 360) % 360
    return math.degrees(alt), az_deg


def _find_altitude_crossing(
    lat: float,
    lon: float,
    day: date,
    target_alt: float,
    *,
    rising: bool,
    tz: timezone,
) -> datetime | None:
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    best: datetime | None = None
    best_err = 99.0
    # 2-minute scan, then refine. Polar day/night returns None.
    for minute in range(0, 24 * 60, 2):
        dt = start + timedelta(minutes=minute)
        alt, _ = _solar_position(lat, lon, dt)
        err = abs(alt - target_alt)
        prev = start + timedelta(minutes=minute - 2) if minute else dt
        prev_alt, _ = _solar_position(lat, lon, prev)
        crossed = (prev_alt - target_alt) * (alt - target_alt) <= 0 and minute > 0
        going_up = alt > prev_alt
        if crossed and going_up == rising and err < best_err:
            # Linear interpolate
            frac = (target_alt - prev_alt) / (alt - prev_alt + 1e-9)
            cand = prev + timedelta(seconds=120 * frac)
            best = cand
            best_err = err
    return best


def solar_day(lat: float, lon: float, day: date, tz_offset_hours: float) -> SolarDay:
    tz = timezone(timedelta(hours=tz_offset_hours))
    sunrise = _find_altitude_crossing(lat, lon, day, -0.833, rising=True, tz=tz)
    sunset = _find_altitude_crossing(lat, lon, day, -0.833, rising=False, tz=tz)
    golden_start = _find_altitude_crossing(lat, lon, day, 6.0, rising=False, tz=tz)
    civil_dusk = _find_altitude_crossing(lat, lon, day, -6.0, rising=False, tz=tz)

    noon_guess = datetime(day.year, day.month, day.day, 12, tzinfo=tz)
    # Solar noon ≈ midpoint, scan for max altitude
    peak = noon_guess
    peak_alt = -90.0
    start = datetime(day.year, day.month, day.day, tzinfo=tz)
    for minute in range(8 * 60, 16 * 60, 2):
        dt = start + timedelta(minutes=minute)
        alt, _ = _solar_position(lat, lon, dt)
        if alt > peak_alt:
            peak_alt = alt
            peak = dt

    polar_night = sunrise is None and sunset is None and peak_alt < 0
    polar_day = sunrise is None and sunset is None and peak_alt > 0

    if polar_night:
        dummy = datetime.combine(day, time(12, 0), tzinfo=tz)
        return SolarDay(
            sunrise=dummy,
            sunset=dummy,
            solar_noon=peak,
            golden_start=dummy,
            golden_end=dummy,
            civil_dusk=dummy,
            sunset_azimuth_deg=270.0,
            day_length=timedelta(0),
            is_polar_night=True,
        )
    if polar_day:
        dummy_s = datetime.combine(day, time(0, 0), tzinfo=tz)
        dummy_e = dummy_s + timedelta(hours=23, minutes=59)
        _, az = _solar_position(lat, lon, peak)
        return SolarDay(
            sunrise=dummy_s,
            sunset=dummy_e,
            solar_noon=peak,
            golden_start=dummy_e - timedelta(minutes=40),
            golden_end=dummy_e,
            civil_dusk=dummy_e,
            sunset_azimuth_deg=az,
            day_length=timedelta(hours=24),
            is_polar_day=True,
        )

    assert sunrise and sunset
    if golden_start is None:
        golden_start = sunset - timedelta(minutes=35)
    if civil_dusk is None:
        civil_dusk = sunset + timedelta(minutes=25)
    _, az = _solar_position(lat, lon, sunset)
    return SolarDay(
        sunrise=sunrise,
        sunset=sunset,
        solar_noon=peak,
        golden_start=golden_start,
        golden_end=sunset,
        civil_dusk=civil_dusk,
        sunset_azimuth_deg=az,
        day_length=sunset - sunrise,
    )


def guess_offset_hours(lon: float) -> float:
    """Rough civil offset from longitude when the browser did not send one."""
    return round(lon / 15)


def minutes_until(then: datetime, now: datetime) -> int:
    return int((then - now).total_seconds() // 60)
