import io
import time
import math
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

class VideoStreamGenerator:
    def __init__(self):
        self.width = 640
        self.height = 360
        self.frame_count = 0
        self.target_x = 100.0
        self.target_dir = 1.0

    def generate_frame(self, camera_id: str = "CAM-01") -> bytes:
        self.frame_count += 1
        t = time.time()

        # Target animation
        self.target_x += self.target_dir * 2.5
        if self.target_x > 500:
            self.target_dir = -1.0
        elif self.target_x < 80:
            self.target_dir = 1.0

        target_y = int(self.height * 0.62 + math.sin(self.frame_count * 0.2) * 3)

        img = Image.new("RGB", (self.width, self.height), color=(14, 20, 24))
        draw = ImageDraw.Draw(img)

        # Tactical background: ground & terrain
        ground_y = int(self.height * 0.65)
        draw.rectangle([(0, ground_y), (self.width, self.height)], fill=(22, 30, 36))

        # Distant terrain
        draw.polygon([(0, ground_y), (160, int(self.height * 0.45)), (320, ground_y)], fill=(16, 24, 30))
        draw.polygon([(260, ground_y), (460, int(self.height * 0.40)), (640, ground_y)], fill=(18, 27, 33))

        # Geofence Perimeter Fence Wire & Posts
        fence_top = int(self.height * 0.54)
        fence_bottom = int(self.height * 0.76)
        for post_x in range(30, self.width, 50):
            draw.line([(post_x, fence_top), (post_x, fence_bottom)], fill=(45, 60, 75), width=2)
        draw.line([(0, int(self.height * 0.58)), (self.width, int(self.height * 0.58))], fill=(50, 75, 95), width=1)
        draw.line([(0, int(self.height * 0.70)), (self.width, int(self.height * 0.70))], fill=(50, 75, 95), width=1)

        # Virtual Tripwire Overlay (Glowing Cyan/Amber Line)
        wire_y = int(self.height * 0.68)
        draw.line([(0, wire_y), (self.width, wire_y)], fill=(0, 240, 255), width=2)
        draw.text((15, wire_y - 14), "RESTRICTED GEOFENCE // TRIPWIRE TW-01", fill=(0, 240, 255))

        # Foliage simulation (Left side - swaying)
        foliage_sway = int(math.sin(self.frame_count * 0.3) * 6)
        draw.ellipse([(60 + foliage_sway, ground_y - 70), (140 + foliage_sway, ground_y + 10)], fill=(24, 45, 36), outline=(30, 70, 50))
        draw.text((70 + foliage_sway, ground_y - 82), "AMBIENT FOLIAGE", fill=(80, 180, 120))

        # Moving Target: Human Silhouette
        tx = int(self.target_x)
        ty = target_y - 70
        tw, th = 38, 75

        # Target bounding box (RED when crossed wire, AMBER before)
        is_crossed = (ty + th) >= wire_y
        box_color = (255, 45, 45) if is_crossed else (255, 180, 20)

        # Draw bipedal silhouette
        head_radius = 8
        draw.ellipse([(tx + tw//2 - head_radius, ty), (tx + tw//2 + head_radius, ty + head_radius*2)], fill=(55, 45, 45))
        draw.rectangle([(tx + 10, ty + 18), (tx + tw - 10, ty + 48)], fill=(65, 50, 50)) # Torso
        draw.line([(tx + 14, ty + 48), (tx + 8, ty + th)], fill=(65, 50, 50), width=4) # Left leg
        draw.line([(tx + tw - 14, ty + 48), (tx + tw - 8, ty + th)], fill=(65, 50, 50), width=4) # Right leg

        # Bounding box & Corner Brackets
        draw.rectangle([(tx, ty), (tx + tw, ty + th)], outline=box_color, width=2)
        cl = 8
        draw.line([(tx, ty), (tx + cl, ty)], fill=box_color, width=3)
        draw.line([(tx, ty), (tx, ty + cl)], fill=box_color, width=3)
        draw.line([(tx + tw, ty), (tx + tw - cl, ty)], fill=box_color, width=3)
        draw.line([(tx + tw, ty), (tx + tw, ty + cl)], fill=box_color, width=3)

        # Tag above target
        draw.rectangle([(tx - 6, ty - 22), (tx + tw + 34, ty - 4)], fill=(12, 16, 20))
        label_text = f"TARGET: HUMAN [0.96]" if is_crossed else "TRACK #01 [0.88]"
        draw.text((tx - 2, ty - 20), label_text, fill=box_color)

        # Top HUD Banner
        draw.rectangle([(0, 0), (self.width, 32)], fill=(10, 14, 18))
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((12, 8), f"LIVE // {camera_id} - SECTOR 4 [HOMOGRAPHY: LOCKED]", fill=(0, 230, 200))
        draw.text((self.width - 200, 8), f"{now_str} IST", fill=(200, 220, 230))

        # Bottom HUD Telemetry
        draw.rectangle([(0, self.height - 24), (self.width, self.height)], fill=(10, 14, 18))
        draw.text((12, self.height - 18), "FPS: 28.4 | JITTER: 0.02px | ADAPTIVE BASELINE: ACTIVE", fill=(130, 160, 180))
        status_color = (255, 50, 50) if is_crossed else (0, 230, 150)
        status_msg = "ALERT: RESTRICTED BUFFER INTRUSION" if is_crossed else "MONITORING // PERIMETER CLEAR"
        draw.text((self.width - 260, self.height - 18), status_msg, fill=status_color)

        # Reticle center
        cx, cy = self.width // 2, self.height // 2
        draw.line([(cx - 15, cy), (cx + 15, cy)], fill=(40, 60, 75), width=1)
        draw.line([(cx, cy - 15), (cx, cy + 15)], fill=(40, 60, 75), width=1)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        return buf.getvalue()

stream_generator = VideoStreamGenerator()

def mjpeg_stream(camera_id: str = "CAM-01"):
    while True:
        frame_bytes = stream_generator.generate_frame(camera_id=camera_id)
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.045)  # ~22 FPS
