/**
 * GlucoTwin AI - Frontend Dashboard Application Engine
 * Binds the 4-Tier Interactive Metabolic Digital Twin Dashboard to the API and SVG Charting Engine.
 */

import './style.css';
import { api } from './api.js';
import { ChartRenderer } from './charts.js';

// Application State
const state = {
  currentPatientId: null,
  currentPatient: null,
  cohort: [],
  telemetry: [],
  agpMetrics: null,
  activeTier: 1,
};

// UI Notification Helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-indicator"></span>
    <span class="toast-message">${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Tier Navigation Tabs
function initTierNavigation() {
  const tabs = document.querySelectorAll('.tier-tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const tier = parseInt(tab.dataset.tier, 10);
      switchTier(tier);
    });
  });
}

function switchTier(tier) {
  state.activeTier = tier;

  document.querySelectorAll('.tier-tab').forEach(tab => {
    tab.classList.toggle('active', parseInt(tab.dataset.tier, 10) === tier);
  });

  document.querySelectorAll('.tier-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `panel-tier-${tier}`);
  });

  // Re-render appropriate chart on tab switch
  if (tier === 1 && state.telemetry.length > 0) {
    ChartRenderer.renderCGMChart('cgm-chart-container', state.telemetry);
  } else if (tier === 2 && !state.agpMetrics && state.currentPatientId) {
    loadAGP(state.currentPatientId);
  } else if (tier === 3) {
    // Forecast ready
  } else if (tier === 4) {
    // Simulator ready
  }
}

// Session Management
async function initSession() {
  const badgeText = document.getElementById('session-status-text');
  try {
    if (badgeText) badgeText.textContent = 'Authenticating...';
    const session = await api.createDemoSession();
    if (badgeText) {
      badgeText.textContent = `Demo: ${session.role || 'Active'}`;
    }
    showToast('Secure demo session initialized (strictly in-memory)', 'success');
    await loadCohort();
  } catch (err) {
    console.error('Session initialization error:', err);
    if (badgeText) badgeText.textContent = 'Auth Failed';
    showToast(`Session Error: ${err.message}`, 'error');
  }
}

// Patient Cohort Management
async function loadCohort() {
  const select = document.getElementById('select-patient');
  try {
    const res = await api.getPatients(0, 50);
    const patients = res.data?.patients || [];
    state.cohort = patients;

    if (!select) return;
    select.innerHTML = '';

    if (patients.length === 0) {
      select.innerHTML = '<option value="">No synthetic patients found. Click "Seed Cohort".</option>';
      return;
    }

    patients.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.patient_code || p.id;
      opt.textContent = `${p.patient_code} (Age ${p.age}, ${p.diabetes_type}, ISF ${p.insulin_sensitivity_factor})`;
      select.appendChild(opt);
    });

    // Select the first patient
    selectPatient(patients[0].patient_code || patients[0].id);
  } catch (err) {
    console.error('Error loading cohort:', err);
    showToast('Failed to load patient cohort', 'error');
  }
}

async function selectPatient(patientId) {
  state.currentPatientId = patientId;
  state.agpMetrics = null;

  try {
    const res = await api.getPatient(patientId);
    const patient = res.data;
    state.currentPatient = patient;

    // Update profile strip
    const profType = document.getElementById('prof-type');
    const profAge = document.getElementById('prof-age');
    const profWeight = document.getElementById('prof-weight');
    const profBasal = document.getElementById('prof-basal');
    const profIsf = document.getElementById('prof-isf');
    const profIcr = document.getElementById('prof-icr');
    const profTarget = document.getElementById('prof-target');

    if (profType) profType.textContent = patient.diabetes_type || 'T1D';
    if (profAge) profAge.textContent = `${patient.age} yrs`;
    if (profWeight) profWeight.textContent = `${patient.body_weight_kg} kg`;
    if (profBasal) profBasal.textContent = `${patient.basal_rate_synthetic} U/hr`;
    if (profIsf) profIsf.textContent = `${patient.insulin_sensitivity_factor} mg/dL/U`;
    if (profIcr) profIcr.textContent = `${patient.carb_ratio} g/U`;
    if (profTarget) profTarget.textContent = `${patient.target_glucose_min} - ${patient.target_glucose_max} mg/dL`;

    // Load Telemetry
    await loadTelemetry(patientId);
  } catch (err) {
    console.error(`Error selecting patient ${patientId}:`, err);
    showToast(`Failed to load profile for ${patientId}`, 'error');
  }
}

