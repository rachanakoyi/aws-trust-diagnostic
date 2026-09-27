"""Canonical data schema for Automatic Weather Station (AWS) observations."""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import json


@dataclass
class WeatherObservation:
    """Standardized internal representation of an AWS observation.
    
    Adheres strictly to the canonical schema required across all connectors:
      - timestamp: ISO 8601 string or UTC datetime
      - station_id: Unique station identifier
      - temperature: Dry bulb temperature in °C
      - pressure: Atmospheric/surface pressure in hPa
      - humidity: Relative humidity in %
      - latitude: Station latitude
      - longitude: Station longitude
      - source: Data source descriptor ('IMD AWS' or 'FALLBACK PUBLIC WEATHER API')
      - raw_payload: Original unprocessed payload from upstream API
      - ingestion_status: Metadata status (e.g. 'OK', 'SYNTHETIC_DEMO', 'INJECTED_FAULT')
    """
    timestamp: str
    station_id: str
    temperature: Optional[float]
    pressure: Optional[float]
    humidity: Optional[float]
    latitude: float
    longitude: float
    source: str
    raw_payload: Optional[str] = None
    ingestion_status: str = "OK"

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeatherObservation":
        """Instantiate from dictionary, handling types cleanly."""
        temp = float(data["temperature"]) if data.get("temperature") is not None else None
        pres = float(data["pressure"]) if data.get("pressure") is not None else None
        hum = float(data["humidity"]) if data.get("humidity") is not None else None
        lat = float(data.get("latitude", 0.0))
        lon = float(data.get("longitude", 0.0))

        raw = data.get("raw_payload")
        if isinstance(raw, (dict, list)):
            raw = json.dumps(raw)

        return cls(
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            station_id=str(data.get("station_id", "UNKNOWN_AWS")),
            temperature=temp,
            pressure=pres,
            humidity=hum,
            latitude=lat,
            longitude=lon,
            source=str(data.get("source", "UNKNOWN")),
            raw_payload=raw,
            ingestion_status=str(data.get("ingestion_status", "OK"))
        )

    def validate_types(self) -> bool:
        """Basic type sanity check."""
        return (
            isinstance(self.timestamp, str) and
            isinstance(self.station_id, str) and
            (self.temperature is None or isinstance(self.temperature, (int, float))) and
            (self.pressure is None or isinstance(self.pressure, (int, float))) and
            (self.humidity is None or isinstance(self.humidity, (int, float)))
        )
