/* Конфігурація UI */
const CFG = {
  API_REST: "/processed_agent_data/",
  WS_PATH: "/ws",
  MAX_LOG: 80,
  MAX_CHART: 200,
  Z_BASELINE: 16500,
  WARN_Z_DEV: 100,
  BAD_Z_DEV: 2000,
  WARN_Y: 100,
  BAD_Y: 500,
  TILES: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
  TILES_ATTR:
    '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OSM</a> &copy; <a href="https://carto.com/attributions" target="_blank">CARTO</a>',
  DEFAULT_LAT: 50.4501,
  DEFAULT_LNG: 30.5234,
  DEFAULT_ZOOM: 13,
};

const STATE_COLORS = {
  GOOD: "#3fb950",
  WARNING: "#d29922",
  BAD: "#f85149",
};

/* Стан інтерфейсу */
const counts = { GOOD: 0, WARNING: 0, BAD: 0 };
const zHist = [];
const xHist = [];
const yHist = [];

let prevLatLng = null;
let currentStateSeg = null;
let currentStateKey = null;
let carMarker = null;
let allLatLngs = [];
let logCount = 0;
let wsRetryTimer = null;

/* Посилання на DOM */
const $ = (id) => document.getElementById(id);

const statusPill = $("status-pill");
const statusText = $("status-text");
const hdrPoints = $("hdr-points");
const hdrDist = $("hdr-dist");
const hdrDot = $("hdr-dot");
const hdrState = $("hdr-last-state");
const cntGood = $("cnt-good");
const cntWarning = $("cnt-warning");
const cntBad = $("cnt-bad");
const barGood = $("bar-good");
const barWarning = $("bar-warning");
const barBad = $("bar-bad");
const logBadge = $("log-badge");
const eventLog = $("event-log");
const btnFit = $("btn-fit");

/* Карта */
const canvasRenderer = L.canvas({ padding: 0.5 });

const map = L.map("map", {
  center: [CFG.DEFAULT_LAT, CFG.DEFAULT_LNG],
  zoom: CFG.DEFAULT_ZOOM,
  zoomControl: false,
  renderer: canvasRenderer,
});

L.tileLayer(CFG.TILES, {
  maxZoom: 19,
  attribution: CFG.TILES_ATTR,
  subdomains: "abcd",
}).addTo(map);

L.control.zoom({ position: "topright" }).addTo(map);

const stateLayers = {
  GOOD: L.featureGroup().addTo(map),
  WARNING: L.featureGroup().addTo(map),
  BAD: L.featureGroup().addTo(map),
};

document.querySelectorAll("[data-toggle]").forEach((checkbox) => {
  checkbox.addEventListener("change", (event) => {
    const target = event.target;
    const key = target.getAttribute("data-toggle");

    if (!key || !stateLayers[key]) {
      return;
    }

    if (target.checked) {
      stateLayers[key].addTo(map);
      return;
    }

    map.removeLayer(stateLayers[key]);
  });
});

const carIcon = L.divIcon({
  className: "",
  html: '<div class="rv-car"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

btnFit.addEventListener("click", () => {
  if (allLatLngs.length === 0) {
    return;
  }

  map.fitBounds(L.latLngBounds(allLatLngs), { padding: [48, 48], maxZoom: 17 });
});

/* Графіки */
const chartDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  animation: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: "rgba(22,27,34,0.95)",
      borderColor: "rgba(240,246,252,0.1)",
      borderWidth: 1,
      titleColor: "#8b949e",
      bodyColor: "#e6edf3",
      padding: 8,
      titleFont: { family: "'Inter', sans-serif", size: 11 },
      bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
    },
  },
  scales: {
    x: { display: false },
    y: {
      grid: { color: "rgba(240,246,252,0.06)" },
      ticks: {
        color: "#8b949e",
        font: { family: "'JetBrains Mono', monospace", size: 10 },
        maxTicksLimit: 4,
      },
      border: { color: "rgba(240,246,252,0.08)" },
    },
  },
  elements: {
    point: { radius: 0, hoverRadius: 3 },
    line: { borderWidth: 1.5, tension: 0.3 },
  },
};

