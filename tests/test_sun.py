from datetime import date

from lastlight.sun import heading_name, solar_day


def test_delhi_october_sunset_is_evening():
    day = solar_day(28.6139, 77.2090, date(2026, 10, 10), 5.5)
    assert day.sunset.hour >= 17
    assert day.sunset.hour <= 19
    assert day.sunrise.hour >= 5
    assert day.sunrise.hour <= 7
    assert day.day_length.total_seconds() > 10 * 3600
    assert heading_name(day.sunset_azimuth_deg) in {
        "west",
        "southwest",
        "northwest",
        "south",
    }


def test_heading_wraps():
    assert heading_name(0) == "north"
    assert heading_name(359) == "north"
    assert heading_name(90) == "east"
