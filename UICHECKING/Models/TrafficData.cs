namespace UICHECKING.Models;

public class TrafficData
{
    public int Id { get; set; }
    public string PlateNumber { get; set; } = string.Empty;
    public string VehicleType { get; set; } = string.Empty;
    public double Confidence { get; set; }
    public DateTime TimeDetected { get; set; }
    public string ImagePath { get; set; } = string.Empty;
}
