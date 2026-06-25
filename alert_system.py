"""
alert_system.py — Real-Time Alert & SOS Engine
Module 3: Sends tiered notifications to user, family, and doctor app
          with vitals + GPS location during critical events.

Alert tiers:
  normal   → no action
  low      → on-watch haptic + screen nudge
  moderate → push notification to user phone
  high     → push to user + emergency contacts
  critical → SOS: simultaneous push + SMS + GPS dispatch to doctor & family

Debounce logic prevents alert storms: each dimension is suppressed for
a cooldown window after firing, unless the level escalates.
"""

import time
import json
import datetime
from typing import Dict, List, Optional
from health_profile import HealthProfile


# ── Thresholds (score → alert level) ────────────────────────────────────────
LEVEL_THRESHOLDS = {
    "critical": 80,
    "high":     60,
    "moderate": 40,
    "low":      20,
}

# ── Cooldown windows (seconds) before same dimension can re-alert ────────────
COOLDOWN = {
    "critical": 30,
    "high":     60,
    "moderate": 120,
    "low":      300,
    "normal":   0,
}

# ── Human-readable alert messages ────────────────────────────────────────────
MESSAGES = {
    "cardiac": {
        "critical": "Critical cardiac anomaly detected. Possible arrhythmia. Seek immediate medical attention.",
        "high":     "Elevated cardiac risk. Heart rate or HRV significantly abnormal.",
        "moderate": "Mild cardiac irregularity detected. Monitor closely.",
        "low":      "Heart rate slightly outside normal range.",
    },
    "spo2": {
        "critical": "Critical: Blood oxygen dangerously low. Emergency help dispatched.",
        "high":     "Blood oxygen low. Move to fresh air. Seek medical help if persistent.",
        "moderate": "Blood oxygen slightly below normal. Rest and breathe slowly.",
        "low":      "Minor SpO₂ variation detected.",
    },
    "stress": {
        "critical": "Extreme stress response. Autonomic system under severe strain.",
        "high":     "High stress levels detected. Take a break and breathe.",
        "moderate": "Elevated stress. Consider a short walk or breathing exercise.",
        "low":      "Mild stress detected.",
    },
    "fatigue": {
        "critical": "Severe fatigue. Risk of impaired judgment. Rest immediately.",
        "high":     "High fatigue levels. Consider resting soon.",
        "moderate": "Moderate fatigue detected.",
        "low":      "Slight fatigue noted.",
    },
    "fall": {
        "critical": "Possible fall detected! Emergency contacts being notified.",
        "high":     "Unusual impact detected. Are you okay?",
        "moderate": "Minor impact detected.",
        "low":      "Movement anomaly detected.",
    },
}


