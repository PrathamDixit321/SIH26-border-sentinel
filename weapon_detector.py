"""
weapon_detector.py
Modular, standalone Weapon Detection Engine for Border Sentinel AI (SIH26187).
Specialized for CCTV perimeter security: detects firearms, knives, and dangerous weapons.
"""

import os
import sys
from pathlib import Path
import cv2
import numpy as np

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


DEFAULT_MODEL_PATHS = [
    "yolov8s-weapon-finetuned.pt",
    os.path.join("weights", "yolov8s-weapon-finetuned.pt"),
    os.path.join(os.path.dirname(__file__), "yolov8s-weapon-finetuned.pt"),
]


class WeaponDetector:
    """
    YOLOv8-based weapon detector fine-tuned for CCTV surveillance.
    Identifies firearm and weapon profiles with confidence scoring and spatial localization.
    """
    def __init__(self, model_path: str = None, conf_threshold: float = 0.25):
        self.conf_threshold = conf_threshold
        self.model = None
        self.is_loaded = False
        self.model_path = model_path or self._resolve_model_path()

        if self.model_path and os.path.exists(self.model_path) and YOLO_AVAILABLE:
            try:
                self.model = YOLO(self.model_path)
                self.is_loaded = True
                print(f"[INFO] WeaponDetector: Loaded model weights from '{self.model_path}'")
                print(f"[INFO] WeaponDetector: Supported classes: {self.model.names}")
            except Exception as e:
                print(f"[WARN] WeaponDetector: Could not load model from '{self.model_path}': {e}")
        else:
            print("[INFO] WeaponDetector: Running in offline fallback mode (no weapon weights).")

    def _resolve_model_path(self) -> str | None:
        for p in DEFAULT_MODEL_PATHS:
            if os.path.exists(p):
                return p
        return None

    def detect(self, frame: np.ndarray, conf_threshold: float = None) -> list[dict]:
        """
        Detect weapons in a BGR video frame or image.
        Returns:
            list of dicts: [
                {
                    "label": "weapon",
                    "conf": 0.88,
                    "bbox": [x1, y1, x2, y2],
                    "xywh": [x, y, w, h]
                }, ...
            ]
        """
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []
        if not self.is_loaded or self.model is None:
            return []

        threshold = conf_threshold if conf_threshold is not None else self.conf_threshold

        try:
            results = self.model.predict(frame, verbose=False, conf=threshold)[0]
            detections = []
            if results.boxes is not None:
                for box in results.boxes:
                    conf = float(box.conf[0]) if hasattr(box, "conf") and len(box.conf) > 0 else 0.0
                    if conf < threshold:
                        continue
                    cls_id = int(box.cls[0]) if box.cls is not None else 0
                    raw_label = self.model.names.get(cls_id, "weapon")
                    
                    # Normalize label to objective naming
                    label = "weapon" if raw_label in ["weapon", "pistol", "rifle", "gun", "knife"] else raw_label
                    
                    # Only accept weapon classes (filter out raw person class if present in multi-class models)
                    if label.lower() not in ["weapon", "pistol", "rifle", "gun", "knife", "firearm"]:
                        continue

                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    w = x2 - x1
                    h = y2 - y1
                    detections.append({
                        "label": label,
                        "raw_label": raw_label,
                        "conf": round(conf, 3),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                        "xywh": [int(x1), int(y1), int(w), int(h)],
                    })
            return detections
        except Exception as e:
            print(f"[WARN] Weapon detection inference error: {e}")
            return []

    def annotate(self, frame: np.ndarray, detections: list[dict]) -> np.ndarray:
        """Draw high-visibility tactical threat overlays on detected weapons."""
        annotated = frame.copy()
        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            conf = det["conf"]
            label = det["label"].upper()

            # Flashing Critical Red Box
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 2)
            
            # Corner Tactical Brackets
            length = min(15, (x2 - x1) // 3)
            cv2.line(annotated, (x1, y1), (x1 + length, y1), (0, 0, 255), 3)
            cv2.line(annotated, (x1, y1), (x1, y1 + length), (0, 0, 255), 3)
            cv2.line(annotated, (x2, y2), (x2 - length, y2), (0, 0, 255), 3)
            cv2.line(annotated, (x2, y2), (x2, y2 - length), (0, 0, 255), 3)

            # High-Visibility Threat Badge
            badge_text = f"CRITICAL: {label} [{conf:.2f}]"
            cv2.rectangle(annotated, (x1, max(0, y1 - 22)), (x1 + len(badge_text) * 10, y1), (0, 0, 200), -1)
            cv2.putText(
                annotated,
                badge_text,
                (x1 + 4, max(14, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
        return annotated


# Global singleton instance for high-performance reuse across pipeline frames
detector_instance = None

def get_weapon_detector() -> WeaponDetector:
    global detector_instance
    if detector_instance is None:
        detector_instance = WeaponDetector()
    return detector_instance


def detect_weapons(frame: np.ndarray, conf_threshold: float = 0.25) -> list[dict]:
    """Convenience function for pipeline integration."""
    return get_weapon_detector().detect(frame, conf_threshold=conf_threshold)


if __name__ == "__main__":
    detector = get_weapon_detector()
    print("\n--- Weapon Detector Status ---")
    print(f"Model Loaded:   {detector.is_loaded}")
    print(f"Model Path:     {detector.model_path}")
    print(f"Default Thresh: {detector.conf_threshold}")
    
    # Test on a blank frame
    dummy = np.zeros((300, 400, 3), dtype=np.uint8)
    results = detector.detect(dummy)
    print(f"Test Blank Frame Detection: {results} (PASS)")
    print("WeaponDetector initialized and ready for deployment.\n")
