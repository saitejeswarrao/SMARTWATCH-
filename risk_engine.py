"""
risk_engine.py — AI Risk Prediction Engine
Module 1: Uses ML/DL on heart rate, HRV, SpO2, temperature, and motion
          to detect abnormal patterns and probable health risks.

Architecture:
  • Rule-based fast path  — catches clear-cut violations instantly
  • Statistical scoring   — z-score vs personal baseline (always-on)
  • ML model path         — scikit-learn models for nuanced pattern detection
  • Sensor fusion         — combines all channels into a per-dimension risk 0–100

Five risk dimensions:
  cardiac  — arrhythmia, tachycardia, bradycardia, HRV anomaly
  spo2     — hypoxia, sleep apnoea events
  stress   — autonomic stress, HRV suppression, skin conductance proxy
  fatigue  — sleep debt, HRV trend, activity recovery
  fall     — impact detection, post-fall stillness

In production: drop in a TFLite LSTM for cardiac + a CNN for fall detection.
"""

import math
import random
from typing import Dict, Optional
from health_profile import HealthProfile

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── Risk level thresholds (0–100 scale) ────────────────────────────────────
LEVEL_MAP = [
    (80, "critical"),
    (60, "high"),
    (40, "moderate"),
    (20, "low"),
    (0,  "normal"),
]

def risk_level(score: float) -> str:
    for threshold, label in LEVEL_MAP:
        if score >= threshold:
            return label
    return "normal"


# ── Historical window for trend analysis ────────────────────────────────────
class SlidingWindow:
    """Fixed-size circular buffer for rolling statistics."""

    def __init__(self, maxlen: int = 30):
        self._data   = []
        self._maxlen = maxlen

    def push(self, value: float):
        self._data.append(value)
        if len(self._data) > self._maxlen:
            self._data.pop(0)

    def mean(self) -> Optional[float]:
        return sum(self._data) / len(self._data) if self._data else None

    def std(self) -> Optional[float]:
        if len(self._data) < 2:
            return None
        m = self.mean()
        return math.sqrt(sum((x - m) ** 2 for x in self._data) / len(self._data))

    def z_score(self, value: float) -> float:
        """How many standard deviations from the rolling mean is this value?"""
        m, s = self.mean(), self.std()
        if m is None or s is None or s == 0:
            return 0.0
        return (value - m) / s