# ── Alert record ─────────────────────────────────────────────────────────────
class Alert:
    def __init__(self, dimension: str, level: str, score: float,
                 reading: dict, profile: HealthProfile):
        self.id          = f"{dimension}_{int(time.time()*1000)}"
        self.dimension   = dimension
        self.level       = level
        self.score       = score
        self.message     = MESSAGES.get(dimension, {}).get(level, "Health alert.")
        self.timestamp   = datetime.datetime.utcnow().isoformat() + "Z"
        self.vitals      = {k: reading[k] for k in
                            ("heart_rate", "spo2", "hrv_ms", "temp_c",
                             "stress", "accel_g") if k in reading}
        self.gps_lat     = reading.get("gps_lat")
        self.gps_lng     = reading.get("gps_lng")
        self.user_name   = profile.name
        self.contacts    = profile.emergency_contacts
        self.resolved    = False

    def to_dict(self) -> dict:
        return {
            "alert_id":  self.id,
            "dimension": self.dimension,
            "level":     self.level,
            "score":     self.score,
            "message":   self.message,
            "timestamp": self.timestamp,
            "vitals":    self.vitals,
            "gps":       {"lat": self.gps_lat, "lng": self.gps_lng},
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


# ── Alert system ─────────────────────────────────────────────────────────────
class AlertSystem:
    """
    Evaluates risk scores, manages debounce/cooldown,
    and dispatches tiered notifications.
    """

    def __init__(self, profile: HealthProfile):
        self.profile = profile
        self._log: List[Alert] = []
        # Tracks last alert time + level per dimension for debounce
        self._last_alert: Dict[str, dict] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def evaluate(self, risks: dict, reading: dict) -> List[Alert]:
        """
        Evaluate all risk dimensions and fire alerts as needed.
        Returns list of Alert objects fired this cycle.
        """
        fired = []
        for dim in ("cardiac", "spo2", "stress", "fatigue", "fall"):
            score = risks.get(dim, 0)
            level = self._score_to_level(score)
            if level == "normal":
                continue
            if self._is_suppressed(dim, level):
                continue
            alert = Alert(dim, level, score, reading, self.profile)
            self._dispatch(alert)
            self._record(dim, level, alert)
            fired.append(alert)

        return fired

    def get_log(self, last_n: int = 20) -> List[dict]:
        """Return the last N alert records as dicts."""
        return [a.to_dict() for a in self._log[-last_n:]]

    def unresolved(self) -> List[Alert]:
        return [a for a in self._log if not a.resolved]

    def resolve(self, alert_id: str):
        for a in self._log:
            if a.id == alert_id:
                a.resolved = True

    # ── Dispatch logic ────────────────────────────────────────────────────────

    def _dispatch(self, alert: Alert):
        """
        Route alert to appropriate channels based on severity.
        Replace print() stubs with real FCM / Twilio / WebSocket calls.
        """
        print(f"\n  ╔═══ ALERT [{alert.level.upper()}] ═══════════════════════")
        print(f"  ║  Dimension : {alert.dimension}")
        print(f"  ║  Score     : {alert.score}/100")
        print(f"  ║  Message   : {alert.message}")
        print(f"  ║  Time      : {alert.timestamp}")
        print(f"  ║  Vitals    : HR={alert.vitals.get('heart_rate')} bpm | "
              f"SpO2={alert.vitals.get('spo2')}% | "
              f"HRV={alert.vitals.get('hrv_ms')} ms")

        if alert.level in ("moderate", "high", "critical"):
            self._push_to_user(alert)

        if alert.level in ("high", "critical"):
            self._push_to_contacts(alert)

        if alert.level == "critical":
            self._sos_dispatch(alert)

        print(f"  ╚══════════════════════════════════════════════")

    def _push_to_user(self, alert: Alert):
        # In production: FCM / APNs push notification
        print(f"  ║  [PUSH → User] {alert.message}")

    def _push_to_contacts(self, alert: Alert):
        for contact in alert.contacts:
            # In production: Twilio SMS + FCM to family/doctor app
            print(f"  ║  [PUSH → {contact['role'].title()} "
                  f"({contact['name']})] {alert.dimension.upper()} risk alert")

    def _sos_dispatch(self, alert: Alert):
        """Full SOS: multi-channel emergency dispatch with GPS."""
        print(f"  ║  ⚡ SOS DISPATCHED")
        for contact in alert.contacts:
            # SMS stub — replace with Twilio client.messages.create(...)
            print(f"  ║  [SMS → {contact['name']} ({contact['phone']})]")
            print(f"  ║     {alert.user_name} — {alert.message}")
            if alert.gps_lat:
                maps_url = (f"https://maps.google.com/?q="
                            f"{alert.gps_lat},{alert.gps_lng}")
                print(f"  ║     Location: {maps_url}")

    # ── Debounce helpers ──────────────────────────────────────────────────────

    def _score_to_level(self, score: float) -> str:
        for level, threshold in sorted(
                LEVEL_THRESHOLDS.items(), key=lambda x: -x[1]):
            if score >= threshold:
                return level
        return "normal"

    def _is_suppressed(self, dim: str, level: str) -> bool:
        """
        Suppress if we already fired this dimension at the same or higher level
        within the cooldown window. Allow through if level escalated.
        """
        last = self._last_alert.get(dim)
        if not last:
            return False

        level_order = ["low", "moderate", "high", "critical"]
        last_level_idx = level_order.index(last["level"]) if last["level"] in level_order else -1
        curr_level_idx = level_order.index(level) if level in level_order else 0

        # Always allow escalation
        if curr_level_idx > last_level_idx:
            return False

        elapsed = time.time() - last["time"]
        return elapsed < COOLDOWN.get(level, 60)

    def _record(self, dim: str, level: str, alert: Alert):
        self._log.append(alert)
        self._last_alert[dim] = {"level": level, "time": time.time()}
        # Keep log bounded to last 500 alerts
        if len(self._log) > 500:
            self._log = self._log[-500:]