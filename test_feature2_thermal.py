"""Focused checks for architecture-level thermal input support."""

from unittest.mock import patch

import cv2
import numpy as np
import ultralytics

with patch.object(ultralytics, "YOLO", return_value=None):
    import pipeline as pipeline_module
    from backend.app.models import AlertCreate
    from pipeline import (
        LowLightEnhancer,
        ThermalNormalizer,
        _preprocess_input_frame,
        align_frames,
        compute_change_mask,
        process_video,
    )


def test_thermal_normalizer_accepts_8_and_16_bit_grayscale():
    normalizer = ThermalNormalizer()
    thermal_8bit = np.arange(80 * 64, dtype=np.uint8).reshape(64, 80)
    thermal_16bit = thermal_8bit.astype(np.uint16) * 200 + 7000

    for frame in (thermal_8bit, thermal_16bit, thermal_16bit[:, :, None]):
        display_bgr, processed_gray = normalizer.process(frame)
        assert display_bgr.shape == (64, 80, 3)
        assert processed_gray.shape == (64, 80)
        assert display_bgr.dtype == np.uint8
        assert processed_gray.dtype == np.uint8


def test_rgb_default_path_preserves_original_frame():
    frame = np.full((64, 80, 3), (110, 140, 170), dtype=np.uint8)
    display_bgr, processed_gray, low_light, mean_luminance = _preprocess_input_frame(
        frame,
        "RGB",
        LowLightEnhancer(),
        ThermalNormalizer(),
    )

    assert np.array_equal(display_bgr, frame)
    assert np.array_equal(processed_gray, cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    assert low_light is False
    assert mean_luminance == float(np.mean(processed_gray))


def test_mode_is_explicit_and_thermal_uses_shared_cv_stages():
    gray = np.tile(np.arange(80, dtype=np.uint8) + 100, (64, 1))
    gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    enhancer = LowLightEnhancer()
    normalizer = ThermalNormalizer()

    rgb_view, _, _, _ = _preprocess_input_frame(gray_bgr, "RGB", enhancer, normalizer)
    thermal_view, thermal_gray, _, _ = _preprocess_input_frame(gray_bgr, "THERMAL", enhancer, normalizer)
    assert np.array_equal(rgb_view, gray_bgr)
    assert not np.array_equal(thermal_view, gray_bgr)

    changed = gray.copy()
    cv2.rectangle(changed, (30, 20), (45, 50), 255, -1)
    _, changed_gray, _, _ = _preprocess_input_frame(
        cv2.cvtColor(changed, cv2.COLOR_GRAY2BGR), "THERMAL", enhancer, normalizer
    )
    aligned = align_frames(thermal_gray, changed_gray)
    mask, _, _ = compute_change_mask(thermal_gray, aligned, min_area=1, min_dim=1)
    assert aligned.shape == thermal_gray.shape
    assert mask.shape == thermal_gray.shape


def test_invalid_thermal_frames_fail_with_clear_errors():
    normalizer = ThermalNormalizer()
    invalid_frames = (
        None,
        np.empty((0, 10), dtype=np.uint8),
        np.zeros((10,), dtype=np.uint8),
        np.zeros((10, 10, 2), dtype=np.uint8),
        np.zeros((10, 10, 4), dtype=np.uint8),
        np.full((10, 10), np.nan, dtype=np.float32),
    )

    for frame in invalid_frames:
        try:
            normalizer.process(frame)
        except ValueError:
            continue
        raise AssertionError(f"Expected invalid frame to be rejected: {frame!r}")


def test_video_source_with_missing_frames_exits_cleanly():
    class EmptyCapture:
        released = False

        def isOpened(self):
            return True

        def read(self):
            return False, None

        def release(self):
            self.released = True

    capture = EmptyCapture()
    with patch("pipeline.cv2.VideoCapture", return_value=capture):
        assert process_video("empty.mp4", show_live=False, input_mode="THERMAL") == []
    assert capture.released


def test_thermal_video_path_emits_mode_tagged_alerts():
    background = np.tile(np.linspace(9500, 10200, 320, dtype=np.uint16), (240, 1))
    frames = [background.copy() for _ in range(7)]
    for frame_index in range(3, 7):
        frames[frame_index][70:180, 100 + (frame_index - 3) * 4:145 + (frame_index - 3) * 4] = 15000

    class ThermalCapture:
        def __init__(self):
            self.frames = [background.copy(), *frames]

        def isOpened(self):
            return True

        def read(self):
            return (True, self.frames.pop(0)) if self.frames else (False, None)

        def get(self, property_id):
            return 30.0

        def release(self):
            pass

    capture = ThermalCapture()
    with (
        patch.object(pipeline_module, "MODEL", None),
        patch.object(pipeline_module.cv2, "VideoCapture", return_value=capture),
        patch.object(pipeline_module, "send_alert_to_api"),
        patch.object(pipeline_module, "send_frame_to_stream"),
    ):
        alerts = pipeline_module.process_video("thermal-memory-sequence", show_live=False, input_mode="THERMAL")

    assert alerts
    assert all(alert["input_mode"] == "THERMAL" for alert in alerts)


def test_alert_contract_carries_input_mode_with_rgb_compatibility_default():
    assert AlertCreate(input_mode="THERMAL").model_dump()["input_mode"] == "THERMAL"
    assert AlertCreate().model_dump()["input_mode"] == "RGB"


if __name__ == "__main__":
    test_thermal_normalizer_accepts_8_and_16_bit_grayscale()
    test_rgb_default_path_preserves_original_frame()
    test_mode_is_explicit_and_thermal_uses_shared_cv_stages()
    test_invalid_thermal_frames_fail_with_clear_errors()
    test_video_source_with_missing_frames_exits_cleanly()
    test_thermal_video_path_emits_mode_tagged_alerts()
    test_alert_contract_carries_input_mode_with_rgb_compatibility_default()
    print("ALL FEATURE 2 THERMAL INPUT TESTS PASSED")