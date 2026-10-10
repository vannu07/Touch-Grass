"""A short list of cities so a judge can issue a ticket without sharing GPS."""

CITIES = [
    {"id": "delhi", "name": "Delhi", "lat": 28.6139, "lon": 77.2090, "offset": 5.5, "urban": True},
    {"id": "mumbai", "name": "Mumbai", "lat": 19.0760, "lon": 72.8777, "offset": 5.5, "urban": True},
    {"id": "bengaluru", "name": "Bengaluru", "lat": 12.9716, "lon": 77.5946, "offset": 5.5, "urban": True},
    {"id": "london", "name": "London", "lat": 51.5074, "lon": -0.1278, "offset": 1.0, "urban": True},
    {"id": "newyork", "name": "New York", "lat": 40.7128, "lon": -74.0060, "offset": -4.0, "urban": True},
    {"id": "sf", "name": "San Francisco", "lat": 37.7749, "lon": -122.4194, "offset": -7.0, "urban": True},
    {"id": "tokyo", "name": "Tokyo", "lat": 35.6762, "lon": 139.6503, "offset": 9.0, "urban": True},
    {"id": "berlin", "name": "Berlin", "lat": 52.5200, "lon": 13.4050, "offset": 2.0, "urban": True},
    {"id": "sydney", "name": "Sydney", "lat": -33.8688, "lon": 151.2093, "offset": 11.0, "urban": True},
    {"id": "nairobi", "name": "Nairobi", "lat": -1.2921, "lon": 36.8219, "offset": 3.0, "urban": True},
    {"id": "sao", "name": "São Paulo", "lat": -23.5505, "lon": -46.6333, "offset": -3.0, "urban": True},
    {"id": "oslo", "name": "Oslo", "lat": 59.9139, "lon": 10.7522, "offset": 2.0, "urban": True},
    {"id": "denver", "name": "Denver", "lat": 39.7392, "lon": -104.9903, "offset": -6.0, "urban": False},
    {"id": "kathmandu", "name": "Kathmandu", "lat": 27.7172, "lon": 85.3240, "offset": 5.75, "urban": True},
]


def get_city(city_id: str) -> dict | None:
    for c in CITIES:
        if c["id"] == city_id:
            return c
    return None
