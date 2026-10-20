/**
 * GlucoTwin AI - API Client Module
 * Manages in-memory JWT demo session tokens, HTTP Bearer headers, and standardized error handling.
 * SECURITY NOTICE: Tokens are held strictly in-memory (never in localStorage or sessionStorage)
 * to comply with Phase 5 Security and Privacy standards against XSS exfiltration.
 */

const getApiBase = () => {
  const envUrl = typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL;
  if (envUrl) {
    return `${envUrl.replace(/\/$/, '')}/api/v1`;
  }
  return '/api/v1';
};

class ApiClient {
  constructor() {
    // Strictly in-memory session variables (zero browser persistent storage)
    this.token = null;
    this.userRole = null;
    this.sandboxId = null;
    this.apiBase = getApiBase();
  }

  setSession(token, role, sandbox) {
    this.token = token;
    this.userRole = role;
    this.sandboxId = sandbox;
  }

  clearSession() {
    this.token = null;
    this.userRole = null;
    this.sandboxId = null;
  }

  async request(endpoint, options = {}) {
    const url = `${this.apiBase}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      let response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle 401 unauthenticated by automatically acquiring a new in-memory demo session
      if (response.status === 401 && !endpoint.includes('/auth/')) {
        this.clearSession();
        await this.createDemoSession();
        headers['Authorization'] = `Bearer ${this.token}`;
        response = await fetch(url, { ...options, headers });
      }

      const json = await response.json();
      return json;
    } catch (err) {
      console.error(`API Request Failed: ${endpoint}`, err);
      throw err;
    }
  }

  async createDemoSession(clinicianName = 'Research Clinician') {
    const resp = await fetch(`${this.apiBase}/auth/demo-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clinician_name: clinicianName,
        requested_sandbox: 'sandbox-demo-t1d'
      })
    });
    const data = await resp.json();
    if (data.success && data.data) {
      this.setSession(
        data.data.access_token,
        data.data.role,
        data.data.sandbox_id
      );
      return data.data;
    }
    throw new Error(data.error?.message || 'Failed to initialize demo session');
  }

  async logout() {
    if (this.token) {
      try {
        await this.request('/auth/logout', { method: 'POST' });
      } catch (e) {
        // ignore logout errors
      }
    }
    this.clearSession();
  }

  // Patient Cohort Endpoints
  async getPatients(skip = 0, limit = 50) {
    return this.request(`/patients/?skip=${skip}&limit=${limit}`);
  }

  async getPatient(identifier) {
    return this.request(`/patients/${identifier}`);
  }

  async seedCohort(count = 5, seed = 42) {
    return this.request('/patients/seed-cohort', {
      method: 'POST',
      body: JSON.stringify({ count, seed })
    });
  }

  // Tier 1: Observed Telemetry Endpoints
  async getTelemetry(patientId, limit = 288, order = 'asc') {
    return this.request(`/patients/${patientId}/telemetry?limit=${limit}&order=${order}`);
  }

  async ingestTelemetry(patientId, readings) {
    return this.request(`/patients/${patientId}/telemetry`, {
      method: 'POST',
      body: JSON.stringify({ readings })
    });
  }

  async ingestObservation(patientId, observation) {
    return this.request('/observations/ingest', {
      method: 'POST',
      body: JSON.stringify({
        patient_id: patientId,
        observations: [observation]
      })
    });
  }

  async seedTelemetry(patientId, days = 7, seed = 42) {
    return this.request(`/patients/${patientId}/seed-telemetry`, {
      method: 'POST',
      body: JSON.stringify({ days, seed })
    });
  }

  async downloadTelemetryCsv(patientId, limit = 2016) {
    const url = `${this.apiBase}/patients/${patientId}/telemetry/export?limit=${limit}`;
    const headers = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const resp = await fetch(url, { headers });
    if (!resp.ok) {
      throw new Error(`Failed to export CSV: HTTP ${resp.status}`);
    }
    const blob = await resp.blob();
    const downloadUrl = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.download = `glucotwin_${patientId}_telemetry.csv`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(downloadUrl);
    a.remove();
  }

  // Tier 2: Derived AGP Metrics Endpoints
  async getGlycemicMetrics(patientId, windowDays = 14) {
    return this.request(`/patients/${patientId}/metrics?window_days=${windowDays}&persist=true`);
  }

  // Tier 3: Predicted Digital Twin Forecast Endpoints
  async runForecast(patientId, horizonMinutes = 60, includeUncertainty = true) {
    return this.request(`/patients/${patientId}/twin/forecast`, {
      method: 'POST',
      body: JSON.stringify({
        horizon_minutes: horizonMinutes,
        include_uncertainty: includeUncertainty
      })
    });
  }

  // Tier 4: Hypothetical What-If Simulation Endpoints
  async runSimulation(patientId, scenarioPayload) {
    return this.request(`/patients/${patientId}/twin/simulate`, {
      method: 'POST',
      body: JSON.stringify(scenarioPayload)
    });
  }
}

export const api = new ApiClient();
