# AI Traffic License Plate Detection

Website ASP.NET Core MVC ket hop FastAPI Python de upload video giao thong, nhan dien phuong tien/bien so xe bang AI, xuat video da xu ly va file CSV ket qua.

## Yeu Cau Moi Truong

- .NET SDK/Runtime 10, project dang target `net10.0`
- Python 3.11
- `uv` de quan ly moi truong ao Python
- Trinh duyet Chrome/Edge

## Cau Truc Chinh

```text
CheckingUI-main
├── UICHECKING
│   ├── Controllers/HomeController.cs
│   ├── Models/TrafficData.cs
│   ├── Views/Home/Index.cshtml
│   ├── Views/Home/Result.cshtml
│   ├── Program.cs
│   └── wwwroot
│       ├── uploads
│       ├── processed
│       ├── css
│       └── js
└── license_plate_detector
    ├── api.py
    ├── main.py
    ├── add_missing_data.py
    ├── visualize.py
    ├── util.py
    ├── models/license_plate_detector.pt
    ├── sort/sort.py
    ├── uploads
    └── processed
```

## Chay FastAPI Python

Mo terminal thu nhat:

```powershell
cd C:\Users\OS\Downloads\CheckingUI-main\CheckingUI-main\license_plate_detector
uv venv
uv pip install -r requirements.txt
uv python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

Kiem tra API:

```text
http://127.0.0.1:8000/docs
```

Giu terminal FastAPI luon mo trong luc xu ly video.

## Chay Website ASP.NET Core MVC

Mo terminal thu hai:

```powershell
cd C:\Users\OS\Downloads\CheckingUI-main\CheckingUI-main\UICHECKING
dotnet run --launch-profile http
```

Mo website:

```text
http://localhost:5236
```

## Cach Su Dung

1. Mo `http://localhost:5236`.
2. Chon file video `.mp4`, `.avi`, hoac `.mov`.
3. Bam `Process Video`.
4. Doi FastAPI xu ly AI. Video lon/4K co the mat nhieu phut neu chay CPU.
5. Trang ket qua se hien:
   - Video da nhan dien.
   - Bang du lieu bien so tu CSV.
   - Card thong ke.
   - Bieu do Chart.js.

## Luu Y Quan Trong

- FastAPI phai chay truoc khi bam `Process Video`.
- Model bien so phai ton tai tai:

```text
license_plate_detector\models\license_plate_detector.pt
```

- Module SORT phai ton tai tai:

```text
license_plate_detector\sort\sort.py
```

- Ket qua AI duoc tao trong:

```text
license_plate_detector\processed
```

- Ket qua hien thi tren MVC duoc copy sang:

```text
UICHECKING\wwwroot\processed
```

## Xu Ly Loi Thuong Gap

### `uvicorn is not recognized`

Dung lenh nay thay vi goi truc tiep `uvicorn`:

```powershell
uv run python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

### Khong ket noi duoc FastAPI

Kiem tra FastAPI da chay chua:

```text
http://127.0.0.1:8000/docs
```

Neu chua mo duoc, chay lai terminal FastAPI.

### `ModuleNotFoundError: No module named 'sort.sort'`

Kiem tra file nay co ton tai:

```text
license_plate_detector\sort\sort.py
```

### Loi load model `.pt`

Kiem tra file model:

```text
license_plate_detector\models\license_plate_detector.pt
```

Project da cau hinh `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` cho subprocess de load checkpoint YOLO cu voi PyTorch moi.

### `Image.ANTIALIAS` cua EasyOCR/Pillow

Project da co shim trong `util.py` de tuong thich Pillow moi. Neu van gap loi, hay dam bao dang chay dung source moi nhat va restart FastAPI.

### Timeout khi xu ly video

MVC da cau hinh timeout 2 gio. Neu video rat lon hoac 4K, xu ly CPU co the rat cham. Nen thu video ngan hon de test nhanh.

### Video ket qua khong xem duoc tren Chrome

Pipeline dang xuat `.webm` bang codec VP8 de Chrome/Edge xem duoc. Neu con thay video den/0:00, hay restart FastAPI va upload lai de tao ket qua moi.

## Lenh Restart Nhanh

Dung ca hai terminal bang `Ctrl + C`, sau do chay lai:

FastAPI:

```powershell
cd C:\Users\OS\Downloads\CheckingUI-main\CheckingUI-main\license_plate_detector
uv run python -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
```

MVC:

```powershell
cd C:\Users\OS\Downloads\CheckingUI-main\CheckingUI-main\UICHECKING
dotnet run --launch-profile http
```
