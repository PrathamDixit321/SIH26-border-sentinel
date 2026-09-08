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
from collections import deque
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
CLAHE = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))


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


def compute_change_mask(prev_gray, aligned_curr_gray, thresh=28, blur_ksize=5, border_margin=18, min_area=600, min_dim=30):
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

    merged_mask = cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=2)
    merged_contours, _ = cv2.findContours(merged_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter using adaptive min_area and min_dim
    merged_contours = [
        c for c in merged_contours
        if cv2.contourArea(c) >= min_area and max(cv2.boundingRect(c)[2], cv2.boundingRect(c)[3]) >= min_dim
    ]

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


class SceneTracker:
    """
    Tracks detected motion regions across temporal frames to distinguish:
      - Stationary parked cars / surface reflections (zero displacement over multiple frames).
      - Moving pedestrians (compact moving targets with active spatial displacement).
      - Moving vehicles and sweeping headlight beams (large scale + active displacement).
    """
    def __init__(self, max_dist=40):
        self.tracks = {}
        self.next_id = 0
        self.max_dist = max_dist

    def update(self, detections, frame_idx):
        assigned = set()
        matched = []

        for d in detections:
            x, y, w, h, area, sol, frags, ar, contour = d
            cx, cy = x + w / 2.0, y + h / 2.0

            best_id = None
            min_dist = self.max_dist

            for tid, t in self.tracks.items():
                if tid in assigned:
                    continue
                dist = np.hypot(cx - t["cx"], cy - t["cy"])
                if dist < min_dist:
                    min_dist = dist
                    best_id = tid

            if best_id is not None:
                assigned.add(best_id)
                t = self.tracks[best_id]
                t["cx"] = cx
                t["cy"] = cy
                t["frames"] += 1
                t["disp"] = np.hypot(cx - t["init_cx"], cy - t["init_cy"])
                t["bbox"] = (x, y, w, h)
                t["area"] = area
                t["sol"] = sol
                t["frags"] = frags
                t["ar"] = ar
                t["contour"] = contour
                t["last_frame"] = frame_idx
                matched.append(t)
            else:
                tid = self.next_id
                self.next_id += 1
                new_track = {
                    "id": tid,
                    "init_cx": cx, "init_cy": cy,
                    "cx": cx, "cy": cy,
                    "frames": 1,
                    "disp": 0.0,
                    "bbox": (x, y, w, h),
                    "area": area,
                    "sol": sol,
                    "frags": frags,
                    "ar": ar,
                    "contour": contour,
                    "last_frame": frame_idx
                }
                self.tracks[tid] = new_track
                assigned.add(tid)
                matched.append(new_track)

        # Purge stale tracks (not seen in last 12 frames)
        stale = [tid for tid, t in self.tracks.items() if frame_idx - t["last_frame"] > 12]
        for tid in stale:
            del self.tracks[tid]

        return matched


def classify_track(track, yolo_detections, is_high_altitude=False):
    """
    Classifies a tracked region into distinct operational categories:
      1. HUMAN (Pedestrian) [RED BOX]
      2. HUMAN (Vehicle / Headlight) [AMBER BOX]
      3. NATURAL (Trees / Wind Foliage) [GREEN BOX]
      4. STATIC (Parked Car / Reflection) [GRAY BOX]
    """
    x, y, w, h = track["bbox"]
    area = track["area"]
    solidity = track["sol"]
    fragments = track["frags"]
    aspect_ratio = track["ar"]
    disp = track["disp"]
    frames = track["frames"]

    metrics = {
        "area": round(area, 1),
        "solidity": round(solidity, 3),
        "fragments": fragments,
        "aspect_ratio": round(aspect_ratio, 2),
        "displacement": round(disp, 1),
        "frames_tracked": frames,
        "yolo_match": None
    }

    # 1. Spatial YOLO match
    for det in yolo_detections:
        overlap = check_bbox_overlap((x, y, w, h), det["bbox"])
        if overlap > 0.15:
            metrics["yolo_match"] = det["label"]
            reason = f"YOLO detected {det['label']} ({det['conf']:.2f}) in region"
            return "HUMAN", 0.95, reason, metrics, "PEDESTRIAN"

    # 2. Stationary Parked Vehicle / Ground Reflection:
    # Has lived for multiple frames but its centroid has virtually zero displacement (< 14px)
    if frames >= 12 and disp < 14.0:
        reason = f"Stationary parked car / surface reflection (displacement={disp:.1f}px over {frames} frames)"
        return "STATIC", 0.90, reason, metrics, "PARKED_CAR"

    # 3. Moving Vehicle or Sweeping Headlight Illumination:
    # Large moving surface or illumination traversing the roadway
    if area >= 2200 and (disp >= 20.0 or aspect_ratio >= 1.2):
        reason = f"Vehicle or headlight beam moving (area={area:.0f}px, displacement={disp:.1f}px)"
        return "HUMAN", 0.85, reason, metrics, "VEHICLE"

    # 4. Wind / Tree Foliage Motion:
    # Multi-fragment scattering or low solidity
    if fragments >= 3 or (fragments >= 2 and area > 800) or solidity < 0.65:
        reason = f"Tree foliage/wind movement ({fragments} fragments, solidity={solidity:.2f})"
        return "NATURAL", 0.85, reason, metrics, "TREES"

    # 5. Walking Pedestrian:
    # Compact target with active displacement trajectory or human profile
    if is_high_altitude:
        is_pedestrian = (0.20 <= aspect_ratio <= 0.95 and h >= 18 and solidity >= 0.70) or disp >= 20.0
    else:
        is_pedestrian = (0.15 <= aspect_ratio <= 0.85 and h >= 45 and solidity >= 0.70) or disp >= 25.0

    if is_pedestrian and solidity >= 0.68:
        reason = f"Moving pedestrian (displacement={disp:.1f}px, h={h}px, solidity={solidity:.2f})"
        return "HUMAN", 0.80, reason, metrics, "PEDESTRIAN"

    reason = f"Ambient/foliage movement (solidity={solidity:.2f}, AR={aspect_ratio:.2f})"
    return "NATURAL", 0.60, reason, metrics, "TREES"


def process_video(path, show_live=True):
    """
    Process video stream or file frame-by-frame with telemetry logging
    and real-time on-screen visual detection overlay.
    """
    cap = cv2.VideoCapture(path)
    ret, prev_frame = cap.read()
    if not ret:
        print(f"Could not open or read video at '{path}'.")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS)
    fps = fps if fps > 0 else 30.0
    delay_ms = max(1, int(1000 / fps))

    # Normalize temporal stride across camera frame rates (~80-100ms window)
    stride = max(1, round(fps / 12.0))

    # Sample initial lighting level to detect darkness/night conditions
    init_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    mean_lum = float(np.mean(init_gray))
    is_low_light = mean_lum < 55.0
    is_high_altitude = is_low_light or (fps > 45.0)

    # Adaptive CV parameters
    thresh = 18 if is_low_light else 28
    min_area = 220 if is_high_altitude else 600
    min_dim = 16 if is_high_altitude else 30

    print(f"Processing video: {path}")
    print(f"FPS: {fps:.1f} | Dynamic Stride: {stride} frames (~{stride/fps*1000:.1f}ms window)")
    if is_low_light:
        print(f"[NIGHT VISION ENGAGED] Low-light scene detected (Mean Lum: {mean_lum:.1f}/255). CLAHE contrast boost enabled.")
    if is_high_altitude:
        print(f"[HIGH-ALTITUDE PERSPECTIVE MODE] Scaled for distant targets & high elevations (e.g. 12th floor).")
    print("Controls: Press [SPACE] to pause/resume, [Q] to exit live view.")
    print("=" * 70)

    tracker = SceneTracker()
    frame_buffer = deque(maxlen=stride + 1)
    frame_idx = 0
    alerts = []

    while True:
        ret, curr_frame = cap.read()
        if not ret:
            break
        frame_idx += 1
        curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)

        # Apply CLAHE contrast boost in darkness
        if is_low_light:
            processed_gray = CLAHE.apply(curr_gray)
        else:
            processed_gray = curr_gray

        frame_buffer.append(processed_gray)
        if len(frame_buffer) <= stride:
            continue

        ref_gray = frame_buffer[0]

        # 1. Align current frame to the reference frame
        aligned = align_frames(ref_gray, processed_gray)

        # 2. Extract change mask and contours with adaptive parameters
        mask, contours, raw_contours = compute_change_mask(
            ref_gray, aligned, thresh=thresh, min_area=min_area, min_dim=min_dim
        )

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

        # Visualization frame
        display_frame = curr_frame.copy() if show_live else None

        # Build raw detection tuples for tracking
        raw_dets = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            hull = cv2.convexHull(c)
            h_area = cv2.contourArea(hull) if len(hull) >= 3 else area
            sol = area / h_area if h_area > 0 else 0
            ar = float(w) / h if h > 0 else 1.0
            frags = count_fragments_inside(c, raw_contours)
            raw_dets.append((x, y, w, h, area, sol, frags, ar, c))

        # Update scene tracks across frames
        tracked_objects = tracker.update(raw_dets, frame_idx)

        # 4. Classify tracked objects
        for track in tracked_objects:
            label, conf, reason, metrics, category = classify_track(
                track, yolo_detections, is_high_altitude=is_high_altitude
            )
            x, y, w, h = track["bbox"]

            print(f"[Frame {frame_idx:04d}] Track #{track['id']:02d} at ({x},{y},{w},{h}) -> {label} [{category}] (conf: {conf:.2f})")
            print(f"    Reason:  {reason}")
            print(f"    Metrics: area={metrics['area']}, sol={metrics['solidity']}, disp={metrics['displacement']}px, frames={metrics['frames_tracked']}, frags={metrics['fragments']}")

            if label == "HUMAN":
                alert = {
                    "frame": frame_idx,
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "label": label,
                    "category": category,
                    "confidence": conf,
                    "reason": reason,
                    "metrics": metrics
                }
                alerts.append(alert)

            # Visual overlay by category
            if show_live:
                if category == "PEDESTRIAN":
                    # RED for Walking Pedestrian
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(display_frame, f"HUMAN: Pedestrian ({conf:.2f})", (x, max(18, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 255), 2)
                elif category == "VEHICLE":
                    # AMBER/GOLD for Moving Vehicle or Headlight
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 215, 255), 2)
                    cv2.putText(display_frame, f"VEHICLE/HEADLIGHT ({conf:.2f})", (x, max(18, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 215, 255), 2)
                elif category == "TREES":
                    # GREEN for Trees / Wind Foliage
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 230, 0), 1)
                    cv2.putText(display_frame, f"TREES/WIND ({conf:.2f})", (x, max(18, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 230, 0), 1)
                elif category == "PARKED_CAR":
                    # MUTED GRAY for Stationary Parked Cars
                    cv2.rectangle(display_frame, (x, y), (x + w, y + h), (140, 140, 140), 1)
                    cv2.putText(display_frame, "PARKED CAR (Static)", (x, max(18, y - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.35, (180, 180, 180), 1)

        # 5. Live HUD and interactive window
        if show_live:
            # Top HUD bar
            cv2.rectangle(display_frame, (0, 0), (display_frame.shape[1], 34), (25, 25, 25), -1)
            mode_badge = " [NIGHT VISION]" if is_low_light else ""
            hud_text = f"Border Sentinel AI{mode_badge} | Frame: {frame_idx} | Active Alerts: {len(alerts)}"
            cv2.putText(display_frame, hud_text, (10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)
            cv2.putText(display_frame, "[SPACE] Pause  [Q] Quit", (display_frame.shape[1] - 180, 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (180, 180, 180), 1)

            try:
                cv2.imshow("Border Sentinel AI - Live Surveillance Monitor", display_frame)
                key = cv2.waitKey(delay_ms) & 0xFF
                if key == ord('q'):
                    print("\n[INFO] Playback closed by user.")
                    break
                elif key == ord(' '):
                    print("\n[PAUSED] Press any key to resume...")
                    cv2.waitKey(-1)
            except cv2.error:
                show_live = False

    cap.release()
    if show_live:
        try:
            cv2.destroyAllWindows()
        except cv2.error:
            pass

    print("=" * 70)
    print(f"Completed {frame_idx} frames. Generated {len(alerts)} human/vehicle alerts.")
    return alerts


def run_synthetic_smoke_test():
    """Run a smoke test on synthetic frames to verify pipeline without a video file."""
    print("No video provided - running synthetic smoke test instead.\n")
    frame1 = np.random.randint(80, 100, (300, 400), dtype=np.uint8)
    frame2 = frame1.copy()
    cv2.rectangle(frame2, (150, 120), (190, 220), 200, -1)  # Simulated human/solid blob

    mask, contours, raw_contours = compute_change_mask(frame1, frame2)
    print(f"Detected {len(contours)} changed region(s).")
    tracker = SceneTracker()
    raw_dets = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = cv2.contourArea(c)
        raw_dets.append((x, y, w, h, area, 1.0, 1, 0.5, c))
    tracked = tracker.update(raw_dets, 1)
    for t in tracked:
        label, conf, reason, metrics, cat = classify_track(t, yolo_detections=[])
        print(f"  -> Classified as {label} [{cat}] (confidence {conf:.2f})")
        print(f"     Reason:  {reason}")
        print(f"     Metrics: {metrics}\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_video(sys.argv[1])
    else:
        run_synthetic_smoke_test()


