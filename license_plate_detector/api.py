import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov"}

UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

app = FastAPI(title="AI License Plate Detection API")
app.mount("/processed", StaticFiles(directory=PROCESSED_DIR), name="processed")


class VideoRequest(BaseModel):
    input_video_path: str
    output_csv_path: str
    output_video_path: str


@app.get("/")
def health_check():
    return {"status": "running", "message": "AI API is ready"}


@app.post("/process")
async def process_uploaded_video(video: UploadFile = File(...)):
    extension = Path(video.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only .mp4, .avi and .mov files are supported.")

    job_id = uuid4().hex
    input_video_path = UPLOAD_DIR / f"{job_id}{extension}"
    output_csv_path = PROCESSED_DIR / f"{job_id}.csv"
    output_video_path = PROCESSED_DIR / f"{job_id}_processed.mp4"

    try:
        with input_video_path.open("wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

        run_pipeline(input_video_path, output_csv_path, output_video_path)

        return {
            "status": "success",
            "message": "Video processed successfully.",
            "csv_url": str(output_csv_path),
            "video_url": str(output_video_path),
            "processed_video_url": str(output_video_path),
        }
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"AI processing failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected API error: {exc}") from exc
    finally:
        await video.close()


@app.post("/api/process-video")
def process_video_by_path(req: VideoRequest):
    input_video_path = Path(req.input_video_path)
    output_csv_path = Path(req.output_csv_path)
    output_video_path = Path(req.output_video_path)

    if not input_video_path.exists():
        raise HTTPException(status_code=400, detail="Input video file was not found.")

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        run_pipeline(input_video_path, output_csv_path, output_video_path)
        return {
            "status": "success",
            "message": "Video processed successfully.",
            "csv_url": str(output_csv_path),
            "video_url": str(output_video_path),
            "processed_video_url": str(output_video_path),
        }
    except subprocess.CalledProcessError as exc:
        raise HTTPException(status_code=500, detail=f"AI processing failed: {exc}") from exc


def run_pipeline(input_video_path: Path, output_csv_path: Path, output_video_path: Path):
    raw_csv_path = output_csv_path.with_name(f"{output_csv_path.stem}_raw.csv")
    # TẠO THÊM ĐƯỜNG DẪN VIDEO TẠM THỜI (RAW)
    raw_video_path = output_video_path.with_name(f"{output_video_path.stem}_raw.mp4")
    
    process_env = os.environ.copy()
    process_env["PYTHONIOENCODING"] = "utf-8"
    process_env["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"

    try:
        # Bước 1: Trích xuất AI
        subprocess.run(
            [sys.executable, "main.py", str(input_video_path), str(raw_csv_path)],
            cwd=BASE_DIR, env=process_env, check=True,
        )
        
        # Bước 2: Nội suy dữ liệu
        subprocess.run(
            [sys.executable, "add_missing_data.py", str(raw_csv_path), str(output_csv_path)],
            cwd=BASE_DIR, env=process_env, check=True,
        )
        
        # Bước 3: Visualize (Vẽ khung hình vào file RAW TẠM THỜI)
        subprocess.run(
            [sys.executable, "visualize.py", str(input_video_path), str(output_csv_path), str(raw_video_path)],
            cwd=BASE_DIR, env=process_env, check=True,
        )
        
        # BƯỚC 4: Dùng FFmpeg tối ưu hóa cho Web
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", str(raw_video_path),
            "-vcodec", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(output_video_path) 
        ]
        subprocess.run(
            ffmpeg_cmd,
            cwd=BASE_DIR, env=process_env, check=True,
        )
        
    finally:
     
        if raw_csv_path.exists():
            os.remove(raw_csv_path)
        if raw_video_path.exists():
            os.remove(raw_video_path)