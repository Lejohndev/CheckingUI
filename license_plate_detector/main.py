import os

# Allow loading the trusted YOLO checkpoint created with older PyTorch/Ultralytics.
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")

from ultralytics import YOLO
import cv2
import numpy as np
import sys
from sort.sort import *
from util import get_car, read_license_plate, write_csv

results = {}
VEHICLE_TYPE_BY_CLASS_ID = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck",
}

# Khởi tạo tracker
mot_tracker = Sort()

# Load models
coco_model = YOLO('yolov8n.pt')

# LƯU Ý: THAY ĐỔI ĐƯỜNG DẪN DƯỚI ĐÂY THÀNH MODEL BIỂN SỐ CỦA BẠN
license_plate_detector = YOLO('./models/license_plate_detector.pt')
video_path = sys.argv[1] if len(sys.argv) > 1 else './sample.mp4'
csv_path = sys.argv[2] if len(sys.argv) > 2 else './test.csv'
# LƯU Ý: ĐỔI TÊN VIDEO CỦA BẠN VÀO ĐÂY
cap = cv2.VideoCapture(video_path)


vehicles = [2, 3, 5, 7]


def calculate_iou(box_a, box_b):
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])

    if x_right <= x_left or y_bottom <= y_top:
        return 0

    intersection = (x_right - x_left) * (y_bottom - y_top)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return intersection / float(area_a + area_b - intersection)


def get_vehicle_type(track, detections_with_types):
    if len(track) == 0:
        return "unknown"

    track_box = track[:4]
    best_type = "unknown"
    best_iou = 0
    for detection in detections_with_types:
        iou = calculate_iou(track_box, detection["bbox"])
        if iou > best_iou:
            best_iou = iou
            best_type = detection["vehicle_type"]

    return best_type if best_iou > 0.1 else "unknown"

# Đọc frame
frame_nmr = -1
ret = True
while ret:
    frame_nmr += 1
    ret, frame = cap.read()
    if ret:
        results[frame_nmr] = {}
        
        # 1. Phát hiện phương tiện
        detections = coco_model(frame, device=0)[0]
        detections_ = []
        detections_with_types = []
        for detection in detections.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = detection
            if int(class_id) in vehicles:
                detections_.append([x1, y1, x2, y2, score])
                detections_with_types.append({
                    "bbox": [x1, y1, x2, y2],
                    "vehicle_type": VEHICLE_TYPE_BY_CLASS_ID.get(int(class_id), "unknown"),
                })

        # 2. Theo dõi phương tiện (Tracking)
        if len(detections_) == 0:
            track_ids = np.empty((0, 5))
        else:
            track_ids = mot_tracker.update(np.asarray(detections_))

        # 3. Phát hiện biển số
        license_plates = license_plate_detector(frame)[0]
        for license_plate in license_plates.boxes.data.tolist():
            x1, y1, x2, y2, score, class_id = license_plate

            # 4. Gắn biển số vào phương tiện tương ứng
            xcar1, ycar1, xcar2, ycar2, car_id = get_car(license_plate, track_ids)
            vehicle_type = get_vehicle_type([xcar1, ycar1, xcar2, ycar2, car_id], detections_with_types)

           
            if car_id == -1:
                
                xcar1, ycar1, xcar2, ycar2 = x1, y1, x2, y2
                car_id = f"unknown_{frame_nmr}_{int(x1)}" 
                vehicle_type = "unknown"
            if True: 
                # Cắt ảnh biển số
                license_plate_crop = frame[int(y1):int(y2), int(x1): int(x2), :]

                # Phóng to ảnh lên để dễ đọc
                license_plate_crop_resized = cv2.resize(license_plate_crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

              
                gray_crop = cv2.cvtColor(license_plate_crop_resized, cv2.COLOR_BGR2GRAY)
                
             
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                license_plate_crop_clahe = clahe.apply(gray_crop)
            

              
                license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_clahe)

                if license_plate_text is not None:
                    print(f"[OK] Frame {frame_nmr} | Vehicle ID {car_id} | Plate: {license_plate_text} (Score: {license_plate_text_score:.2f})")
                    results[frame_nmr][car_id] = {'car': {'bbox': [xcar1, ycar1, xcar2, ycar2],
                                                          'vehicle_type': vehicle_type},
                                                  'license_plate': {'bbox': [x1, y1, x2, y2],
                                                                    'text': license_plate_text,
                                                                    'bbox_score': score,
                                                                    'text_score': license_plate_text_score}}
                else:
                    print(f"[NO OCR] Frame {frame_nmr} | Vehicle ID {car_id} | Cannot read plate clearly.")

# Ghi kết quả ra CSV
write_csv(results, csv_path)
print(f"Data saved to {csv_path}")
