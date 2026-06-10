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
  const timelineChart = document.getElementById("timelineChart");

  if (vehicleTypeChart) {
    new Chart(vehicleTypeChart, {
      type: "doughnut",
      data: {
        labels: data.vehicleLabels,
        datasets: [{
          data: data.vehicleValues,
          backgroundColor: ["#0c74a5", "#14b8a6", "#94a3b8", "#2563eb", "#64748b"],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: "bottom"
          }
        }
      }
    });
  }

  if (timelineChart) {
    new Chart(timelineChart, {
      type: "line",
      data: {
        labels: data.timelineLabels,
        datasets: [{
          label: "Vehicles",
          data: data.timelineValues,
          borderColor: "#0c74a5",
          backgroundColor: "rgba(20, 184, 166, 0.18)",
          fill: true,
          tension: 0.35
        }]
      },
      options: {
        responsive: true,
        scales: {
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0
            }
          }
        }
      }
    });
  }
}
