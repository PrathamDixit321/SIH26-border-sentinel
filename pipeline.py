"""
pipeline.py
Enhanced Border Sentinel CV Pipeline:
  1. Camera jitter compensation using Affine Partial 2D / Homography.
  2. Gaussian-filtered change detection with edge-border margin masking.
  3. Spatial intersection check between YOLO bounding boxes and change contours.
  4. Multi-heuristic explainable classifier (solidity, fragmentation, compactness, aspect ratio).
  5. Detailed metric telemetry per region to enable real-data threshold tuning.
"""

import sys
import cv2
import numpy as np
try:
    from ultralytics import YOLO
    MODEL = YOLO("yolov8n.pt")
except (ImportError, Exception) as e:
    MODEL = None
    print(f"[INFO] Running in heuristic-only mode (YOLO unavailable: {e})")

# Allowed classes for surveillance alerts (COCO: 0=person, 2=car, 3=motorcycle, 5=bus, 7=truck)
TARGET_CLASSES = {0: "person", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}

ORB = cv2.ORB_create(500)
BF_MATCHER = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def align_frames(prev_gray, curr_gray):
    """Align curr to prev using Partial Affine (rotation + translation)
    to handle camera jitter without projective shear distortion."""
    kp1, des1 = ORB.detectAndCompute(prev_gray, None)
    kp2, des2 = ORB.detectAndCompute(curr_gray, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        return curr_gray

    matches = BF_MATCHER.match(des1, des2)
    matches = sorted(matches, key=lambda m: m.distance)[:80]

    if len(matches) < 8:
        return curr_gray

    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    # Partial Affine is much less prone to crazy warping than 8-DOF homography
    M, inliers = cv2.estimateAffinePartial2D(dst_pts, src_pts, method=cv2.RANSAC, ransacReprojThreshold=4.0)
    if M is None:
        return curr_gray

    h, w = prev_gray.shape
    aligned = cv2.warpAffine(curr_gray, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return aligned


def compute_change_mask(prev_gray, aligned_curr_gray, thresh=25, blur_ksize=5, border_margin=15):
    """Gaussian blur + frame differencing with border exclusion to avoid warping artifacts."""
    prev_blurred = cv2.GaussianBlur(prev_gray, (blur_ksize, blur_ksize), 0)
    curr_blurred = cv2.GaussianBlur(aligned_curr_gray, (blur_ksize, blur_ksize), 0)

    diff = cv2.absdiff(prev_blurred, curr_blurred)
    _, mask = cv2.threshold(diff, thresh, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    # Mask out border edges to avoid false positives from warp boundaries
    h, w = mask.shape
    mask[:border_margin, :] = 0
    mask[-border_margin:, :] = 0
    mask[:, :border_margin] = 0
    mask[:, -border_margin:] = 0

    raw_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_contours = [c for c in raw_contours if cv2.contourArea(c) > 20]

    merged_mask = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=2)
    merged_contours, _ = cv2.findContours(merged_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    merged_contours = [c for c in merged_contours if cv2.contourArea(c) > 300]

    return merged_mask, merged_contours, raw_contours


def count_fragments_inside(contour, raw_contours):
    """Counts how many raw fragmented blobs fall within this candidate region."""
    x, y, w, h = cv2.boundingRect(contour)
    count = 0
    for rc in raw_contours:
        rx, ry, rw, rh = cv2.boundingRect(rc)
        cx, cy = rx + rw / 2.0, ry + rh / 2.0
        if x <= cx <= x + w and y <= cy <= y + h:
            count += 1
    return count


def check_bbox_overlap(box_a, box_b):
    """Computes intersection-over-box_a (contour) to verify if a YOLO box covers the change."""
    xa1, ya1, wa, ha = box_a
    xa2, ya2 = xa1 + wa, ya1 + ha

    xb1, yb1, xb2, yb2 = box_b

    # Intersection rectangle
    inter_x1 = max(xa1, xb1)
    inter_y1 = max(ya1, yb1)
    inter_x2 = min(xa2, xb2)
    inter_y2 = min(ya2, yb2)

    inter_w = max(0, inter_x2 - inter_x1)
    inter_h = max(0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h

    contour_area = wa * ha
    if contour_area == 0:
        return 0.0
    return inter_area / float(contour_area)


def classify_change(contour, yolo_detections, raw_contours):
    """
    Classifies a changed region as HUMAN or NATURAL.
    Returns: (label, confidence, reason, metrics_dict)
    """
    area = cv2.contourArea(contour)
    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = float(w) / h if h > 0 else 0.0

    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull) if len(hull) >= 3 else area
    solidity = (area / hull_area) if hull_area > 0 else 0.0

    perimeter = cv2.arcLength(contour, True)
    compactness = (4.0 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0

    fragments = count_fragments_inside(contour, raw_contours)

    # 1. Check spatial intersection with YOLO detections
    yolo_match = None
    for det in yolo_detections:
        overlap = check_bbox_overlap((x, y, w, h), det["bbox"])
        if overlap > 0.15:  # Overlaps at least 15% of the changed region
            yolo_match = det
            break

    metrics = {
        "area": round(area, 1),
        "solidity": round(solidity, 3),
        "compactness": round(compactness, 3),
        "fragments": fragments,
        "aspect_ratio": round(aspect_ratio, 2),
        "yolo_match": yolo_match["label"] if yolo_match else None
    }

    if yolo_match:
        reason = f"YOLO detected {yolo_match['label']} ({yolo_match['conf']:.2f}) overlapping the region"
        return "HUMAN", 0.95, reason, metrics

    # 2. Heuristic rules based on geometry
    if fragments >= 4:
        reason = f"{fragments} scattered fragments detected inside region (typical wind/foliage movement)"
        return "NATURAL", 0.75, reason, metrics

    if solidity > 0.75 and 0.25 <= aspect_ratio <= 2.5 and compactness > 0.15:
        reason = f"Compact, unified shape (solidity={solidity:.2f}, compactness={compactness:.2f})"
        return "HUMAN", 0.65, reason, metrics

    reason = f"Irregular, non-solid shape (solidity={solidity:.2f}, fragments={fragments})"
    return "NATURAL", 0.55, reason, metrics


def process_video(path):
    """
    Process video stream or file frame-by-frame with telemetry logging.
    """
    cap = cv2.VideoCapture(path)
    ret, prev_frame = cap.read()
    if not ret:
        print(f"Could not open or read video at '{path}'.")
        return []

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    frame_idx = 0
    alerts = []

    print(f"Processing video: {path}")
    print("=" * 70)

    while True:
        ret, curr_frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        # 1. Align current frame to previous frame
        aligned = align_frames(prev_gray, curr_gray)

        # 2. Extract change mask and contours
        mask, contours, raw_contours = compute_change_mask(prev_gray, aligned)

        # 3. Object detection on the current frame
        yolo_detections = []
        if MODEL is not None:
            results = MODEL.predict(curr_frame, verbose=False)[0]
            if results.boxes is not None:
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    if cls_id in TARGET_CLASSES:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        conf = float(box.conf[0])
                        yolo_detections.append({
                            "label": TARGET_CLASSES[cls_id],
                            "conf": conf,
                            "bbox": [x1, y1, x2, y2]
                        })

        # 4. Classify each changed region and log telemetry
        for c in contours:
            label, conf, reason, metrics = classify_change(c, yolo_detections, raw_contours)
            x, y, w, h = cv2.boundingRect(c)

            print(f"[Frame {frame_idx:04d}] Region at (x={x}, y={y}, w={w}, h={h}) -> {label} (conf: {conf:.2f})")
            print(f"    Reason:  {reason}")
            print(f"    Metrics: area={metrics['area']}, solidity={metrics['solidity']}, fragments={metrics['fragments']}, compactness={metrics['compactness']}, aspect_ratio={metrics['aspect_ratio']}, yolo={metrics['yolo_match']}")

            if label == "HUMAN":
                alert = {
                    "frame": frame_idx,
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "label": label,
                    "confidence": conf,
                    "reason": reason,
                    "metrics": metrics
                }
                alerts.append(alert)

        # 5. Chain forward: current frame becomes reference for next comparison
        prev_gray = curr_gray

    cap.release()
    print("=" * 70)
    print(f"Completed {frame_idx} frames. Generated {len(alerts)} human-caused alerts.")
    return alerts


def run_synthetic_smoke_test():
    """Run a smoke test on synthetic frames to verify pipeline without a video file."""
    print("No video provided - running synthetic smoke test instead.\n")
    frame1 = np.random.randint(80, 100, (300, 400), dtype=np.uint8)
    frame2 = frame1.copy()
    cv2.rectangle(frame2, (150, 120), (190, 220), 200, -1)  # Simulated human/solid blob

    mask, contours, raw_contours = compute_change_mask(frame1, frame2)
    print(f"Detected {len(contours)} changed region(s).")
    for c in contours:
        label, conf, reason, metrics = classify_change(c, yolo_detections=[], raw_contours=raw_contours)
        print(f"  -> Classified as {label} (confidence {conf:.2f})")
        print(f"     Reason:  {reason}")
        print(f"     Metrics: {metrics}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_video(sys.argv[1])
    else:
        run_synthetic_smoke_test()

