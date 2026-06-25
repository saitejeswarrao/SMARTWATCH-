"""
health_profile.py — Personalised Health Profile & Adaptive Thresholds
Module 2: Adapts thresholds and alerts to each user based on age,
medical conditions, lifestyle, and historical data.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import json


# ── Known conditions and their risk weights ──────────────────────────────────
CONDITION_WEIGHTS = {
    "hypertension":       0.30,
    "diabetes":           0.20,
    "heart_disease":      0.40,
    "atrial_fibrillation":0.45,
    "copd":               0.35,
    "sleep_apnea":        0.25,
    "obesity":            0.15,
    "anemia":             0.15,
}

# ── Age-based baseline adjustments ──────────────────────────────────────────
def _age_multiplier(age: int) -> float:
    if age < 18:  return 0.85
    if age < 30:  return 1.00
    if age < 45:  return 1.05
    if age < 60:  return 1.15
    if age < 75:  return 1.30
    return 1.50


@dataclass
class HealthProfile:
    """
    Stores everything the AI needs to personalise risk scoring and alerts
    for a specific user. Adaptive thresholds are recalculated on the fly
    using the user's age, weight, conditions, and historical baseline.
    """

    user_id:   str
    name:      str  = "User"
    age:       int  = 30
    weight_kg: float = 70.0
    height_cm: float = 170.0
    conditions: List[str] = field(default_factory=list)
    emergency_contacts: List[Dict[str, str]] = field(default_factory=list)

    # Historical baselines — updated over time by CoachingEngine
    baseline_hr:    float = 72.0
    baseline_hrv:   float = 42.0
    baseline_stress:float = 35.0
    baseline_spo2:  float = 97.0

    # Lifestyle flags
    is_athlete:    bool = False
    is_smoker:     bool = False
    is_pregnant:   bool = False

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def bmi(self) -> float:
        h = self.height_cm / 100
        return round(self.weight_kg / (h * h), 1)

    @property
    def risk_multiplier(self) -> float:
        """
        Composite risk multiplier.
        A 60-year-old with hypertension gets tighter thresholds
        than a healthy 25-year-old athlete.
        """
        base = _age_multiplier(self.age)

        # Conditions add cumulative risk
        for cond in self.conditions:
            base += CONDITION_WEIGHTS.get(cond.lower(), 0.10)

        # Lifestyle modifiers
        if self.is_smoker:   base += 0.15
        if self.is_pregnant: base += 0.10
        if self.bmi > 30:    base += 0.10
        if self.is_athlete:  base -= 0.10   # athletes have lower resting HR etc.

        return round(min(max(base, 0.80), 2.50), 2)

    # ── Adaptive thresholds ──────────────────────────────────────────────────

    def hr_threshold(self) -> Dict[str, int]:
        """Personalised HR alert boundaries (bpm)."""
        m = self.risk_multiplier
        # Athletes naturally run lower resting HR
        low_base  = 45 if self.is_athlete else 50
        high_base = 95 if self.is_athlete else 100
        return {
            "low":      int(low_base  / m),
            "elevated": int(high_base * (m * 0.9)),
            "high":     int(high_base * m),
        }

    def spo2_threshold(self) -> float:
        """Minimum acceptable SpO₂ (%)."""
        if "copd" in self.conditions or "sleep_apnea" in self.conditions:
            return 90.0   # clinical lower limit for these conditions
        if self.risk_multiplier > 1.3:
            return 93.0
        return 92.0

    def hrv_threshold(self) -> float:
        """HRV below this (ms) triggers fatigue/stress flag."""
        base = self.baseline_hrv
        return round(base * 0.65, 1)   # 35% below personal baseline

    def stress_threshold(self) -> int:
        """Stress score above this triggers coaching nudge."""
        return 60 if self.risk_multiplier > 1.2 else 70

    def temp_threshold(self) -> Dict[str, float]:
        """Skin temperature alert range (°C)."""
        return {"low": 35.0, "high": 37.8 if not self.is_pregnant else 37.5}

    # ── Baseline update (called by CoachingEngine) ────────────────────────────

    def update_baseline(self, avg_hr: float, avg_hrv: float,
                         avg_stress: float, avg_spo2: float):
        """
        Smoothly update personal baselines using exponential moving average.
        α=0.1 means new data has 10% weight → gradual adaptation over weeks.
        """
        α = 0.10
        self.baseline_hr     = round(α * avg_hr     + (1 - α) * self.baseline_hr,     1)
        self.baseline_hrv    = round(α * avg_hrv    + (1 - α) * self.baseline_hrv,    1)
        self.baseline_stress = round(α * avg_stress + (1 - α) * self.baseline_stress, 1)
        self.baseline_spo2   = round(α * avg_spo2   + (1 - α) * self.baseline_spo2,   2)

    # ── Serialisation ────────────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id":    self.user_id,
            "name":       self.name,
            "age":        self.age,
            "bmi":        self.bmi,
            "conditions": self.conditions,
            "risk_multiplier": self.risk_multiplier,
            "thresholds": {
                "hr":    self.hr_threshold(),
                "spo2":  self.spo2_threshold(),
                "hrv":   self.hrv_threshold(),
                "stress":self.stress_threshold(),
                "temp":  self.temp_threshold(),
            },
            "baselines": {
                "hr":    self.baseline_hr,
                "hrv":   self.baseline_hrv,
                "stress":self.baseline_stress,
                "spo2":  self.baseline_spo2,
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def __repr__(self) -> str:
        return (f"HealthProfile({self.name}, age={self.age}, "
                f"BMI={self.bmi}, risk_mult={self.risk_multiplier}x, "
                f"conditions={self.conditions})")