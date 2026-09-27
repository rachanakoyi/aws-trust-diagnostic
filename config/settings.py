"""Configuration settings for AWS Observation Trust & Diagnostic Layer."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any
from dotenv import load_dotenv

# Base Directory of the Project
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class StationConfig:
    """Pre-configured AWS station metadata."""
    station_id: str
    name: str
    latitude: float
    longitude: float
    elevation_m: float = 0.0


# Standard Indian Automatic Weather Station benchmarks for testing
PRECONFIGURED_STATIONS: Dict[str, StationConfig] = {
    "AWS_DELHI_001": StationConfig(
        station_id="AWS_DELHI_001",
        name="New Delhi (Safdarjung)",
        latitude=28.585,
        longitude=77.209,
        elevation_m=216.0
    ),
    "AWS_MUMBAI_002": StationConfig(
        station_id="AWS_MUMBAI_002",
        name="Mumbai (Colaba)",
        latitude=18.906,
        longitude=72.814,
        elevation_m=11.0
    ),
    "AWS_CHENNAI_003": StationConfig(
        station_id="AWS_CHENNAI_003",
        name="Chennai (Meenambakkam)",
        latitude=12.994,
        longitude=80.181,
        elevation_m=16.0
    ),
    "AWS_KOLKATA_004": StationConfig(
        station_id="AWS_KOLKATA_004",
        name="Kolkata (Alipore)",
        latitude=22.533,
        longitude=88.326,
        elevation_m=6.0
    ),
    "AWS_BENGALURU_005": StationConfig(
        station_id="AWS_BENGALURU_005",
        name="Bengaluru (City AWS)",
        latitude=12.971,
        longitude=77.594,
        elevation_m=920.0
    ),
}


@dataclass
class Settings:
    """Global system configuration."""

    # Data Source
    data_source_mode: str = os.getenv("DATA_SOURCE", "fallback").lower()
    imd_api_url: str = os.getenv("IMD_API_URL", "").strip()
    imd_api_key: str = os.getenv("IMD_API_KEY", "").strip()
    imd_api_token: str = os.getenv("IMD_API_TOKEN", "").strip()

    # Polling & Ingestion
    poll_interval_seconds: int = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
    default_station_id: str = os.getenv("DEFAULT_STATION_ID", "AWS_DELHI_001")
    demo_mode: bool = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

    # Storage
    db_path: Path = BASE_DIR / os.getenv("DB_PATH", "database/app.db")

    # Meteorological Physical Plausibility Limits (WMO / IMD AWS Range standards)
    temp_min: float = float(os.getenv("TEMP_MIN", "-15.0"))  # °C
    temp_max: float = float(os.getenv("TEMP_MAX", "55.0"))   # °C
    pressure_min: float = float(os.getenv("PRESSURE_MIN", "850.0"))  # hPa (surface pressure range)
    pressure_max: float = float(os.getenv("PRESSURE_MAX", "1080.0")) # hPa
    humidity_min: float = float(os.getenv("HUMIDITY_MIN", "0.0"))    # %
    humidity_max: float = float(os.getenv("HUMIDITY_MAX", "100.0"))  # %

    # Maximum Plausible Step Rates of Change (between 5-15 min observations)
    max_temp_step_change: float = float(os.getenv("MAX_TEMP_STEP_CHANGE", "5.0"))      # °C per step
    max_pressure_step_change: float = float(os.getenv("MAX_PRESSURE_STEP_CHANGE", "6.0"))  # hPa per step
    max_humidity_step_change: float = float(os.getenv("MAX_HUMIDITY_STEP_CHANGE", "25.0")) # % per step

    # Persistence / Frozen Sensor Check
    persistence_window: int = int(os.getenv("PERSISTENCE_WINDOW", "5"))
    persistence_tolerance: float = 0.05  # Within ±0.05 is considered identical

    # Communication Gap Threshold (seconds without observation)
    communication_gap_threshold_sec: int = 1800  # 30 minutes


# Singleton settings instance
settings = Settings()
