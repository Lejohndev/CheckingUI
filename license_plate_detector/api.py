import os
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Hệ thống nhận diện biển số AI")

# Định nghĩa cấu trúc dữ liệu mà ASP.NET sẽ gửi sang
class VideoRequest(BaseModel):
    input_video_path: str
    output_csv_path: str
    output_video_path: str

@app.post("/api/process-video")
def process_video(req: VideoRequest):
    # Kiểm tra xem file video từ ASP.NET gửi sang có tồn tại không
    if not os.path.exists(req.input_video_path):
        raise HTTPException(status_code=400, detail="Không tìm thấy file video đầu vào!")

    # Tạo tên file CSV tạm thời (raw) trước khi nội suy
    raw_csv_path = req.output_csv_path.replace(".csv", "_raw.csv")

    try:
        print("[1/3] Đang chạy YOLO & OCR để trích xuất dữ liệu...")
        subprocess.run(["python", "main.py", req.input_video_path, raw_csv_path], check=True)

        print("[2/3] Đang chạy nội suy (Interpolation) để làm mượt dữ liệu...")
        subprocess.run(["python", "add_missing_data.py", raw_csv_path, req.output_csv_path], check=True)

        print("[3/3] Đang vẽ khung và xuất video kết quả...")
        subprocess.run(["python", "visualize.py", req.input_video_path, req.output_csv_path, req.output_video_path], check=True)

        # Dọn dẹp file CSV raw tạm thời (tùy chọn)
        if os.path.exists(raw_csv_path):
            os.remove(raw_csv_path)

        return {
            "status": "success", 
            "message": "Xử lý video hoàn tất!",
            "csv_url": req.output_csv_path,
            "video_url": req.output_video_path
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống AI trong lúc chạy script: {str(e)}")