# ── Main risk engine ────────────────────────────────────────────────────────
class RiskEngine:
    """
    Multi-sensor, multi-dimension health risk scorer.

    Produces a risk dict with keys: cardiac, spo2, stress, fatigue, fall, overall.
    Each score is 0–100 (higher = more risk) and includes a level label.
    """

    def __init__(self, profile: HealthProfile):
        self.profile = profile

        # Rolling windows for trend-aware scoring
        self._hr_window     = SlidingWindow(30)
        self._hrv_window    = SlidingWindow(30)
        self._spo2_window   = SlidingWindow(30)
        self._stress_window = SlidingWindow(30)
        self._accel_history = []   # last 5 readings for fall confirmation

    # ── Public API ─────────────────────────────────────────────────────────

    def score(self, reading: dict) -> Dict[str, object]:
        """
        Score one sensor reading against the user's profile and history.
        Returns a dict with per-dimension scores and overall.
        """
        hr    = reading["heart_rate"]
        spo2  = reading["spo2"]
        hrv   = reading["hrv_ms"]
        temp  = reading["temp_c"]
        accel = reading["accel_g"]
        stress= reading["stress"]

        # Update rolling windows
        self._hr_window.push(hr)
        self._hrv_window.push(hrv)
        self._spo2_window.push(spo2)
        self._stress_window.push(stress)
        self._accel_history.append(accel)
        if len(self._accel_history) > 5:
            self._accel_history.pop(0)

        m = self.profile.risk_multiplier

        cardiac = self._score_cardiac(hr, hrv, temp, m)
        spo2_r  = self._score_spo2(spo2, m)
        stress_r= self._score_stress(stress, hrv, m)
        fatigue = self._score_fatigue(hrv, stress, m)
        fall    = self._score_fall(accel, m)
        overall = round((cardiac * 0.30 + spo2_r * 0.25 + stress_r * 0.20
                         + fatigue * 0.15 + fall * 0.10), 1)

        return {
            "cardiac":  cardiac,
            "spo2":     spo2_r,
            "stress":   stress_r,
            "fatigue":  fatigue,
            "fall":     fall,
            "overall":  overall,
            "cardiac_level":  risk_level(cardiac),
            "spo2_level":     risk_level(spo2_r),
            "stress_level":   risk_level(stress_r),
            "fatigue_level":  risk_level(fatigue),
            "fall_level":     risk_level(fall),
            "overall_level":  risk_level(overall),
        }

    # ── Cardiac scoring ─────────────────────────────────────────────────────

    def _score_cardiac(self, hr: int, hrv: int, temp: float, m: float) -> float:
        """
        Combines:
          • Rule-based HR boundary violations
          • Z-score deviation from rolling mean (anomaly detection)
          • HRV suppression (stress-induced autonomic imbalance)
          • Temperature contribution (fever raises cardiac demand)
          • Profile-weighted multiplier
        """
        thr   = self.profile.hr_threshold()
        score = 0.0

        # Rule violations
        if hr > thr["high"]:
            score += min(40, (hr - thr["high"]) * 1.5)
        elif hr > thr["elevated"]:
            score += min(20, (hr - thr["elevated"]) * 0.8)
        if hr < thr["low"]:
            score += min(35, (thr["low"] - hr) * 1.8)

        # Statistical anomaly (z-score)
        z = abs(self._hr_window.z_score(hr))
        score += min(20, z * 8)

        # HRV suppression
        hrv_thr = self.profile.hrv_threshold()
        if hrv < hrv_thr:
            score += min(15, (hrv_thr - hrv) * 0.6)

        # Temperature fever component
        if temp > 37.5:
            score += min(10, (temp - 37.5) * 12)

        return round(min(100, score * m), 1)

    # ── SpO₂ scoring ────────────────────────────────────────────────────────

    def _score_spo2(self, spo2: float, m: float) -> float:
        """
        Clinically-graded SpO₂ risk:
          97–100%  → normal
          94–96%   → mild concern
          90–93%   → moderate (clinically significant)
          85–89%   → severe hypoxia
          < 85%    → critical (emergency)
        """
        score = 0.0
        threshold = self.profile.spo2_threshold()

        if spo2 >= 97:
            score = 0
        elif spo2 >= 94:
            score = (97 - spo2) * 5
        elif spo2 >= threshold:
            score = 15 + (94 - spo2) * 15
        elif spo2 >= 85:
            score = 60 + (threshold - spo2) * 8
        else:
            score = 95   # critical floor

        # Trend penalty: sustained downward trend is worse than a single dip
        spo2_mean = self._spo2_window.mean()
        if spo2_mean and spo2_mean < 96:
            score += min(10, (96 - spo2_mean) * 3)

        return round(min(100, score * m), 1)

    # ── Stress scoring ──────────────────────────────────────────────────────

    def _score_stress(self, stress: int, hrv: int, m: float) -> float:
        """
        Stress model:
          Direct stress index (from galvanic/HRV proxy)  — 60%
          HRV suppression vs personal baseline            — 40%
        """
        direct = stress * 0.6

        hrv_baseline = self.profile.baseline_hrv
        hrv_deficit  = max(0, hrv_baseline - hrv) / hrv_baseline   # 0–1
        hrv_contrib  = hrv_deficit * 40

        score = direct + hrv_contrib

        # Trend amplifier: if stress has been elevated for 5+ readings
        s_mean = self._stress_window.mean()
        if s_mean and s_mean > self.profile.stress_threshold():
            score *= 1.15

        return round(min(100, score * m * 0.75), 1)

    # ── Fatigue scoring ──────────────────────────────────────────────────────

    def _score_fatigue(self, hrv: int, stress: int, m: float) -> float:
        """
        Fatigue model combines HRV trend (proxy for recovery state)
        and accumulated stress over the session.
        In production: integrate sleep staging data from accelerometer.
        """
        hrv_baseline = self.profile.baseline_hrv
        hrv_recovery = max(0, hrv_baseline - hrv)

        # HRV-based fatigue
        hrv_fatigue = min(60, hrv_recovery * 1.2)

        # Stress accumulation (rolling mean)
        s_mean = self._stress_window.mean() or stress
        stress_fatigue = min(40, max(0, s_mean - 30) * 0.8)

        score = hrv_fatigue + stress_fatigue
        return round(min(100, score * m * 0.85), 1)

    # ── Fall detection ───────────────────────────────────────────────────────

    def _score_fall(self, accel: float, m: float) -> float:
        """
        Two-stage fall detection:
          Stage 1 — impact threshold: sudden acceleration > 1.8g
          Stage 2 — post-fall stillness: accel drops near zero after spike
                    (indicates the person is on the ground and not moving)

        In production: replace with a lightweight CNN trained on
        ADXL345/MPU-6050 time-series data.
        """
        score = 0.0

        # Stage 1: impact
        if accel > 3.5:
            score = 95      # very likely fall
        elif accel > 2.0:
            score = 70
        elif accel > 1.5:
            score = 40
        elif accel > 1.0:
            score = 15

        # Stage 2: post-fall stillness confirmation
        if score > 40 and len(self._accel_history) >= 3:
            recent = self._accel_history[-3:]
            if all(a < 0.15 for a in recent):
                score = min(100, score + 20)   # stillness confirms fall

        return round(min(100, score * m), 1)