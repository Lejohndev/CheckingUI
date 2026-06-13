document.addEventListener("DOMContentLoaded", () => {
  const uploadForm = document.getElementById("uploadForm");
  const videoFile = document.getElementById("videoFile");
  const processButton = document.getElementById("processButton");
  const processSpinner = document.getElementById("processSpinner");
  const buttonText = processButton?.querySelector(".button-text");
  const loadingCard = document.getElementById("loadingCard");

  uploadForm?.addEventListener("submit", (event) => {
    if (!videoFile?.files?.length) {
      event.preventDefault();
      videoFile?.classList.add("is-invalid");
      return;
    }

    processButton.disabled = true;
    processSpinner?.classList.remove("d-none");
    loadingCard?.classList.remove("d-none");
    if (buttonText) {
      buttonText.textContent = "Processing...";
    }
  });

  videoFile?.addEventListener("change", () => {
    videoFile.classList.remove("is-invalid");
  });

  renderTrafficCharts();
});

function renderTrafficCharts() {
  if (!window.Chart || !window.trafficDashboardData) {
    return;
  }

  const data = window.trafficDashboardData;
  const vehicleTypeChart = document.getElementById("vehicleTypeChart");

  if (vehicleTypeChart) {
    new Chart(vehicleTypeChart, {
      type: "doughnut",
      data: {
        labels: data.vehicleLabels,
        datasets: [{
          data: data.vehicleValues,
          backgroundColor: ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#6366f1"],
          borderColor: "#1f2937",
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#9ca3af"
            }
          }
        }
      }
    });
  }
}