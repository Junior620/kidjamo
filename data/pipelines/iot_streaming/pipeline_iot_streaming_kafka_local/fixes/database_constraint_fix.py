"""
Fix for Database Constraint Violation - Unique Timestamp Generation

The issue: Multiple measurements generated simultaneously have identical timestamps,
causing duplicate key violations on the unique constraint (device_id, patient_id, recorded_at).

Solution: Add microsecond precision and sequential numbering to ensure unique timestamps.
"""

import time
from datetime import datetime, timedelta
import threading
from typing import Dict

class TimestampManager:
    """Thread-safe timestamp manager to ensure unique measurement timestamps"""

    def __init__(self):
        self._lock = threading.Lock()
        self._last_timestamp = {}  # Per patient/device tracking
        self._sequence_counter = {}

    def get_unique_timestamp(self, patient_id: str, device_id: str) -> datetime:
        """Generate unique timestamp for measurement"""
        with self._lock:
            key = f"{patient_id}_{device_id}"
            current_time = datetime.now()

            # Check if we need to increment to avoid duplicates
            if key in self._last_timestamp:
                last_time = self._last_timestamp[key]

                # If same second, add microseconds to make unique
                if current_time.replace(microsecond=0) == last_time.replace(microsecond=0):
                    # Increment sequence counter for this second
                    if key not in self._sequence_counter:
                        self._sequence_counter[key] = 0

                    self._sequence_counter[key] += 1

                    # Add microseconds based on sequence
                    microseconds = min(999999, self._sequence_counter[key])
                    current_time = current_time.replace(microsecond=microseconds)

                    # If we've used all microseconds in this second, move to next second
                    if microseconds >= 999999:
                        current_time = current_time.replace(second=current_time.second + 1, microsecond=0)
                        self._sequence_counter[key] = 0
                else:
                    # New second, reset counter
                    self._sequence_counter[key] = 0

            self._last_timestamp[key] = current_time
            return current_time

# Global timestamp manager instance
timestamp_manager = TimestampManager()

def get_unique_measurement_timestamp(patient_id: str, device_id: str) -> datetime:
    """Get unique timestamp for measurement - use this in simulator"""
    return timestamp_manager.get_unique_timestamp(patient_id, device_id)

# Database insertion with conflict resolution
def safe_measurement_insert(cursor, measurements_data):
    """Insert measurements with conflict resolution"""

    # Use ON CONFLICT to handle any remaining duplicates
    query = """
        INSERT INTO measurements (
            patient_id, device_id, recorded_at, received_at,
            heart_rate_bpm, respiratory_rate_min, spo2_percent, 
            temperature_celsius, ambient_temp_celsius, hydration_percent,
            activity_level, heat_index_celsius, pain_scale, 
            battery_percent, signal_quality, quality_flag, 
            data_source, is_validated
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (device_id, patient_id, recorded_at) 
        DO UPDATE SET
            received_at = EXCLUDED.received_at,
            heart_rate_bpm = EXCLUDED.heart_rate_bpm,
            respiratory_rate_min = EXCLUDED.respiratory_rate_min,
            spo2_percent = EXCLUDED.spo2_percent,
            temperature_celsius = EXCLUDED.temperature_celsius,
            ambient_temp_celsius = EXCLUDED.ambient_temp_celsius,
            hydration_percent = EXCLUDED.hydration_percent,
            activity_level = EXCLUDED.activity_level,
            heat_index_celsius = EXCLUDED.heat_index_celsius,
            pain_scale = EXCLUDED.pain_scale,
            battery_percent = EXCLUDED.battery_percent,
            signal_quality = EXCLUDED.signal_quality,
            quality_flag = EXCLUDED.quality_flag,
            data_source = EXCLUDED.data_source,
            is_validated = EXCLUDED.is_validated
    """

    cursor.executemany(query, measurements_data)
