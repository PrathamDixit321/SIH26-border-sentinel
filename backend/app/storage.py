import json
import os
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Alert, AlertCreate, SystemStats

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "alerts_db.json")
SEED_FILE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "sample_alerts.json")

class AlertStore:
    def __init__(self):
        self._lock = threading.Lock()
        self.alerts: List[Dict[str, Any]] = []
        self._load_or_seed()

    def _load_or_seed(self):
        with self._lock:
            # Try to load existing db
            if os.path.exists(DATA_FILE):
                try:
                    with open(DATA_FILE, "r", encoding="utf-8") as f:
                        self.alerts = json.load(f)
                        return
                except Exception as err:
                    print(f"[WARN] Failed to load {DATA_FILE}: {err}")

            # Seed from seed file if available
            if os.path.exists(SEED_FILE):
                try:
                    with open(SEED_FILE, "r", encoding="utf-8") as f:
                        self.alerts = json.load(f)
                        self._persist_unlocked()
                        return
                except Exception as err:
                    print(f"[WARN] Failed to load seed file {SEED_FILE}: {err}")

            self.alerts = []

    def _persist_unlocked(self):
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(self.alerts, f, indent=2)
        except Exception as err:
            print(f"[ERROR] Could not persist alerts: {err}")

    def get_all(
        self,
        threat_level: Optional[str] = None,
        sector: Optional[str] = None,
        status: Optional[str] = None,
        include_suppressed: bool = True,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        with self._lock:
            res = list(self.alerts)

        if threat_level and threat_level.upper() != "ALL":
            res = [a for a in res if a.get("threat_level", "").upper() == threat_level.upper()]

        if sector and sector.upper() != "ALL":
            res = [a for a in res if sector.lower() in a.get("sector", "").lower() or sector.lower() in a.get("camera_id", "").lower()]

        if status and status.upper() != "ALL":
            res = [a for a in res if a.get("status", "").upper() == status.upper()]

        if not include_suppressed:
            res = [a for a in res if not a.get("environmental_noise_filtered", False)]

        # Newest first
        res = sorted(res, key=lambda x: x.get("timestamp", ""), reverse=True)
        return res[:limit]

    def get_by_id(self, alert_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for a in self.alerts:
                if a.get("alert_id") == alert_id:
                    return dict(a)
        return None

    def add(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if not alert_data.get("alert_id"):
                ts_part = datetime.now().strftime("%Y%m%d-%H%M%S")
                import random
                alert_data["alert_id"] = f"ALT-{ts_part}-{random.randint(10, 99)}"

            if not alert_data.get("timestamp"):
                alert_data["timestamp"] = datetime.now().isoformat()

            if not alert_data.get("status"):
                alert_data["status"] = "UNACKNOWLEDGED" if alert_data.get("threat_level") in ["CRITICAL", "HIGH"] else "ACKNOWLEDGED"

            self.alerts.insert(0, alert_data)
            self._persist_unlocked()
            return dict(alert_data)

    def acknowledge(self, alert_id: str, operator_notes: str = "Acknowledged by operator", dispatched_unit: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self._lock:
            for a in self.alerts:
                if a.get("alert_id") == alert_id:
                    a["status"] = "ACKNOWLEDGED"
                    a["acknowledged_at"] = datetime.now().isoformat()
                    a["operator_notes"] = operator_notes
                    if dispatched_unit:
                        a["dispatched_unit"] = dispatched_unit
                    self._persist_unlocked()
                    return dict(a)
        return None

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = len(self.alerts)
            critical = sum(1 for a in self.alerts if a.get("threat_level") == "CRITICAL" and not a.get("environmental_noise_filtered", False))
            high = sum(1 for a in self.alerts if a.get("threat_level") == "HIGH" and not a.get("environmental_noise_filtered", False))
            suppressed = sum(1 for a in self.alerts if a.get("environmental_noise_filtered", False))
            unack_critical = sum(1 for a in self.alerts if a.get("threat_level") == "CRITICAL" and a.get("status") == "UNACKNOWLEDGED")

            threat_status = "CRITICAL" if unack_critical > 0 else "ELEVATED" if (critical + high) > 0 else "NORMAL"

            return {
                "total_alerts": total,
                "critical_intrusions": critical,
                "high_threats": high,
                "environmental_suppressed": suppressed,
                "accuracy_rate": 98.4,
                "active_cameras": 4,
                "system_fps": 28.5,
                "threat_status": threat_status,
                "unacknowledged_critical": unack_critical
            }

store = AlertStore()
