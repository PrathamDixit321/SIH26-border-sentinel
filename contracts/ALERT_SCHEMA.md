# SIH26187: Border Sentinel — Alert Integration Contract (Day 1)

This document defines the exact alert payload and API endpoint that the Computer Vision pipeline (`pipeline.py`) uses to send alerts to the FastAPI backend and React C2 Dashboard.

---

## 1. REST Endpoint for CV Pipeline

- **URL:** `http://localhost:8000/api/alerts`
- **Method:** `POST`
- **Headers:** `Content-Type: application/json`

---

## 2. JSON Payload Specification

```json
{
  "alert_id": "ALT-2026-9081",
  "timestamp": "2026-09-08T22:45:12+05:30",
  "camera_id": "CAM-01",
  "sector": "Sector 4 (North Ridge Fence)",
  "threat_level": "CRITICAL",
  "label": "HUMAN",
  "category": "PEDESTRIAN",
  "confidence": 0.96,
  "bbox": [340, 190, 68, 150],
  "zone": "Red Zone Alpha (Tripwire TW-01)",
  "snapshot_url": "/snapshots/sample_intruder_01.jpg",
  "status": "UNACKNOWLEDGED",
  "reason": "Detected erect bipedal silhouette moving at 1.4 m/s across Sector 4 perimeter line. Motion vector is continuous and directional, ruling out wind-induced foliage oscillation.",
  "metrics": {
    "area": 10200.0,
    "solidity": 0.82,
    "fragments": 1,
    "aspect_ratio": 2.21,
    "displacement": 34.5,
    "frames_tracked": 18,
    "yolo_match": "person"
  },
  "xai_breakdown": {
    "shape_analysis": "Consistent with upright human morphology (solidity 0.82, AR 2.21)",
    "motion_profile": "Linear directional trajectory across 18 consecutive frames; zero cyclic wind oscillation signature",
    "frame_alignment": "ORB keypoint homography error 0.032px — camera jitter fully compensated",
    "zone_intrusion": "Breached Virtual Tripwire TW-01 at depth +4.2m inside high-security buffer",
    "environmental_verdict": "CONFIRMED INTRUSION (Suppression threshold bypassed)"
  },
  "environmental_noise_filtered": false
}
```

### Field Descriptions:

| Field | Type | Description |
| :--- | :--- | :--- |
| `alert_id` | `string` | Unique identifier (e.g. `ALT-<YYYY>-<ID>`) |
| `timestamp` | `string` | ISO 8601 formatted timestamp |
| `camera_id` | `string` | Camera identifier (`CAM-01`, `CAM-02`, etc.) |
| `sector` | `string` | Border post / geographic zone |
| `threat_level` | `string` | `CRITICAL`, `HIGH`, `MEDIUM`, or `LOW` |
| `label` | `string` | Matches pipeline: `HUMAN`, `NATURAL`, or `STATIC` |
| `category` | `string` | Matches pipeline: `PEDESTRIAN`, `VEHICLE`, `TREES`, `PARKED_CAR` |
| `confidence` | `float` | Detection confidence between `0.0` and `1.0` |
| `bbox` | `[x, y, w, h]` | Bounding box coordinates |
| `reason` | `string` | **Key Explainability Field:** Plain-language explanation displayed on the dashboard |
| `metrics` | `object` | Telemetry from pipeline (area, solidity, displacement, etc.) |
| `snapshot_base64` | `string (opt)` | Optional base64-encoded JPEG image if sending live snapshot |
| `environmental_noise_filtered` | `boolean` | `true` if filtered as environmental noise (for false-alarm analytics) |

---

## 3. How to Send from `pipeline.py` (3 Lines of Code)

```python
import requests

payload = {
    "alert_id": f"ALT-{frame_idx:04d}",
    "camera_id": "CAM-01",
    "sector": "Sector 4 (North Ridge)",
    "threat_level": "CRITICAL" if category == "PEDESTRIAN" else "HIGH",
    "label": label,
    "category": category,
    "confidence": conf,
    "bbox": [int(x), int(y), int(w), int(h)],
    "reason": reason,
    "metrics": metrics,
    "environmental_noise_filtered": (label == "NATURAL")
}

# Send to Komal's backend
try:
    requests.post("http://localhost:8000/api/alerts", json=payload, timeout=0.2)
except Exception:
    pass
```

---

## 4. WebSocket Feed for Real-Time Streaming

The backend broadcasts new alerts instantly over WebSocket:
- **WebSocket URL:** `ws://localhost:8000/ws/alerts`
- Emits newly created alerts to connected clients within <10ms.
