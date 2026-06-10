using Microsoft.AspNetCore.Http.Features;
using Microsoft.AspNetCore.DataProtection;

var builder = WebApplication.CreateBuilder(args);
var dataProtectionPath = Path.Combine(builder.Environment.ContentRootPath, "App_Data", "DataProtectionKeys");
Directory.CreateDirectory(dataProtectionPath);

builder.WebHost.ConfigureKestrel(options =>
{
    // Keep Kestrel aligned with the multipart upload limit for video files.
    options.Limits.MaxRequestBodySize = 512 * 1024 * 1024;
});

// Add services to the container.
builder.Services.AddControllersWithViews();
builder.Services.AddDataProtection()
    .PersistKeysToFileSystem(new DirectoryInfo(dataProtectionPath));
builder.Services.Configure<FormOptions>(options =>
{
    // Cho phép upload video dung lượng lớn hơn mặc định.
    options.MultipartBodyLengthLimit = 512 * 1024 * 1024;
});
builder.Services.AddHttpClient("TrafficAiApi", client =>
{
    client.BaseAddress = new Uri("http://127.0.0.1:8000/");
    client.Timeout = TimeSpan.FromHours(2);
});

var app = builder.Build();

CreateStaticFolder(app.Environment.WebRootPath, "uploads");
CreateStaticFolder(app.Environment.WebRootPath, "processed");
CreateStaticFolder(app.Environment.WebRootPath, "css");
CreateStaticFolder(app.Environment.WebRootPath, "js");

// Configure the HTTP request pipeline.
if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    // The default HSTS value is 30 days. You may want to change this for production scenarios, see https://aka.ms/aspnetcore-hsts.
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();

app.UseRouting();

app.UseAuthorization();

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.Run();

static void CreateStaticFolder(string webRootPath, string folderName)
{
    Directory.CreateDirectory(Path.Combine(webRootPath, folderName));
}
