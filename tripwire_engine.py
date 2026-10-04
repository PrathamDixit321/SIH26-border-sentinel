"""
tripwire_engine.py
Feature 2: Virtual Tripwire & Geofenced Security Zone Engine for Border Sentinel AI.

Provides:
1. Calibrated Virtual Tripwire line definition (TW-01 North Ridge).
2. Target ground-contact point calculation & signed perimeter penetration distance.
3. Multi-zone spatial classification (Red Zone Alpha, Amber Buffer, Green Safe Zone).
4. Explainable XAI breakdown generation for border security personnel.
5. Tactical HUD rendering of the laser tripwire with dynamic breach states.
"""

from dataclasses import dataclass
import cv2
import numpy as np


@dataclass
class ZoneVerdict:
    zone_name: str
    threat_level: str
    is_breach: bool
    penetration_depth_m: float
    approach_margin_m: float
    xai_explanation: str


class LowLightEnhancer:
    """
    Conditionally enhances visibility in dark surveillance frames using
    adaptive gamma correction and CLAHE in LAB space.
    Employs Schmitt-trigger hysteresis to eliminate on/off flickering in transition zones.
    """
    def __init__(self, low_thresh: float = 50.0, high_thresh: float = 65.0, clip_limit: float = 2.2, gamma: float = 1.35):
        self.low_thresh = low_thresh
        self.high_thresh = high_thresh
        self.clip_limit = clip_limit
        self.gamma = gamma
        self.is_active = False
        self.clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
        inv_gamma = 1.0 / gamma
        self.gamma_lut = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype(np.uint8)

    def process(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray, bool, float]:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        mean_lum = float(np.mean(gray))

        if self.is_active:
            if mean_lum > self.high_thresh:
                self.is_active = False
        else:
            if mean_lum < self.low_thresh:
                self.is_active = True

        if not self.is_active:
            return frame_bgr, gray, False, mean_lum

        gamma_bgr = cv2.LUT(frame_bgr, self.gamma_lut)
        lab = cv2.cvtColor(gamma_bgr, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)
        enhanced_l = self.clahe.apply(l_channel)
        enhanced_lab = cv2.merge((enhanced_l, a_channel, b_channel))
        enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
        enhanced_gray = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2GRAY)

        return enhanced_bgr, enhanced_gray, True, mean_lum



