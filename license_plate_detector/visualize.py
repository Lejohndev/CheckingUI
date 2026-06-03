import ast
import cv2
import numpy as np
import pandas as pd
import sys
def draw_dashed_rectangle(img, pt1, pt2, color, thickness=2, dash_length=15):
    """
    Hàm vẽ khung hình chữ nhật nét đứt (Dashed Rectangle)
    """
    x1, y1 = pt1
    x2, y2 = pt2
    
    # Vẽ viền trên và dưới
    for x in range(x1, x2, dash_length * 2):
        cv2.line(img, (x, y1), (min(x + dash_length, x2), y1), color, thickness)
        cv2.line(img, (x, y2), (min(x + dash_length, x2), y2), color, thickness)
        
    # Vẽ viền trái và phải
    for y in range(y1, y2, dash_length * 2):
        cv2.line(img, (x1, y), (x1, min(y + dash_length, y2)), color, thickness)
        cv2.line(img, (x2, y), (x2, min(y + dash_length, y2)), color, thickness)
        
    return img
video_in = sys.argv[1] if len(sys.argv) > 1 else 'sample.mp4'
csv_in = sys.argv[2] if len(sys.argv) > 2 else './test_interpolated.csv'
video_out = sys.argv[3] if len(sys.argv) > 3 else './out.mp4'
results = pd.read_csv(csv_in)
# Nếu không có file test_interpolated.csv, bạn đổi lại thành test.csv nhé
results['license_number_score'] = pd.to_numeric(results['license_number_score'], errors='coerce').fillna(0)

# load video
video_path = 'sample.mp4'
cap = cv2.VideoCapture(video_in)

fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Specify the codec
fps = cap.get(cv2.CAP_PROP_FPS)
width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
out = cv2.VideoWriter(video_out, fourcc, fps, (width, height))

# Chiều cao của ảnh biển số sau khi zoom (Gốc là 400, thu nhỏ lại còn 150)
ZOOM_H = 150 
TEXT_BG_H = 70 # Chiều cao của nền trắng chứa chữ

license_plate = {}
for car_id in np.unique(results['car_id']):
    max_ = np.amax(results[results['car_id'] == car_id]['license_number_score'])
    license_plate[car_id] = {'license_crop': None,
                             'license_plate_number': results[(results['car_id'] == car_id) &
                                                             (results['license_number_score'] == max_)]['license_number'].iloc[0]}
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, results[(results['car_id'] == car_id) &
                                             (results['license_number_score'] == max_)]['frame_nmr'].iloc[0])
    ret, frame = cap.read()

    if not ret or frame is None:
        continue

    x1, y1, x2, y2 = ast.literal_eval(results[(results['car_id'] == car_id) &
                                              (results['license_number_score'] == max_)]['license_plate_bbox'].iloc[0].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ','))

    try:
        license_crop = frame[int(y1):int(y2), int(x1):int(x2), :]
        # Thu nhỏ kích thước crop theo biến ZOOM_H
        license_crop = cv2.resize(license_crop, (int((x2 - x1) * ZOOM_H / (y2 - y1)), ZOOM_H))
        license_plate[car_id]['license_crop'] = license_crop
    except Exception as e:
        pass


frame_nmr = -1
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

# read frames
ret = True
while ret:
    ret, frame = cap.read()
    frame_nmr += 1
    
    if ret and frame is not None:
        df_ = results[results['frame_nmr'] == frame_nmr]
        for row_indx in range(len(df_)):
            
            # TỌA ĐỘ XE
            car_x1, car_y1, car_x2, car_y2 = ast.literal_eval(df_.iloc[row_indx]['car_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ','))
            
            # VẼ KHUNG XE (NÉT ĐỨT, MỎNG)
            draw_dashed_rectangle(frame, (int(car_x1), int(car_y1)), (int(car_x2), int(car_y2)), (0, 255, 0), thickness=2, dash_length=15)

            # TỌA ĐỘ BIỂN SỐ TRÊN XE
            x1, y1, x2, y2 = ast.literal_eval(df_.iloc[row_indx]['license_plate_bbox'].replace('[ ', '[').replace('   ', ' ').replace('  ', ' ').replace(' ', ','))
            
            # VẼ KHUNG BIỂN SỐ (VIỀN ĐỎ MỎNG)
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)

            # XỬ LÝ VẼ POP-UP BIỂN SỐ PHÓNG TO + CHỮ
            current_car_id = df_.iloc[row_indx]['car_id']
            if current_car_id in license_plate:
                license_crop = license_plate[current_car_id]['license_crop']
                plate_text = license_plate[current_car_id]['license_plate_number']
                
                if license_crop is not None:
                    try:
                        H, W, _ = license_crop.shape

                    
                        offset_y = 20 # Khoảng cách từ nóc xe lên pop-up
                        start_y_crop = int(car_y1) - offset_y - H
                        start_y_text_bg = start_y_crop - TEXT_BG_H

                     
                        if start_y_text_bg < 0:
                            shift = abs(start_y_text_bg) + 10
                            start_y_text_bg += shift
                            start_y_crop += shift

                
                        start_x = int((car_x2 + car_x1 - W) / 2)
                       
                        frame[start_y_crop : start_y_crop + H, start_x : start_x + W, :] = license_crop

                  
                        frame[start_y_text_bg : start_y_text_bg + TEXT_BG_H, start_x : start_x + W, :] = (255, 255, 255)

                        
                        font_scale = 0.8
                        font_thickness = 2
                        (text_width, text_height), _ = cv2.getTextSize(plate_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)

                        # Căn giữa chữ vào nền trắng
                        text_x = start_x + int((W - text_width) / 2)
                        text_y = start_y_text_bg + int((TEXT_BG_H + text_height) / 2)

                        # In chữ lên video
                        cv2.putText(frame, plate_text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), font_thickness)

                    except Exception as e:
                        pass

        out.write(frame)

out.release()
cap.release()