"""Stage 2: detect changed regions between two aligned videos.

This stage uses the alignment code from step1_two_video_alignment.py and adds
only frame differencing, thresholding, and contour extraction. It creates an
annotated preview and prints each frame's changed-region boxes and areas.

Run:
    python step2_change_detection.py before.mp4 after.mp4 --preview
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from step1_two_video_alignment import align_after_to_before, labeled_panel, reset_alignment_state


def detect_changed_regions(
    before_bgr: np.ndarray,
    aligned_after_bgr: np.ndarray,
    threshold: int,
    min_area: int,
    blur_size: int,
) -> tuple[np.ndarray, list[tuple[int, int, int, int, float]]]:
    """Return a cleaned binary difference mask and filtered changed regions."""
    before_gray = cv2.cvtColor(before_bgr, cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(aligned_after_bgr, cv2.COLOR_BGR2GRAY)
    before_blurred = cv2.GaussianBlur(before_gray, (blur_size, blur_size), 0)
    after_blurred = cv2.GaussianBlur(after_gray, (blur_size, blur_size), 0)

    difference = cv2.absdiff(before_blurred, after_blurred)
    _, mask = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)

    # Remove isolated pixels, then join nearby pixels belonging to one object.
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.dilate(mask, kernel, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        regions.append((x, y, width, height, area))
    regions.sort(key=lambda region: region[4], reverse=True)
    return mask, regions


def main(
    before_path: str,
    after_path: str,
    output_path: str,
    preview: bool,
    threshold: int,
    min_area: int,
    sample_fps: float,
) -> None:
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
    before_ok, first_before = before_cap.read()
    if not before_ok:
        raise RuntimeError("The before video contains no readable frames.")
    height, width = first_before.shape[:2]
    before_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), output_fps, (width * 3, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create preview video: {output}")

    print(f"Difference threshold: {threshold} | Minimum contour area: {min_area} px")
    print(f"Sampling at {output_fps:.1f} FPS (every {frame_interval} source frames).")
    print("Green boxes are changed regions. Press Q to quit preview mode.")

    window_name = "Stage 2 - Change Detection Surveillance Monitor"
    if preview:
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        disp_w = min(1440, width * 3)
        disp_h = int(height * (disp_w / (width * 3)))
        cv2.resizeWindow(window_name, disp_w, disp_h)
        print("Live preview window opened. Controls: [SPACE] Pause/Resume, [Q] Quit preview.")

    source_frame_index = 0
    processed_frames = 0
    frames_with_changes = 0
    total_regions = 0
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
        mask, regions = detect_changed_regions(
            before_frame, aligned_after, threshold, min_area, blur_size=5
        )

        annotated_after = aligned_after.copy()
        for x, y, region_width, region_height, area in regions:
            cv2.rectangle(
                annotated_after, (x, y), (x + region_width, y + region_height), (0, 255, 0), 2
            )
            cv2.putText(
                annotated_after,
                f"change: {area:.0f}px",
                (x, max(20, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (0, 255, 0),
                2,
            )

        mask_bgr = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
        combined = np.hstack((
            labeled_panel(before_frame, "Before (reference)"),
            labeled_panel(annotated_after, f"Aligned after | {len(regions)} changed region(s)"),
            labeled_panel(mask_bgr, f"Difference mask | {matches} matches, {inliers} inliers"),
        ))
        writer.write(combined)

        if regions:
            frames_with_changes += 1
            total_regions += len(regions)
            region_summary = ", ".join(
                f"({x}, {y}, {w}, {h}), area={area:.0f}"
                for x, y, w, h, area in regions
            )
            print(f"Source frame {source_frame_index} ({source_frame_index / before_fps:.2f}s): {region_summary}")

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
    print(f"Frames with changes: {frames_with_changes} | Total detected regions: {total_regions}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 2: extract changed regions from two videos.")
    parser.add_argument("before_video", help="Path to the before/reference video")
    parser.add_argument("after_video", help="Path to the after video")
    parser.add_argument("--output", default="outputs/change_detection_preview.mp4", help="Preview video path")
    parser.add_argument("--preview", action="store_true", dest="preview", default=True, help="Show live popup preview window (default: True)")
    parser.add_argument("--no-preview", action="store_false", dest="preview", help="Disable live popup preview window (save video only)")
    parser.add_argument("--threshold", type=int, default=35, help="Pixel difference threshold (default: 35)")
    parser.add_argument("--min-area", type=int, default=500, help="Minimum contour area in pixels (default: 500)")
    parser.add_argument("--sample-fps", type=float, default=3.0, help="Frames per second to process (default: 3)")
    arguments = parser.parse_args()
    main(
        arguments.before_video,
        arguments.after_video,
        arguments.output,
        arguments.preview,
        arguments.threshold,
        arguments.min_area,
        arguments.sample_fps,
    )
