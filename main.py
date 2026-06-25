"""
main.py — AI Smartwatch Health Monitoring System
Entry point: wires all 6 modules and runs the continuous monitoring loop.

Usage:
    pip install cryptography numpy scikit-learn
    python main.py
"""

import time
import json
from health_profile import HealthProfile
from sensor_data import SensorManager
from risk_engine import RiskEngine
from alert_system import AlertSystem
from coaching import CoachingEngine
from security import DataVault
from cloud_sync import CloudSync


def main():
    print("=" * 60)
    print("  AI Smartwatch Health Monitoring System — Starting up")
    print("=" * 60)

    # ── 1. Initialise user profile ──────────────────────────────
    profile = HealthProfile(
        user_id="user_001",
        name="Arjun Sharma",
        age=34,
        weight_kg=72.0,
        height_cm=175,
        conditions=[],          # e.g. ["hypertension", "diabetes"]
        emergency_contacts=[
            {"name": "Dr. Meera", "phone": "+91-9000000001", "role": "doctor"},
            {"name": "Priya Sharma", "phone": "+91-9000000002", "role": "family"},
        ],
    )

    # ── 2. Initialise all modules ───────────────────────────────
    sensors = SensorManager()
    risk    = RiskEngine(profile)
    alerts  = AlertSystem(profile)
    coach   = CoachingEngine()
    vault   = DataVault()
    cloud   = CloudSync(user_id=profile.user_id)

    print(f"\n  User         : {profile.name}, age {profile.age}")
    print(f"  Risk multiplier: {profile.risk_multiplier}x")
    print(f"  HR thresholds  : {profile.hr_threshold()}")
    print(f"  SpO2 minimum   : {profile.spo2_threshold()}%")
    print("\n  Monitoring started — press Ctrl+C to stop.\n")
    print("-" * 60)

    cycle = 0
    try:
        while True:
            cycle += 1
            print(f"\n[Cycle {cycle}]")

            # Step 1 — read sensors
            reading = sensors.read()
            print(f"  Vitals  : HR={reading['heart_rate']} bpm | "
                  f"SpO2={reading['spo2']}% | HRV={reading['hrv_ms']} ms | "
                  f"Temp={reading['temp_c']}°C | Stress={reading['stress']}/100")

            # Step 2 — encrypt and sync to cloud
            encrypted = vault.encrypt(reading)
            cloud.push(encrypted, metadata={"cycle": cycle})

            # Step 3 — AI risk scoring
            risks = risk.score(reading)
            print(f"  Risks   : Cardiac={risks['cardiac']} | SpO2={risks['spo2']} | "
                  f"Stress={risks['stress']} | Fall={risks['fall']} | "
                  f"Overall={risks['overall']}")

            # Step 4 — alert evaluation
            triggered = alerts.evaluate(risks, reading)
            if triggered:
                for a in triggered:
                    print(f"⚠ ALERT [{a.level.upper()}] — {a.dimension} risk={a.score}")

            # Step 5 — coaching update
            coach.update(reading, risks)

            # Step 6 — weekly summary every 10 cycles (demo)
            if cycle % 10 == 0:
                summary = coach.weekly_summary()
                print(f"\n  ── Weekly Summary ──────────────────")
                print(f"  Avg HR: {summary.get('avg_hr')} bpm")
                print(f"  Avg Stress: {summary.get('avg_stress')}/100")
                print(f"  Sleep score: {summary.get('sleep_score')}/100")
                print(f"  Top risk: {summary.get('top_risk')}")
                print(f"  Tip: {summary.get('tip')}")
                print(f"  ────────────────────────────────────")

            time.sleep(2)   # 2s demo cadence (use 15s in production)

    except KeyboardInterrupt:
        print("\n\n  Monitoring stopped.")
        summary = coach.weekly_summary()
        print("\n  ── Final Session Summary ───────────────")
        for k, v in summary.items():
            print(f"    {k}: {v}")
        print("=" * 60)


if __name__ == "__main__":
    main()