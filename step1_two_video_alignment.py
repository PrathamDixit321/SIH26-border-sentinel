"""Stage 1: inspect alignment between a before and after video.

This script deliberately stops after frame reading and alignment.  It creates a
three-panel preview video:
    before frame | original after frame | after frame aligned to before

Run:
    python step1_two_video_alignment.py before.mp4 after.mp4
    python step1_two_video_alignment.py before.mp4 after.mp4 --preview
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


import math

ORB_FEATURES = 2_000
LOWE_RATIO = 0.75
MIN_GOOD_MATCHES = 15
MIN_INLIERS = 15
RANSAC_REPROJECTION_THRESHOLD = 4.0

_LAST_VALID_TRANSFORM: tuple[str, np.ndarray] | None = None


def reset_alignment_state() -> None:
    """Reset the cached transformation matrix between video runs."""
    global _LAST_VALID_TRANSFORM
    _LAST_VALID_TRANSFORM = None


def is_homography_sane(H: np.ndarray | None, width: int, height: int) -> bool:
    """Check that homography does not produce vanishing-line perspective singularities."""
    if H is None:
        return False
    # Perspective coefficients must be very small to avoid vanishing line intersecting the frame
    if abs(H[2, 0]) > 0.0015 or abs(H[2, 1]) > 0.0015:
        return False
    corners = np.float32([[0, 0], [width, 0], [width, height], [0, height]]).reshape(-1, 1, 2)
    warped = cv2.perspectiveTransform(corners, H)
    if warped is None or np.isnan(warped).any() or np.isinf(warped).any():
        return False
    warped_pts = warped.reshape(-1, 2)
    if not cv2.isContourConvex(np.int32(warped_pts).reshape(-1, 1, 2)):
        return False
    area = cv2.contourArea(warped_pts)
    orig_area = float(width * height)
    if area < 0.60 * orig_area or area > 1.50 * orig_area:
        return False
    return True


def is_affine_sane(M: np.ndarray | None, width: int, height: int) -> bool:
    """Check that affine transform scale and rotation angles are physically realistic for jitter."""
    if M is None:
        return False
    scale = math.sqrt(M[0, 0] ** 2 + M[0, 1] ** 2)
    angle = math.degrees(math.atan2(M[1, 0], M[0, 0]))
    if not (0.75 <= scale <= 1.30) or abs(angle) > 25.0:
        return False
    return True


def apply_transform(
    img: np.ndarray,
    transform_type: str,
    matrix: np.ndarray,
    target_w: int,
    target_h: int,
    border_mode: int = cv2.BORDER_CONSTANT,
    border_value: tuple[int, int, int] = (0, 0, 0),
) -> np.ndarray:
    """Apply either a perspective or affine warp cleanly without repeating edge pixels."""
    if transform_type == "H":
        return cv2.warpPerspective(
            img, matrix, (target_w, target_h), flags=cv2.INTER_LINEAR, borderMode=border_mode, borderValue=border_value
        )
    elif transform_type == "M":
        return cv2.warpAffine(
            img, matrix, (target_w, target_h), flags=cv2.INTER_LINEAR, borderMode=border_mode, borderValue=border_value
        )
    return img


def compute_valid_overlap_mask(
    transform_type: str, matrix: np.ndarray, target_w: int, target_h: int, margin: int = 12
) -> np.ndarray:
    """Return a binary mask of pixels that genuinely originate from the transformed after-frame."""
    ones = np.ones((target_h, target_w), dtype=np.uint8) * 255
    if transform_type == "H":
        mask = cv2.warpPerspective(
            ones, matrix, (target_w, target_h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0
        )
    else:
        mask = cv2.warpAffine(
            ones, matrix, (target_w, target_h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT, borderValue=0
        )
    if margin > 0:
        kernel = np.ones((margin, margin), dtype=np.uint8)
        mask = cv2.erode(mask, kernel)
    return mask


def align_after_to_before_with_mask(
    before_bgr: np.ndarray, after_bgr: np.ndarray
) -> tuple[np.ndarray, int, int, np.ndarray]:
    """Warp after_bgr into before_bgr perspective with clean seamless blending.

    Returns (clean_aligned_frame, num_matches, num_inliers, valid_overlap_mask).
    Non-overlapping margins are seamlessly filled with reference pixels instead of
    streaked BORDER_REPLICATE stripes to prevent broken pixels and false contours.
    """
    global _LAST_VALID_TRANSFORM
    target_h, target_w = before_bgr.shape[:2]
    if after_bgr.shape[:2] != (target_h, target_w):
        after_bgr = cv2.resize(after_bgr, (target_w, target_h))

    before_gray = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(after_bgr, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
    before_kp, before_des = orb.detectAndCompute(before_gray, None)
    after_kp, after_des = orb.detectAndCompute(after_gray, None)

    def fallback(good_count: int, inlier_count: int):
        if _LAST_VALID_TRANSFORM is not None:
            ttype, tmat = _LAST_VALID_TRANSFORM
            warped = apply_transform(after_bgr, ttype, tmat, target_w, target_h)
            vmask = compute_valid_overlap_mask(ttype, tmat, target_w, target_h)
            clean = np.where(vmask[:, :, None] > 0, warped, before_bgr)
            return clean, good_count, inlier_count, vmask
        full_mask = np.ones((target_h, target_w), dtype=np.uint8) * 255
        return after_bgr, good_count, inlier_count, full_mask

    if before_des is None or after_des is None:
        return fallback(0, 0)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    candidate_matches = matcher.knnMatch(after_des, before_des, k=2)
    good_matches = [
        first for first, second in candidate_matches
        if first.distance < LOWE_RATIO * second.distance
    ]
    if len(good_matches) < MIN_GOOD_MATCHES:
        return fallback(len(good_matches), 0)

    source_points = np.float32([after_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    destination_points = np.float32([before_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    # 1. Try Homography with strict geometric sanity checks
    homography, inlier_mask_h = cv2.findHomography(
        source_points,
        destination_points,
        cv2.RANSAC,
        RANSAC_REPROJECTION_THRESHOLD,
    )
    inliers_h = int(inlier_mask_h.sum()) if inlier_mask_h is not None else 0
    inlier_ratio_h = inliers_h / len(good_matches) if good_matches else 0.0
    if inliers_h >= MIN_INLIERS and inlier_ratio_h >= 0.18 and is_homography_sane(homography, target_w, target_h):
        _LAST_VALID_TRANSFORM = ("H", homography)
        warped = apply_transform(after_bgr, "H", homography, target_w, target_h)
        vmask = compute_valid_overlap_mask("H", homography, target_w, target_h)
        clean = np.where(vmask[:, :, None] > 0, warped, before_bgr)
        return clean, len(good_matches), inliers_h, vmask

    # 2. Try Partial Affine (rotation, translation, scale)
    M, inlier_mask_a = cv2.estimateAffinePartial2D(
        source_points,
        destination_points,
        method=cv2.RANSAC,
        ransacReprojThreshold=RANSAC_REPROJECTION_THRESHOLD,
    )
    inliers_a = int(inlier_mask_a.sum()) if inlier_mask_a is not None else 0
    if inliers_a >= 12 and is_affine_sane(M, target_w, target_h):
        _LAST_VALID_TRANSFORM = ("M", M)
        warped = apply_transform(after_bgr, "M", M, target_w, target_h)
        vmask = compute_valid_overlap_mask("M", M, target_w, target_h)
        clean = np.where(vmask[:, :, None] > 0, warped, before_bgr)
        return clean, len(good_matches), inliers_a, vmask

    # 3. Graceful fallback on occlusion
    return fallback(len(good_matches), max(inliers_h, inliers_a))


def align_after_to_before(before_bgr: np.ndarray, after_bgr: np.ndarray) -> tuple[np.ndarray, int, int]:
    """Backwards-compatible wrapper returning (aligned_frame, num_matches, num_inliers)."""
    aligned, matches, inliers, _ = align_after_to_before_with_mask(before_bgr, after_bgr)
    return aligned, matches, inliers


def labeled_panel(frame: np.ndarray, label: str) -> np.ndarray:
    panel = frame.copy()
    cv2.rectangle(panel, (0, 0), (panel.shape[1], 34), (20, 20, 20), -1)
    cv2.putText(panel, label, (10, 23), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (255, 255, 255), 2)
    return panel


def main(before_path: str, after_path: str, output_path: str, preview: bool, sample_fps: float) -> None:
    reset_alignment_state()
    before_cap = cv2.VideoCapture(before_path)
    after_cap = cv2.VideoCapture(after_path)
    if not before_cap.isOpened() or not after_cap.isOpened():
        raise RuntimeError("Could not open one or both input videos.")

    before_fps = before_cap.get(cv2.CAP_PROP_FPS) or 30.0
    after_fps = after_cap.get(cv2.CAP_PROP_FPS) or 30.0
    if sample_fps <= 0:
        raise ValueError("sample_fps must be greater than zero.")
    requested_output_fps = min(sample_fps, before_fps, after_fps)
    frame_interval = max(1, round(before_fps / requested_output_fps))
    # Match the preview duration to the before video even when FPS is not divisible.
    output_fps = before_fps / frame_interval

    ok, first_before = before_cap.read()
    if not ok:
        raise RuntimeError("The before video contains no readable frames.")
    height, width = first_before.shape[:2]
    before_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output),
        cv2.VideoWriter_fourcc(*"mp4v"),
        output_fps,
        (width * 3, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create preview video: {output}")

    print(f"Before: {before_path} ({before_fps:.2f} FPS)")
    print(f"After:  {after_path} ({after_fps:.2f} FPS)")
    print(f"Sampling at {output_fps:.1f} FPS (every {frame_interval} source frames).")
    window_name = "Stage 1 - Two-Video Alignment Monitor"
    if preview:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        disp_w = min(1440, width * 3)
        disp_h = int(height * (disp_w / (width * 3)))
        cv2.resizeWindow(window_name, disp_w, disp_h)
        print("Live preview window opened. Controls: [SPACE] Pause/Resume, [Q] Quit preview.")

    source_frame_index = 0
    processed_frames = 0
    while True:
        before_ok, before_frame = before_cap.read()
        after_ok, after_frame = after_cap.read()
        if not before_ok or not after_ok:
            break

        if source_frame_index % frame_interval != 0:
            source_frame_index += 1
            continue

        if before_frame.shape[:2] != (height, width):
            before_frame = cv2.resize(before_frame, (width, height))
        original_after = cv2.resize(after_frame, (width, height))
        aligned_after, matches, inliers = align_after_to_before(before_frame, original_after)

        aligned_label = f"After aligned | matches: {matches}, inliers: {inliers}"
        preview_frame = np.hstack((
            labeled_panel(before_frame, "Before (reference)"),
            labeled_panel(original_after, "After (original)"),
            labeled_panel(aligned_after, aligned_label),
        ))
        writer.write(preview_frame)

        if processed_frames % 30 == 0:
            print(f"Source frame {source_frame_index}: {matches} matches, {inliers} homography inliers")
        if preview:
            try:
                cv2.imshow(window_name, preview_frame)
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
    print(f"Saved {processed_frames} sampled preview frame(s) to: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 1: align an after video to a before video.")
    parser.add_argument("before_video", help="Path to the before/reference video")
    parser.add_argument("after_video", help="Path to the after video")
    parser.add_argument("--output", default="outputs/alignment_preview.mp4", help="Preview video path")
    parser.add_argument("--preview", action="store_true", dest="preview", default=True, help="Show live popup preview window (default: True)")
    parser.add_argument("--no-preview", action="store_false", dest="preview", help="Disable live popup preview window (save video only)")
    parser.add_argument("--sample-fps", type=float, default=3.0, help="Frames per second to process (default: 3)")
    arguments = parser.parse_args()
    main(arguments.before_video, arguments.after_video, arguments.output, arguments.preview, arguments.sample_fps)