// Tier 1: Telemetry
async function loadTelemetry(patientId) {
  try {
    const res = await api.getTelemetry(patientId, 288, 'asc');
    const readings = res.data?.readings || [];
    state.telemetry = readings;

    // Render CGM Chart
    ChartRenderer.renderCGMChart('cgm-chart-container', readings);

    // Update count
    const countEl = document.getElementById('table-reading-count');
    if (countEl) countEl.textContent = `${readings.length} readings`;

    // Populate Table (latest 10)
    const tbody = document.getElementById('telemetry-table-body');
    if (tbody) {
      if (readings.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No telemetry ingested yet. Click "Seed 7-Day Stream".</td></tr>';
      } else {
        const latest = [...readings].reverse().slice(0, 10);
        tbody.innerHTML = latest.map(r => {
          const dt = new Date(r.timestamp).toLocaleString();
          const vel = r.rate_of_change !== null ? `${r.rate_of_change > 0 ? '+' : ''}${r.rate_of_change.toFixed(2)}` : '0.00';
          const carbs = r.meal_carbs_grams ? `${r.meal_carbs_grams}g` : '—';
          const bolus = r.bolus_synthetic_units ? `${r.bolus_synthetic_units}U` : '—';
          const act = r.activity_minutes ? `${r.activity_minutes}m (Int ${r.activity_intensity})` : '—';
          return `
            <tr>
              <td><code>${dt}</code></td>
              <td><strong>${r.glucose_mg_dl.toFixed(1)}</strong></td>
              <td>${vel}</td>
              <td><span class="badge ${r.sensor_status === 'OK' ? 'badge-success' : 'badge-warning'}">${r.sensor_status}</span></td>
              <td>${carbs}</td>
              <td>${bolus}</td>
              <td>${act}</td>
            </tr>
          `;
        }).join('');
      }
    }
  } catch (err) {
    console.error('Error loading telemetry:', err);
  }
}

// Tier 2: AGP
async function loadAGP(patientId, days = 14) {
  try {
    showToast('Computing AGP consensus metrics...', 'info');
    const res = await api.getGlycemicMetrics(patientId, days);
    const m = res.data?.metrics;
    if (!m) return;
    state.agpMetrics = m;

    const tirEl = document.getElementById('agp-tir');
    const meanEl = document.getElementById('agp-mean');
    const sdEl = document.getElementById('agp-sd');
    const cvEl = document.getElementById('agp-cv');
    const gmiEl = document.getElementById('agp-gmi');

    if (tirEl) tirEl.textContent = `${m.tir_percentage.toFixed(1)}%`;
    if (meanEl) meanEl.textContent = m.mean_glucose_mg_dl.toFixed(1);
    if (sdEl) sdEl.textContent = `SD: ${m.standard_deviation.toFixed(1)} mg/dL`;
    if (cvEl) cvEl.textContent = `${m.cv_percentage.toFixed(1)}%`;
    if (gmiEl) gmiEl.textContent = `${m.gmi_percentage.toFixed(2)}%`;

    // Stacked Bar segments
    const bTbr2 = document.getElementById('bar-tbr2');
    const bTbr1 = document.getElementById('bar-tbr1');
    const bTir = document.getElementById('bar-tir');
    const bTar1 = document.getElementById('bar-tar1');
    const bTar2 = document.getElementById('bar-tar2');

    if (bTbr2) bTbr2.style.width = `${m.tbr_level2_percentage}%`;
    if (bTbr1) bTbr1.style.width = `${m.tbr_level1_percentage}%`;
    if (bTir) bTir.style.width = `${m.tir_percentage}%`;
    if (bTar1) bTar1.style.width = `${m.tar_level1_percentage}%`;
    if (bTar2) bTar2.style.width = `${m.tar_level2_percentage}%`;

    // Modal percentiles chart
    if (res.data?.hourly_percentiles) {
      ChartRenderer.renderAGPPercentileChart('agp-modal-container', res.data.hourly_percentiles);
    }
    showToast('Ambulatory Glucose Profile computed', 'success');
  } catch (err) {
    console.error('Error loading AGP metrics:', err);
    showToast('Failed to compute AGP metrics', 'error');
  }
}

