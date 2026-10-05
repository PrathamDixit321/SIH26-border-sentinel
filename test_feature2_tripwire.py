"""
test_feature2_tripwire.py
Demonstration and validation of Feature 2 (Virtual Tripwire & Geofenced Security Zone Engine).
Tests:
1. Geometric line intersection & penetration depth:
   - Validates that a target crossing below TW-01 is identified as a CRITICAL breach into Red Zone Alpha.
   - Validates that an approaching target within the 45px buffer is flagged as HIGH Amber Buffer Warning.
   - Validates that an external motion above the perimeter is classified as LOW Green Buffer Zone.
2. Resolution invariance test:
   - Validates that normalized coordinates scale perfectly across 720p, 1080p, and 4K surveillance streams.
3. Visual HUD test:
   - Generates a synthetic surveillance frame with the laser tripwire and saves an artifact to outputs/test_tripwire_hud.jpg.
"""

import os
import cv2
import numpy as np
from tripwire_engine import VirtualTripwire, ZoneVerdict


def test_tripwire_spatial_classification():
    print("=" * 70)
    print("TEST 1: VIRTUAL TRIPWIRE TW-01 SPATIAL BREACH & BUFFER EVALUATION")
    print("=" * 70)

    # Frame size 1280x720. Tripwire runs approximately across y=420.
    tripwire = VirtualTripwire(
        name="TW-01",
        p1_norm=(0.0, 0.60),  # y = 432
        p2_norm=(1.0, 0.60),  # y = 432
        buffer_margin_px=50.0,
        px_per_meter=20.0,
    )
    frame_shape = (720, 1280)

    # Case A: Intruder foot at y = 500 (inside restricted territory below line)
    intruder_bbox = [600, 380, 60, 120]  # foot_y = 380 + 120 = 500 (+68px penetration)
    verdict_a = tripwire.evaluate_target(intruder_bbox, frame_shape)
    print(f"Case A (Intruder at foot_y=500):")
    print(f"  -> Zone: {verdict_a.zone_name}")
    print(f"  -> Threat Level: {verdict_a.threat_level}")
    print(f"  -> Breach: {verdict_a.is_breach} | Depth: +{verdict_a.penetration_depth_m:.1f}m")
    print(f"  -> XAI: {verdict_a.xai_explanation}")
    assert verdict_a.is_breach is True
    assert verdict_a.threat_level == "CRITICAL"
    assert "Red Zone Alpha" in verdict_a.zone_name
    assert verdict_a.penetration_depth_m > 3.0

    # Case B: Target approaching perimeter at foot_y = 410 (within 50px buffer above line)
    approach_bbox = [600, 310, 60, 100]  # foot_y = 410 (-22px margin)
    verdict_b = tripwire.evaluate_target(approach_bbox, frame_shape)
    print(f"\nCase B (Approaching target at foot_y=410):")
    print(f"  -> Zone: {verdict_b.zone_name}")
    print(f"  -> Threat Level: {verdict_b.threat_level}")
    print(f"  -> Breach: {verdict_b.is_breach} | Margin: {verdict_b.approach_margin_m:.1f}m")
    print(f"  -> XAI: {verdict_b.xai_explanation}")
    assert verdict_b.is_breach is False
    assert verdict_b.threat_level == "HIGH"
    assert "Amber Buffer Zone" in verdict_b.zone_name

    # Case C: Safe target far outside fence at foot_y = 250 (182px outside)
    safe_bbox = [600, 150, 60, 100]  # foot_y = 250
    verdict_c = tripwire.evaluate_target(safe_bbox, frame_shape)
    print(f"\nCase C (Distant foliage/animal at foot_y=250):")
    print(f"  -> Zone: {verdict_c.zone_name}")
    print(f"  -> Threat Level: {verdict_c.threat_level}")
    print(f"  -> Breach: {verdict_c.is_breach} | Margin: {verdict_c.approach_margin_m:.1f}m")
    print(f"  -> XAI: {verdict_c.xai_explanation}")
    assert verdict_c.is_breach is False
    assert verdict_c.threat_level == "LOW"
    assert "Green Buffer Zone" in verdict_c.zone_name

    print("\n[PASS] All 3 spatial perimeter cases classified with 100% precision!")
    return True


def test_resolution_invariance():
    print("\n" + "=" * 70)
    print("TEST 2: RESOLUTION INVARIANCE ACROSS SURVEILLANCE STREAMS")
    print("=" * 70)

    tripwire = VirtualTripwire(p1_norm=(0.1, 0.5), p2_norm=(0.9, 0.5))

    resolutions = [
        (480, 640),    # SD
        (720, 1280),   # 720p HD
        (1080, 1920),  # 1080p FHD
        (2160, 3840),  # 4K UHD
    ]

    for h, w in resolutions:
        (x1, y1), (x2, y2) = tripwire.get_pixel_endpoints(w, h)
        assert y1 == int(0.5 * h)
        assert y2 == int(0.5 * h)
        assert x1 == int(0.1 * w)
        assert x2 == int(0.9 * w)
        print(f"  -> {w}x{h}: TW Line ({x1}, {y1}) -> ({x2}, {y2}) [OK]")

    print("[PASS] Normalized coordinates scale flawlessly across all sensor resolutions!")
    return True


def test_hud_rendering():
    print("\n" + "=" * 70)
    print("TEST 3: TACTICAL HUD LASER OVERLAY RENDERING")
    print("=" * 70)

    synthetic_frame = np.full((720, 1280, 3), 35, dtype=np.uint8)
    tripwire = VirtualTripwire()
    tripwire.draw_hud_tripwire(synthetic_frame, is_breached=True)

    os.makedirs("outputs", exist_ok=True)
    out_path = "outputs/test_tripwire_hud.jpg"
    cv2.imwrite(out_path, synthetic_frame)
    assert os.path.exists(out_path)
    print(f"[PASS] Rendered tactical laser tripwire saved to: {out_path}")
    return True


if __name__ == "__main__":
    test_tripwire_spatial_classification()
    test_resolution_invariance()
    test_hud_rendering()
    print("\nALL FEATURE 2 TRIPWIRE TESTS PASSED SUCCESSFULLY!")
