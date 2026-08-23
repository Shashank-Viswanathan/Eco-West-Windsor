import os
from datetime import datetime
import cv2
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
import pandas as pd
from ultralytics import YOLO

VIDEO_PATH = "garden_test.mp4" 
OUTPUT_CSV = "bee_visit_data.csv"
CROPS_FOLDER = "bee_crops"
FPS = 30  
RE_ENTRY_SECONDS = 15  
MIN_VISIT_FRAMES = 5 

os.makedirs(CROPS_FOLDER, exist_ok=True)

def get_video_timestamp(filepath):
    """Attempts to extract creation date from MP4 metadata, defaults to current time if missing."""
    try:
        parser = createParser(filepath)
        if parser:
            with parser:
                metadata = extractMetadata(parser)
                if metadata and metadata.has("creation_date"):
                    return str(metadata.get("creation_date"))
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


print("--- ENTER PATCH METADATA ---")
auto_timestamp = get_video_timestamp(VIDEO_PATH)
print(f"Detected Video Timestamp: {auto_timestamp}")

user_time = (
    input(
        f"Timestamp & Date [Press Enter to use '{auto_timestamp}']: "
    ).strip()
    or auto_timestamp
)
temp_weather = input(
    "Temperature & Weather (e.g., 78F, Sunny / 22C, Part Cloud): "
).strip()
patch_area = input("Patch Area in m^2 (e.g., 1.5): ").strip()
floral_type = input(
    "Floral Richness & Type (e.g., High - Coneflower, Milkweed): "
).strip()
nesting_prox = input(
    "Nesting Proximity (e.g., 2m to bare soil, 5m to wood pile): "
).strip()
lego_scale = input("LEGO Ring Scale in cm (e.g., 15): ").strip()
cam_angle = input(
    "Camera Height & Angle (e.g., 1m height, 45-deg downward): "
).strip()
print("\nLoading vision model...")
model = YOLO("yolov8n.pt")

cap = cv2.VideoCapture(VIDEO_PATH)
if not cap.isOpened():
    print(f"Error: Could not open video file '{VIDEO_PATH}'. Check file path.")
    exit()

print(f"Processing video '{VIDEO_PATH}'...")

bee_tracks = {}
frame_count = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    results = model.track(
        frame, persist=True, tracker="bytetrack.yaml", verbose=False
    )

    if results[0].boxes.id is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        track_ids = results[0].boxes.id.int().cpu().tolist()

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = map(int, box)

        
            h, w, _ = frame.shape
            pad = 10
            crop_x1, crop_y1 = max(0, x1 - pad), max(0, y1 - pad)
            crop_x2, crop_y2 = min(w, x2 + pad), min(h, y2 + pad)
            cropped_img = frame[crop_y1:crop_y2, crop_x1:crop_x2]

            if track_id not in bee_tracks:
                bee_tracks[track_id] = {
                    "first_frame": frame_count,
                    "last_frame": frame_count,
                    "crop": cropped_img,
                }
            else:
                bee_tracks[track_id]["last_frame"] = frame_count
                bee_tracks[track_id]["crop"] = cropped_img

cap.release()
raw_visits = []

for track_id, data in bee_tracks.items():
    duration = data["last_frame"] - data["first_frame"] + 1

    if duration >= MIN_VISIT_FRAMES:
        crop_filename = os.path.join(CROPS_FOLDER, f"bee_track_{track_id}.jpg")
        cv2.imwrite(crop_filename, data["crop"])

        raw_visits.append(
            {
                "video_file": VIDEO_PATH,
                "timestamp_date": user_time,
                "temperature_weather": temp_weather,
                "patch_area_m2": patch_area,
                "floral_richness_type": floral_type,
                "nesting_proximity": nesting_prox,
                "lego_ring_scale_cm": lego_scale,
                "camera_height_angle": cam_angle,
                "track_id": track_id,
                "first_frame": data["first_frame"],
                "last_frame": data["last_frame"],
                "duration_seconds": round(duration / FPS, 2),
                "crop_image": crop_filename,
            }
        )

raw_visits = sorted(raw_visits, key=lambda x: x["first_frame"])

MAX_GAP_FRAMES = RE_ENTRY_SECONDS * FPS
filtered_events = []
current_event_id = 1
last_seen_frame = -999999

for visit in raw_visits:
    gap = visit["first_frame"] - last_seen_frame

    if gap <= MAX_GAP_FRAMES and len(filtered_events) > 0:
        visit["unique_bee_event_id"] = filtered_events[-1][
            "unique_bee_event_id"
        ]
        visit["visit_type"] = "Re-entry / Repeat Visit"
    else:
        visit["unique_bee_event_id"] = f"BEE_EVENT_{current_event_id:03d}"
        current_event_id += 1
        visit["visit_type"] = "New Unique Individual"

    last_seen_frame = visit["last_frame"]
    filtered_events.append(visit)
df_new = pd.DataFrame(filtered_events)
if os.path.exists(OUTPUT_CSV):
    df_existing = pd.read_csv(OUTPUT_CSV)
    df_final = pd.concat([df_existing, df_new], ignore_index=True)
else:
    df_final = df_new

df_final.to_csv(OUTPUT_CSV, index=False)

unique_count = (
    len(set(d["unique_bee_event_id"] for d in filtered_events))
    if filtered_events
    else 0
)

print("\n--- PROCESSING COMPLETE ---")
print(f"Total Video Frames Processed: {frame_count}")
print(f"Raw Insect Tracks Detected: {len(raw_visits)}")
print(f"Final Count of Unique Bee Events: {unique_count}")
print(f"All tracking data and patch metadata appended to: '{OUTPUT_CSV}'")
print(f"Cropped photos saved to folder: '{CROPS_FOLDER}/'")
