"""
sensor_data.py — Sensor Data Layer (PPG, SpO₂, Accelerometer, Temp, HRV, GPS)
Module: Hardware abstraction — swap simulate() for real BLE SDK calls
        (e.g. Polar SDK, Garmin Connect IQ, Apple HealthKit, Android Health SDK).

Simulates realistic physiological variation including:
  - Circadian HR rhythm (lower at night, higher mid-day)
  - Activity bursts detected by accelerometer
  - Correlated stress ↔ HRV ↔ HR patterns
  - Occasional anomaly injection for testing alert system
"""

import math
import random
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class SensorReading:
    """One snapshot of all sensor channels at a point in time."""
    timestamp:  float
    heart_rate: int           # bpm
    spo2:       float         # %
    hrv_ms:     int           # milliseconds
    temp_c:     float         # °C skin temperature
    accel_g:    float         # peak acceleration in g (gravity units)
    stress:     int           # 0–100 composite
    steps:      int           # cumulative step count
    gps_lat:    Optional[float] = None
    gps_lng:    Optional[float] = None
    activity:   str = "resting"   # resting | walking | running | sleeping

    def to_dict(self) -> dict:
        return {
            "timestamp":  self.timestamp,
            "heart_rate": self.heart_rate,
            "spo2":       self.spo2,
            "hrv_ms":     self.hrv_ms,
            "temp_c":     self.temp_c,
            "accel_g":    self.accel_g,
            "stress":     self.stress,
            "steps":      self.steps,
            "gps_lat":    self.gps_lat,
            "gps_lng":    self.gps_lng,
            "activity":   self.activity,
        }


class SensorManager:
    """
    Manages all on-watch sensor channels.

    In production, replace `_read_hardware()` with real BLE reads:

        import asyncio
        from bleak import BleakClient
        async def _read_hardware(self, address):
            async with BleakClient(address) as client:
                hr_data = await client.read_gatt_char(HR_UUID)
                return int.from_bytes(hr_data[1:3], "little")
    """

    def __init__(self, simulate_anomalies: bool = True,
                 anomaly_probability: float = 0.05):
        self._tick        = 0
        self._steps       = 0
        self._sim_anomaly = simulate_anomalies
        self._anomaly_p   = anomaly_probability
        self._activity    = "resting"
        self._activity_ticks_left = 0

        # Fixed demo GPS (Hyderabad, India)
        self._gps_lat = 17.3850 + random.uniform(-0.005, 0.005)
        self._gps_lng = 78.4867 + random.uniform(-0.005, 0.005)

    # ── Public API ───────────────────────────────────────────────────────────

    def read(self) -> dict:
        """Return one SensorReading as a dict (JSON-serialisable)."""
        return self._build_reading().to_dict()

    def read_typed(self) -> SensorReading:
        """Return a typed SensorReading dataclass."""
        return self._build_reading()

    # ── Internal simulation ──────────────────────────────────────────────────

    def _build_reading(self) -> SensorReading:
        self._tick += 1
        t = self._tick

        # Determine activity state
        self._update_activity()

        # Circadian rhythm offset (peaks at midday, dips at 3am)
        hour      = (time.localtime().tm_hour + time.localtime().tm_min / 60)
        circadian = 5 * math.sin(math.pi * (hour - 6) / 12)

        # Activity-based HR boost
        activity_hr_boost = {"resting": 0, "walking": 15, "running": 40, "sleeping": -8}
        act_boost = activity_hr_boost.get(self._activity, 0)

        # Base vitals with physiological correlation
        stress   = self._simulate_stress(t)
        hr       = self._simulate_hr(t, circadian, act_boost, stress)
        hrv      = self._simulate_hrv(hr, stress)
        spo2     = self._simulate_spo2(t, self._activity)
        temp     = self._simulate_temp(t, stress)
        accel    = self._simulate_accel(self._activity)
        self._steps += self._step_increment(self._activity)

        # Optionally inject a dramatic anomaly for alert testing
        if self._sim_anomaly and random.random() < self._anomaly_p:
            hr, spo2, accel = self._inject_anomaly(hr, spo2, accel)

        return SensorReading(
            timestamp  = round(time.time(), 3),
            heart_rate = hr,
            spo2       = spo2,
            hrv_ms     = hrv,
            temp_c     = temp,
            accel_g    = accel,
            stress     = stress,
            steps      = self._steps,
            gps_lat    = self._gps_lat,
            gps_lng    = self._gps_lng,
            activity   = self._activity,
        )

    # ── Per-channel simulators ───────────────────────────────────────────────

    def _simulate_hr(self, t: int, circadian: float,
                     act_boost: int, stress: int) -> int:
        base  = 72 + circadian + act_boost + stress * 0.15
        noise = random.gauss(0, 2.5)
        wave  = 4 * math.sin(t / 8)   # slow sinusoidal drift
        return max(35, min(220, int(base + noise + wave)))

    def _simulate_hrv(self, hr: int, stress: int) -> int:
        # Higher HR and stress → lower HRV (well-established inverse relationship)
        base  = max(8, 80 - (hr - 60) * 0.6 - stress * 0.3)
        noise = random.gauss(0, 4)
        return max(8, int(base + noise))

    def _simulate_spo2(self, t: int, activity: str) -> float:
        base  = 97.5
        if activity == "running":  base -= 0.8
        if activity == "sleeping": base += 0.2
        noise = random.gauss(0, 0.3)
        return round(min(100.0, max(88.0, base + noise)), 1)

    def _simulate_stress(self, t: int) -> int:
        base  = 35
        wave  = 12 * math.sin(t / 20)   # slow stress oscillation
        noise = random.gauss(0, 8)
        return max(0, min(100, int(base + wave + noise)))

    def _simulate_temp(self, t: int, stress: int) -> float:
        base  = 36.5 + stress * 0.005
        noise = random.gauss(0, 0.08)
        return round(max(34.0, min(40.0, base + noise)), 2)

    def _simulate_accel(self, activity: str) -> float:
        accel_map = {
            "resting":  (0.0,  0.05),
            "walking":  (0.3,  0.15),
            "running":  (1.2,  0.30),
            "sleeping": (0.0,  0.02),
        }
        mean, std = accel_map.get(activity, (0.05, 0.05))
        return round(max(0.0, random.gauss(mean, std)), 3)

    def _simulate_anomaly(self) -> tuple:
        """Pick a random anomaly type."""
        return random.choice(["tachycardia", "bradycardia", "low_spo2", "fall"])

    def _inject_anomaly(self, hr: int, spo2: float, accel: float):
        anomaly = self._simulate_anomaly()
        if anomaly == "tachycardia":
            hr   = random.randint(130, 180)
        elif anomaly == "bradycardia":
            hr   = random.randint(35, 48)
        elif anomaly == "low_spo2":
            spo2 = round(random.uniform(85.0, 91.5), 1)
        elif anomaly == "fall":
            accel = round(random.uniform(2.5, 5.0), 3)
        return hr, spo2, accel

    # ── Activity state machine ───────────────────────────────────────────────

    def _update_activity(self):
        if self._activity_ticks_left > 0:
            self._activity_ticks_left -= 1
            return
        # Transition probabilities per tick
        next_activity = random.choices(
            ["resting", "walking", "running", "sleeping"],
            weights=[55, 28, 10, 7]
        )[0]
        self._activity = next_activity
        self._activity_ticks_left = random.randint(3, 15)

    def _step_increment(self, activity: str) -> int:
        return {"resting": 0, "walking": 2, "running": 5, "sleeping": 0}.get(activity, 0)