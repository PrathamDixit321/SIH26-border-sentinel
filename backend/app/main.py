import os
import json
import base64
import random
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse

from .models import Alert, AlertCreate, AlertAcknowledge, SystemStats
from .storage import store
from .streamer import mjpeg_stream

app = FastAPI(
    title="Border Sentinel AI — Surveillance & Alert Ingestion API",
    description="Backend API for Ministry of Home Affairs Video Analytics Platform (SIH26187)",
    version="1.0.0"
)

# CORS configuration for React Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure snapshot directory exists and mount as static
SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=SNAPSHOT_DIR), name="snapshots")

# WebSocket Connection Manager for live alert dispatch
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WS] Client connected. Active clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"[WS] Client disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as err:
                print(f"[WS WARN] Failed to send message to client: {err}")
                self.disconnect(connection)

manager = ConnectionManager()

@app.get("/api/health")
def health_check():
    return {
        "status": "OPERATIONAL",
        "service": "Border Sentinel AI Backend",
        "time": datetime.now().isoformat(),
        "active_clients": len(manager.active_connections)
    }

@app.get("/api/stats")
def get_stats():
    """Returns real-time analytics for threat prevention and false-alarm rejection."""
    return store.get_stats()

@app.get("/api/alerts")
def get_alerts(
    threat_level: Optional[str] = Query(None, description="Filter by threat level: CRITICAL, HIGH, MEDIUM, LOW, or ALL"),
    sector: Optional[str] = Query(None, description="Filter by sector name or camera ID"),
    status: Optional[str] = Query(None, description="Filter by status: UNACKNOWLEDGED, ACKNOWLEDGED, or ALL"),
    include_suppressed: bool = Query(True, description="Include filtered environmental noise events"),
    limit: int = Query(50, ge=1, le=200)
):
    """Retrieves all surveillance alerts matching filter criteria."""
    return store.get_all(
        threat_level=threat_level,
        sector=sector,
        status=status,
        include_suppressed=include_suppressed,
        limit=limit
    )

