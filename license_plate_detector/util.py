import string
import os

import torch  # Load Torch DLLs before Paddle to avoid CUDA DLL conflicts on Windows.
import paddle
from PIL import Image
from paddleocr import PaddleOCR

if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.Resampling.LANCZOS


PADDLE_OCR_DEVICE = os.environ.get("PADDLE_OCR_DEVICE", "gpu:0")

if PADDLE_OCR_DEVICE.startswith("gpu") and not paddle.device.is_compiled_with_cuda():
    raise RuntimeError(
        "PaddleOCR is configured to use GPU, but this Python has CPU-only Paddle. "
        "Run with a Python environment that has paddlepaddle-gpu installed, or set "
        "PADDLE_OCR_DEVICE=cpu."
    )


ocr = PaddleOCR(
    device=PADDLE_OCR_DEVICE,
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    lang='en', 
    enable_mkldnn=False,
    det_db_thresh=0.1,        
    det_db_box_thresh=0.3,    
    det_db_unclip_ratio=2.0   
)

dict_char_to_int = {'O': '0', 'D': '0', 'Q': '0', 'I': '1', 'J': '3', 'A': '4', 'G': '6', 'S': '5', 'B': '8', 'Z': '2', 'T': '1', 'L': '4'}

dict_int_to_char = {'0': 'D', 'O': 'D', '1': 'I', '3': 'J', '4': 'A', '6': 'G', '5': 'S', '8': 'B', '2': 'Z'}

def write_csv(results, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
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
    Loại bỏ tạm dấu '-' và '.' để đếm chính xác số lượng ký tự thực tế (từ 6-9 ký tự).
    """
    real_chars = text.replace('-', '').replace('.', '').replace(' ', '')
    if len(real_chars) < 6 or len(real_chars) > 9:
        return False
    return True

def format_license(text):
    """
    Chuẩn hóa OCR thông minh áp dụng cho MỌI loại biển số Việt Nam
    (Bao gồm: Xe máy, Ô tô, Biển 4 số, Biển 5 số, Biển quân đội...)
    """
    license_plate_ = ''

    alphanumeric_chars = [c for c in text if c.isalnum()]
    total_chars = len(alphanumeric_chars)
    
    char_index = 0 
    
    for char in text:
        if not char.isalnum():
            license_plate_ += char
            continue
            
        # 4 kí tự cuối cùng của biển số Việt Nam LUÔN LUÔN là số
        if char_index >= total_chars - 4:
            license_plate_ += dict_char_to_int.get(char, char)
            
        # 2 kí tự đầu thường là số (Mã tỉnh). 
        # Ngoại trừ biển quân đội, nhưng chuẩn hóa thành số là tốt nhất cho >95% trường hợp.
        elif char_index == 0 or char_index == 1:
            license_plate_ += dict_char_to_int.get(char, char)
            
        # Kí tự thứ 3 (index 2) ở biển dân sự luôn là Chữ cái (Series VD: A, B, C...)
        elif char_index == 2:
            license_plate_ += dict_int_to_char.get(char, char)
            
        # Các kí tự ở giữa (index 3 đến total_chars - 5)
        # Có thể là số (biển xe máy VD: 29A1, số 1 là index 3) 
        # Hoặc chữ (biển LD VD: 29LD, chữ D là index 3)
        # -> Giữ nguyên gốc của OCR để đảm bảo độ chính xác tuyệt đối, không ép kiểu.
        else:
            license_plate_ += char 
            
        char_index += 1
        
    return license_plate_

def read_license_plate(license_plate_crop):
    """
    Hàm đọc biển số sử dụng kỹ thuật 'Đường xích đạo' (Absolute Midline).
    Chia dòng chính xác tuyệt đối 100% cho biển số Việt Nam.
    """
    # 1. Lấy chiều cao (H) và chiều rộng (W) của khung ảnh biển số
    H, W = license_plate_crop.shape[:2]
    aspect_ratio = W / float(H)

    result = ocr.ocr(license_plate_crop)
    
    if not result or not result[0]:
        return None, None

    res = result[0]
    detections = []
    
    # 2. Bóc tách dữ liệu từ PaddleX / PaddleOCR
    if hasattr(res, 'rec_texts') or (isinstance(res, dict) and 'rec_texts' in res):
        texts = getattr(res, 'rec_texts', []) if hasattr(res, 'rec_texts') else res.get('rec_texts', [])
        scores = getattr(res, 'rec_scores', []) if hasattr(res, 'rec_scores') else res.get('rec_scores', [])
        polys = getattr(res, 'dt_polys', []) if hasattr(res, 'dt_polys') else res.get('dt_polys', [])
        
        for i in range(len(texts)):
            poly = polys[i] if i < len(polys) else [[0, 0], [0, 0], [0, 0], [0, 0]]
            detections.append((poly, (texts[i], scores[i])))
    elif isinstance(res, list):
        detections = res

    if not detections:
        return None, None

    # 3. Tính toán Tọa độ Tâm (cx, cy)
    parsed_boxes = []
    for det in detections:
        try:
            if not det or len(det) < 2: continue
            poly = det[0]
            text, score = det[1]
            if hasattr(poly, 'tolist'): poly = poly.tolist()
            
            ys = [pt[1] for pt in poly]
            xs = [pt[0] for pt in poly]
            cy = sum(ys) / len(ys)
            cx = sum(xs) / len(xs)
            
            parsed_boxes.append({'text': str(text).upper(), 'score': float(score), 'cx': cx, 'cy': cy})
        except Exception:
            continue

    if not parsed_boxes:
        return None, None

    # 4. THUẬT TOÁN ĐƯỜNG XÍCH ĐẠO (Midline Split)
    # Tỷ lệ Rộng/Cao < 2.5 chắc chắn là biển 2 dòng (Xe máy hoặc Ô tô biển ngắn)
    if aspect_ratio < 2.5:
        row1 = []
        row2 = []
        for box in parsed_boxes:
            # Nếu tâm của chữ nằm ở Nửa Trên của bức ảnh (cy < H / 2) -> Đưa vào Dòng 1
            if box['cy'] < (H / 2.0):
                row1.append(box)
            # Nếu nằm ở Nửa Dưới -> Đưa vào Dòng 2
            else:
                row2.append(box)
        
        # Sắp xếp các ký tự trong mỗi dòng từ Trái qua Phải
        row1.sort(key=lambda x: x['cx'])
        row2.sort(key=lambda x: x['cx'])
        
        # Ghép Dòng 1 trước, Dòng 2 sau
        final_sorted_boxes = row1 + row2
    else:
        # Biển dài 1 dòng thì chỉ việc xếp từ Trái qua Phải
        parsed_boxes.sort(key=lambda x: x['cx'])
        final_sorted_boxes = parsed_boxes

    # 5. Tổng hợp chuỗi ký tự
    full_text = ""
    score_sum = 0
    for b in final_sorted_boxes:
        full_text += b['text']
        score_sum += b['score']

    total_detections = len(final_sorted_boxes)
    if total_detections == 0:
        return None, None

    avg_score = score_sum / total_detections
    clean_text = full_text.replace(' ', '').replace('.', '')
    
    print(f"   -> [PaddleOCR Absolute] Đọc được: '{clean_text}' (Score: {avg_score:.2f})")

    # 6. Ép chuẩn Format biển số Việt Nam
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