const ctxZ = $("chartZ").getContext("2d");
const chartZ = new Chart(ctxZ, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "Z dev",
        data: [],
        borderColor: "#3fb950",
        backgroundColor: "rgba(63,185,80,0.08)",
        fill: true,
      },
    ],
  },
  options: {
    ...chartDefaults,
    plugins: {
      ...chartDefaults.plugins,
      annotation: {
        annotations: {
          baseline: {
            type: "line",
            yMin: 0,
            yMax: 0,
            borderColor: "rgba(240,246,252,0.2)",
            borderWidth: 1,
            borderDash: [4, 4],
          },
          warnHigh: {
            type: "line",
            yMin: CFG.WARN_Z_DEV,
            yMax: CFG.WARN_Z_DEV,
            borderColor: "rgba(210,153,34,0.5)",
            borderWidth: 1,
            borderDash: [3, 3],
            label: {
              content: "WARN",
              display: true,
              position: "end",
              font: { size: 9 },
              color: "#d29922",
              backgroundColor: "transparent",
              padding: 2,
            },
          },
          warnLow: {
            type: "line",
            yMin: -CFG.WARN_Z_DEV,
            yMax: -CFG.WARN_Z_DEV,
            borderColor: "rgba(210,153,34,0.5)",
            borderWidth: 1,
            borderDash: [3, 3],
          },
          badHigh: {
            type: "line",
            yMin: CFG.BAD_Z_DEV,
            yMax: CFG.BAD_Z_DEV,
            borderColor: "rgba(248,81,73,0.5)",
            borderWidth: 1,
            borderDash: [3, 3],
            label: {
              content: "BAD",
              display: true,
              position: "end",
              font: { size: 9 },
              color: "#f85149",
              backgroundColor: "transparent",
              padding: 2,
            },
          },
          badLow: {
            type: "line",
            yMin: -CFG.BAD_Z_DEV,
            yMax: -CFG.BAD_Z_DEV,
            borderColor: "rgba(248,81,73,0.5)",
            borderWidth: 1,
            borderDash: [3, 3],
          },
        },
      },
    },
    scales: {
      ...chartDefaults.scales,
      y: {
        ...chartDefaults.scales.y,
        title: { display: false },
      },
    },
  },
});

const ctxXY = $("chartXY").getContext("2d");
const chartXY = new Chart(ctxXY, {
  type: "line",
  data: {
    labels: [],
    datasets: [
      {
        label: "X",
        data: [],
        borderColor: "#58a6ff",
        backgroundColor: "rgba(88,166,255,0.06)",
        fill: false,
      },
      {
        label: "Y",
        data: [],
        borderColor: "#bc8cff",
        backgroundColor: "rgba(188,140,255,0.06)",
        fill: false,
      },
    ],
  },
  options: {
    ...chartDefaults,
    plugins: {
      ...chartDefaults.plugins,
      legend: {
        display: true,
        labels: {
          color: "#8b949e",
          boxWidth: 10,
          boxHeight: 10,
          font: { family: "'Inter', sans-serif", size: 10 },
          padding: 12,
        },
      },
    },
  },
});

/* Допоміжні функції */
function fmt(value, decimals = 5) {
  return Number(value).toFixed(decimals);
}

function fmtTime(timestamp) {
  if (!timestamp) {
    return "—";
  }

  const date = new Date(timestamp);
  return date.toLocaleTimeString("uk-UA", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const radiusKm = 6371;
  const radians = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * radians) / 2) ** 2 +
    Math.cos(lat1 * radians) *
      Math.cos(lat2 * radians) *
      Math.sin(((lon2 - lon1) * radians) / 2) ** 2;

  return radiusKm * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function totalDistKm() {
  let distance = 0;

  for (let index = 1; index < allLatLngs.length; index += 1) {
    distance += haversineKm(
      allLatLngs[index - 1][0],
      allLatLngs[index - 1][1],
      allLatLngs[index][0],
      allLatLngs[index][1],
    );
  }

  return distance;
}

function setStatus(type, text) {
  statusText.textContent = text;
  statusPill.className = `status-pill ${type}`.trim();
}

