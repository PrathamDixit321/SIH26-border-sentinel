"""
mock_pipeline_feed.py
Simulates the live Border Sentinel CV Pipeline sending alerts to Komal's FastAPI backend.
Demonstrates:
  1. Human intruder crossing boundary -> CRITICAL threat
  2. Vehicle intrusion -> HIGH threat
  3. Foliage moving in wind -> LOW threat (Suppressed environmental noise)
"""

import time
import requests
import random
from datetime import datetime

API_URL = "http://localhost:8000/api/alerts"

SCENARIOS = [
    {
        "threat_level": "CRITICAL",
        "label": "HUMAN",
        "category": "PEDESTRIAN",
        "confidence": 0.96,
        "camera_id": "CAM-01",
        "sector": "Sector 4 (North Ridge Fence)",
        "bbox": [340, 190, 68, 150],
        "zone": "Red Zone Alpha (Tripwire TW-01)",
        "snapshot_url": "/snapshots/sample_intruder_01.jpg",
        "reason": "Detected erect bipedal silhouette (aspect ratio 2.21, solidity 0.82) moving directionally at 1.4 m/s across Sector 4 perimeter line. Motion vector is continuous and directional (confidence 96.0%), ruling out wind-induced foliage oscillation.",
        "metrics": {
            "area": 10200.0, "solidity": 0.82, "fragments": 1, "aspect_ratio": 2.21, "displacement": 34.5, "frames_tracked": 18, "yolo_match": "person"
        },
        "xai_breakdown": {
            "shape_analysis": "Upright human morphology (solidity 0.82, AR 2.21)",
            "motion_profile": "Linear directional trajectory across 18 frames; zero cyclic wind oscillation signature",
            "frame_alignment": "ORB keypoint homography error 0.032px — camera jitter fully compensated",
            "zone_intrusion": "Breached Virtual Tripwire TW-01 at depth +4.2m inside high-security buffer",
            "environmental_verdict": "CONFIRMED INTRUSION (Suppression threshold bypassed)"
        },
        "environmental_noise_filtered": False
    },
    {
        "threat_level": "LOW",
        "label": "NATURAL",
        "category": "TREES",
        "confidence": 0.89,
        "camera_id": "CAM-02",
        "sector": "Sector 2 (Dense Foliage Valley)",
        "bbox": [210, 140, 90, 80],
        "zone": "Outer Perimeter Bushline",
        "snapshot_url": "/snapshots/sample_foliage_03.jpg",
        "reason": "Harmonic back-and-forth pixel oscillation detected matching local wind gust profile (18 km/h). Object lacks rigid bipedal structure (solidity 0.46, 5 fragmented blobs) and cohesive trajectory. Threat suppressed automatically.",
        "metrics": {
            "area": 7200.0, "solidity": 0.46, "fragments": 5, "aspect_ratio": 0.89, "displacement": 3.1, "frames_tracked": 35, "yolo_match": None
        },
        "xai_breakdown": {
            "shape_analysis": "Highly amorphous boundary with continuous edge fragmentation (5 fragments)",
            "motion_profile": "Sinusoidal oscillatory vector (period 1.2s), net displacement near zero (3.1px)",
            "frame_alignment": "Background alignment confirmed stationary anchor points",
            "zone_intrusion": "No restricted line breach",
            "environmental_verdict": "FALSE ALARM SUPPRESSED (Saved operator alert fatigue)"
        },
        "environmental_noise_filtered": True
    },
    {
        "threat_level": "HIGH",
        "label": "HUMAN",
        "category": "VEHICLE",
        "confidence": 0.92,
        "camera_id": "CAM-03",
        "sector": "Sector 7 (Riverine Outpost)",
        "bbox": [480, 240, 140, 95],
        "zone": "Perimeter Buffer Corridor Bravo",
        "snapshot_url": "/snapshots/sample_vehicle_02.jpg",
        "reason": "High-velocity non-organic vehicle profile identified traversing river embankment at 8.2 m/s with sustained thermal/pixel cluster density.",
        "metrics": {
            "area": 13300.0, "solidity": 0.89, "fragments": 1, "aspect_ratio": 1.47, "displacement": 84.0, "frames_tracked": 24, "yolo_match": "truck"
        },
        "xai_breakdown": {
            "shape_analysis": "Low-slung motorized chassis profile (Aspect ratio 1.47, high pixel rigidity)",
            "motion_profile": "High speed translational vector along unauthorized access track",
            "frame_alignment": "Homography stabilized; no optical parallax error detected",
            "zone_intrusion": "Corridor Bravo entry violation",
            "environmental_verdict": "CONFIRMED VEHICLE TARGET"
        },
        "environmental_noise_filtered": False
    },
    {
        "threat_level": "CRITICAL",
        "label": "HUMAN",
        "category": "PEDESTRIAN",
        "confidence": 0.94,
        "camera_id": "CAM-04",
        "sector": "Sector 5 (Desert Dune Watch)",
        "bbox": [160, 280, 110, 55],
        "zone": "Inner Security Fence Ground Line",
        "snapshot_url": "/snapshots/sample_crawler_04.jpg",
        "reason": "Low-profile prone human silhouette detected crawling along fence foundation with periodic pauses. Pixel change density indicates manual contact at fence sensor junction.",
        "metrics": {
            "area": 6050.0, "solidity": 0.76, "fragments": 1, "aspect_ratio": 0.50, "displacement": 22.4, "frames_tracked": 29, "yolo_match": "person"
        },
        "xai_breakdown": {
            "shape_analysis": "Prone horizontal human posture (Aspect ratio 0.50, limb articulation detected)",
            "motion_profile": "Intermittent directional crawl at 0.3 m/s towards primary barrier",
            "frame_alignment": "Ground baseline homography confirmed static ground level",
            "zone_intrusion": "Direct physical proximity breach to fence wire",
            "environmental_verdict": "IMMEDIATE THREAT DEPLOYMENT RECOMMENDED"
        },
        "environmental_noise_filtered": False
    }
]

def send_alert(scenario, count):
    alert_id = f"ALT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
    payload = dict(scenario)
    payload["alert_id"] = alert_id
    payload["timestamp"] = datetime.now().isoformat()
    payload["status"] = "UNACKNOWLEDGED" if payload["threat_level"] in ["CRITICAL", "HIGH"] else "ACKNOWLEDGED"

    print(f"\n[PIPELINE -> BACKEND] #{count} Sending {payload['threat_level']} Alert: {payload['category']} in {payload['sector']}")
    print(f"   Reason: {payload['reason']}")
    try:
        res = requests.post(API_URL, json=payload, timeout=2.0)
        if res.status_code == 200:
            print(f"   [SUCCESS] Backend accepted alert: {alert_id} (HTTP {res.status_code})")
        else:
            print(f"   [WARN] Backend returned status {res.status_code}: {res.text}")
    except Exception as err:
        print(f"   [ERROR] Could not connect to {API_URL}: {err}")

def main():
    print("=" * 70)
    print("Border Sentinel — Mock Pipeline Alert Streamer")
    print(f"Targeting FastAPI Backend: {API_URL}")
    print("=" * 70)

    count = 0
    while True:
        scenario = random.choice(SCENARIOS)
        count += 1
        send_alert(scenario, count)
        sleep_sec = random.randint(5, 10)
        print(f"Waiting {sleep_sec}s for next event (Press Ctrl+C to stop)...")
        try:
            time.sleep(sleep_sec)
        except KeyboardInterrupt:
            print("\nStopped.")
            break

if __name__ == "__main__":
    main()
