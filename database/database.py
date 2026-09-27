"""SQLite Database layer for AWS Observation Trust & Diagnostic Layer.

Implements strict immutable observation persistence and tracks QC flags,
AI diagnostics, and operator feedback actions without ever altering raw data.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

from config.settings import settings
from data_sources.schema import WeatherObservation

logger = logging.getLogger(__name__)


class Database:
    """Manages SQLite storage and historical query retrieval."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or settings.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create a connection with row factory and foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self) -> None:
        """Create database tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Raw Observations Table (IMMUTABLE)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                station_id TEXT NOT NULL,
                temperature REAL,
                pressure REAL,
                humidity REAL,
                latitude REAL,
                longitude REAL,
                source TEXT NOT NULL,
                raw_payload TEXT,
                ingestion_status TEXT DEFAULT 'OK',
                created_at TEXT NOT NULL
            );
            """)

            cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_obs_station_time 
            ON observations (station_id, timestamp);
            """)

            # 2. Deterministic QC Results Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS qc_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER NOT NULL,
                range_flag INTEGER NOT NULL,
                rate_flag INTEGER NOT NULL,
                persistence_flag INTEGER NOT NULL,
                missing_flag INTEGER NOT NULL,
                consistency_flag INTEGER NOT NULL,
                qc_score REAL NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            """)

            # 3. AI Diagnostics & Evidence Fusion Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS diagnostics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER NOT NULL,
                classification TEXT NOT NULL,
                confidence REAL NOT NULL,
                temporal_score REAL NOT NULL,
                multivariate_score REAL NOT NULL,
                evidence TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                explanation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            """)

            # 4. Operator Review Actions Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS operator_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagnostic_id INTEGER,
                observation_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                notes TEXT,
                operator_id TEXT DEFAULT 'OPERATOR_1',
                timestamp TEXT NOT NULL,
                FOREIGN KEY (observation_id) REFERENCES observations(id) ON DELETE CASCADE
            );
            """)

            conn.commit()
            logger.info("Database schema initialized at %s", self.db_path)

    # -------------------------------------------------------------
    # Insert Methods (Raw observations are NEVER modified)
    # -------------------------------------------------------------

    def insert_observation(self, obs: WeatherObservation) -> int:
        """Insert a raw weather observation and return its unique ID."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO observations (
                timestamp, station_id, temperature, pressure, humidity,
                latitude, longitude, source, raw_payload, ingestion_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                obs.timestamp, obs.station_id, obs.temperature, obs.pressure, obs.humidity,
                obs.latitude, obs.longitude, obs.source, obs.raw_payload, obs.ingestion_status, now_utc
            ))
            obs_id = cursor.lastrowid
            conn.commit()
            return obs_id

    def insert_qc_result(
        self,
        observation_id: int,
        range_flag: bool,
        rate_flag: bool,
        persistence_flag: bool,
        missing_flag: bool,
        consistency_flag: bool,
        qc_score: float,
        details: Optional[Dict[str, Any]] = None
    ) -> int:
        """Record deterministic QC checks for an observation."""
        now_utc = datetime.now(timezone.utc).isoformat()
        details_json = json.dumps(details or {})
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO qc_results (
                observation_id, range_flag, rate_flag, persistence_flag,
                missing_flag, consistency_flag, qc_score, details, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                observation_id,
                int(range_flag),
                int(rate_flag),
                int(persistence_flag),
                int(missing_flag),
                int(consistency_flag),
                float(qc_score),
                details_json,
                now_utc
            ))
            qc_id = cursor.lastrowid
            conn.commit()
            return qc_id

    def insert_diagnostic(
        self,
        observation_id: int,
        classification: str,
        confidence: float,
        temporal_score: float,
        multivariate_score: float,
        evidence: List[str],
        recommended_action: str,
        explanation: str
    ) -> int:
        """Record AI anomaly diagnosis and evidence fusion results."""
        now_utc = datetime.now(timezone.utc).isoformat()
        evidence_json = json.dumps(evidence)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO diagnostics (
                observation_id, classification, confidence, temporal_score,
                multivariate_score, evidence, recommended_action, explanation, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                observation_id, classification, float(confidence),
                float(temporal_score), float(multivariate_score),
                evidence_json, recommended_action, explanation, now_utc
            ))
            diag_id = cursor.lastrowid
            conn.commit()
            return diag_id

    def insert_operator_action(
        self,
        observation_id: int,
        action: str,
        diagnostic_id: Optional[int] = None,
        notes: str = "",
        operator_id: str = "OPERATOR_IMD"
    ) -> int:
        """Record operator decision regarding an observation alert."""
        now_utc = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO operator_actions (
                diagnostic_id, observation_id, action, notes, operator_id, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                diagnostic_id, observation_id, action, notes, operator_id, now_utc
            ))
            act_id = cursor.lastrowid
            conn.commit()
            return act_id

    # -------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------

    def check_duplicate(self, station_id: str, timestamp: str) -> bool:
        """Check if station_id + timestamp already exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 1 FROM observations WHERE station_id = ? AND timestamp = ? LIMIT 1
            """, (station_id, timestamp))
            return cursor.fetchone() is not None

    def get_recent_observations(
        self,
        station_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Retrieve recent observations for a station ordered chronologically."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM (
                SELECT * FROM observations 
                WHERE station_id = ? 
                ORDER BY timestamp DESC, id DESC 
                LIMIT ?
            ) ORDER BY timestamp ASC, id ASC
            """, (station_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_pipeline_records(
        self,
        station_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch combined observation, QC, and diagnostic records."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                o.id AS observation_id,
                o.timestamp,
                o.station_id,
                o.temperature,
                o.pressure,
                o.humidity,
                o.latitude,
                o.longitude,
                o.source,
                o.ingestion_status,
                q.range_flag,
                q.rate_flag,
                q.persistence_flag,
                q.missing_flag,
                q.consistency_flag,
                q.qc_score,
                d.id AS diagnostic_id,
                d.classification,
                d.confidence,
                d.temporal_score,
                d.multivariate_score,
                d.evidence,
                d.recommended_action,
                d.explanation,
                oa.action AS operator_action,
                oa.timestamp AS operator_action_time
            FROM (
                SELECT * FROM observations 
                WHERE station_id = ? 
                ORDER BY timestamp DESC, id DESC 
                LIMIT ?
            ) o
            LEFT JOIN qc_results q ON o.id = q.observation_id
            LEFT JOIN diagnostics d ON o.id = d.observation_id
            LEFT JOIN (
                SELECT observation_id, action, timestamp,
                       ROW_NUMBER() OVER (PARTITION BY observation_id ORDER BY id DESC) as rn
                FROM operator_actions
            ) oa ON o.id = oa.observation_id AND oa.rn = 1
            ORDER BY o.timestamp ASC, o.id ASC
            """, (station_id, limit))
            records = []
            for row in cursor.fetchall():
                d = dict(row)
                if d.get("evidence") and isinstance(d["evidence"], str):
                    try:
                        d["evidence"] = json.loads(d["evidence"])
                    except Exception:
                        pass
                records.append(d)
            return records

    def get_station_health_stats(self, station_id: str, limit: int = 100) -> Dict[str, Any]:
        """Compute measurable station health indicators."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT 
                COUNT(o.id) as total_observations,
                SUM(CASE WHEN q.range_flag = 1 OR q.rate_flag = 1 OR q.consistency_flag = 1 THEN 1 ELSE 0 END) as anomalous_count,
                SUM(CASE WHEN q.persistence_flag = 1 THEN 1 ELSE 0 END) as frozen_sensor_incidents,
                SUM(CASE WHEN q.missing_flag = 1 OR o.temperature IS NULL OR o.pressure IS NULL OR o.humidity IS NULL THEN 1 ELSE 0 END) as missing_data_incidents,
                SUM(CASE WHEN d.classification = 'PROBABLE_SENSOR_FAULT' THEN 1 ELSE 0 END) as fault_alerts,
                SUM(CASE WHEN d.classification = 'UNCERTAIN' THEN 1 ELSE 0 END) as review_alerts,
                SUM(CASE WHEN d.classification = 'PROBABLE_GENUINE_EVENT' THEN 1 ELSE 0 END) as genuine_events
            FROM (
                SELECT * FROM observations WHERE station_id = ? ORDER BY id DESC LIMIT ?
            ) o
            LEFT JOIN qc_results q ON o.id = q.observation_id
            LEFT JOIN diagnostics d ON o.id = d.observation_id
            """, (station_id, limit))
            row = cursor.fetchone()
            if not row or row["total_observations"] == 0:
                return {
                    "total_observations": 0,
                    "anomalous_count": 0,
                    "frozen_sensor_incidents": 0,
                    "missing_data_incidents": 0,
                    "fault_alerts": 0,
                    "review_alerts": 0,
                    "genuine_events": 0,
                    "data_availability_pct": 100.0
                }
            total = row["total_observations"]
            missing = row["missing_data_incidents"] or 0
            avail = max(0.0, min(100.0, round(100.0 * (1.0 - (missing / total)), 1)))
            return {
                "total_observations": total,
                "anomalous_count": row["anomalous_count"] or 0,
                "frozen_sensor_incidents": row["frozen_sensor_incidents"] or 0,
                "missing_data_incidents": missing,
                "fault_alerts": row["fault_alerts"] or 0,
                "review_alerts": row["review_alerts"] or 0,
                "genuine_events": row["genuine_events"] or 0,
                "data_availability_pct": avail
            }

    def clear_database(self) -> None:
        """Utility for test suites and demo resets."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM operator_actions;")
            cursor.execute("DELETE FROM diagnostics;")
            cursor.execute("DELETE FROM qc_results;")
            cursor.execute("DELETE FROM observations;")
            conn.commit()


# Singleton database instance
db = Database()