function normalizeRoadState(value) {
  if (typeof value !== "string") {
    return null;
  }

  const normalized = value.trim().toUpperCase();
  return Object.hasOwn(STATE_COLORS, normalized) ? normalized : null;
}

function normalizeSample(sample) {
  if (!sample || typeof sample !== "object") {
    return null;
  }

  const state = normalizeRoadState(sample.road_state);
  if (!state) {
    return null;
  }

  if (sample.agent_data?.gps && sample.agent_data?.accelerometer) {
    const { gps, accelerometer } = sample.agent_data;

    if (
      gps.latitude == null ||
      gps.longitude == null ||
      accelerometer.x == null ||
      accelerometer.y == null ||
      accelerometer.z == null
    ) {
      return null;
    }

    return {
      road_state: state,
      gps: {
        latitude: Number(gps.latitude),
        longitude: Number(gps.longitude),
      },
      accelerometer: {
        x: Number(accelerometer.x),
        y: Number(accelerometer.y),
        z: Number(accelerometer.z),
      },
      time: sample.agent_data.time ?? sample.timestamp ?? null,
    };
  }

  if (
    sample.latitude == null ||
    sample.longitude == null ||
    sample.x == null ||
    sample.y == null ||
    sample.z == null
  ) {
    return null;
  }

  return {
    road_state: state,
    gps: {
      latitude: Number(sample.latitude),
      longitude: Number(sample.longitude),
    },
    accelerometer: {
      x: Number(sample.x),
      y: Number(sample.y),
      z: Number(sample.z),
    },
    time: sample.timestamp ?? sample.time ?? null,
  };
}

function updateKPIs() {
  const total = counts.GOOD + counts.WARNING + counts.BAD || 1;

  cntGood.textContent = counts.GOOD;
  cntWarning.textContent = counts.WARNING;
  cntBad.textContent = counts.BAD;
  barGood.style.width = `${(counts.GOOD / total) * 100}%`;
  barWarning.style.width = `${(counts.WARNING / total) * 100}%`;
  barBad.style.width = `${(counts.BAD / total) * 100}%`;
  hdrPoints.textContent = allLatLngs.length;
  hdrDist.textContent = totalDistKm().toFixed(1);
}

function updateCharts() {
  const labels = zHist.map((_, index) => index + 1);

  chartZ.data.labels = labels;
  chartZ.data.datasets[0].data = zHist;
  chartXY.data.labels = labels;
  chartXY.data.datasets[0].data = xHist;
  chartXY.data.datasets[1].data = yHist;
  chartZ.update("none");
  chartXY.update("none");
}

function pushChartPoint(x, y, z) {
  zHist.push(z - CFG.Z_BASELINE);
  xHist.push(x);
  yHist.push(y);

  if (zHist.length <= CFG.MAX_CHART) {
    return;
  }

  zHist.shift();
  xHist.shift();
  yHist.shift();
}

function addLogItem(sample, isNew = false) {
  const empty = eventLog.querySelector(".log-empty");
  if (empty) {
    empty.remove();
  }

  const item = document.createElement("div");
  item.className = `log-item${isNew ? " log-new" : ""}`;
  item.innerHTML = `
    <div class="log-dot ${sample.road_state}"></div>
    <div class="log-body">
      <div class="log-coords">${fmt(sample.gps.latitude)}, ${fmt(sample.gps.longitude)}</div>
      <div class="log-acc">x ${fmt(sample.accelerometer.x, 1)} y ${fmt(sample.accelerometer.y, 1)} z ${fmt(sample.accelerometer.z, 0)}</div>
    </div>
    <div class="log-time">${fmtTime(sample.time)}</div>
  `;

  eventLog.prepend(item);
  logCount += 1;
  logBadge.textContent = logCount;
  logBadge.classList.add("has-items");

  while (eventLog.children.length > CFG.MAX_LOG) {
    eventLog.removeChild(eventLog.lastChild);
  }
}

