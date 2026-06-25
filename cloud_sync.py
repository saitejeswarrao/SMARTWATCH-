"""
cloud_sync.py — Continuous Cloud Monitoring & Sync
Module 4: Syncs encrypted health data to Firebase / MySQL for long-term
          trend analysis and doctor review.

Architecture:
  • LocalBuffer  — ring buffer for offline resilience (stores readings when offline)
  • CloudSync    — main sync manager; batches uploads, retries on failure
  • FirebaseAdapter (stub) — replace body with firebase_admin SDK calls
  • MySQLAdapter (stub)    — replace body with mysql-connector-python calls

In production, pick one backend:

  Firebase (real-time, mobile-first):
    pip install firebase-admin
    import firebase_admin
    from firebase_admin import credentials, firestore
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
    db = firestore.client()

  MySQL (structured, hospital-grade):
    pip install mysql-connector-python
    import mysql.connector
    conn = mysql.connector.connect(
        host="your-db-host", user="...", password="...", database="healthdb"
    )
"""

import json
import time
import datetime
import threading
from collections import deque
from typing import Optional, List, Dict, Any


# ── Local offline buffer ──────────────────────────────────────────────────────
class LocalBuffer:
    """
    Stores readings locally when the network is unavailable.
    Uses a fixed-size deque; oldest readings are dropped if buffer fills.
    In production: persist to SQLite for power-loss durability.
    """

    def __init__(self, maxlen: int = 1000):
        self._queue: deque = deque(maxlen=maxlen)
        self._lock  = threading.Lock()

    def enqueue(self, payload: dict):
        with self._lock:
            self._queue.append(payload)

    def drain(self, batch_size: int = 50) -> List[dict]:
        """Remove and return up to batch_size items from the front."""
        with self._lock:
            batch = []
            for _ in range(min(batch_size, len(self._queue))):
                batch.append(self._queue.popleft())
            return batch

    def __len__(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0


# ── Firebase adapter (stub) ───────────────────────────────────────────────────
class FirebaseAdapter:
    """
    Wraps firebase_admin Firestore writes.
    Replace _write() with real Firestore calls.

    Collection structure:
      users/{user_id}/readings/{reading_id}
      users/{user_id}/risk_scores/{score_id}
      users/{user_id}/alerts/{alert_id}
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._online = True   # simulated connectivity

    def write_reading(self, payload: dict) -> bool:
        """Write an encrypted reading to Firestore."""
        return self._write(f"users/{self.user_id}/readings", payload)

    def write_risk(self, risks: dict) -> bool:
        """Write a risk score record to Firestore."""
        return self._write(f"users/{self.user_id}/risk_scores", risks)

    def write_alert(self, alert: dict) -> bool:
        """Write an alert record to Firestore."""
        return self._write(f"users/{self.user_id}/alerts", alert)

    def _write(self, collection: str, data: dict) -> bool:
        """
        STUB — replace with:
            doc_ref = db.collection(collection).document()
            doc_ref.set(data)
            return True
        """
        if not self._online:
            return False
        # Simulate ~95% success rate (network flakiness)
        import random
        success = random.random() > 0.05
        if success:
            ts = datetime.datetime.utcnow().strftime("%H:%M:%S")
            print(f"  [Firebase ✓] {collection} — {ts}")
        else:
            print(f"  [Firebase ✗] Upload failed — queued for retry")
        return success


# ── MySQL adapter (stub) ──────────────────────────────────────────────────────
class MySQLAdapter:
    """
    Wraps mysql-connector-python writes for hospital-grade storage.
    Replace _execute() with real connection pool calls.

    Schema reference: see database schema panel in the dashboard.
    """

    def __init__(self, host: str = "localhost", database: str = "healthdb",
                 user: str = "health_user", password: str = ""):
        self.host     = host
        self.database = database
        # In production:
        #   self.pool = mysql.connector.pooling.MySQLConnectionPool(
        #       pool_name="health_pool", pool_size=5,
        #       host=host, database=database, user=user, password=password
        #   )
        self._connected = False   # stub defaults to disconnected

    def insert_reading(self, reading_id: str, user_id: str,
                       reading: dict, encrypted: bool) -> bool:
        sql = """
            INSERT INTO readings
              (reading_id, user_id, timestamp, heart_rate, spo2, hrv_ms,
               temp_c, accel_g, encrypted)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (
            reading_id, user_id,
            datetime.datetime.utcfromtimestamp(reading["timestamp"]),
            reading["heart_rate"], reading["spo2"], reading["hrv_ms"],
            reading["temp_c"], reading["accel_g"], encrypted,
        )
        return self._execute(sql, params)

    def _execute(self, sql: str, params: tuple) -> bool:
        """
        STUB — replace with:
            conn = self.pool.get_connection()
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            cursor.close()
            conn.close()
            return True
        """
        if not self._connected:
            return False   # would retry via LocalBuffer
        return True


# ── Main CloudSync manager ────────────────────────────────────────────────────
class CloudSync:
    """
    Orchestrates all cloud uploads with:
      • Offline buffering — reads saved locally if network unavailable
      • Batch retry       — buffered reads flushed on reconnect
      • Integrity signing — HMAC fingerprint on each payload
      • Async flush       — background thread drains buffer every 30s
    """

    def __init__(self, user_id: str,
                 backend: str = "firebase",
                 secret_key: str = "change-me-in-production"):
        self.user_id    = user_id
        self._secret    = secret_key
        self._buffer    = LocalBuffer(maxlen=500)
        self._upload_count = 0
        self._fail_count   = 0

        # Backend selection
        if backend == "firebase":
            self._adapter = FirebaseAdapter(user_id)
        else:
            self._adapter = MySQLAdapter()   # type: ignore

        # Background flush thread
        self._flush_thread = threading.Thread(
            target=self._background_flush, daemon=True
        )
        self._flush_thread.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def push(self, encrypted_reading: bytes, metadata: Optional[dict] = None):
        """
        Queue an encrypted reading for cloud upload.
        If online: uploads immediately.
        If offline: stores in LocalBuffer for retry.
        """
        payload = {
            "user_id":   self.user_id,
            "data":      encrypted_reading.hex() if isinstance(encrypted_reading, bytes)
                         else str(encrypted_reading),
            "timestamp": time.time(),
            "metadata":  metadata or {},
        }
        # Attach HMAC integrity fingerprint
        payload["hmac"] = self._sign(payload)

        success = self._upload(payload)
        if not success:
            self._buffer.enqueue(payload)
            self._fail_count += 1
        else:
            self._upload_count += 1

    def push_risk(self, risks: dict):
        """Upload a risk score record (plaintext — scores, not raw vitals)."""
        record = {
            "user_id":   self.user_id,
            "timestamp": time.time(),
            "risks":     risks,
        }
        self._adapter.write_risk(record)

    def push_alert(self, alert: dict):
        """Upload an alert record for doctor dashboard."""
        self._adapter.write_alert(alert)

    def stats(self) -> dict:
        return {
            "uploaded":    self._upload_count,
            "failed":      self._fail_count,
            "buffered":    len(self._buffer),
            "success_rate":round(
                self._upload_count / max(1, self._upload_count + self._fail_count) * 100,
                1
            ),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _upload(self, payload: dict) -> bool:
        return self._adapter.write_reading(payload)

    def _sign(self, payload: dict) -> str:
        """HMAC-SHA256 integrity fingerprint (excludes the hmac field itself)."""
        import hashlib, hmac as hmac_lib
        data = {k: v for k, v in payload.items() if k != "hmac"}
        raw  = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        return hmac_lib.new(self._secret.encode(), raw, hashlib.sha256).hexdigest()

    def _background_flush(self):
        """Periodically retry buffered readings (runs in background thread)."""
        while True:
            time.sleep(30)
            if not self._buffer.is_empty():
                batch = self._buffer.drain(50)
                retried = 0
                for payload in batch:
                    if self._upload(payload):
                        self._upload_count += 1
                        retried += 1
                    else:
                        self._buffer.enqueue(payload)   # re-queue failed
                if retried:
                    print(f"  [CloudSync] Flushed {retried}/{len(batch)} buffered readings")