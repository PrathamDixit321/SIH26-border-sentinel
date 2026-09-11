"""Stage 4: Explainable Human vs. Natural Classifier with Real-Time Alert Engine.

Built for Smart India Hackathon 2026 — Problem Statement SIH26187.
Distinguishes genuine human intrusions from natural environmental motion
(foliage, wind, shadows, reflections) and generates explainable plain-English
reasoning, intrusion snapshots, and structured alerts.json logs.

Run:
    python step4_classifier_alerts.py "Yash Raj 1.mp4" "Yash Raj 2.mp4"
    python step4_classifier_alerts.py "Yash Raj 1.mp4" "Yash Raj 2.mp4" --no-preview
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

from step1_two_video_alignment import (
    align_after_to_before_with_mask,
    labeled_panel,
    reset_alignment_state,
)

# Target surveillance categories (COCO: 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck)
TARGET_CLASSES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

# Color palette (BGR)
COLOR_HUMAN_PEDESTRIAN = (0, 0, 255)       # Red - Critical Intruder Alert
COLOR_HUMAN_VEHICLE = (0, 215, 255)          # Amber/Gold - Vehicle Alert
COLOR_NATURAL_TREES = (0, 230, 0)           # Emerald Green - Natural Foliage (Filtered)
COLOR_STATIC = (140, 140, 140)              # Muted Slate - Ambient / Static


def compute_clean_difference(
    before_bgr: np.ndarray,
    aligned_after_bgr: np.ndarray,
    valid_mask: np.ndarray,
    threshold: int = 35,
    min_area: int = 500,
    blur_size: int = 5,
) -> tuple[np.ndarray, list[dict], list[np.ndarray]]:
    """Compute frame difference strictly within the valid mutual field of view.

    Prevents border replication artifacts from generating fake change contours.
    Returns (cleaned_mask, regions_info, raw_contours).
    """
    before_gray = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(aligned_after_bgr, cv2.COLOR_BGR2GRAY)

    before_blurred = cv2.GaussianBlur(before_gray, (blur_size, blur_size), 0)
    after_blurred = cv2.GaussianBlur(after_gray, (blur_size, blur_size), 0)

    difference = cv2.absdiff(before_blurred, after_blurred)
    _, mask = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)

    # Exclude any pixels outside the valid mutual field of view
    if valid_mask is not None:
        mask = cv2.bitwise_and(mask, mask, mask=valid_mask)

    # Morphological noise removal
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    raw_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_contours = [c for c in raw_contours if cv2.contourArea(c) > 20]

    dilated_mask = cv2.dilate(mask, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    regions = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)

        hull = cv2.convexHull(contour)
        hull_area = float(cv2.contourArea(hull)) if len(hull) >= 3 else area
        solidity = area / hull_area if hull_area > 0 else 1.0
        aspect_ratio = float(w) / h if h > 0 else 1.0

        # Count smaller sub-fragments inside this bounding region
        fragments = 0
        for rc in raw_contours:
            rx, ry, rw, rh = cv2.boundingRect(rc)
            cx, cy = rx + rw / 2.0, ry + rh / 2.0
            if x <= cx <= x + w and y <= cy <= y + h:
                fragments += 1
        fragments = max(1, fragments)

        regions.append({
            "bbox": [int(x), int(y), int(w), int(h)],
            "area": area,
            "solidity": solidity,
            "aspect_ratio": aspect_ratio,
            "fragments": fragments,
            "contour": contour,
        })

    regions.sort(key=lambda r: r["area"], reverse=True)
    return mask, regions, raw_contours


def detect_yolo_targets(model: YOLO, aligned_frame: np.ndarray, confidence: float) -> list[dict]:
    """Run YOLOv8 object detection restricted to person and vehicle classes."""
    results = model.predict(
        source=aligned_frame,
        conf=confidence,
        classes=list(TARGET_CLASSES),
        verbose=False,
    )[0]
    detections = []
    if results.boxes is None:
        return detections
    for box in results.boxes:
        cls_id = int(box.cls[0])
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        detections.append({
            "label": TARGET_CLASSES[cls_id],
            "confidence": float(box.conf[0]),
            "bbox": [x1, y1, x2, y2],
        })
    return detections


def compute_bbox_overlap(region_bbox: list[int], yolo_bbox: list[float]) -> float:
    """Intersection-over-region area to check if YOLO detection covers change."""
    x, y, w, h = region_bbox
    x1, y1, x2, y2 = yolo_bbox
    ix1, iy1 = max(float(x), float(x1)), max(float(y), float(y1))
    ix2, iy2 = min(float(x + w), float(x2)), min(float(y + h), float(y2))
    inter_w = max(0.0, ix2 - ix1)
    inter_h = max(0.0, iy2 - iy1)
    inter_area = inter_w * inter_h
    region_area = float(w * h)
    return inter_area / region_area if region_area > 0 else 0.0


def classify_region(
    region: dict, yolo_detections: list[dict], overlap_threshold: float = 0.15
) -> tuple[str, str, float, str, dict]:
    """Classify a changed region into HUMAN, NATURAL, or STATIC with explainable metrics."""
    x, y, w, h = region["bbox"]
    area = region["area"]
    solidity = region["solidity"]
    fragments = region["fragments"]
    aspect_ratio = region["aspect_ratio"]

    # 1. Check spatial overlap with YOLO detections
    best_match = None
    best_overlap = 0.0
    for det in yolo_detections:
        overlap = compute_bbox_overlap(region["bbox"], det["bbox"])
        if overlap > best_overlap:
            best_overlap, best_match = overlap, det

    if best_match is not None and best_overlap >= overlap_threshold:
        yolo_label = best_match["label"]
        yolo_conf = best_match["confidence"]
        if yolo_label == "person":
            category = "PEDESTRIAN"
            label = "HUMAN"
            reason = f"YOLO detected person ({yolo_conf:.2f}, overlap {best_overlap:.0%}) in active change region"
            confidence = max(0.90, yolo_conf)
        else:
            category = "VEHICLE"
            label = "HUMAN"
            reason = f"YOLO detected {yolo_label} ({yolo_conf:.2f}, overlap {best_overlap:.0%}) in active change region"
            confidence = max(0.88, yolo_conf)
        return label, category, confidence, reason, best_match

    # 2. Heuristic: Moving Vehicle / Sweeping Headlight Illumination
    if area >= 2500 and aspect_ratio >= 1.2 and solidity >= 0.60:
        return (
            "HUMAN",
            "VEHICLE",
            0.82,
            f"Moving vehicle profile (area={area:.0f}px, aspect_ratio={aspect_ratio:.2f})",
            None,
        )

    # 3. Heuristic: Natural Wind / Tree Foliage Movement
    # Tree foliage produces scattered multi-fragment blobs or low solidity
    if fragments >= 3 or (fragments >= 2 and area > 1000) or solidity < 0.65:
        return (
            "NATURAL",
            "TREES",
            0.85,
            f"Tree foliage/wind movement ({fragments} fragments, solidity={solidity:.2f})",
            None,
        )

    # 4. Heuristic: Walking Pedestrian (Silhouette Analysis when YOLO misses due to distance/darkness)
    is_pedestrian_shape = (0.20 <= aspect_ratio <= 0.95) and h >= 22 and solidity >= 0.68
    if is_pedestrian_shape and fragments <= 2:
        return (
            "HUMAN",
            "PEDESTRIAN",
            0.78,
            f"Moving pedestrian profile (solidity={solidity:.2f}, AR={aspect_ratio:.2f}, h={h}px)",
            None,
        )

    # 5. Ambient / Static fluctuation
    return (
        "NATURAL",
        "AMBIENT",
        0.65,
        f"Ambient lighting/environmental motion (solidity={solidity:.2f}, AR={aspect_ratio:.2f})",
        None,
    )


def save_alert_snapshot(
    frame: np.ndarray,
    alert_info: dict,
    snapshot_path: Path,
) -> None:
    """Save an annotated snapshot crop of the intrusion alert."""
    x, y, w, h = alert_info["bbox"]
    pad = 30
    h_max, w_max = frame.shape[:2]
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(w_max, x + w + pad), min(h_max, y + h + pad)

    crop = frame[y1:y2, x1:x2].copy()
    box_x, box_y = x - x1, y - y1
    color = COLOR_HUMAN_PEDESTRIAN if alert_info["category"] == "PEDESTRIAN" else COLOR_HUMAN_VEHICLE
    cv2.rectangle(crop, (box_x, box_y), (box_x + w, box_y + h), color, 2)

    # Header banner
    banner = np.zeros((48, crop.shape[1], 3), dtype=np.uint8)
    banner[:] = (20, 20, 20)
    badge = f"ALERT: {alert_info['label']} [{alert_info['category']}] {alert_info['confidence']:.2f}"
    cv2.putText(banner, badge, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    time_str = f"Time: {alert_info['timestamp_sec']:.2f}s | Frame: {alert_info['frame']}"
    cv2.putText(banner, time_str, (8, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 200, 200), 1)

    combined_crop = np.vstack((banner, crop))
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(snapshot_path), combined_crop)


def draw_hud_header(
    panel: np.ndarray, frame_idx: int, time_sec: float, alert_count: int, matches: int, inliers: int
) -> None:
    """Render a clean surveillance HUD header on top of the preview display."""
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 34), (20, 20, 20), -1)
    hud_left = f"Border Sentinel AI | Frame: {frame_idx:04d} ({time_sec:04.1f}s) | Active Human Alerts: {alert_count}"
    cv2.putText(panel, hud_left, (12, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

    hud_right = f"ORB: {matches} matches, {inliers} inliers | [SPACE] Pause [Q] Quit"
    cv2.putText(panel, hud_right, (panel.shape[1] - 440, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 180, 180), 1)


def main(
    before_path: str,
    after_path: str,
    output_path: str,
    alerts_json_path: str,
    snapshots_dir: str,
    preview: bool,
    threshold: int,
    min_area: int,
    sample_fps: float,
    yolo_confidence: float,
    overlap_threshold: float,
) -> None:
    reset_alignment_state()
    before_cap = cv2.VideoCapture(before_path)
    after_cap = cv2.VideoCapture(after_path)
    if not before_cap.isOpened() or not after_cap.isOpened():
        raise RuntimeError("Could not open one or both input videos.")
    if sample_fps <= 0:
        raise ValueError("sample_fps must be greater than zero.")

    before_fps = before_cap.get(cv2.CAP_PROP_FPS) or 30.0
    after_fps = after_cap.get(cv2.CAP_PROP_FPS) or 30.0
    requested_fps = min(sample_fps, before_fps, after_fps)
    frame_interval = max(1, round(before_fps / requested_fps))
    output_fps = before_fps / frame_interval

    before_ok, first_before = before_cap.read()
    if not before_ok:
        raise RuntimeError("The before video contains no readable frames.")
    height, width = first_before.shape[:2]
    before_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), output_fps, (width * 3, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not create preview video: {output}")

    snapshots_path = Path(snapshots_dir)
    snapshots_path.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print("Border Sentinel AI — Stage 4 Explainable Surveillance Classifier")
    print(f"Sampling at {output_fps:.1f} FPS | Diff Threshold: {threshold} | Min Area: {min_area} px")
    print(f"YOLO Confidence: {yolo_confidence} | Overlap Threshold: {overlap_threshold:.0%}")
    print(f"Recording output to: {output}")
    print("=" * 75)

    print("Loading YOLOv8n detector...")
    model = YOLO("yolov8n.pt")

    window_name = "Border Sentinel AI - Stage 4 Intelligent Surveillance Monitor"
    if preview:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        disp_w = min(1440, width * 3)
        disp_h = int(height * (disp_w / (width * 3)))
        cv2.resizeWindow(window_name, disp_w, disp_h)
        print("Live preview window opened. Controls: [SPACE] Pause/Resume, [Q] Quit preview.\n")

    source_frame_index = 0
    processed_frames = 0
    all_alerts = []
    total_regions_checked = 0

    while True:
        before_ok, before_frame = before_cap.read()
        after_ok, after_frame = after_cap.read()
        if not before_ok or not after_ok:
            break

        if source_frame_index % frame_interval != 0:
            source_frame_index += 1
            continue

        before_frame = cv2.resize(before_frame, (width, height))
        after_frame = cv2.resize(after_frame, (width, height))

        # 1. Seamless robust alignment with valid overlap mask (no edge smears)
        aligned_after, matches, inliers, valid_mask = align_after_to_before_with_mask(
            before_frame, after_frame
        )

        # 2. Extract clean difference mask within valid mutual overlap area
        diff_mask, regions, raw_contours = compute_clean_difference(
            before_frame, aligned_after, valid_mask, threshold=threshold, min_area=min_area, blur_size=5
        )

        # 3. Detect YOLO targets in aligned after frame
        yolo_targets = detect_yolo_targets(model, aligned_after, yolo_confidence)

        # 4. Classify each changed region
        annotated_after = aligned_after.copy()
        current_frame_alerts = []

        for region_idx, region in enumerate(regions, start=1):
            total_regions_checked += 1
            label, category, conf, reason, yolo_match = classify_region(
                region, yolo_targets, overlap_threshold=overlap_threshold
            )
            x, y, w, h = region["bbox"]
            time_sec = source_frame_index / before_fps

            # Pick distinct operational colors
            if label == "HUMAN":
                color = COLOR_HUMAN_PEDESTRIAN if category == "PEDESTRIAN" else COLOR_HUMAN_VEHICLE
                thickness = 2
                tag = f"HUMAN: {category} ({conf:.2f})"
                alert_entry = {
                    "frame": source_frame_index,
                    "timestamp_sec": round(time_sec, 2),
                    "label": label,
                    "category": category,
                    "confidence": round(conf, 3),
                    "bbox": [x, y, w, h],
                    "reason": reason,
                    "metrics": {
                        "area": round(region["area"], 1),
                        "solidity": round(region["solidity"], 3),
                        "aspect_ratio": round(region["aspect_ratio"], 2),
                        "fragments": region["fragments"],
                    },
                }
                current_frame_alerts.append(alert_entry)
                all_alerts.append(alert_entry)

                # Save intrusion snapshot crop
                snapshot_file = snapshots_path / f"alert_f{source_frame_index:04d}_{category.lower()}_{x}_{y}.jpg"
                alert_entry["snapshot_file"] = str(snapshot_file)
                save_alert_snapshot(aligned_after, alert_entry, snapshot_file)
            elif category == "TREES":
                color = COLOR_NATURAL_TREES
                thickness = 1
                tag = f"TREES/WIND ({conf:.2f})"
            else:
                color = COLOR_STATIC
                thickness = 1
                tag = f"STATIC ({conf:.2f})"

            # Render bounding box and text badge
            cv2.rectangle(annotated_after, (x, y), (x + w, y + h), color, thickness)
            cv2.putText(
                annotated_after,
                tag,
                (x, max(20, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.42,
                color,
                2 if label == "HUMAN" else 1,
            )

            # Log detections to terminal
            if label == "HUMAN":
                print(
                    f"⚠️ [ALERT] Frame {source_frame_index} ({time_sec:.2f}s) | "
                    f"{label} [{category}] at ({x}, {y}, {w}, {h}) -> {reason}"
                )

        # 5. Build 3-Panel Display
        # Panel 1: Reference
        panel1 = labeled_panel(before_frame, "Before (reference)")

        # Panel 2: Aligned After with Classifications
        panel2_label = f"Aligned After | {len(current_frame_alerts)} Human Alert(s), {len(regions)} Change(s)"
        panel2 = labeled_panel(annotated_after, panel2_label)

        # Panel 3: Difference Mask with Telemetry HUD
        diff_mask_bgr = cv2.cvtColor(diff_mask, cv2.COLOR_GRAY2BGR)
        # Highlight human intrusion boxes in difference mask as well
        for alert in current_frame_alerts:
            ax, ay, aw, ah = alert["bbox"]
            cv2.rectangle(diff_mask_bgr, (ax, ay), (ax + aw, ay + ah), (0, 0, 255), 2)
        panel3_label = f"Clean Difference Mask | {matches} matches, {inliers} inliers"
        panel3 = labeled_panel(diff_mask_bgr, panel3_label)

        combined = np.hstack((panel1, panel2, panel3))

        # Draw sleek top HUD
        time_sec = source_frame_index / before_fps
        draw_hud_header(combined, source_frame_index, time_sec, len(current_frame_alerts), matches, inliers)

        writer.write(combined)

        if preview:
            try:
                cv2.imshow(window_name, combined)
                key = cv2.waitKey(max(1, int(1000 / output_fps))) & 0xFF
                if key == ord("q"):
                    print("\n[INFO] Playback preview closed by user.")
                    break
                elif key == ord(" "):
                    print("\n[PAUSED] Press any key to resume...")
                    cv2.waitKey(-1)
            except cv2.error:
                preview = False

        processed_frames += 1
        source_frame_index += 1

    before_cap.release()
    after_cap.release()
    writer.release()
    if preview:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass

    # Save structured JSON alert history
    alerts_file = Path(alerts_json_path)
    alerts_file.parent.mkdir(parents=True, exist_ok=True)
    with open(alerts_file, "w", encoding="utf-8") as f:
        json.dump(all_alerts, f, indent=2)

    print("\n" + "=" * 75)
    print(f"Surveillance analysis completed successfully!")
    print(f"Processed {processed_frames} sampled frames.")
    print(f"Checked {total_regions_checked} changed regions across footage.")
    print(f"Generated and logged {len(all_alerts)} human/vehicle intrusion alert(s).")
    print(f"Saved surveillance preview video to: {output}")
    print(f"Saved structured alerts JSON to:       {alerts_file}")
    print(f"Saved intrusion image snapshots to:   {snapshots_path}/")
    print("=" * 75)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Stage 4: Explainable Human vs. Natural Classifier with Real-Time Alert Engine."
    )
    parser.add_argument("before_video", help="Path to the before/reference video")
    parser.add_argument("after_video", help="Path to the after video")
    parser.add_argument(
        "--output", default="outputs/stage4_classified_surveillance.mp4", help="Preview video path"
    )
    parser.add_argument(
        "--alerts-json", default="outputs/alerts.json", help="Path to export alerts.json log"
    )
    parser.add_argument(
        "--snapshots-dir", default="outputs/alerts", help="Directory to save intrusion snapshot crops"
    )
    parser.add_argument(
        "--preview", action="store_true", dest="preview", default=True, help="Show live popup preview window (default: True)"
    )
    parser.add_argument(
        "--no-preview", action="store_false", dest="preview", help="Disable live popup preview window"
    )
    parser.add_argument(
        "--threshold", type=int, default=35, help="Pixel difference threshold (default: 35)"
    )
    parser.add_argument(
        "--min-area", type=int, default=500, help="Minimum contour area in pixels (default: 500)"
    )
    parser.add_argument(
        "--sample-fps", type=float, default=3.0, help="Frames per second to process (default: 3)"
    )
    parser.add_argument(
        "--yolo-confidence", type=float, default=0.35, help="YOLO confidence threshold (default: 0.35)"
    )
    parser.add_argument(
        "--overlap-threshold", type=float, default=0.15, help="Minimum region coverage by YOLO box (default: 0.15)"
    )
    args = parser.parse_args()
    main(
        args.before_video,
        args.after_video,
        args.output,
        args.alerts_json,
        args.snapshots_dir,
        args.preview,
        args.threshold,
        args.min_area,
        args.sample_fps,
        args.yolo_confidence,
        args.overlap_threshold,
    )