function buildPopupHtml(sample) {
  return `
    <div class="rv-popup">
      <div class="rv-popup-state">
        <span class="rv-popup-badge ${sample.road_state}">${sample.road_state}</span>
      </div>
      <div class="rv-popup-grid">
        <strong>GPS</strong>
        <span class="rv-popup-mono">${fmt(sample.gps.latitude)}, ${fmt(sample.gps.longitude)}</span>
        <strong>Час</strong>
        <span>${fmtTime(sample.time)}</span>
        <strong>acc x</strong><span class="rv-popup-mono">${fmt(sample.accelerometer.x, 1)}</span>
        <strong>acc y</strong><span class="rv-popup-mono">${fmt(sample.accelerometer.y, 1)}</span>
        <strong>acc z</strong><span class="rv-popup-mono">${fmt(sample.accelerometer.z, 0)}</span>
      </div>
    </div>
  `;
}

function processPoint(rawSample, animate = false) {
  const sample = normalizeSample(rawSample);
  if (!sample) {
    return false;
  }

  const latlng = [sample.gps.latitude, sample.gps.longitude];
  allLatLngs.push(latlng);

  if (prevLatLng !== null) {
    if (sample.road_state === currentStateKey && currentStateSeg) {
      currentStateSeg.addLatLng(latlng);
    } else {
      if (currentStateSeg) {
        currentStateSeg.addLatLng(latlng);
      }

      currentStateKey = sample.road_state;
      currentStateSeg = L.polyline([prevLatLng, latlng], {
        color: STATE_COLORS[sample.road_state],
        weight: 5,
        opacity: 0.88,
        lineCap: "round",
        lineJoin: "round",
        renderer: canvasRenderer,
      });

      currentStateSeg.bindPopup(buildPopupHtml(sample), { maxWidth: 240 });
      stateLayers[sample.road_state].addLayer(currentStateSeg);
    }
  } else {
    currentStateKey = sample.road_state;
  }

  prevLatLng = latlng;

  if (!carMarker) {
    carMarker = L.marker(latlng, { icon: carIcon, zIndexOffset: 1000 }).addTo(map);
  } else {
    carMarker.setLatLng(latlng);
  }

  if (animate) {
    map.panTo(latlng, { animate: true, duration: 0.4 });
  }

  counts[sample.road_state] += 1;
  updateKPIs();
  hdrDot.style.background = STATE_COLORS[sample.road_state];
  hdrState.textContent = sample.road_state;

  pushChartPoint(sample.accelerometer.x, sample.accelerometer.y, sample.accelerometer.z);
  updateCharts();
  addLogItem(sample, animate);

  return true;
}

/* Завантаження історії */
async function loadHistory() {
  setStatus("", "Завантаження даних з Store...");

  try {
    const response = await fetch(CFG.API_REST);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    let processedCount = 0;

    data.forEach((sample) => {
      if (processPoint(sample, false)) {
        processedCount += 1;
      }
    });

    if (allLatLngs.length > 1) {
      map.fitBounds(L.latLngBounds(allLatLngs), { padding: [48, 48], maxZoom: 17 });
    }

    setStatus("connected", `Store API · ${processedCount} записів`);
  } catch (error) {
    setStatus("error", `Помилка завантаження: ${error.message}`);
    console.error(error);
  }
}

/* Підключення до WebSocket */
function connectWS() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = `${protocol}://${location.host}${CFG.WS_PATH}`;
  const websocket = new WebSocket(wsUrl);

  websocket.onopen = () => {
    setStatus("connected", "WebSocket live · отримуємо нові точки");

    if (wsRetryTimer) {
      clearTimeout(wsRetryTimer);
      wsRetryTimer = null;
    }
  };

  websocket.onmessage = (event) => {
    try {
      const sample = JSON.parse(event.data);
      const processed = processPoint(sample, true);

      if (!processed) {
        console.warn("WS payload skipped:", sample);
      }
    } catch (error) {
      console.warn("WS parse error:", error);
    }
  };

  websocket.onclose = () => {
    setStatus("error", "WebSocket відключено · повторна спроба...");
    wsRetryTimer = setTimeout(connectWS, 3500);
  };

  websocket.onerror = () => {
    websocket.close();
  };
}

/* Запуск інтерфейсу */
loadHistory().then(connectWS);
