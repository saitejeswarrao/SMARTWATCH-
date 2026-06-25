"""
coaching.py — Smart Feedback & Coaching Engine
Module 6: Provides daily/weekly insights — sleep score, stress trend,
          activity summary, and personalised lifestyle recommendations.

Architecture:
  • SlidingWindow accumulators track all vital channels
  • SleepStager infers sleep phases from HR + HRV + accelerometer at rest
  • WeeklySummary computes 7-day aggregates and generates actionable tips
  • TipSelector maps the highest-risk dimension to curated advice
"""

import math
import statistics
from collections import deque
from typing import Dict, List, Optional, Deque


# ── Curated coaching tips per risk dimension & severity ──────────────────────
TIPS: Dict[str, List[str]] = {
    "cardiac": [
        "Stay hydrated — even mild dehydration raises resting heart rate.",
        "Try paced breathing: inhale 4 counts, exhale 6 counts for 5 minutes.",
        "Avoid caffeine after 2 pm — it can elevate HR for up to 6 hours.",
        "A short 10-minute walk after meals reduces post-meal HR spikes.",
    ],
    "spo2": [
        "Move to a well-ventilated area and take slow, deep breaths.",
        "Avoid lying face-down during sleep — it can compress the chest.",
        "If SpO₂ stays below 94% for more than 5 minutes, seek medical help.",
        "Practice diaphragmatic breathing: breathe from your belly, not your chest.",
    ],
    "stress": [
        "Try the 4-7-8 technique: inhale 4s, hold 7s, exhale 8s. Repeat 4 times.",
        "A 5-minute walk outdoors lowers cortisol by up to 15%.",
        "Cold water on your wrists activates the parasympathetic nervous system.",
        "Write down 3 things you're grateful for — it shifts cognitive load.",
    ],
    "fatigue": [
        "Prioritise consistent sleep — same bedtime improves HRV by ~20% in 2 weeks.",
        "Avoid screens 1 hour before bed — blue light suppresses melatonin.",
        "A 20-minute nap (no longer) can restore alertness without sleep inertia.",
        "Magnesium-rich foods (dark chocolate, nuts, spinach) support deeper sleep.",
    ],
    "fall": [
        "Ensure walkways are clear and well-lit — most falls happen at home.",
        "Consider balance exercises like single-leg stands (30s each side daily).",
        "Non-slip footwear reduces fall risk by up to 40% for older adults.",
        "If dizziness accompanies the alert, sit down immediately and hydrate.",
    ],
    "general": [
        "You're doing great — keep up your current routine!",
        "Aim for 7–9 hours of sleep tonight to consolidate today's activity.",
        "150 minutes of moderate exercise per week reduces all-cause mortality by 35%.",
    ],
}

ACTIVITY_TIPS = {
    "running": "Great run! Rehydrate within 30 minutes and do a 5-min cool-down stretch.",
    "walking": "Nice walk. Walking 8,000 steps/day is associated with significantly lower mortality risk.",
    "sleeping": "Rest detected. Deep, consistent sleep is the #1 recovery tool.",
    "resting": "Light day noted. Even gentle stretching improves circulation.",
}


# ── Sleep staging (simplified heuristic) ────────────────────────────────────
class SleepStager:
    """
    Infers basic sleep phases from HR + HRV + accelerometer patterns.
    In production: use a trained LSTM on 30-second epoch windows.

    Phases:
      awake  — HR variable, movement detected
      light  — HR lower, some movement, HRV moderate
      deep   — HR very low, minimal movement, HRV high
      rem    — HR variable but accel ~0 (REM atonia)
    """

    def infer(self, hr: int, hrv: int, accel: float) -> str:
        if accel > 0.15:
            return "awake"
        if hr < 55 and hrv > 55 and accel < 0.05:
            return "deep"
        if hr < 65 and accel < 0.08:
            return "light"
        if hr > 60 and accel < 0.06:
            return "rem"
        return "awake"

    def score_session(self, phases: List[str]) -> int:
        """Score a sleep session 0–100 based on phase distribution."""
        if not phases:
            return 0
        counts = {p: phases.count(p) for p in ("awake", "light", "deep", "rem")}
        total  = len(phases)
        deep_pct = counts["deep"] / total
        rem_pct  = counts["rem"]  / total
        awake_pct= counts["awake"]/ total

        score  = min(40, deep_pct  * 200)   # deep sleep: up to 40 pts (ideal ~20%)
        score += min(30, rem_pct   * 150)   # REM:        up to 30 pts (ideal ~20%)
        score += min(20, (1 - awake_pct) * 22)  # continuity: up to 20 pts
        score += 10  # base participation bonus
        return min(100, int(score))