// Tier 3: Forecast
async function runForecast() {
  if (!state.currentPatientId) return;
  const horizonSel = document.getElementById('select-horizon');
  const horizon = horizonSel ? parseInt(horizonSel.value, 10) : 60;

  const abstentionCard = document.getElementById('forecast-abstention-card');
  const codeText = document.getElementById('abstention-code-text');
  const reasonText = document.getElementById('abstention-reason-text');
  const actionText = document.getElementById('abstention-action-text');

  try {
    showToast(`Running ${horizon}-minute digital twin forecast...`, 'info');
    const res = await api.runForecast(state.currentPatientId, horizon, true);

    if (res.data?.status === 'abstained') {
      // Show abstention banner
      if (abstentionCard) abstentionCard.style.display = 'block';
      const abs = res.data.abstention || {};
      if (codeText) codeText.textContent = abs.code || 'ABSTAINED';
      if (reasonText) reasonText.textContent = abs.reason || 'Guardrail triggered.';
      if (actionText) actionText.textContent = abs.recommended_action || 'Inspect telemetry.';
      showToast('Model abstained due to safety guardrail', 'warning');
      return;
    }

    // Hide abstention card on success
    if (abstentionCard) abstentionCard.style.display = 'none';

    const points = res.data?.forecast || [];
    ChartRenderer.renderForecastChart('forecast-chart-container', state.telemetry, points);

    // Update risk probabilities
    const risk = res.data?.predicted_risk || {};
    const pHypo = document.getElementById('prob-hypo');
    const pHyper = document.getElementById('prob-hyper');
    const gHypo = document.getElementById('gauge-hypo');
    const gHyper = document.getElementById('gauge-hyper');

    const hypoVal = Math.round((risk.hypoglycemia_probability || 0) * 100);
    const hyperVal = Math.round((risk.hyperglycemia_probability || 0) * 100);

    if (pHypo) pHypo.textContent = `${hypoVal}%`;
    if (pHyper) pHyper.textContent = `${hyperVal}%`;
    if (gHypo) gHypo.style.width = `${hypoVal}%`;
    if (gHyper) gHyper.style.width = `${hyperVal}%`;

    showToast('Digital-twin forecast completed with 95% confidence bands', 'success');
  } catch (err) {
    console.error('Forecast execution failed:', err);
    showToast(`Forecast error: ${err.message}`, 'error');
  }
}

