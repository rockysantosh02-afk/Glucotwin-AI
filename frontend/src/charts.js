/**
 * GlucoTwin AI - High-Performance Pure SVG Charting Engine
 * Generates responsive, interactive clinical visualizations with zero external dependencies.
 */

export class ChartRenderer {
  /**
   * Helper to compute coordinate scaling.
   */
  static getScales(width, height, padding, xMin, xMax, yMin, yMax) {
    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;

    const scaleX = (val) => padding.left + ((val - xMin) / (xMax - xMin || 1)) * plotWidth;
    const scaleY = (val) => padding.top + plotHeight - ((val - yMin) / (yMax - yMin || 1)) * plotHeight;

    return { scaleX, scaleY, plotWidth, plotHeight };
  }

  /**
   * Tier 1: Continuous Glucose Monitoring (CGM) Chart
   */
  static renderCGMChart(containerId, readings) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!readings || readings.length === 0) {
      container.innerHTML = `<div class="chart-placeholder">No telemetry readings to display. Seed or ingest data to visualize.</div>`;
      return;
    }

    const width = 1000;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 50 };

    const yMin = 40.0;
    const yMax = Math.max(260.0, ...readings.map(r => r.glucose_mg_dl + 20));

    // Time scaling (indices 0 to N-1)
    const n = readings.length;
    const { scaleX, scaleY, plotWidth, plotHeight } = this.getScales(width, height, padding, 0, n - 1, yMin, yMax);

    // Target Range Box (70 to 180 mg/dL)
    const tirYTop = scaleY(180.0);
    const tirYBottom = scaleY(70.0);
    const tirBoxHeight = tirYBottom - tirYTop;

    // Build SVG Path for CGM curve
    let pathD = '';
    let areaD = `M ${scaleX(0)} ${scaleY(yMin)} `;

    readings.forEach((r, i) => {
      const x = scaleX(i);
      const y = scaleY(r.glucose_mg_dl);
      if (i === 0) {
        pathD += `M ${x} ${y} `;
        areaD += `L ${x} ${y} `;
      } else {
        pathD += `L ${x} ${y} `;
        areaD += `L ${x} ${y} `;
      }
    });

    areaD += `L ${scaleX(n - 1)} ${scaleY(yMin)} Z`;

    // Event Markers (Meals & Boluses)
    let eventElements = '';
    readings.forEach((r, i) => {
      const x = scaleX(i);
      const y = scaleY(r.glucose_mg_dl);

      if (r.meal_carbs_grams && r.meal_carbs_grams > 0) {
        eventElements += `
          <g class="marker-group" transform="translate(${x}, ${y - 12})">
            <polygon points="0,-7 6,0 0,7 -6,0" fill="#10b981" stroke="#ffffff" stroke-width="1.5" />
            <text x="0" y="-10" text-anchor="middle" fill="#34d399" font-size="9" font-family="JetBrains Mono" font-weight="600">${r.meal_carbs_grams}g</text>
          </g>
        `;
      }

      if (r.bolus_synthetic_units && r.bolus_synthetic_units > 0) {
        eventElements += `
          <g class="marker-group" transform="translate(${x}, ${y + 14})">
            <circle cx="0" cy="0" r="4.5" fill="#38bdf8" stroke="#ffffff" stroke-width="1.5" />
            <text x="0" y="14" text-anchor="middle" fill="#38bdf8" font-size="9" font-family="JetBrains Mono" font-weight="600">${r.bolus_synthetic_units}U</text>
          </g>
        `;
      }
    });

    // Gridlines and labels
    const gridYValues = [54, 70, 120, 180, 250];
    let gridLines = '';
    gridYValues.forEach(val => {
      const gy = scaleY(val);
      const isTarget = (val === 70 || val === 180);
      gridLines += `
        <line x1="${padding.left}" y1="${gy}" x2="${width - padding.right}" y2="${gy}" 
              stroke="${isTarget ? '#10b981' : 'rgba(255,255,255,0.08)'}" 
              stroke-dasharray="${isTarget ? '4,4' : '2,4'}" stroke-width="${isTarget ? '1.5' : '1'}" />
        <text x="${padding.left - 8}" y="${gy + 4}" fill="${isTarget ? '#34d399' : '#64748b'}" 
              font-size="10" font-family="JetBrains Mono" text-anchor="end">${val}</text>
      `;
    });

    // Time ticks (first, middle, last)
    const firstTime = readings[0].timestamp ? new Date(readings[0].timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '0m';
    const lastTime = readings[n - 1].timestamp ? new Date(readings[n - 1].timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `${n * 5}m`;
    const midIdx = Math.floor(n / 2);
    const midTime = readings[midIdx].timestamp ? new Date(readings[midIdx].timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `${midIdx * 5}m`;

    const timeLabels = `
      <text x="${scaleX(0)}" y="${height - 12}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="start">${firstTime}</text>
      <text x="${scaleX(midIdx)}" y="${height - 12}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="middle">${midTime}</text>
      <text x="${scaleX(n - 1)}" y="${height - 12}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="end">${lastTime}</text>
    `;

    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%" preserveAspectRatio="none">
        <defs>
          <linearGradient id="cgmAreaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#38bdf8" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="#38bdf8" stop-opacity="0.0"/>
          </linearGradient>
        </defs>

        <!-- Target Zone (70 - 180 mg/dL) -->
        <rect x="${padding.left}" y="${tirYTop}" width="${plotWidth}" height="${tirBoxHeight}" 
              fill="rgba(16, 185, 129, 0.08)" stroke="none" />

        <!-- Grid Lines -->
        ${gridLines}

        <!-- Shaded Area -->
        <path d="${areaD}" fill="url(#cgmAreaGrad)" />

        <!-- Glucose Curve -->
        <path d="${pathD}" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linejoin="round" />

        <!-- Events -->
        ${eventElements}

        <!-- X Axis Labels -->
        ${timeLabels}
      </svg>
    `;
  }

  /**
   * Tier 2: Modal Day 24-Hour AGP Percentiles Chart
   */
  static renderAGPPercentileChart(containerId, hourlyPercentiles) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!hourlyPercentiles || hourlyPercentiles.length === 0) {
      container.innerHTML = `<div class="chart-placeholder">Compute AGP to render modal day curve.</div>`;
      return;
    }

    const width = 1000;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 50 };

    const yMin = 40.0;
    const yMax = 280.0;
    const { scaleX, scaleY, plotWidth, plotHeight } = this.getScales(width, height, padding, 0, 23, yMin, yMax);

    // Target range rectangle
    const tirYTop = scaleY(180.0);
    const tirYBottom = scaleY(70.0);

    // Construct 10th - 90th envelope path
    let env1090Top = '';
    let env1090Bottom = '';
    let env2575Top = '';
    let env2575Bottom = '';
    let medianPath = '';

    hourlyPercentiles.forEach((hp, i) => {
      const x = scaleX(hp.hour);
      const y10 = scaleY(hp.p10);
      const y25 = scaleY(hp.p25);
      const y50 = scaleY(hp.p50);
      const y75 = scaleY(hp.p75);
      const y90 = scaleY(hp.p90);

      if (i === 0) {
        env1090Top += `M ${x} ${y90} `;
        env2575Top += `M ${x} ${y75} `;
        medianPath += `M ${x} ${y50} `;
      } else {
        env1090Top += `L ${x} ${y90} `;
        env2575Top += `L ${x} ${y75} `;
        medianPath += `L ${x} ${y50} `;
      }
    });

    for (let i = hourlyPercentiles.length - 1; i >= 0; i--) {
      const hp = hourlyPercentiles[i];
      const x = scaleX(hp.hour);
      env1090Bottom += `L ${x} ${scaleY(hp.p10)} `;
      env2575Bottom += `L ${x} ${scaleY(hp.p25)} `;
    }

    const path1090 = `${env1090Top} ${env1090Bottom} Z`;
    const path2575 = `${env2575Top} ${env2575Bottom} Z`;

    // Hour markers (00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00)
    let hourLabels = '';
    [0, 3, 6, 9, 12, 15, 18, 21].forEach(h => {
      const x = scaleX(h);
      hourLabels += `<text x="${x}" y="${height - 12}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="middle">${h.toString().padStart(2, '0')}:00</text>`;
    });

    // Y Axis grid
    let gridLines = '';
    [70, 120, 180, 250].forEach(val => {
      const gy = scaleY(val);
      gridLines += `
        <line x1="${padding.left}" y1="${gy}" x2="${width - padding.right}" y2="${gy}" 
              stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,3" />
        <text x="${padding.left - 8}" y="${gy + 4}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="end">${val}</text>
      `;
    });

    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%" preserveAspectRatio="none">
        <!-- Target band (70 - 180) -->
        <rect x="${padding.left}" y="${tirYTop}" width="${plotWidth}" height="${tirYBottom - tirYTop}" 
              fill="rgba(16, 185, 129, 0.08)" stroke="none" />

        ${gridLines}

        <!-- 10th - 90th percentile envelope -->
        <path d="${path1090}" fill="rgba(99, 102, 241, 0.15)" stroke="rgba(99, 102, 241, 0.4)" stroke-width="1" />

        <!-- 25th - 75th percentile envelope -->
        <path d="${path2575}" fill="rgba(99, 102, 241, 0.32)" stroke="rgba(129, 140, 248, 0.6)" stroke-width="1" />

        <!-- 50th median curve -->
        <path d="${medianPath}" fill="none" stroke="#ec4899" stroke-width="3" stroke-linecap="round" />

        ${hourLabels}
      </svg>
    `;
  }

  /**
   * Tier 3: Forward Digital Twin Forecast Trajectory Chart
   */
  static renderForecastChart(containerId, historyReadings, forecastPoints) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!forecastPoints || forecastPoints.length === 0) {
      container.innerHTML = `<div class="chart-placeholder">Click 'Run Twin Forecast' to calculate projection.</div>`;
      return;
    }

    const width = 1000;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 50 };

    const hist = historyReadings ? historyReadings.slice(-12) : [];
    const totalPoints = hist.length + forecastPoints.length;

    const allG = [
      ...hist.map(r => r.glucose_mg_dl),
      ...forecastPoints.map(p => p.predicted_glucose),
      ...forecastPoints.filter(p => p.ci_upper).map(p => p.ci_upper)
    ];

    const yMin = Math.max(40.0, Math.min(54.0, ...allG) - 10);
    const yMax = Math.max(240.0, Math.max(...allG) + 20);

    const { scaleX, scaleY, plotWidth } = this.getScales(width, height, padding, 0, totalPoints - 1, yMin, yMax);

    // Target range band
    const tirYTop = scaleY(180.0);
    const tirYBottom = scaleY(70.0);

    // History curve
    let histPath = '';
    hist.forEach((r, i) => {
      const x = scaleX(i);
      const y = scaleY(r.glucose_mg_dl);
      histPath += `${i === 0 ? 'M' : 'L'} ${x} ${y} `;
    });

    // Bridge point: last historical point connecting to first forecast point
    const bridgeX = scaleX(hist.length - 1);
    const bridgeY = scaleY(hist[hist.length - 1].glucose_mg_dl);

    // Forecast path
    let fcPath = `M ${bridgeX} ${bridgeY} `;
    forecastPoints.forEach((p, i) => {
      const x = scaleX(hist.length + i);
      const y = scaleY(p.predicted_glucose);
      fcPath += `L ${x} ${y} `;
    });

    // 95% Confidence Interval Fan Path
    let ciFanPath = '';
    if (forecastPoints[0].ci_lower !== null) {
      let ciTop = `M ${bridgeX} ${bridgeY} `;
      let ciBottom = '';

      forecastPoints.forEach((p, i) => {
        const x = scaleX(hist.length + i);
        ciTop += `L ${x} ${scaleY(p.ci_upper)} `;
      });

      for (let i = forecastPoints.length - 1; i >= 0; i--) {
        const p = forecastPoints[i];
        const x = scaleX(hist.length + i);
        ciBottom += `L ${x} ${scaleY(p.ci_lower)} `;
      }
      ciBottom += `L ${bridgeX} ${bridgeY} Z`;
      ciFanPath = `${ciTop} ${ciBottom}`;
    }

    // Vertical bridge line separating history from prediction
    const bridgeLine = `
      <line x1="${bridgeX}" y1="${padding.top}" x2="${bridgeX}" y2="${height - padding.bottom}" 
            stroke="rgba(255,255,255,0.25)" stroke-dasharray="4,4" stroke-width="1.5" />
      <text x="${bridgeX - 8}" y="${padding.top + 14}" fill="#38bdf8" font-size="10" font-family="JetBrains Mono" text-anchor="end">Now</text>
      <text x="${bridgeX + 8}" y="${padding.top + 14}" fill="#ec4899" font-size="10" font-family="JetBrains Mono" text-anchor="start">Forecast &rarr;</text>
    `;

    // Horizontal grid
    let grid = '';
    [70, 180].forEach(val => {
      const gy = scaleY(val);
      grid += `
        <line x1="${padding.left}" y1="${gy}" x2="${width - padding.right}" y2="${gy}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,3" />
        <text x="${padding.left - 8}" y="${gy + 4}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="end">${val}</text>
      `;
    });

    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%" preserveAspectRatio="none">
        <!-- Target band (70 - 180) -->
        <rect x="${padding.left}" y="${tirYTop}" width="${plotWidth}" height="${tirYBottom - tirYTop}" 
              fill="rgba(16, 185, 129, 0.08)" stroke="none" />

        ${grid}

        <!-- 95% Confidence Interval Fan -->
        ${ciFanPath ? `<path d="${ciFanPath}" fill="rgba(139, 92, 246, 0.22)" stroke="rgba(139, 92, 246, 0.4)" stroke-width="1" />` : ''}

        <!-- History Line -->
        <path d="${histPath}" fill="none" stroke="#38bdf8" stroke-width="2.5" />

        <!-- Transition boundary -->
        ${bridgeLine}

        <!-- Forecast Line -->
        <path d="${fcPath}" fill="none" stroke="#ec4899" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />

        <!-- Terminal Forecast Marker -->
        <circle cx="${scaleX(totalPoints - 1)}" cy="${scaleY(forecastPoints[forecastPoints.length - 1].predicted_glucose)}" 
                r="5" fill="#ec4899" stroke="#fff" stroke-width="2" />
      </svg>
    `;
  }

  /**
   * Tier 4: Comparative Counterfactual Simulation Chart (Baseline vs Perturbed)
   */
  static renderComparativeSimChart(containerId, trajectoryPoints) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!trajectoryPoints || trajectoryPoints.length === 0) {
      container.innerHTML = `<div class="chart-placeholder">Run simulation scenario to render trajectory comparison.</div>`;
      return;
    }

    const width = 1000;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 50 };

    const n = trajectoryPoints.length;
    const allG = [
      ...trajectoryPoints.map(p => p.baseline_glucose),
      ...trajectoryPoints.map(p => p.simulated_glucose)
    ];

    const yMin = Math.max(40.0, Math.min(...allG) - 15);
    const yMax = Math.max(220.0, Math.max(...allG) + 20);

    const { scaleX, scaleY, plotWidth } = this.getScales(width, height, padding, 0, n - 1, yMin, yMax);

    // Target range band
    const tirYTop = scaleY(180.0);
    const tirYBottom = scaleY(70.0);

    // Baseline Path (dashed grey)
    let basePath = '';
    // Simulated Path (solid cyan)
    let simPath = '';

    trajectoryPoints.forEach((p, i) => {
      const x = scaleX(i);
      const by = scaleY(p.baseline_glucose);
      const sy = scaleY(p.simulated_glucose);

      basePath += `${i === 0 ? 'M' : 'L'} ${x} ${by} `;
      simPath += `${i === 0 ? 'M' : 'L'} ${x} ${sy} `;
    });

    // Delta Shading Polygon
    let deltaPolyTop = `M ${scaleX(0)} ${scaleY(trajectoryPoints[0].simulated_glucose)} `;
    let deltaPolyBottom = '';
    trajectoryPoints.forEach((p, i) => {
      deltaPolyTop += `L ${scaleX(i)} ${scaleY(p.simulated_glucose)} `;
    });
    for (let i = n - 1; i >= 0; i--) {
      deltaPolyBottom += `L ${scaleX(i)} ${scaleY(trajectoryPoints[i].baseline_glucose)} `;
    }
    const deltaPoly = `${deltaPolyTop} ${deltaPolyBottom} Z`;

    // Time ticks
    let timeTicks = '';
    [0, 60, 120, 180, 240].forEach(m => {
      const stepIdx = Math.floor(m / 5);
      if (stepIdx < n) {
        timeTicks += `<text x="${scaleX(stepIdx)}" y="${height - 12}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="middle">+${m}m</text>`;
      }
    });

    // Grid
    let grid = '';
    [70, 120, 180].forEach(val => {
      const gy = scaleY(val);
      grid += `
        <line x1="${padding.left}" y1="${gy}" x2="${width - padding.right}" y2="${gy}" stroke="rgba(255,255,255,0.08)" stroke-dasharray="3,3" />
        <text x="${padding.left - 8}" y="${gy + 4}" fill="#64748b" font-size="10" font-family="JetBrains Mono" text-anchor="end">${val}</text>
      `;
    });

    container.innerHTML = `
      <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%" preserveAspectRatio="none">
        <!-- Target band (70 - 180) -->
        <rect x="${padding.left}" y="${tirYTop}" width="${plotWidth}" height="${tirYBottom - tirYTop}" 
              fill="rgba(16, 185, 129, 0.08)" stroke="none" />

        ${grid}

        <!-- Shaded Delta Area between curves -->
        <path d="${deltaPoly}" fill="rgba(6, 182, 212, 0.15)" stroke="none" />

        <!-- Unperturbed Baseline Line (Dashed) -->
        <path d="${basePath}" fill="none" stroke="#94a3b8" stroke-dasharray="5,5" stroke-width="2" />

        <!-- Counterfactual Simulated Line (Solid Cyan) -->
        <path d="${simPath}" fill="none" stroke="#06b6d4" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />

        ${timeTicks}
      </svg>
    `;
  }
}
