from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime

class AlertMetrics(BaseModel):
    area: Optional[float] = 0.0
    solidity: Optional[float] = 0.0
    fragments: Optional[int] = 0
    aspect_ratio: Optional[float] = 0.0
    displacement: Optional[float] = 0.0
    frames_tracked: Optional[int] = 0
    yolo_match: Optional[str] = None

class XAIBreakdown(BaseModel):
    shape_analysis: Optional[str] = "Shape analyzed"
    motion_profile: Optional[str] = "Motion profile analyzed"
    frame_alignment: Optional[str] = "ORB homography alignment applied"
    zone_intrusion: Optional[str] = "Perimeter perimeter assessment"
    environmental_verdict: Optional[str] = "Evaluated against wind/foliage thresholds"

class AlertBase(BaseModel):
    camera_id: str = "CAM-01"
    sector: str = "Sector 4 (North Ridge Fence)"
    threat_level: str = "CRITICAL"  # CRITICAL, HIGH, MEDIUM, LOW
    label: str = "HUMAN"           # HUMAN, NATURAL, STATIC
    category: str = "PEDESTRIAN"    # PEDESTRIAN, VEHICLE, TREES, PARKED_CAR
    confidence: float = 0.95
    bbox: List[int] = Field(default_factory=lambda: [100, 100, 50, 100])
    zone: Optional[str] = "Red Zone Alpha"
    snapshot_url: Optional[str] = "/snapshots/sample_intruder_01.jpg"
    snapshot_base64: Optional[str] = None
    reason: str = "Motion detected crossing border line"
    metrics: Optional[AlertMetrics] = None
    xai_breakdown: Optional[XAIBreakdown] = None
    environmental_noise_filtered: bool = False

class AlertCreate(AlertBase):
    alert_id: Optional[str] = None
    timestamp: Optional[str] = None

class Alert(AlertBase):
    alert_id: str
    timestamp: str
    status: str = "UNACKNOWLEDGED"  # UNACKNOWLEDGED, ACKNOWLEDGED
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    operator_notes: Optional[str] = None

class AlertAcknowledge(BaseModel):
    operator_notes: Optional[str] = "Reviewed by operator"
    dispatched_unit: Optional[str] = None

class SystemStats(BaseModel):
    total_alerts: int
    critical_intrusions: int
    high_threats: int
    environmental_suppressed: int
    accuracy_rate: float
    active_cameras: int
    system_fps: float
    threat_status: str  # NORMAL, ELEVATED, CRITICAL