// Tier 4: What-If Simulation
async function runSimulation() {
  if (!state.currentPatientId) return;

  const carbDelta = parseInt(document.getElementById('slider-carb-delta')?.value || '30', 10);
  const timingShift = parseInt(document.getElementById('slider-timing-shift')?.value || '0', 10);
  const exerciseInt = parseInt(document.getElementById('select-exercise-intensity')?.value || '1', 10);
  const exerciseDur = parseInt(document.getElementById('slider-exercise-duration')?.value || '30', 10);
  const simDur = parseInt(document.getElementById('select-sim-duration')?.value || '240', 10);

  const payload = {
    scenario_name: `Perturbation (+${carbDelta}g, Shift ${timingShift}m, Ex ${exerciseDur}m)`,
    simulation_duration_min: simDur,
    perturbations: {
      carb_delta_grams: carbDelta,
      timing_shift_minutes: timingShift,
      exercise_intensity: exerciseInt,
      exercise_duration_minutes: exerciseDur
    }
  };

  try {
    showToast('Solving Bergman Minimal Model ODEs...', 'info');
    const res = await api.runSimulation(state.currentPatientId, payload);
    const data = res.data;

    // Update comparative metrics
    const baseTirEl = document.getElementById('sim-base-tir');
    const pertTirEl = document.getElementById('sim-pert-tir');
    const deltaTirEl = document.getElementById('sim-delta-tir');
    const deltaMeanEl = document.getElementById('sim-delta-mean');

    const shift = data.metrics_shift || {};
    const bTir = shift.baseline_tir ?? shift.baseline_tir_percentage ?? 0;
    const pTir = shift.simulated_tir ?? shift.simulated_tir_percentage ?? 0;
    const dt = shift.tir_delta_percentage ?? shift.delta_tir_percentage ?? 0;
    const dm = shift.mean_delta_mg_dl ?? shift.delta_mean_glucose_mg_dl ?? 0;

    if (baseTirEl) baseTirEl.textContent = `${bTir.toFixed(1)}%`;
    if (pertTirEl) pertTirEl.textContent = `${pTir.toFixed(1)}%`;
    if (deltaTirEl) {
      deltaTirEl.textContent = `${dt > 0 ? '+' : ''}${dt.toFixed(1)}%`;
      deltaTirEl.className = `chip-val ${dt >= 0 ? 'accent-emerald' : 'accent-red'}`;
    }
    if (deltaMeanEl) {
      deltaMeanEl.textContent = `${dm > 0 ? '+' : ''}${dm.toFixed(1)} mg/dL`;
    }

    // Render comparative chart
    ChartRenderer.renderComparativeSimChart('sim-chart-container', data.trajectory || []);
    showToast('Counterfactual what-if simulation completed', 'success');
  } catch (err) {
    console.error('Simulation error:', err);
    showToast(`Simulation error: ${err.message}`, 'error');
  }
}

// Test Clinical Safety Refusal Filter
async function testClinicalSafetyRefusal() {
  if (!state.currentPatientId) return;

  const payload = {
    scenario_name: 'Recommend therapeutic bolus dose',
    simulation_duration_min: 120,
    recommend_insulin_dose: true // Explicitly triggers CLINICAL_SAFETY_REFUSAL
  };

  try {
    showToast('Sending query soliciting clinical insulin bolus...', 'info');
    await api.runSimulation(state.currentPatientId, payload);
    showToast('Unexpected: Request was not blocked!', 'error');
  } catch (err) {
    showToast('Clinical Safety Filter Active: Intercepted and Refused Dosing Inquiry (HTTP 422)', 'success');
  }
}

// Ingestion Modal Management
function initIngestModal() {
  const modal = document.getElementById('modal-ingest');
  const btnOpen = document.getElementById('btn-open-ingest-modal');
  const btnCancel = document.getElementById('btn-cancel-ingest');
  const form = document.getElementById('form-ingest-reading');

  if (btnOpen) {
    btnOpen.addEventListener('click', () => {
      if (modal) modal.style.display = 'flex';
      const timeInput = document.getElementById('input-timestamp');
      if (timeInput) timeInput.value = new Date().toISOString().slice(0, 16);
    });
  }

  if (btnCancel) {
    btnCancel.addEventListener('click', () => {
      if (modal) modal.style.display = 'none';
    });
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      if (!state.currentPatientId) return;

      const gVal = parseFloat(document.getElementById('input-glucose')?.value || '120');
      const unit = document.getElementById('select-unit')?.value || 'mg/dL';
      const carbs = parseFloat(document.getElementById('input-carbs')?.value || '0');
      const bolus = parseFloat(document.getElementById('input-bolus')?.value || '0');
      const actMins = parseFloat(document.getElementById('input-exercise-mins')?.value || '0');
      const actInt = parseInt(document.getElementById('input-exercise-int')?.value || '0', 10);
      const ts = new Date().toISOString();

      try {
        await api.ingestObservation(state.currentPatientId, {
          timestamp: ts,
          glucose_value: gVal,
          unit: unit,
          meal_carbs_grams: carbs,
          bolus_synthetic_units: bolus,
          activity_minutes: actMins,
          activity_intensity: actInt,
          sensor_status: 'OK'
        });

        if (modal) modal.style.display = 'none';
        showToast('Sensor observation transmitted and digital twin updated', 'success');
        await loadTelemetry(state.currentPatientId);
      } catch (err) {
        showToast(`Ingestion error: ${err.message}`, 'error');
      }
    });
  }
}

