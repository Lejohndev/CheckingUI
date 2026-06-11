import string
from PIL import Image

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

import easyocr

# Khởi tạo reader của EasyOCR. 
reader = easyocr.Reader(['en'], gpu=True)


dict_char_to_int = {'O': '0', 'D': '0', 'I': '1', 'J': '3', 'A': '4', 'G': '6', 'S': '5', 'B': '8', 'Z': '2', 'T': '1', 'L': '4'}
dict_int_to_char = {'0': 'D', 'O': 'D', '1': 'I', '3': 'J', '4': 'A', '6': 'G', '5': 'S', '8': 'B', '2': 'Z'}

def write_csv(results, output_path):
    with open(output_path, 'w') as f:
        f.write('{},{},{},{},{},{},{},{}\n'.format('frame_nmr', 'car_id', 'vehicle_type', 'car_bbox',
                                                   'license_plate_bbox', 'license_plate_bbox_score', 'license_number',
                                                   'license_number_score'))

        for frame_nmr in results.keys():
            for car_id in results[frame_nmr].keys():
                if 'car' in results[frame_nmr][car_id].keys() and \
                   'license_plate' in results[frame_nmr][car_id].keys() and \
                   'text' in results[frame_nmr][car_id]['license_plate'].keys():
                    f.write('{},{},{},{},{},{},{},{}\n'.format(frame_nmr,
                                                               car_id,
                                                               results[frame_nmr][car_id]['car'].get('vehicle_type', 'unknown'),
                                                               '[{} {} {} {}]'.format(
                                                                   results[frame_nmr][car_id]['car']['bbox'][0],
                                                                   results[frame_nmr][car_id]['car']['bbox'][1],
                                                                   results[frame_nmr][car_id]['car']['bbox'][2],
                                                                   results[frame_nmr][car_id]['car']['bbox'][3]),
                                                               '[{} {} {} {}]'.format(
                                                                   results[frame_nmr][car_id]['license_plate']['bbox'][0],
                                                                   results[frame_nmr][car_id]['license_plate']['bbox'][1],
                                                                   results[frame_nmr][car_id]['license_plate']['bbox'][2],
                                                                   results[frame_nmr][car_id]['license_plate']['bbox'][3]),
                                                               results[frame_nmr][car_id]['license_plate']['bbox_score'],
                                                               results[frame_nmr][car_id]['license_plate']['text'],
                                                               results[frame_nmr][car_id]['license_plate']['text_score'])
                            )

def license_complies_format(text):
    """
    Kiểm tra độ dài cơ bản của biển số.
    Loại bỏ tạm dấu '-' để đếm chính xác số lượng ký tự thực tế (từ 7-9 ký tự).
    """
    real_chars = text.replace('-', '')
    if len(real_chars) < 7 or len(real_chars) > 9:
        return False
    return True

def format_license(text):
    """
    Chuẩn hóa OCR thông minh áp dụng cho MỌI loại biển số Việt Nam
    (Bao gồm: Xe máy, Ô tô, Biển 4 số, Biển 5 số...)
    """
    license_plate_ = ''
    

    alphanumeric_chars = [c for c in text if c.isalnum()]
    total_chars = len(alphanumeric_chars)
    
    char_index = 0 
    
    for char in text:
       
        if not char.isalnum():
            license_plate_ += char
            continue
            
       
        if char_index == 0 or char_index == 1:
            license_plate_ += dict_char_to_int.get(char, char)
            
       
        elif char_index == 2:
            license_plate_ += dict_int_to_char.get(char, char)
            
        
        elif char_index >= total_chars - 5 and char_index > 2:
            license_plate_ += dict_char_to_int.get(char, char)
            
       
        else:
            license_plate_ += char 
            
      
        char_index += 1
        
    return license_plate_

def read_license_plate(license_plate_crop):
    """
    Đọc biển số bằng OCR
    """
    detections = reader.readtext(
        license_plate_crop, 
        allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.-',
        adjust_contrast=0.5
    )
    
    
    if len(detections) == 0:
        return None, None

    full_text = ""
    score_sum = 0
    
    for detection in detections:
        bbox, text, score = detection
        full_text += text.upper()
        score_sum += score
        
    avg_score = score_sum / len(detections)
    
    # LÀM SẠCH: Chỉ xóa khoảng trắng và dấu chấm, GIỮ LẠI DẤU TRỪ (-)
    clean_text = full_text.replace(' ', '').replace('.', '')
    
    print(f"   -> [OCR Raw] Text: '{clean_text}'")

    if license_complies_format(clean_text):
        return format_license(clean_text), avg_score

    return None, None

def get_car(license_plate, vehicle_track_ids):
    x1, y1, x2, y2, score, class_id = license_plate
    margin = 30 

    foundIt = False
    for j in range(len(vehicle_track_ids)):
        xcar1, ycar1, xcar2, ycar2, car_id = vehicle_track_ids[j]

        if x1 > (xcar1 - margin) and y1 > (ycar1 - margin) and x2 < (xcar2 + margin) and y2 < (ycar2 + margin):
            car_indx = j
            foundIt = True
            break

    if foundIt:
        return vehicle_track_ids[car_indx]

    return -1, -1, -1, -1, -1
