"""
pipeline.py
Core border-surveillance pipeline:
  1. Align frame N to frame N-1 (ORB + homography) so camera jitter doesn't
     look like a "change"
  2. Compute a change mask between the aligned frames
  3. Run YOLOv8 object detection on the current frame
  4. Classify the change as HUMAN-CAUSED vs NATURAL using a simple, explainable
     heuristic (regularity of motion shape + whether YOLO detected a person/
     vehicle in that region)
  5. "Chain" comparisons: always compare against the MOST RECENT frame, not a
     fixed baseline, so natural scene drift (e.g. lighting, foliage) doesn't
     keep re-triggering alerts forever.

Run with:  python3 pipeline.py path/to/video.mp4
If no video is given, it runs on two synthetic test frames so you can verify
the logic works even before you have real footage.
"""

import sys
import cv2
import numpy as np
from ultralytics import YOLO

MODEL = YOLO("yolov8n.pt")  # auto-downloads pretrained COCO weights on first run


def align_frames(prev_gray, curr_gray):
    """Align curr to prev using ORB features + homography, to cancel out
    small camera-angle/jitter shifts before we compare pixels."""
    orb = cv2.ORB_create(500)
    kp1, des1 = orb.detectAndCompute(prev_gray, None)
    kp2, des2 = orb.detectAndCompute(curr_gray, None)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        return curr_gray  # not enough features to align (e.g. blank frames) - skip

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = matcher.match(des1, des2)
    matches = sorted(matches, key=lambda m: m.distance)[:80]

    if len(matches) < 8:
        return curr_gray

    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

    H, _ = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)
    if H is None:
        return curr_gray

    h, w = prev_gray.shape
    aligned = cv2.warpPerspective(curr_gray, H, (w, h))
    return aligned


def compute_change_mask(prev_gray, aligned_curr_gray, thresh=25):
    """Absolute frame difference + thresholding.
    Returns BOTH:
      - raw_contours: small individual blobs BEFORE heavy dilation, used to
        measure fragmentation (many tiny scattered blobs = wind/foliage-like)
      - merged_contours: the same blobs after dilation groups nearby ones into
        single regions, used to define the actual alert bounding boxes.
    Classifying fragmentation on the merged mask alone hides the very signal
    that separates human-shaped motion from scattered natural motion, so we
    keep both."""
    diff = cv2.absdiff(prev_gray, aligned_curr_gray)
    _, mask = cv2.threshold(diff, thresh, 255, cv2.THRESH_BINARY)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    raw_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    raw_contours = [c for c in raw_contours if cv2.contourArea(c) > 15]  # drop 1-pixel noise only

    merged_mask = cv2.dilate(mask, np.ones((9, 9), np.uint8), iterations=3)
    merged_contours, _ = cv2.findContours(merged_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    merged_contours = [c for c in merged_contours if cv2.contourArea(c) > 300]

    return merged_mask, merged_contours, raw_contours


def count_fragments_inside(contour, raw_contours):
    """How many of the small raw blobs fall inside this merged region's
    bounding box? Many small fragments -> scattered/natural. One or two
    large fragments -> a single solid human/object-shaped blob."""
    x, y, w, h = cv2.boundingRect(contour)
    count = 0
    for rc in raw_contours:
        rx, ry, rw, rh = cv2.boundingRect(rc)
        cx, cy = rx + rw / 2, ry + rh / 2
        if x <= cx <= x + w and y <= cy <= y + h:
            count += 1
    return count


def classify_change(contour, yolo_boxes_in_region, raw_contours):
    """
    Explainable heuristic classifier (no training needed for a hackathon):
      - If YOLO detected a person/vehicle overlapping this changed region -> HUMAN
      - Else, judge by TWO signals together:
          1. fragmentation: many small scattered blobs inside this region
             (leaves/branches moving independently) -> NATURAL
          2. solidity: a single compact, filled-in shape (a person/object
             silhouette) -> HUMAN
    Returns (label, confidence, reason_string) - the reason is what your
    dashboard should display for explainability.
    """
    if yolo_boxes_in_region:
        return "HUMAN", 0.9, f"YOLO detected {yolo_boxes_in_region[0]} in the changed region"

    area = cv2.contourArea(contour)
    hull = cv2.convexHull(contour)
    hull_area = cv2.contourArea(hull) if len(hull) >= 3 else area
    solidity = area / hull_area if hull_area > 0 else 0

    x, y, w, h = cv2.boundingRect(contour)
    aspect_ratio = w / h if h > 0 else 0

    fragments = count_fragments_inside(contour, raw_contours)

    if fragments >= 4:
        return "NATURAL", 0.7, f"{fragments} scattered independent blobs in this region - typical of wind/foliage"
    if solidity > 0.75 and 0.3 < aspect_ratio < 3.0:
        return "HUMAN", 0.6, f"single compact, regular-shaped blob (solidity={solidity:.2f})"
    return "NATURAL", 0.5, f"irregular shape, low solidity ({solidity:.2f})"


def process_video(path):
    cap = cv2.VideoCapture(path)
    ret, prev_frame = cap.read()
    if not ret:
        print("Could not read video.")
        return

    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    frame_idx = 0
    alerts = []

    while True:
        ret, curr_frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        # 1. Align current frame to the previous one
        aligned = align_frames(prev_gray, curr_gray)

        # 2. Change detection against the MOST RECENT frame (chained, adaptive baseline)
        mask, contours, raw_contours = compute_change_mask(prev_gray, aligned)

        # 3. Object detection on the raw current frame
        results = MODEL.predict(curr_frame, verbose=False)[0]
        detected_labels = [MODEL.names[int(c)] for c in results.boxes.cls] if results.boxes is not None else []

        # 4. Classify each changed region
        for c in contours:
            label, conf, reason = classify_change(c, detected_labels, raw_contours)
            if label == "HUMAN":
                x, y, w, h = cv2.boundingRect(c)
                alerts.append({
                    "frame": frame_idx,
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "label": label,
                    "confidence": conf,
                    "reason": reason,
                })

        # 5. Chain forward: this frame becomes the baseline for the next comparison
        prev_gray = curr_gray

    cap.release()
    print(f"Processed {frame_idx} frames. {len(alerts)} human-caused change alerts generated.")
    for a in alerts[:10]:
        print(a)
    return alerts


def run_synthetic_smoke_test():
    """No video? Prove the alignment + diff + classify logic runs correctly
    on two synthetic frames: one with a small rectangle 'person' added."""
    print("No video provided - running synthetic smoke test instead.\n")
    frame1 = np.random.randint(80, 100, (300, 400), dtype=np.uint8)  # background noise
    frame2 = frame1.copy()
    cv2.rectangle(frame2, (150, 120), (190, 220), 200, -1)  # a compact "person-shaped" blob

    mask, contours, raw_contours = compute_change_mask(frame1, frame2)
    print(f"Detected {len(contours)} changed region(s).")
    for c in contours:
        label, conf, reason = classify_change(c, yolo_boxes_in_region=[], raw_contours=raw_contours)
        print(f"  -> classified as {label} (confidence {conf}) because: {reason}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_video(sys.argv[1])
    else:
        run_synthetic_smoke_test()