# ── Coaching engine ──────────────────────────────────────────────────────────
class CoachingEngine:
    """
    Accumulates sensor readings and risk scores over time,
    then generates personalised daily and weekly coaching insights.
    """

    def __init__(self, window_size: int = 60):
        self._readings: Deque[dict]  = deque(maxlen=window_size)
        self._risks:    Deque[dict]  = deque(maxlen=window_size)
        self._sleep_phases: List[str] = []
        self._stager = SleepStager()
        self._tip_index: Dict[str, int] = {}   # cycles through tips per dimension

    # ── Update ────────────────────────────────────────────────────────────────

    def update(self, reading: dict, risks: dict):
        """Call once per monitoring cycle to accumulate data."""
        self._readings.append(reading)
        self._risks.append(risks)

        # Infer sleep phase if person appears to be sleeping
        if reading.get("activity") == "sleeping":
            phase = self._stager.infer(
                reading["heart_rate"], reading["hrv_ms"], reading["accel_g"]
            )
            self._sleep_phases.append(phase)

    # ── Real-time tip ─────────────────────────────────────────────────────────

    def live_tip(self, risks: dict) -> Optional[str]:
        """Return the most relevant tip for the current risk snapshot."""
        top_dim = self._top_risk_dimension(risks)
        if not top_dim:
            return None
        tips = TIPS.get(top_dim, TIPS["general"])
        idx  = self._tip_index.get(top_dim, 0)
        tip  = tips[idx % len(tips)]
        self._tip_index[top_dim] = idx + 1
        return tip

    def activity_tip(self, activity: str) -> str:
        return ACTIVITY_TIPS.get(activity, ACTIVITY_TIPS["resting"])

    # ── Daily summary ─────────────────────────────────────────────────────────

    def daily_summary(self) -> dict:
        if len(self._readings) < 5:
            return {"status": "collecting data — need at least 5 readings"}

        hrs     = [r["heart_rate"] for r in self._readings]
        spoes   = [r["spo2"]       for r in self._readings]
        hrvs    = [r["hrv_ms"]     for r in self._readings]
        strs    = [r["stress"]     for r in self._readings]
        steps   = max((r["steps"] for r in self._readings), default=0)
        acts    = [r.get("activity","resting") for r in self._readings]

        sleep_score = self._stager.score_session(self._sleep_phases)
        top_dim     = self._top_risk_dimension(self._risks[-1] if self._risks else {})

        return {
            "avg_hr":          round(statistics.mean(hrs), 1),
            "min_hr":          min(hrs),
            "max_hr":          max(hrs),
            "avg_spo2":        round(statistics.mean(spoes), 1),
            "avg_hrv":         round(statistics.mean(hrvs), 1),
            "avg_stress":      round(statistics.mean(strs), 1),
            "peak_stress":     max(strs),
            "total_steps":     steps,
            "active_minutes":  acts.count("walking") + acts.count("running"),
            "sleep_score":     sleep_score,
            "sleep_phases":    self._phase_breakdown(self._sleep_phases),
            "top_risk":        top_dim or "none",
            "tip":             self.live_tip(self._risks[-1]) if self._risks else None,
        }

    # ── Weekly summary ────────────────────────────────────────────────────────

    def weekly_summary(self) -> dict:
        """Aggregated 7-day (or session) insights with lifestyle recommendations."""
        if len(self._readings) < 5:
            return {"status": "collecting data — need at least 5 readings"}

        daily = self.daily_summary()
        risks = [r.get("overall", 0) for r in self._risks]
        avg_overall = round(statistics.mean(risks), 1) if risks else 0.0

        # Trend direction: is overall risk increasing or decreasing?
        trend = "stable"
        if len(risks) >= 10:
            first_half = statistics.mean(risks[:len(risks)//2])
            sec_half   = statistics.mean(risks[len(risks)//2:])
            if sec_half > first_half + 5:
                trend = "worsening"
            elif sec_half < first_half - 5:
                trend = "improving"

        top_dim = self._top_risk_dimension_overall()

        return {
            "avg_hr":          daily["avg_hr"],
            "avg_hrv":         daily["avg_hrv"],
            "avg_stress":      daily["avg_stress"],
            "avg_spo2":        daily["avg_spo2"],
            "avg_overall_risk":avg_overall,
            "risk_trend":      trend,
            "total_steps":     daily["total_steps"],
            "active_minutes":  daily["active_minutes"],
            "sleep_score":     daily["sleep_score"],
            "top_risk":        top_dim or "none",
            "tip":             self._pick_tip(top_dim),
            "lifestyle_recs":  self._lifestyle_recommendations(daily, avg_overall),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _top_risk_dimension(self, risks: dict) -> Optional[str]:
        dims = {k: v for k, v in risks.items()
                if k in ("cardiac", "spo2", "stress", "fatigue", "fall")}
        return max(dims, key=dims.get) if dims else None

    def _top_risk_dimension_overall(self) -> Optional[str]:
        if not self._risks:
            return None
        avgs = {}
        for dim in ("cardiac", "spo2", "stress", "fatigue", "fall"):
            vals = [r.get(dim, 0) for r in self._risks]
            avgs[dim] = statistics.mean(vals) if vals else 0
        return max(avgs, key=avgs.get)

    def _pick_tip(self, dim: Optional[str]) -> str:
        tips = TIPS.get(dim or "general", TIPS["general"])
        return tips[0]

    def _phase_breakdown(self, phases: List[str]) -> dict:
        if not phases:
            return {"awake": 0, "light": 0, "deep": 0, "rem": 0}
        total = len(phases)
        return {p: round(phases.count(p) / total * 100, 1)
                for p in ("awake", "light", "deep", "rem")}

    def _lifestyle_recommendations(self, daily: dict, avg_risk: float) -> List[str]:
        recs = []
        if daily["avg_stress"] > 55:
            recs.append("Your stress trend is elevated. Schedule a rest day and try mindfulness.")
        if daily["sleep_score"] < 60:
            recs.append("Sleep quality needs attention. Aim for a consistent sleep schedule.")
        if daily["avg_hrv"] < 30:
            recs.append("HRV is suppressed. Prioritise recovery — avoid intense training today.")
        if daily["total_steps"] < 5000:
            recs.append("Step count is low. A 20-minute walk after dinner adds ~2,000 steps.")
        if daily["avg_spo2"] < 96:
            recs.append("SpO₂ average is slightly low. Ensure good ventilation while sleeping.")
        if avg_risk > 50:
            recs.append("Overall risk is elevated. Consider scheduling a check-up.")
        if not recs:
            recs.append("All metrics look healthy. Keep up your current lifestyle!")
        return recs