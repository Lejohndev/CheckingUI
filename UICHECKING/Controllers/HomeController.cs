using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc;
using UICHECKING.Models;

namespace UICHECKING.Controllers;

public class HomeController : Controller
{
    private const double MinimumRecognitionConfidence = 0.5;
    private readonly ILogger<HomeController> _logger;
    private readonly IWebHostEnvironment _environment;
    private readonly IHttpClientFactory _httpClientFactory;
    private static readonly HashSet<string> AllowedVideoExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".mp4",
        ".avi",
        ".mov"
    };

    public HomeController(
        ILogger<HomeController> logger,
        IWebHostEnvironment environment,
        IHttpClientFactory httpClientFactory)
    {
        _logger = logger;
        _environment = environment;
        _httpClientFactory = httpClientFactory;
    }

    public IActionResult Index()
    {
        return View();
    }

    [HttpGet]
    public IActionResult UploadVideo()
    {
        return RedirectToAction(nameof(Index));
    }

    [HttpPost]
    [ValidateAntiForgeryToken]
    [RequestSizeLimit(512 * 1024 * 1024)]
    [RequestFormLimits(MultipartBodyLengthLimit = 512 * 1024 * 1024)]
    public async Task<IActionResult> UploadVideo(IFormFile? videoFile)
    {
        if (videoFile == null || videoFile.Length == 0)
        {
            ModelState.AddModelError("videoFile", "Vui lòng chọn một file video trước khi xử lý.");
            return View("Index");
        }

        var extension = Path.GetExtension(videoFile.FileName);
        if (!AllowedVideoExtensions.Contains(extension))
        {
            ModelState.AddModelError("videoFile", "Định dạng file không hợp lệ. Chỉ hỗ trợ .mp4, .avi và .mov.");
            return View("Index");
        }

        Directory.CreateDirectory(GetWebRootPath("uploads"));
        Directory.CreateDirectory(GetWebRootPath("processed"));

        var safeFileName = $"{Path.GetFileNameWithoutExtension(videoFile.FileName)}_{DateTime.UtcNow:yyyyMMddHHmmssfff}{extension}";
        var uploadPath = Path.Combine(GetWebRootPath("uploads"), safeFileName);

        await using (var fileStream = new FileStream(uploadPath, FileMode.Create))
        {
            await videoFile.CopyToAsync(fileStream);
        }

        try
        {
            var client = _httpClientFactory.CreateClient("TrafficAiApi");
            await using var videoStream = System.IO.File.OpenRead(uploadPath);
            using var content = new MultipartFormDataContent();
            using var fileContent = new StreamContent(videoStream);
            fileContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(GetVideoMimeType(extension));
            content.Add(fileContent, "video", safeFileName);

            var response = await client.PostAsync("process", content);
            var responseBody = await response.Content.ReadAsStringAsync();

            if (!response.IsSuccessStatusCode)
            {
                _logger.LogWarning("FastAPI returned {StatusCode}: {Body}", response.StatusCode, responseBody);
                ViewBag.ErrorMessage = "AI server xử lý thất bại. Vui lòng kiểm tra log Python/FastAPI và thử lại.";
                return View("Index");
            }

            var result = await BuildResultViewModelAsync(responseBody, Path.GetFileNameWithoutExtension(safeFileName), client);
            if (result == null)
            {
                ViewBag.ErrorMessage = "Không đọc được kết quả trả về từ AI server. Vui lòng kiểm tra định dạng response.";
                return View("Index");
            }

            return RedirectToAction(nameof(Result), new
            {
                videoPath = result.VideoPath,
                csvPath = result.CsvPath
            });
        }
        catch (HttpRequestException ex)
        {
            _logger.LogError(ex, "Cannot connect to FastAPI server");
            ViewBag.ErrorMessage = "Không kết nối được FastAPI tại http://127.0.0.1:8000/process. Hãy chạy Python API rồi thử lại.";
            return View("Index");
        }
        catch (TaskCanceledException ex)
        {
            _logger.LogError(ex, "FastAPI processing timed out");
            ViewBag.ErrorMessage = "Quá trình xử lý mất quá nhiều thời gian. Vui lòng thử video ngắn hơn hoặc tăng timeout API.";
            return View("Index");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unexpected error while processing video");
            ViewBag.ErrorMessage = "Có lỗi xảy ra trong quá trình xử lý video. Vui lòng thử lại sau.";
            return View("Index");
        }
    }

    [HttpGet]
    public IActionResult Result(string? videoPath, string? csvPath)
    {
        if (string.IsNullOrWhiteSpace(videoPath) || string.IsNullOrWhiteSpace(csvPath))
        {
            return RedirectToAction(nameof(Index));
        }

        return View(CreateTrafficResultViewModel(videoPath, csvPath));
    }

    public IActionResult Privacy()
    {
        return View();
    }

    [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
    public IActionResult Error()
    {
        return View(new ErrorViewModel { RequestId = Activity.Current?.Id ?? HttpContext.TraceIdentifier });
    }

    private async Task<TrafficResultViewModel?> BuildResultViewModelAsync(
        string responseBody,
        string fallbackBaseName,
        HttpClient client)
    {
        string? videoReference;
        string? csvReference;

        try
        {
            using var document = JsonDocument.Parse(responseBody);
            var root = document.RootElement;

            videoReference = GetFirstString(root, "processed_video_url", "video_url", "videoPath", "video_path", "processedVideo", "processed_video", "output_video_path");
            csvReference = GetFirstString(root, "csv_url", "csvPath", "csv_path", "csvFile", "csv_file", "output_csv_path");

            if (root.TryGetProperty("data", out var data))
            {
                videoReference ??= GetFirstString(data, "processed_video_url", "video_url", "videoPath", "video_path", "processedVideo", "processed_video", "output_video_path");
                csvReference ??= GetFirstString(data, "csv_url", "csvPath", "csv_path", "csvFile", "csv_file", "output_csv_path");
            }
        }
        catch (JsonException ex)
        {
            _logger.LogWarning(ex, "FastAPI response is not valid JSON: {Body}", responseBody);
            return null;
        }

        if (string.IsNullOrWhiteSpace(videoReference) || string.IsNullOrWhiteSpace(csvReference))
        {
            return null;
        }

        var videoPath = await ResolveReturnedFileAsync(videoReference, "processed", $"{fallbackBaseName}_processed", client);
        var csvPath = await ResolveReturnedFileAsync(csvReference, "processed", $"{fallbackBaseName}.csv", client);
        return CreateTrafficResultViewModel(videoPath, csvPath);
    }

    private TrafficResultViewModel CreateTrafficResultViewModel(string videoPath, string csvPath)
    {
        var records = ReadTrafficDataFromCsv(csvPath);
        var uniqueVehicles = GetUniqueVehicles(records);
        var recognizedRecords = GetUniqueRecognizedPlates(records)
            .ToList();
        var vehicleTypes = uniqueVehicles.Count > 0
            ? uniqueVehicles.Select(item => item.VehicleType)
            : records.Select(item => item.VehicleType);

        return new TrafficResultViewModel
        {
            VideoPath = videoPath,
            CsvPath = csvPath,
            Records = recognizedRecords,
            TotalVehicles = uniqueVehicles.Count > 0 ? uniqueVehicles.Count : records.Count,
            TotalPlatesRead = recognizedRecords.Count,
            VehicleTypeCounts = vehicleTypes
                .GroupBy(vehicleType => string.IsNullOrWhiteSpace(vehicleType) ? "Không xác định" : vehicleType)
                .ToDictionary(group => group.Key, group => group.Count())
        };
    }

    private static List<TrafficData> GetUniqueVehicles(List<TrafficData> records)
    {
        return records
            .Where(item => !string.IsNullOrWhiteSpace(item.CarId))
            .GroupBy(item => item.CarId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group
                .OrderByDescending(item => item.Confidence)
                .First())
            .ToList();
    }

    private static IEnumerable<TrafficData> GetUniqueRecognizedPlates(List<TrafficData> records)
    {
        var recognizedRecords = records
            .Where(IsRecognizedPlate)
            .ToList();

        var bestPlatePerVehicle = recognizedRecords
            .Where(item => !string.IsNullOrWhiteSpace(item.CarId))
            .GroupBy(item => item.CarId, StringComparer.OrdinalIgnoreCase)
            .Select(group => group
                .OrderByDescending(item => item.Confidence)
                .First());

        var bestPlateWithoutVehicle = recognizedRecords
            .Where(item => string.IsNullOrWhiteSpace(item.CarId))
            .GroupBy(item => NormalizePlateKey(item.PlateNumber), StringComparer.OrdinalIgnoreCase)
            .Where(group => !string.IsNullOrWhiteSpace(group.Key))
            .Select(group => group
                .OrderByDescending(item => item.Confidence)
                .First());

        return bestPlatePerVehicle
            .Concat(bestPlateWithoutVehicle)
            .GroupBy(item => NormalizePlateKey(item.PlateNumber), StringComparer.OrdinalIgnoreCase)
            .Where(group => !string.IsNullOrWhiteSpace(group.Key))
            .Select(group => group
                .OrderByDescending(item => item.Confidence)
                .First());
    }

    private async Task<string> ResolveReturnedFileAsync(
        string fileReference,
        string targetFolder,
        string fallbackFileName,
        HttpClient client)
    {
        fileReference = fileReference.Trim().Trim('"');
        var processedFolder = GetWebRootPath(targetFolder);
        Directory.CreateDirectory(processedFolder);

        if (Uri.TryCreate(fileReference, UriKind.Absolute, out var uri) &&
            (uri.Scheme == Uri.UriSchemeHttp || uri.Scheme == Uri.UriSchemeHttps))
        {
            var extension = Path.GetExtension(uri.LocalPath);
            var fileName = EnsureExtension(fallbackFileName, extension);
            var destinationPath = Path.Combine(processedFolder, fileName);
            var bytes = await client.GetByteArrayAsync(uri);
            await System.IO.File.WriteAllBytesAsync(destinationPath, bytes);
            return $"/{targetFolder}/{fileName}";
        }

        if (Path.IsPathRooted(fileReference) && System.IO.File.Exists(fileReference))
        {
            var webPath = TryConvertPhysicalPathToWebPath(fileReference);
            if (!string.IsNullOrWhiteSpace(webPath))
            {
                return webPath;
            }

            var extension = Path.GetExtension(fileReference);
            var fileName = EnsureExtension(fallbackFileName, extension);
            var destinationPath = Path.Combine(processedFolder, fileName);
            System.IO.File.Copy(fileReference, destinationPath, overwrite: true);
            return $"/{targetFolder}/{fileName}";
        }

        if (fileReference.StartsWith('/'))
        {
            return fileReference;
        }

        return "/" + fileReference.Replace("\\", "/").TrimStart('/');
    }

    private List<TrafficData> ReadTrafficDataFromCsv(string csvWebPath)
    {
        var csvPhysicalPath = MapWebPathToPhysicalPath(csvWebPath);
        if (string.IsNullOrWhiteSpace(csvPhysicalPath) || !System.IO.File.Exists(csvPhysicalPath))
        {
            return new List<TrafficData>();
        }

        var lines = System.IO.File.ReadAllLines(csvPhysicalPath);
        if (lines.Length <= 1)
        {
            return new List<TrafficData>();
        }

        var headers = SplitCsvLine(lines[0]).Select(NormalizeHeader).ToList();
        var records = new List<TrafficData>();

        for (var i = 1; i < lines.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(lines[i]))
            {
                continue;
            }

            var values = SplitCsvLine(lines[i]);
            var row = new Dictionary<string, string>();
            for (var headerIndex = 0; headerIndex < headers.Count; headerIndex++)
            {
                // Giữ giá trị đầu tiên nếu CSV có nhiều header quy về cùng một tên.
                row.TryAdd(headers[headerIndex], headerIndex < values.Count ? values[headerIndex] : string.Empty);
            }

            var confidence = TryGetDouble(row, "licensenumberscore", "confidence", "licenseplatebboxscore", "score");
            var timeDetected = TryGetDateTime(row, "timedetected", "timestamp", "time");
            if (timeDetected == DateTime.MinValue)
            {
                timeDetected = DateTime.Today.AddSeconds(TryGetDouble(row, "framenmr", "frame", "framenumber") / 30);
            }

            records.Add(new TrafficData
            {
                Id = records.Count + 1,
                CarId = GetFirstValue(row, "carid", "vehicleid", "trackid") ?? string.Empty,
                PlateNumber = GetFirstValue(row, "platenumber", "licenseplate", "licensenumber", "plate") ?? "Unknown",
                VehicleType = ToVietnameseVehicleType(GetFirstValue(row, "vehicletype", "type", "class")),
                Confidence = confidence,
                TimeDetected = timeDetected == DateTime.MinValue ? DateTime.Now : timeDetected,
                ImagePath = GetFirstValue(row, "imagepath", "image", "thumbnail") ?? string.Empty
            });
        }

        return records;
    }

    private static bool IsRecognizedPlate(TrafficData item)
    {
        return item.Confidence >= MinimumRecognitionConfidence &&
            !string.IsNullOrWhiteSpace(item.PlateNumber) &&
            item.PlateNumber != "0" &&
            item.PlateNumber != "Unknown";
    }

    private static string NormalizePlateKey(string plateNumber)
    {
        var cleaned = new string(plateNumber
            .Where(char.IsLetterOrDigit)
            .Select(char.ToUpperInvariant)
            .ToArray());

        if (string.IsNullOrWhiteSpace(cleaned))
        {
            return string.Empty;
        }

        var normalized = new List<char>(cleaned.Length);
        for (var i = 0; i < cleaned.Length; i++)
        {
            var character = cleaned[i];
            var shouldBeDigit = i < 2 || i >= Math.Max(0, cleaned.Length - 5);
            normalized.Add(shouldBeDigit
                ? NormalizePlateDigit(character)
                : NormalizePlateLetter(character));
        }

        return new string(normalized.ToArray());
    }

    private static char NormalizePlateDigit(char character)
    {
        return character switch
        {
            'O' or 'D' or 'Q' => '0',
            'I' or 'L' or 'T' => '1',
            'Z' => '2',
            'J' => '3',
            'A' => '4',
            'S' => '5',
            'G' => '6',
            'B' => '8',
            _ => character
        };
    }

    private static char NormalizePlateLetter(char character)
    {
        return character switch
        {
            '0' or 'O' => 'D',
            '1' or 'I' or 'L' or 'T' => 'T',
            '3' => 'J',
            '4' => 'A',
            '5' => 'S',
            '6' => 'G',
            '8' => 'B',
            '2' => 'Z',
            _ => character
        };
    }

    private static string ToVietnameseVehicleType(string? vehicleType)
    {
        return NormalizeHeader(vehicleType ?? string.Empty) switch
        {
            "car" => "Ô tô",
            "motorcycle" => "Xe máy",
            "motorbike" => "Xe máy",
            "bus" => "Xe buýt",
            "truck" => "Xe tải",
            "bicycle" => "Xe đạp",
            _ => "Không xác định"
        };
    }

    private static string? GetFirstString(JsonElement element, params string[] propertyNames)
    {
        foreach (var propertyName in propertyNames)
        {
            if (element.TryGetProperty(propertyName, out var property) && property.ValueKind == JsonValueKind.String)
            {
                return property.GetString();
            }
        }

        foreach (var jsonProperty in element.EnumerateObject())
        {
            var normalizedJsonName = NormalizeHeader(jsonProperty.Name);
            if (propertyNames.Any(name => NormalizeHeader(name) == normalizedJsonName) &&
                jsonProperty.Value.ValueKind == JsonValueKind.String)
            {
                return jsonProperty.Value.GetString();
            }
        }

        return null;
    }

    private static string? GetFirstValue(Dictionary<string, string> row, params string[] keys)
    {
        foreach (var key in keys)
        {
            if (row.TryGetValue(key, out var value) && !string.IsNullOrWhiteSpace(value))
            {
                return value;
            }
        }

        return null;
    }

    private static double TryGetDouble(Dictionary<string, string> row, params string[] keys)
    {
        var value = GetFirstValue(row, keys);
        return double.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out var result) ? result : 0;
    }

    private static DateTime TryGetDateTime(Dictionary<string, string> row, params string[] keys)
    {
        var value = GetFirstValue(row, keys);
        return DateTime.TryParse(value, CultureInfo.InvariantCulture, DateTimeStyles.AssumeLocal, out var result)
            ? result
            : DateTime.MinValue;
    }

    private static List<string> SplitCsvLine(string line)
    {
        var values = new List<string>();
        var current = new List<char>();
        var inQuotes = false;

        for (var i = 0; i < line.Length; i++)
        {
            var character = line[i];
            if (character == '"')
            {
                if (inQuotes && i + 1 < line.Length && line[i + 1] == '"')
                {
                    current.Add('"');
                    i++;
                }
                else
                {
                    inQuotes = !inQuotes;
                }
            }
            else if (character == ',' && !inQuotes)
            {
                values.Add(new string(current.ToArray()).Trim());
                current.Clear();
            }
            else
            {
                current.Add(character);
            }
        }

        values.Add(new string(current.ToArray()).Trim());
        return values;
    }

    private static string NormalizeHeader(string header)
    {
        return new string(header.Where(char.IsLetterOrDigit).ToArray()).ToLowerInvariant();
    }

    private static string GetVideoMimeType(string extension)
    {
        return extension.ToLowerInvariant() switch
        {
            ".avi" => "video/x-msvideo",
            ".mov" => "video/quicktime",
            _ => "video/mp4"
        };
    }

    private static string EnsureExtension(string fileName, string extension)
    {
        if (string.IsNullOrWhiteSpace(extension))
        {
            return fileName;
        }

        return Path.ChangeExtension(fileName, extension);
    }

    private string GetWebRootPath(string folderName)
    {
        return Path.Combine(_environment.WebRootPath, folderName);
    }

    private string? MapWebPathToPhysicalPath(string webPath)
    {
        if (string.IsNullOrWhiteSpace(webPath))
        {
            return null;
        }

        if (Path.IsPathRooted(webPath) && System.IO.File.Exists(webPath))
        {
            return webPath;
        }

        return Path.Combine(_environment.WebRootPath, webPath.TrimStart('/').Replace("/", Path.DirectorySeparatorChar.ToString()));
    }

    private string? TryConvertPhysicalPathToWebPath(string physicalPath)
    {
        var webRoot = Path.GetFullPath(_environment.WebRootPath);
        var fullPath = Path.GetFullPath(physicalPath);
        if (!fullPath.StartsWith(webRoot, StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        return "/" + Path.GetRelativePath(webRoot, fullPath).Replace("\\", "/");
    }
}
