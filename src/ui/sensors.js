/* =================================================================
 * UrbanPulse IoT · UI для універсальних сенсорів
 * Додає поверх дорожньої вкладки:
 *   — навігацію вкладками у шапці;
 *   — окремий WebSocket /ws/sensors із розподілом за sensor_type;
 *   — рендерери для паркінгів, світлофорів, повітря та енергії;
 *   — опитування /network_anomalies/ для вкладки мережевого стану.
 * ================================================================= */
(() => {
  "use strict";

  const SENSORS_CFG = {
    WS_PATH: "/ws/sensors",
    REST_READINGS: "/sensor_readings/",
    REST_NETWORK: "/network_anomalies/",
    MAX_HISTORY: 60,
    HYDRATE_POLL_MS: 20_000,
    NETWORK_POLL_MS: 10_000,
  };

  // -----------------------------------------------------------------
  // Tab-менеджер
  // -----------------------------------------------------------------
  const tabButtons = Array.from(document.querySelectorAll(".tab-btn"));
  const panels = Object.fromEntries(
    Array.from(document.querySelectorAll(".tab-panel")).map((el) => {
      const key = el.id.replace(/^panel-/, "");
      return [key, el];
    })
  );

  function activateTab(key) {
    tabButtons.forEach((btn) => {
      const active = btn.dataset.tab === key;
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
    Object.entries(panels).forEach(([id, el]) => {
      el.hidden = id !== key;
    });

    // Leaflet/Chart.js не знають про display:none — примусово перерахуємо розміри.
    if (key === "road-vision" && window._rvMap) {
      setTimeout(() => window._rvMap.invalidateSize(), 50);
    }
    if (key === "air-quality" && airState.chart) {
      setTimeout(() => airState.chart.resize(), 50);
    }
  }

  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });

  // -----------------------------------------------------------------
  // Shared helpers
  // -----------------------------------------------------------------
  const $ = (id) => document.getElementById(id);

  const fmt = (n, digits = 1) =>
    Number.isFinite(n) ? n.toLocaleString("uk-UA", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : "—";
  const fmtInt = (n) => (Number.isFinite(n) ? n.toLocaleString("uk-UA") : "—");

  function clearEmptyHint(container) {
    const hint = container.querySelector(".empty-hint");
    if (hint) hint.remove();
  }

  function wireGrafanaLinks() {
    const host = location.hostname || "localhost";
    const base = `http://${host}:3000`;
    const links = Array.from(document.querySelectorAll(".link-list a"));
    const hrefs = [
      `${base}/d/urbanpulse-overview/urbanpulse-e28094-overview`,
      `${base}/d/urbanpulse-air/urbanpulse-e28094-sensors-air-energy-traffic`,
      `${base}/d/urbanpulse-network/urbanpulse-e28094-network-health`,
    ];

    links.forEach((el, idx) => {
      if (hrefs[idx]) el.href = hrefs[idx];
    });
  }

  function upsertCard(container, id, create, update) {
    let card = container.querySelector(`[data-id="${CSS.escape(id)}"]`);
    if (!card) {
      clearEmptyHint(container);
      card = create();
      card.dataset.id = id;
      container.appendChild(card);
    }
    update(card);
    return card;
  }

  // -----------------------------------------------------------------
  // Car Parks
  // -----------------------------------------------------------------
  const parksState = { items: new Map() };
  const parksGrid = $("parks-grid");

  function handleCarPark(reading) {
    const id = reading.metadata.sensor_id;
    const p = reading.payload;
    parksState.items.set(id, reading);

    upsertCard(
      parksGrid,
      id,
      () => {
        const el = document.createElement("div");
        el.className = "park-card";
        el.innerHTML = `
          <div class="park-card-head">
            <div>
              <div class="park-card-name">Паркомайданчик</div>
              <div class="park-card-id"></div>
            </div>
            <div class="park-card-total"></div>
          </div>
          <div class="park-gauge">
            <svg class="park-gauge-svg" viewBox="0 0 120 64" preserveAspectRatio="xMidYMid meet">
              <path d="M8 56 A52 52 0 0 1 112 56" fill="none" stroke="#2d333b" stroke-width="10" stroke-linecap="round"/>
              <path class="park-gauge-arc" d="M8 56 A52 52 0 0 1 112 56" fill="none" stroke="#06b6d4" stroke-width="10" stroke-linecap="round" stroke-dasharray="0 999"/>
            </svg>
            <div class="park-gauge-label"></div>
          </div>
          <div class="park-stats">
            <span>зайнято: <strong class="park-used">0</strong></span>
            <span>вільно: <strong class="park-free">0</strong></span>
          </div>
        `;
        return el;
      },
      (card) => {
        const rate = p.occupancy_rate ?? p.occupied_spots / p.total_spots;
        const pct = Math.round(rate * 100);
        card.classList.toggle("is-full", pct >= 95);
        card.querySelector(".park-card-id").textContent = id;
        card.querySelector(".park-card-total").textContent = `${p.total_spots} місць`;
        card.querySelector(".park-gauge-label").textContent = `${pct}%`;
        const arc = card.querySelector(".park-gauge-arc");
        // довжина дуги ~163 px -> 163*rate
        arc.setAttribute("stroke-dasharray", `${(163 * rate).toFixed(1)} 999`);
        arc.setAttribute("stroke", pct >= 95 ? "#f85149" : pct >= 80 ? "#d29922" : "#06b6d4");
        card.querySelector(".park-used").textContent = p.occupied_spots;
        card.querySelector(".park-free").textContent = p.total_spots - p.occupied_spots;
      }
    );

    // KPI-банер
    const vals = Array.from(parksState.items.values());
    const totals = vals.reduce(
      (acc, r) => {
        acc.total += r.payload.total_spots;
        acc.occ += r.payload.occupied_spots;
        if (r.payload.occupied_spots / r.payload.total_spots >= 0.95) acc.full += 1;
        return acc;
      },
      { total: 0, occ: 0, full: 0 }
    );
    $("parks-sensor-count").textContent = fmtInt(vals.length);
    $("parks-avg-occ").textContent = totals.total ? `${Math.round((totals.occ / totals.total) * 100)}%` : "0%";
    $("parks-overcrowded").textContent = fmtInt(totals.full);
    $("parks-free").textContent = fmtInt(totals.total - totals.occ);
  }

  // -----------------------------------------------------------------
  // Traffic Lights
  // -----------------------------------------------------------------
  const lightsState = { items: new Map() };
  const lightsGrid = $("lights-grid");

  function handleTrafficLight(reading) {
    const id = reading.metadata.sensor_id;
    const p = reading.payload;
    lightsState.items.set(id, reading);

    upsertCard(
      lightsGrid,
      id,
      () => {
        const el = document.createElement("div");
        el.className = "light-card";
        el.innerHTML = `
          <div class="light-signal">
            <div class="light-bulb red"></div>
            <div class="light-bulb yellow"></div>
            <div class="light-bulb green"></div>
          </div>
          <div class="light-info">
            <div class="light-name">Перехрестя</div>
            <div class="light-id"></div>
            <div class="light-queue">
              <span class="light-queue-label">черга</span>
              <div class="light-queue-bar"><div class="light-queue-fill"></div></div>
              <span class="light-queue-count"></span>
            </div>
            <div class="light-pedestrian"></div>
          </div>
        `;
        return el;
      },
      (card) => {
        const queue = p.queue_length ?? 0;
        card.classList.toggle("is-gridlock", queue >= 20);
        card.querySelector(".light-id").textContent = id;
        card.querySelectorAll(".light-bulb").forEach((b) => b.classList.remove("active"));
        const cls = {
          red: "red", yellow: "yellow", green: "green",
          flashing_yellow: "yellow", off: null,
        }[p.state];
        if (cls) card.querySelector(`.light-bulb.${cls}`).classList.add("active");
        const pct = Math.min(100, (queue / 30) * 100);
        card.querySelector(".light-queue-fill").style.width = `${pct}%`;
        card.querySelector(".light-queue-count").textContent = queue;
        card.querySelector(".light-pedestrian").textContent = p.pedestrian_request ? "⏴ виклик пішохода" : "";
      }
    );

    const vals = Array.from(lightsState.items.values());
    const queueSum = vals.reduce((s, r) => s + (r.payload.queue_length || 0), 0);
    const gridlock = vals.filter((r) => (r.payload.queue_length || 0) >= 20).length;
    $("lights-count").textContent = fmtInt(vals.length);
    $("lights-avg-queue").textContent = vals.length ? fmt(queueSum / vals.length, 0) : "0";
    $("lights-gridlock").textContent = fmtInt(gridlock);
  }

  // -----------------------------------------------------------------
  // Air Quality
  // -----------------------------------------------------------------
  const airState = { items: new Map(), chart: null, series: new Map() };
  const airStations = $("air-stations");

  function aqiCategory(pm25) {
    if (pm25 >= 150) return { label: "Hazardous", color: "#7c3aed" };
    if (pm25 >= 55) return { label: "Very Unhealthy", color: "#ef4444" };
    if (pm25 >= 35) return { label: "Unhealthy", color: "#f59e0b" };
    if (pm25 >= 12) return { label: "Moderate", color: "#facc15" };
    return { label: "Good", color: "#10b981" };
  }

  function ensureAirChart() {
    if (airState.chart || typeof Chart === "undefined") return airState.chart;
    const ctx = $("chart-pm25").getContext("2d");
    airState.chart = new Chart(ctx, {
      type: "line",
      data: { labels: [], datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        plugins: { legend: { labels: { color: "#8b949e", font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: "#8b949e" }, grid: { color: "rgba(240,246,252,0.05)" } },
          y: { ticks: { color: "#8b949e" }, grid: { color: "rgba(240,246,252,0.05)" }, title: { display: true, text: "PM2.5, мкг/м³", color: "#8b949e" } },
        },
      },
    });
    return airState.chart;
  }

  function handleAirQuality(reading) {
    const id = reading.metadata.sensor_id;
    const p = reading.payload;
    airState.items.set(id, reading);
    const aqi = aqiCategory(p.pm2_5);

    upsertCard(
      airStations,
      id,
      () => {
        const el = document.createElement("div");
        el.className = "air-card";
        el.innerHTML = `
          <div class="air-card-head">
            <div class="park-card-id"></div>
            <div class="air-aqi-chip"></div>
          </div>
          <div><span class="air-pm25"></span><span class="air-pm25-unit">мкг/м³ PM2.5</span></div>
          <div class="air-metrics">
            <div class="air-metric"><div class="air-metric-label">PM10</div><div class="air-metric-value pm10">—</div></div>
            <div class="air-metric"><div class="air-metric-label">NO₂</div><div class="air-metric-value no2">—</div></div>
            <div class="air-metric"><div class="air-metric-label">O₃</div><div class="air-metric-value o3">—</div></div>
            <div class="air-metric"><div class="air-metric-label">t °C</div><div class="air-metric-value tmp">—</div></div>
            <div class="air-metric"><div class="air-metric-label">RH %</div><div class="air-metric-value rh">—</div></div>
            <div class="air-metric"><div class="air-metric-label">P hPa</div><div class="air-metric-value pr">—</div></div>
          </div>
        `;
        return el;
      },
      (card) => {
        card.style.setProperty("--aqi-color", aqi.color);
        card.style.setProperty("--aqi-tint", aqi.color);
        card.querySelector(".park-card-id").textContent = id;
        card.querySelector(".air-aqi-chip").textContent = aqi.label;
        card.querySelector(".air-aqi-chip").style.background = aqi.color;
        card.querySelector(".air-pm25").textContent = fmt(p.pm2_5, 1);
        card.querySelector(".pm10").textContent = fmt(p.pm10, 1);
        card.querySelector(".no2").textContent = fmt(p.no2, 1);
        card.querySelector(".o3").textContent = fmt(p.o3, 1);
        card.querySelector(".tmp").textContent = fmt(p.temperature_c, 1);
        card.querySelector(".rh").textContent = fmt(p.humidity_percent, 0);
        card.querySelector(".pr").textContent = fmt(p.pressure_hpa, 0);
      }
    );

    // Чарт PM2.5: одна лінія на сенсор, ковзне вікно 60 точок.
    const chart = ensureAirChart();
    if (chart) {
      let series = airState.series.get(id);
      if (!series) {
        const hue = (airState.series.size * 67) % 360;
        series = { data: [], color: `hsl(${hue}, 70%, 60%)` };
        airState.series.set(id, series);
        chart.data.datasets.push({
          label: id, borderColor: series.color, backgroundColor: series.color,
          data: series.data, tension: 0.25, pointRadius: 0, borderWidth: 1.5,
        });
      }
      const label = new Date(reading.metadata.timestamp).toLocaleTimeString("uk-UA");
      if (!chart.data.labels.includes(label)) chart.data.labels.push(label);
      series.data.push({ x: label, y: p.pm2_5 });
      if (series.data.length > SENSORS_CFG.MAX_HISTORY) series.data.shift();
      if (chart.data.labels.length > SENSORS_CFG.MAX_HISTORY) chart.data.labels.shift();
      chart.update("none");
    }

    const vals = Array.from(airState.items.values());
    const pm25Arr = vals.map((r) => r.payload.pm2_5);
    $("air-max-pm25").textContent = fmt(Math.max(...pm25Arr), 1);
    $("air-avg-pm25").textContent = fmt(pm25Arr.reduce((a, b) => a + b, 0) / pm25Arr.length, 1);
    $("air-unhealthy").textContent = fmtInt(pm25Arr.filter((v) => v >= 35).length);
  }

  // -----------------------------------------------------------------
  // Energy Meters
  // -----------------------------------------------------------------
  const energyState = { items: new Map() };
  const energyGrid = $("energy-grid");

  function handleEnergyMeter(reading) {
    const id = reading.metadata.sensor_id;
    const p = reading.payload;
    energyState.items.set(id, reading);
    const flags = reading.metadata.anomaly_flags || [];
    const isAlert = flags.length > 0;

    upsertCard(
      energyGrid,
      id,
      () => {
        const el = document.createElement("div");
        el.className = "energy-card";
        el.innerHTML = `
          <div class="energy-card-head">
            <div>
              <div class="park-card-name">Лічильник</div>
              <div class="park-card-id"></div>
            </div>
          </div>
          <div><span class="energy-power"></span><span class="energy-power-unit">кВт</span></div>
          <div class="energy-metrics">
            <div><div class="energy-metric-label">U, В</div><div class="energy-metric-value volt">—</div></div>
            <div><div class="energy-metric-label">I, А</div><div class="energy-metric-value cur">—</div></div>
            <div><div class="energy-metric-label">cos φ</div><div class="energy-metric-value pf">—</div></div>
          </div>
          <div class="energy-metrics" style="grid-template-columns:1fr">
            <div><div class="energy-metric-label">Σ кВт·год</div><div class="energy-metric-value kwh">—</div></div>
          </div>
          <div class="energy-flags"></div>
        `;
        return el;
      },
      (card) => {
        card.classList.toggle("is-alert", isAlert);
        card.querySelector(".park-card-id").textContent = id;
        card.querySelector(".energy-power").textContent = fmt(p.power_kw, 2);
        card.querySelector(".volt").textContent = fmt(p.voltage_v, 1);
        card.querySelector(".cur").textContent = fmt(p.current_a, 2);
        card.querySelector(".pf").textContent = p.power_factor != null ? fmt(p.power_factor, 2) : "—";
        card.querySelector(".kwh").textContent = fmt(p.cumulative_kwh, 2);
        const flagsEl = card.querySelector(".energy-flags");
        flagsEl.innerHTML = "";
        flags.forEach((f) => {
          const chip = document.createElement("span");
          chip.className = "anomaly-chip";
          chip.textContent = f;
          flagsEl.appendChild(chip);
        });
      }
    );

    const vals = Array.from(energyState.items.values());
    const totalKw = vals.reduce((s, r) => s + (r.payload.power_kw || 0), 0);
    const pfVals = vals.map((r) => r.payload.power_factor).filter((v) => v != null);
    const voltageAlerts = vals.filter((r) =>
      (r.metadata.anomaly_flags || []).includes("voltage_out_of_range")
    ).length;
    $("energy-total-kw").textContent = fmt(totalKw, 1);
    $("energy-avg-pf").textContent = pfVals.length ? fmt(pfVals.reduce((a, b) => a + b, 0) / pfVals.length, 2) : "—";
    $("energy-voltage-alerts").textContent = fmtInt(voltageAlerts);
  }

  // -----------------------------------------------------------------
  // Dispatcher + WebSocket
  // -----------------------------------------------------------------
  const handlers = {
    car_park: handleCarPark,
    traffic_light: handleTrafficLight,
    air_quality: handleAirQuality,
    energy_meter: handleEnergyMeter,
  };

  function dispatchReading(reading) {
    const handler = handlers[reading.metadata.sensor_type];
    if (handler) handler(reading);
  }

  function connectSensorsWs() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}${SENSORS_CFG.WS_PATH}`;
    let ws;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      console.error("Sensors WS init failed:", err);
      setTimeout(connectSensorsWs, 3_000);
      return;
    }
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        // Очікуємо SensorReadingInDB (має sensor_type), а не повну SensorReading.
        if (data.sensor_type && data.payload) {
          const wrapped = {
            metadata: {
              sensor_id: data.sensor_id,
              sensor_type: data.sensor_type,
              location: { latitude: data.latitude, longitude: data.longitude },
              timestamp: data.timestamp,
              anomaly_flags: data.anomaly_flags || [],
            },
            payload: data.payload,
          };
          dispatchReading(wrapped);
        } else {
          dispatchReading(data);
        }
      } catch (err) {
        console.warn("Sensors WS: не вдалося розібрати повідомлення", err);
      }
    };
    ws.onclose = () => setTimeout(connectSensorsWs, 3_000);
    ws.onerror = () => ws.close();
  }

  // При старті завантажуємо останні показання, щоб вкладки не були порожніми.
  async function hydrateRecent() {
    try {
      const res = await fetch(`${SENSORS_CFG.REST_READINGS}?limit=500`);
      if (!res.ok) return;
      const items = await res.json();
      // Останнє показання на сенсор.
      const latest = new Map();
      for (const r of items) {
        const key = `${r.sensor_type}:${r.sensor_id}`;
        const existing = latest.get(key);
        if (!existing || new Date(r.timestamp) > new Date(existing.timestamp)) {
          latest.set(key, r);
        }
      }
      for (const r of latest.values()) {
        dispatchReading({
          metadata: {
            sensor_id: r.sensor_id,
            sensor_type: r.sensor_type,
            location: { latitude: r.latitude, longitude: r.longitude },
            timestamp: r.timestamp,
            anomaly_flags: r.anomaly_flags || [],
          },
          payload: r.payload,
        });
      }
    } catch (err) {
      console.warn("Sensors hydrate failed:", err);
    }
  }

  // -----------------------------------------------------------------
  // Network health polling
  // -----------------------------------------------------------------
  const netLog = $("net-log");

  async function pollNetworkAnomalies() {
    try {
      const res = await fetch(`${SENSORS_CFG.REST_NETWORK}?limit=100`);
      if (!res.ok) return;
      const items = await res.json();
      netLog.innerHTML = "";
      if (!items.length) {
        netLog.innerHTML = '<div class="log-empty"><p>Поки що все спокійно.</p></div>';
      }
      items.forEach((a) => {
        const row = document.createElement("div");
        row.className = `net-entry ${a.severity}`;
        row.innerHTML = `
          <span class="net-entry-time">${new Date(a.timestamp).toLocaleTimeString("uk-UA")}</span>
          <span class="net-entry-metric">${a.metric} <span style="color:var(--text-muted)">z=${fmt(a.zscore, 2)}</span></span>
          <span class="net-entry-value">${fmt(a.value, 3)}</span>
        `;
        netLog.appendChild(row);
      });
      const now = Date.now();
      const hourAgo = now - 3_600_000;
      const dayAgo = now - 86_400_000;
      $("net-anoms-hour").textContent = fmtInt(items.filter((a) => new Date(a.timestamp).getTime() >= hourAgo).length);
      $("net-anoms-day").textContent = fmtInt(items.filter((a) => new Date(a.timestamp).getTime() >= dayAgo).length);
      $("net-last-update").textContent = new Date().toLocaleTimeString("uk-UA");
    } catch (err) {
      console.warn("Network poll failed:", err);
    }
  }

  // -----------------------------------------------------------------
  // Bootstrap
  // -----------------------------------------------------------------
  window.addEventListener("DOMContentLoaded", () => {
    wireGrafanaLinks();
    hydrateRecent();
    connectSensorsWs();
    pollNetworkAnomalies();
    setInterval(hydrateRecent, SENSORS_CFG.HYDRATE_POLL_MS);
    setInterval(pollNetworkAnomalies, SENSORS_CFG.NETWORK_POLL_MS);
  });
})();
