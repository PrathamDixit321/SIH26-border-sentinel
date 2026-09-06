"""
STEP 1 — Confirm object detection works on your own footage.
Run: python step1_yolo_test.py your_video.mp4
This proves your environment + YOLO pipeline works before building anything else.
"""
import sys
from ultralytics import YOLO

def main(video_path: str):
    model = YOLO("yolov8n.pt")  # auto-downloads pretrained weights on first run
    results = model.predict(
        source=video_path,
        save=True,          # saves annotated output video to runs/detect/predict/
        conf=0.35,           # confidence threshold — lower if it misses obvious people
        classes=[0, 2, 3, 5, 7],  # COCO ids: person, car, motorcycle, bus, truck
    )
    print(f"Done. Check runs/detect/predict/ for the annotated output video.")
    print(f"Processed {len(results)} frames.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python step1_yolo_test.py <path_to_video>")
        sys.exit(1)
    main(sys.argv[1])