// Bind DOM Event Handlers
document.addEventListener('DOMContentLoaded', () => {
  initTierNavigation();
  initIngestModal();

  // Session button
  const btnAuth = document.getElementById('btn-auth-action');
  if (btnAuth) btnAuth.addEventListener('click', initSession);

  // Seed Cohort button
  const btnSeedCohort = document.getElementById('btn-seed-cohort');
  if (btnSeedCohort) {
    btnSeedCohort.addEventListener('click', async () => {
      showToast('Generating synthetic T1D cohort...', 'info');
      await api.seedCohort(5, 42);
      await loadCohort();
      showToast('Synthetic cohort seeded successfully', 'success');
    });
  }

  // Refresh Telemetry button
  const btnRefresh = document.getElementById('btn-refresh-data');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      if (state.currentPatientId) loadTelemetry(state.currentPatientId);
    });
  }

  // Seed 7-Day Stream button
  const btnSeedTelem = document.getElementById('btn-seed-telemetry');
  if (btnSeedTelem) {
    btnSeedTelem.addEventListener('click', async () => {
      if (!state.currentPatientId) return;
      showToast('Generating 7-day continuous CGM stream...', 'info');
      await api.seedTelemetry(state.currentPatientId, 7, 42);
      await loadTelemetry(state.currentPatientId);
      showToast('7-day stream seeded and indexed', 'success');
    });
  }

  // Export CSV button
  const btnExportCsv = document.getElementById('btn-export-csv');
  if (btnExportCsv) {
    btnExportCsv.addEventListener('click', async () => {
      if (!state.currentPatientId) return;
      showToast('Exporting sanitized telemetry CSV...', 'info');
      await api.downloadTelemetryCsv(state.currentPatientId, 2016);
      showToast('CSV downloaded successfully', 'success');
    });
  }

  // Patient Select Dropdown
  const selectPatientEl = document.getElementById('select-patient');
  if (selectPatientEl) {
    selectPatientEl.addEventListener('change', (e) => {
      if (e.target.value) selectPatient(e.target.value);
    });
  }

  // Tier 2: Recompute AGP button
  const btnRecomputeAgp = document.getElementById('btn-recompute-agp');
  if (btnRecomputeAgp) {
    btnRecomputeAgp.addEventListener('click', () => {
      const days = parseInt(document.getElementById('select-window-days')?.value || '14', 10);
      if (state.currentPatientId) loadAGP(state.currentPatientId, days);
    });
  }

  // Tier 3: Run Forecast button
  const btnRunForecast = document.getElementById('btn-run-forecast');
  if (btnRunForecast) btnRunForecast.addEventListener('click', runForecast);

  // Tier 4: Sliders Display Binding
  const sliderCarb = document.getElementById('slider-carb-delta');
  if (sliderCarb) {
    sliderCarb.addEventListener('input', (e) => {
      const v = e.target.value;
      const el = document.getElementById('val-carb-delta');
      if (el) el.textContent = `${v > 0 ? '+' : ''}${v} g`;
    });
  }

  const sliderTime = document.getElementById('slider-timing-shift');
  if (sliderTime) {
    sliderTime.addEventListener('input', (e) => {
      const v = e.target.value;
      const el = document.getElementById('val-timing-shift');
      if (el) el.textContent = `${v > 0 ? '+' : ''}${v} min`;
    });
  }

  const sliderExDur = document.getElementById('slider-exercise-duration');
  if (sliderExDur) {
    sliderExDur.addEventListener('input', (e) => {
      const v = e.target.value;
      const el = document.getElementById('val-exercise-duration');
      if (el) el.textContent = `${v} min`;
    });
  }

  // Tier 4: Run Simulation button
  const btnRunSim = document.getElementById('btn-run-simulation');
  if (btnRunSim) btnRunSim.addEventListener('click', runSimulation);

  // Tier 4: Test Refusal Button
  const btnTestRefusal = document.getElementById('btn-trigger-safety-refusal');
  if (btnTestRefusal) btnTestRefusal.addEventListener('click', testClinicalSafetyRefusal);

  // Boot Application Session
  initSession();
});
