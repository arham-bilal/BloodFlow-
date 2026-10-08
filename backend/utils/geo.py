from math import radians, sin, cos, asin, sqrt

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(a))

def bounding_box(lat, lon, km):
    dlat = km / 111.0
    dlon = km / (111.0 * max(cos(radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon

def fuzz(coord: float) -> float:
    """Public-facing approximate coordinate (~1 km). Never return exact donor location."""
    return round(coord, 2)