class VirtualTripwire:
    """
    Evaluates target intrusions across a defined border virtual tripwire.
    Uses normalized coordinates (0.0 - 1.0) so it automatically scales
    across any video resolution (720p, 1080p, 4K).
    """

    def __init__(
        self,
        name: str = "TW-01",
        p1_norm: tuple[float, float] = (0.05, 0.62),
        p2_norm: tuple[float, float] = (0.95, 0.54),
        buffer_margin_px: float = 45.0,
        px_per_meter: float = 22.0,
    ):
        self.name = name
        self.p1_norm = p1_norm
        self.p2_norm = p2_norm
        self.buffer_margin_px = buffer_margin_px
        self.px_per_meter = px_per_meter

    def get_pixel_endpoints(self, width: int, height: int) -> tuple[tuple[int, int], tuple[int, int]]:
        x1 = int(self.p1_norm[0] * width)
        y1 = int(self.p1_norm[1] * height)
        x2 = int(self.p2_norm[0] * width)
        y2 = int(self.p2_norm[1] * height)
        return (x1, y1), (x2, y2)

    def evaluate_target(self, bbox: list[int] | tuple[int, int, int, int], frame_shape: tuple[int, int]) -> ZoneVerdict:
        """
        Calculates ground contact position and tests breach against the tripwire line.
        bbox: [x, y, w, h]
        frame_shape: (height, width)
        """
        h_frame, w_frame = frame_shape[:2]
        x, y, w, h = bbox
        # Ground contact foot point (center bottom of bounding box)
        foot_x = float(x + (w / 2.0))
        foot_y = float(y + h)

        (x1, y1), (x2, y2) = self.get_pixel_endpoints(w_frame, h_frame)
        dx = float(x2 - x1)
        dy = float(y2 - y1)
        length = np.hypot(dx, dy)
        if length == 0:
            length = 1.0

        # Signed distance from foot point to directed tripwire line
        # Positive = inside restricted zone (towards bottom of frame), Negative = outside perimeter
        signed_dist_px = ((foot_x - x1) * dy - (foot_y - y1) * dx) / length

        # Note: In standard top-left image coordinates, moving downward means larger Y.
        # For a line from left to right (dx > 0), if foot_y > line_y, (foot_x - x1)*dy - (foot_y - y1)*dx is negative.
        # We invert so that downward (interior border territory) is positive penetration.
        penetration_px = -signed_dist_px
        dist_m = float(round(penetration_px / self.px_per_meter, 2))

        if penetration_px > 0:
            # Inside Red Zone Alpha
            depth_m = max(0.5, dist_m)
            return ZoneVerdict(
                zone_name=f"Red Zone Alpha (Tripwire {self.name})",
                threat_level="CRITICAL",
                is_breach=True,
                penetration_depth_m=depth_m,
                approach_margin_m=0.0,
                xai_explanation=f"Breached Virtual Tripwire {self.name} at depth +{depth_m:.1f}m inside high-security buffer",
            )
        elif penetration_px >= -self.buffer_margin_px:
            # Within Perimeter Approach Buffer
            margin_m = max(0.2, abs(dist_m))
            return ZoneVerdict(
                zone_name=f"Amber Buffer Zone (Perimeter Approach {self.name})",
                threat_level="HIGH",
                is_breach=False,
                penetration_depth_m=0.0,
                approach_margin_m=margin_m,
                xai_explanation=f"Target approaching Virtual Tripwire {self.name} within {margin_m:.1f}m perimeter warning margin",
            )
        else:
            # Outside buffer in Green Zone
            margin_m = abs(dist_m)
            return ZoneVerdict(
                zone_name="Green Buffer Zone (External Boundary)",
                threat_level="LOW",
                is_breach=False,
                penetration_depth_m=0.0,
                approach_margin_m=margin_m,
                xai_explanation=f"Motion localized {margin_m:.1f}m outside restricted perimeter boundary",
            )

    def draw_hud_tripwire(
        self,
        frame: np.ndarray,
        is_breached: bool = False,
        label: str | None = None,
    ) -> None:
        """
        Renders tactical tripwire laser and security zone indicator onto OpenCV frame.
        """
        h, w = frame.shape[:2]
        (x1, y1), (x2, y2) = self.get_pixel_endpoints(w, h)

        line_color = (0, 0, 255) if is_breached else (0, 215, 255)
        laser_glow = (50, 50, 255) if is_breached else (0, 140, 255)

        # Glow line
        cv2.line(frame, (x1, y1), (x2, y2), laser_glow, 4, cv2.LINE_AA)
        # Laser core
        cv2.line(frame, (x1, y1), (x2, y2), line_color, 2, cv2.LINE_AA)

        # End nodes
        for pt in [(x1, y1), (x2, y2)]:
            cv2.circle(frame, pt, 6, laser_glow, -1, cv2.LINE_AA)
            cv2.circle(frame, pt, 3, (255, 255, 255), -1, cv2.LINE_AA)

        # Badge text
        badge_text = label or (f"TRIPWIRE {self.name}: BREACH ACTIVE!" if is_breached else f"TRIPWIRE {self.name}: RESTRICTED ZONE")
        mid_x = int((x1 + x2) / 2) - 120
        mid_y = int((y1 + y2) / 2) - 10

        cv2.putText(
            frame,
            badge_text,
            (mid_x, mid_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (0, 0, 255) if is_breached else (0, 255, 255),
            1,
            cv2.LINE_AA,
        )
