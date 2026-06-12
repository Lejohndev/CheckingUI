namespace UICHECKING.Models;

public class TrafficResultViewModel
{
    public string VideoPath { get; set; } = string.Empty;
    public string CsvPath { get; set; } = string.Empty;
    public List<TrafficData> Records { get; set; } = new();
    public int TotalVehicles { get; set; }
    public int TotalPlatesRead { get; set; }
    public Dictionary<string, int> VehicleTypeCounts { get; set; } = new();
}
