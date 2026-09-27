"""Real-time data ingestion manager with graceful IMD-to-Fallback failover.

Handles periodic telemetry acquisition, track connection status, error statistics,
and maintains an in-memory observation buffer for immediate dashboard reactivity.
"""

import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone

from config.settings import settings, PRECONFIGURED_STATIONS
from data_sources.schema import WeatherObservation
from data_sources.imd_connector import IMDConnector, IMDConnectionError
from data_sources.fallback_connector import FallbackWeatherConnector

logger = logging.getLogger(__name__)


class IngestionManager:
    """Manages observation retrieval with robust failover and telemetry telemetry statistics."""

    def __init__(self, data_source_preference: Optional[str] = None):
        self.preferred_source = (data_source_preference or settings.data_source_mode).lower()
        self.imd_connector = IMDConnector()
        self.fallback_connector = FallbackWeatherConnector()

        # Telemetry Ingestion State
        self.active_source: str = "INITIALIZING"
        self.connection_status: str = "CONNECTING"  # 'ONLINE', 'FALLBACK_ACTIVE', 'DISCONNECTED'
        self.last_update_time: Optional[str] = None
        self.observations_received: int = 0
        self.ingestion_errors: int = 0
        self.last_error_message: Optional[str] = None

    def poll_station(
        self,
        station_id: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None
    ) -> WeatherObservation:
        """Retrieve next observation, gracefully falling back if preferred source is unavailable."""
        obs: Optional[WeatherObservation] = None

        # Attempt IMD if configured as preferred
        if self.preferred_source == "imd":
            try:
                obs = self.imd_connector.fetch_latest_observation(station_id, latitude, longitude)
                self.active_source = "IMD AWS"
                self.connection_status = "ONLINE (OFFICIAL IMD)"
                self.last_error_message = None
            except (IMDConnectionError, Exception) as e:
                self.ingestion_errors += 1
                self.last_error_message = f"IMD source unavailable ({str(e)}). Switched to fallback."
                logger.warning(self.last_error_message)

        # Fallback if IMD failed or preferred_source is fallback
        if obs is None:
            try:
                obs = self.fallback_connector.fetch_latest_observation(station_id, latitude, longitude)
                self.active_source = "FALLBACK PUBLIC WEATHER API"
                self.connection_status = "FALLBACK_ACTIVE (PUBLIC API)"
            except Exception as e:
                self.ingestion_errors += 1
                self.connection_status = "DISCONNECTED"
                self.last_error_message = f"Public API fetch error: {str(e)}"
                logger.error(self.last_error_message)
                # Offline synthetic backup fallback
                obs = self.fallback_connector._generate_simulated_fallback(
                    station_id,
                    latitude or 28.585,
                    longitude or 77.209
                )
                self.active_source = "FALLBACK PUBLIC WEATHER API (OFFLINE RESILIENCE)"

        self.last_update_time = datetime.now(timezone.utc).isoformat()
        self.observations_received += 1
        return obs

    def bootstrap_station_history(
        self,
        station_id: str,
        past_hours: int = 24
    ) -> List[WeatherObservation]:
        """Bootstrap initial historical data points for new station or startup."""
        try:
            return self.fallback_connector.fetch_historical_series(station_id, past_hours=past_hours)
        except Exception as e:
            logger.warning("Historical bootstrap error: %s", str(e))
            return []

    def get_status_summary(self) -> Dict[str, Any]:
        """Get live health and status metadata for the dashboard cards."""
        return {
            "active_source": self.active_source,
            "connection_status": self.connection_status,
            "last_update_time": self.last_update_time,
            "observations_received": self.observations_received,
            "ingestion_errors": self.ingestion_errors,
            "last_error_message": self.last_error_message,
            "poll_interval_seconds": settings.poll_interval_seconds,
            "is_fallback": "FALLBACK" in self.active_source
        }