@app.get("/api/alerts/{alert_id}")
def get_alert_detail(alert_id: str):
    """Retrieves full explainability details and metrics for a specific alert."""
    alert = store.get_by_id(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    return alert

@app.post("/api/alerts")
async def ingest_alert(payload: AlertCreate):
    """
    Ingestion endpoint for CV Pipeline (pipeline.py).
    Accepts alerts, validates against schema, stores them, and broadcasts via WebSockets.
    """
    alert_dict = payload.model_dump()

    # Handle base64 snapshot if provided
    if alert_dict.get("snapshot_base64"):
        try:
            img_data = base64.b64decode(alert_dict["snapshot_base64"])
            filename = f"snap_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random.randint(100, 999)}.jpg"
            filepath = os.path.join(SNAPSHOT_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(img_data)
            alert_dict["snapshot_url"] = f"/snapshots/{filename}"
            del alert_dict["snapshot_base64"]
        except Exception as err:
            print(f"[WARN] Failed to decode base64 snapshot: {err}")

    # Fallback snapshot if none provided
    if not alert_dict.get("snapshot_url"):
        if alert_dict.get("environmental_noise_filtered"):
            alert_dict["snapshot_url"] = "/snapshots/sample_foliage_03.jpg"
        elif alert_dict.get("category") == "VEHICLE":
            alert_dict["snapshot_url"] = "/snapshots/sample_vehicle_02.jpg"
        else:
            alert_dict["snapshot_url"] = "/snapshots/sample_intruder_01.jpg"

    saved_alert = store.add(alert_dict)

    # Real-time WebSocket broadcast
    await manager.broadcast({
        "type": "NEW_ALERT",
        "data": saved_alert
    })

    return {
        "status": "ACCEPTED",
        "alert_id": saved_alert["alert_id"],
        "stored_at": saved_alert["timestamp"]
    }

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, body: AlertAcknowledge):
    """Operator acknowledges an alert and dispatches response."""
    updated = store.acknowledge(
        alert_id=alert_id,
        operator_notes=body.operator_notes,
        dispatched_unit=body.dispatched_unit
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")

    await manager.broadcast({
        "type": "ALERT_ACKNOWLEDGED",
        "data": updated
    })
    return updated

@app.get("/api/stream")
def get_live_stream(camera_id: str = "CAM-01"):
    """
    Real-time MJPEG live camera stream with tactical AI overlays.
    Can be directly rendered in browser with <img src="/api/stream?camera_id=CAM-01" />.
    """
    return StreamingResponse(
        mjpeg_stream(camera_id=camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.post("/api/simulate-threat")
async def simulate_threat():
    """Quick demo trigger: simulates a critical human intrusion crossing the perimeter."""
    intruder_types = [
        ("Human Intruder (Upright)", "Sector 4 (North Ridge Fence)", "CAM-01", "Detected erect bipedal silhouette moving at 1.4 m/s across Sector 4 perimeter line. Motion vector is continuous and directional, ruling out wind-induced foliage oscillation.", "/snapshots/sample_intruder_01.jpg", [340, 190, 68, 150]),
        ("Crawling Infiltrator", "Sector 5 (Desert Dune Watch)", "CAM-04", "Low-profile horizontal human silhouette detected crawling along fence foundation with periodic pauses. Pixel change density indicates manual tampering at fence sensor junction.", "/snapshots/sample_crawler_04.jpg", [160, 280, 110, 55]),
        ("Unauthorized ATV / Vehicle", "Sector 7 (Riverine Outpost)", "CAM-03", "High-velocity non-organic vehicle profile identified traversing river embankment at 8.2 m/s with sustained pixel cluster density.", "/snapshots/sample_vehicle_02.jpg", [480, 240, 140, 95])
    ]

    title, sector, cam, reason, snap, bbox = random.choice(intruder_types)
    threat_level = "CRITICAL" if "Human" in title or "Crawling" in title else "HIGH"
    category = "PEDESTRIAN" if "Human" in title or "Crawling" in title else "VEHICLE"

    alert_data = {
        "camera_id": cam,
        "sector": sector,
        "threat_level": threat_level,
        "label": "HUMAN",
        "category": category,
        "confidence": round(random.uniform(0.93, 0.98), 2),
        "bbox": bbox,
        "zone": "Restricted High-Security Zone Alpha",
        "snapshot_url": snap,
        "reason": reason,
        "metrics": {
            "area": round(random.uniform(7000, 12000), 1),
            "solidity": round(random.uniform(0.78, 0.88), 2),
            "fragments": 1,
            "aspect_ratio": 2.15,
            "displacement": round(random.uniform(25.0, 45.0), 1),
            "frames_tracked": random.randint(15, 30),
            "yolo_match": "person" if category == "PEDESTRIAN" else "truck"
        },
        "xai_breakdown": {
            "shape_analysis": f"Consistent with {title} profile (solidity > 0.75)",
            "motion_profile": "Linear directional trajectory; zero cyclic wind oscillation signature",
            "frame_alignment": "ORB keypoint homography error 0.03px — camera jitter compensated",
            "zone_intrusion": "Immediate physical breach of restricted border wire",
            "environmental_verdict": "CONFIRMED INTRUSION (Suppression threshold bypassed)"
        },
        "environmental_noise_filtered": False
    }

    saved = store.add(alert_data)
    await manager.broadcast({"type": "NEW_ALERT", "data": saved})
    return saved

@app.post("/api/simulate-environmental")
async def simulate_environmental():
    """Quick demo trigger: simulates a filtered environmental false alarm (e.g. wind swaying foliage)."""
    alert_data = {
        "camera_id": "CAM-02",
        "sector": "Sector 2 (Dense Foliage Valley)",
        "threat_level": "LOW",
        "label": "NATURAL",
        "category": "TREES",
        "confidence": round(random.uniform(0.85, 0.92), 2),
        "bbox": [210, 140, 90, 80],
        "zone": "Outer Perimeter Bushline",
        "snapshot_url": "/snapshots/sample_foliage_03.jpg",
        "reason": "Harmonic back-and-forth pixel oscillation detected matching local wind gust profile (18 km/h). Object lacks rigid bipedal structure (solidity 0.46, 5 fragmented blobs) and cohesive trajectory. Threat suppressed automatically.",
        "metrics": {
            "area": 7200.0,
            "solidity": 0.46,
            "fragments": 5,
            "aspect_ratio": 0.89,
            "displacement": 3.1,
            "frames_tracked": 35,
            "yolo_match": None
        },
        "xai_breakdown": {
            "shape_analysis": "Highly amorphous boundary with continuous edge fragmentation (5 fragments)",
            "motion_profile": "Sinusoidal oscillatory vector (period 1.2s), net displacement near zero (3.1px)",
            "frame_alignment": "Stationary background anchor points confirmed",
            "zone_intrusion": "No restricted line breach",
            "environmental_verdict": "FALSE ALARM SUPPRESSED (Saved operator alert fatigue)"
        },
        "environmental_noise_filtered": True
    }

    saved = store.add(alert_data)
    await manager.broadcast({"type": "NEW_ALERT", "data": saved})
    return saved

@app.websocket("/ws/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Real-time duplex WebSocket for live alert streaming to React dashboard."""
    await manager.connect(websocket)
    try:
        # Send initial welcome and current telemetry
        await websocket.send_json({
            "type": "CONNECTION_READY",
            "stats": store.get_stats(),
            "time": datetime.now().isoformat()
        })
        while True:
            data = await websocket.receive_text()
            # Client can send pings or heartbeats
            try:
                payload = json.loads(data)
                if payload.get("type") == "PING":
                    await websocket.send_json({"type": "PONG"})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as err:
        print(f"[WS ERROR] {err}")
        manager.disconnect(websocket)
