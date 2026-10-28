(function () {
  var data = document.getElementById("chart-data");
  if (!data) { return; }
  var d = JSON.parse(data.textContent);

  if (typeof Chart === "undefined") {
    document.querySelectorAll(".chart-box").forEach(function (box) {
      box.textContent = "Chart library not found. See the setup step: download chart.umd.js.";
    });
    return;
  }

  var colors = ["#2563eb", "#dc2626", "#059669", "#7c3aed"];
  var thresholdColors = { medium: "#d97706", high: "#dc2626", critical: "#7f1d1d" };

  // risk score over time, with the level thresholds as dashed lines
  var riskSets = [{
    label: "Risk score", data: d.risk.scores, borderColor: colors[0],
    backgroundColor: colors[0], tension: 0.2, pointRadius: 2, borderWidth: 2
  }];
  Object.keys(d.thresholds || {}).forEach(function (name) {
    if (!(name in thresholdColors)) { return; }
    riskSets.push({
      label: name.toUpperCase(), data: d.risk.labels.map(function () { return d.thresholds[name]; }),
      borderColor: thresholdColors[name], borderDash: [6, 4], borderWidth: 1, pointRadius: 0, fill: false
    });
  });
  new Chart(document.getElementById("risk-chart"), {
    type: "line",
    data: { labels: d.risk.labels, datasets: riskSets },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { min: 0, max: 1 } },
      plugins: { legend: { position: "bottom" } }
    }
  });

  // SMART counters
  new Chart(document.getElementById("smart-chart"), {
    type: "line",
    data: {
      labels: d.smart.labels,
      datasets: d.smart.series.map(function (s, i) {
        return { label: s.label, data: s.values, borderColor: colors[i % colors.length],
                 backgroundColor: colors[i % colors.length], tension: 0.1, pointRadius: 0,
                 borderWidth: 2, spanGaps: true };
      })
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: { y: { beginAtZero: true } },
      plugins: { legend: { position: "bottom" } }
    }
  });
})();
