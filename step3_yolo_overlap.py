"""Stage 3: add YOLO person/vehicle overlap checks to changed regions.

This stage reuses Stage 1 alignment and Stage 2 contour detection. It does not
create the final JSON report yet; it prints the YOLO overlap result for each
change region and saves an annotated preview.

Run:
    python step3_yolo_overlap.py before.mp4 after.mp4 --preview --min-area 2000
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from ultralytics import YOLO

from step1_two_video_alignment import align_after_to_before, labeled_panel, reset_alignment_state
from step2_change_detection import detect_changed_regions


# COCO class IDs: person, car, motorcycle, bus, truck.
TARGET_CLASSES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}


def overlap_fraction(region: tuple[int, int, int, int, float], yolo_box: list[float]) -> float:
    """Return the fraction of a change-region bounding box covered by a YOLO box."""
    x, y, width, height, _ = region
    x1, y1, x2, y2 = yolo_box
    intersection_x1, intersection_y1 = max(x, x1), max(y, y1)
    intersection_x2, intersection_y2 = min(x + width, x2), min(y + height, y2)
    intersection = max(0.0, intersection_x2 - intersection_x1) * max(0.0, intersection_y2 - intersection_y1)
    region_box_area = width * height
    return intersection / region_box_area if region_box_area else 0.0


def detect_targets(model: YOLO, aligned_after: object, confidence: float) -> list[dict]:
    """Detect only person and vehicle categories in the aligned after-frame."""
    result = model.predict(
        source=aligned_after,
        conf=confidence,
        classes=list(TARGET_CLASSES),
        verbose=False,
    )[0]
    detections = []
    if result.boxes is None:
        return detections
    for box in result.boxes:
        class_id = int(box.cls[0])
        x1, y1, x2, y2 = [float(value) for value in box.xyxy[0].tolist()]
        detections.append({
            "label": TARGET_CLASSES[class_id],
            "confidence": float(box.conf[0]),
            "bbox": [x1, y1, x2, y2],
        })
    return detections


def main(
    before_path: str,
    after_path: str,
    output_path: str,
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

    print("Loading YOLOv8n model...")
    model = YOLO("yolov8n.pt")
    print(f"Sampling at {output_fps:.1f} FPS | YOLO confidence: {yolo_confidence} | Overlap threshold: {overlap_threshold}")
    print("Amber change boxes overlap a YOLO person/vehicle; green boxes do not. Press Q to quit preview mode.")

    window_name = "Stage 3 - YOLO Overlap Surveillance Monitor"
    if preview:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        disp_w = min(1440, width * 3)
        disp_h = int(height * (disp_w / (width * 3)))
        cv2.resizeWindow(window_name, disp_w, disp_h)
        print("Live preview window opened. Controls: [SPACE] Pause/Resume, [Q] Quit preview.")

    source_frame_index = 0
    processed_frames = 0
    regions_checked = 0
    regions_with_target = 0
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
        aligned_after, matches, inliers = align_after_to_before(before_frame, after_frame)
        _, regions = detect_changed_regions(before_frame, aligned_after, threshold, min_area, blur_size=5)
        yolo_detections = detect_targets(model, aligned_after, yolo_confidence)

        annotated_after = aligned_after.copy()
        for detection in yolo_detections:
            x1, y1, x2, y2 = [int(value) for value in detection["bbox"]]
            cv2.rectangle(annotated_after, (x1, y1), (x2, y2), (255, 180, 0), 1)
            cv2.putText(annotated_after, f"YOLO {detection['label']} {detection['confidence']:.2f}", (x1, max(18, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 180, 0), 1)
        yolo_only = annotated_after.copy()

        for region_number, region in enumerate(regions, start=1):
            x, y, region_width, region_height, area = region
            regions_checked += 1
            best_match = None
            best_overlap = 0.0
            for detection in yolo_detections:
                fraction = overlap_fraction(region, detection["bbox"])
                if fraction > best_overlap:
                    best_overlap, best_match = fraction, detection

            has_target = best_match is not None and best_overlap >= overlap_threshold
            colour = (0, 191, 255) if has_target else (0, 255, 0)  # amber / green
            label = f"{best_match['label']} ({best_overlap:.0%})" if has_target else f"change {area:.0f}px"
            cv2.rectangle(annotated_after, (x, y), (x + region_width, y + region_height), colour, 2)
            cv2.putText(annotated_after, label, (x, max(20, y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 2)

            if has_target:
                regions_with_target += 1
            target_summary = (
                f"{best_match['label']} (YOLO {best_match['confidence']:.2f}, overlap {best_overlap:.0%})"
                if has_target else "none"
            )
            print(
                f"Source frame {source_frame_index} ({source_frame_index / before_fps:.2f}s) | "
                f"region {region_number}: ({x}, {y}, {region_width}, {region_height}), area={area:.0f} | target: {target_summary}"
            )

        panel_label = f"Aligned after | {len(regions)} change region(s), {len(yolo_detections)} YOLO target(s)"
        combined = cv2.hconcat((
            labeled_panel(before_frame, "Before (reference)"),
            labeled_panel(annotated_after, panel_label),
            labeled_panel(yolo_only, f"YOLO targets | ORB: {matches} matches, {inliers} inliers"),
        ))
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
    print(f"\nSaved {processed_frames} sampled frames to: {output}")
    print(f"YOLO checked {regions_checked} changed regions; {regions_with_target} overlapped a person/vehicle.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 3: YOLO overlap check for changed regions.")
    parser.add_argument("before_video", help="Path to the before/reference video")
    parser.add_argument("after_video", help="Path to the after video")
    parser.add_argument("--output", default="outputs/yolo_overlap_preview.mp4", help="Preview video path")
    parser.add_argument("--preview", action="store_true", dest="preview", default=True, help="Show live popup preview window (default: True)")
    parser.add_argument("--no-preview", action="store_false", dest="preview", help="Disable live popup preview window (save video only)")
    parser.add_argument("--threshold", type=int, default=35, help="Pixel difference threshold (default: 35)")
    parser.add_argument("--min-area", type=int, default=500, help="Minimum contour area in pixels (default: 500)")
    parser.add_argument("--sample-fps", type=float, default=3.0, help="Frames per second to process (default: 3)")
    parser.add_argument("--yolo-confidence", type=float, default=0.35, help="YOLO confidence threshold (default: 0.35)")
    parser.add_argument("--overlap-threshold", type=float, default=0.15, help="Minimum region coverage by YOLO box (default: 0.15)")
    arguments = parser.parse_args()
    main(
        arguments.before_video, arguments.after_video, arguments.output, arguments.preview,
        arguments.threshold, arguments.min_area, arguments.sample_fps,
        arguments.yolo_confidence, arguments.overlap_threshold,
    )
