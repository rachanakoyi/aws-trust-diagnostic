"""Official IMD AWS Connector implementation.

Handles secure communication with the India Meteorological Department (IMD)
AWS endpoints when credentials and network access are available. Fails gracefully
to allow automatic switching to the fallback connector without system disruption.
"""

import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import requests

from config.settings import settings, PRECONFIGURED_STATIONS
from data_sources.schema import WeatherObservation

logger = logging.getLogger(__name__)


class IMDConnectionError(Exception):
    """Raised when IMD AWS API is unreachable, unauthorized, or misconfigured."""
    pass


class IMDConnector:
    """Connector for the official IMD Automatic Weather Station API."""

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        api_token: Optional[str] = None,
        timeout_seconds: int = 5
    ):
        self.api_url = (api_url or settings.imd_api_url).strip()
        self.api_key = (api_key or settings.imd_api_key).strip()
        self.api_token = (api_token or settings.imd_api_token).strip()
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        """Check if IMD credentials and URL are present in configuration."""
        return bool(self.api_url)

    def fetch_latest_observation(
        self,
        station_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> WeatherObservation:
        """Fetch the latest observation from IMD AWS endpoint.
        
        Raises IMDConnectionError on failure to trigger graceful fallback.
        """
        if not self.is_configured():
            raise IMDConnectionError(
                "IMD AWS API URL is not configured in .env. Falling back to public weather source."
            )

        headers = {
            "Accept": "application/json",
            "User-Agent": "IMD-AWS-Observation-Trust-Diagnostic-Layer/1.0",
        }
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        params = {"station_id": station_id}

        try:
            response = requests.get(
                self.api_url,
                headers=headers,
                params=params,
                timeout=self.timeout_seconds
            )
            response.raise_for_status()
            payload = response.json()

            # Normalize official payload
            obs = self._parse_imd_payload(payload, station_id, latitude, longitude)
            return obs

        except requests.exceptions.RequestException as e:
            logger.warning("IMD AWS API request failed: %s", str(e))
            raise IMDConnectionError(f"IMD AWS API connection failed: {e}") from e
        except (ValueError, KeyError) as e:
            logger.warning("Failed to parse IMD AWS response: %s", str(e))
            raise IMDConnectionError(f"IMD AWS payload parsing error: {e}") from e

    def _parse_imd_payload(
        self,
        payload: Dict[str, Any],
        station_id: str,
        latitude: Optional[float],
        longitude: Optional[float]
    ) -> WeatherObservation:
        """Map standard IMD AWS response fields to canonical WeatherObservation."""
        # Supports typical IMD AWS schema fields (TA/TEMP, PA/PRES, RH/HUMIDITY)
        temp = payload.get("temperature", payload.get("TEMP", payload.get("TA")))
        pres = payload.get("pressure", payload.get("PRES", payload.get("PA")))
        rh = payload.get("humidity", payload.get("HUMIDITY", payload.get("RH")))
        timestamp = payload.get("timestamp", payload.get("DATETIME", datetime.now(timezone.utc).isoformat()))

        # Location fallback from station metadata if not in payload
        station_meta = PRECONFIGURED_STATIONS.get(station_id)
        lat = payload.get("latitude", latitude or (station_meta.latitude if station_meta else 0.0))
        lon = payload.get("longitude", longitude or (station_meta.longitude if station_meta else 0.0))

        return WeatherObservation(
            timestamp=str(timestamp),
            station_id=station_id,
            temperature=float(temp) if temp is not None else None,
            pressure=float(pres) if pres is not None else None,
            humidity=float(rh) if rh is not None else None,
            latitude=float(lat),
            longitude=float(lon),
            source="IMD AWS",
            raw_payload=json.dumps(payload),
            ingestion_status="OK"
        )
