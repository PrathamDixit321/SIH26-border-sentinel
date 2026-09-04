# Border Sentinel 🛡️

**AI-Based Intelligent Video Analytics Platform for Border Surveillance**
Built for Smart India Hackathon 2026 — Problem Statement **SIH26187**
Organization: Ministry of Home Affairs | Track: Software

---

## 🚩 Problem

India's borders already have CCTV infrastructure, but most of it is only *watched* by humans — meaning intrusions, suspicious movement, or unusual activity can go unnoticed for hours. There's a need for an AI system that watches existing CCTV feeds automatically and alerts personnel in real time — without requiring new hardware.

## 💡 Solution

Border Sentinel AI continuously compares each new video frame against the most recent previous frame to detect *changes* in the scene, then classifies whether that change was caused by **human activity** (a person walking, digging, setting up a tent, a vehicle) or by **natural/environmental factors** (wind, foliage movement, shadows, animals). Only human-caused changes trigger real-time alerts.

## ⚙️ How It Works

1. **Frame Alignment** — ORB feature matching + homography (OpenCV) corrects for camera jitter so a shaking camera isn't mistaken for a "change."
2. **Change Detection** — pixel-level frame differencing + contour extraction highlights exactly where something changed.
3. **Object Detection** — YOLOv8 detects people and vehicles in the footage.
4. **Human vs Natural Classifier** — an explainable heuristic (fragmentation of the changed region + shape solidity + YOLO detections) labels each change.
5. **Adaptive Chaining** — each frame is compared against the *most recent* frame, not a fixed baseline, so gradual natural scene changes don't keep re-triggering alerts.
6. **Dashboard** — live feed, alert history, snapshot, and a plain-language reason for every alert.

## 🌟 What Makes This Different

Most existing CCTV-AI systems detect *that* something/someone is in frame. Border Sentinel AI reasons about *what changed since last time* and explicitly separates human-caused change from natural environmental change — reducing false alarms from wind/animals while catching genuine intrusions, using infrastructure that's already deployed.

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Computer Vision | OpenCV, YOLOv8 (Ultralytics) |
| Frame Alignment | ORB + Homography (OpenCV) |
| Classifier | Heuristic shape/motion analysis (optional fine-tuned ResNet18) |
| Backend | Python, FastAPI |
| Frontend | React |

## 📂 Project Structure
border-sentinel/

├── pipeline.py # Core CV pipeline: alignment, change detection, classification

├── step1_yolo_test.py # Standalone YOLOv8 sanity-check script

├── requirements.txt # Python dependencies

├── dashboard/ # React dashboard (frontend)

└── README.md

## 🚀 Getting Started

```bash
# Clone the repo
git clone https://github.com/PrathamDixit321/SIH26-border-sentinel.git
cd border-sentinel

# Install dependencies
pip install -r requirements.txt

# Run the smoke test (no video needed)
python3 pipeline.py

# Run on a real video file
python3 pipeline.py path/to/video.mp4
```

## 🎥 Demo

The core demo moment: showing the system correctly **ignore** natural motion (e.g. a waving branch) while correctly **flagging** human activity (a person walking through frame) — with a live side-by-side explanation of *why* each decision was made.

## 👥 Team Zero Coders

Pratham Dixit (TL), Yashvardhan Singh Jadon, Komal Verma, Mahi Nagoriya, Keshav Kundan, Yash Raj

## 📄 License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.
