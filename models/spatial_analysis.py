"""Optional Spatial Consistency Analysis Module.

Compares observations with genuine neighboring stations when available.
If neighboring stations are not configured or available, explicitly
reports: 'Spatial evidence: NOT AVAILABLE' without fabricating fake neighbors.
"""

from typing import Dict, Any, List, Optional
import math

from data_sources.schema import WeatherObservation


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class SpatialAnalyzer:
    """Evaluates spatial coherence against neighboring AWS stations if provided."""

    def __init__(self, max_neighbor_distance_km: float = 75.0):
        self.max_neighbor_distance_km = max_neighbor_distance_km

    def analyze(
        self,
        current: WeatherObservation,
        neighbor_observations: Optional[List[WeatherObservation]] = None
    ) -> Dict[str, Any]:
        """Evaluate spatial consistency.
        
        Returns:
            Dict containing:
              - is_available: bool
              - status_text: str ('Spatial evidence: NOT AVAILABLE' or summary)
              - neighbor_count: int
              - spatial_deviation_score: float [0.0, 1.0]
              - spatial_consistent: Optional[bool]
        """
        if not neighbor_observations or len(neighbor_observations) == 0:
            return {
                "is_available": False,
                "status_text": "Spatial evidence: NOT AVAILABLE",
                "neighbor_count": 0,
                "spatial_deviation_score": 0.0,
                "spatial_consistent": None,
                "evidence_note": "No neighboring AWS stations currently configured in spatial buffer."
            }

        # Filter valid neighbors within geographic radius
        valid_neighbors = []
        for n in neighbor_observations:
            if n.station_id == current.station_id:
                continue
            if n.temperature is None or n.pressure is None or n.humidity is None:
                continue
            dist = haversine_distance_km(current.latitude, current.longitude, n.latitude, n.longitude)
            if dist <= self.max_neighbor_distance_km:
                valid_neighbors.append((n, dist))

        if not valid_neighbors:
            return {
                "is_available": False,
                "status_text": "Spatial evidence: NOT AVAILABLE",
                "neighbor_count": 0,
                "spatial_deviation_score": 0.0,
                "spatial_consistent": None,
                "evidence_note": f"No active neighbors within {self.max_neighbor_distance_km} km radius."
            }

        # Compare current station with average of neighbors
        n_temps = [n[0].temperature for n in valid_neighbors]
        n_press = [n[0].pressure for n in valid_neighbors]
        n_rhs = [n[0].humidity for n in valid_neighbors]

        avg_t = sum(n_temps) / len(n_temps)
        avg_p = sum(n_press) / len(n_press)
        avg_rh = sum(n_rhs) / len(n_rhs)

        delta_t = abs(current.temperature - avg_t) if current.temperature is not None else 0.0
        delta_p = abs(current.pressure - avg_p) if current.pressure is not None else 0.0
        delta_rh = abs(current.humidity - avg_rh) if current.humidity is not None else 0.0

        # Meteorological meso-scale threshold tolerances
        temp_incoherent = delta_t > 4.5
        pres_incoherent = delta_p > 5.0
        rh_incoherent = delta_rh > 30.0

        incoherent_count = sum([temp_incoherent, pres_incoherent, rh_incoherent])
        spatial_score = min(1.0, incoherent_count * 0.35 + (delta_t / 10.0) * 0.3)
        consistent = incoherent_count <= 1

        status_text = (
            f"Spatial evidence: {len(valid_neighbors)} neighbor(s) analyzed — "
            f"{'Consistent with regional trend' if consistent else 'Regional anomaly deviation detected'}"
        )

        return {
            "is_available": True,
            "status_text": status_text,
            "neighbor_count": len(valid_neighbors),
            "spatial_deviation_score": round(spatial_score, 3),
            "spatial_consistent": consistent,
            "details": {
                "delta_temp": round(delta_t, 2),
                "delta_pressure": round(delta_p, 2),
                "delta_humidity": round(delta_rh, 1),
                "neighbors": [
                    {"station_id": n[0].station_id, "dist_km": round(n[1], 1)}
                    for n in valid_neighbors
                ]
            }
        }
