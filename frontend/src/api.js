/**
 * GlucoTwin AI - API Client Module
 * Manages JWT demo session tokens, HTTP Bearer headers, and standardized error handling.
 */

const API_BASE = '/api/v1';

class ApiClient {
  constructor() {
    this.token = localStorage.getItem('glucotwin_token') || null;
    this.userRole = localStorage.getItem('glucotwin_role') || null;
    this.sandboxId = localStorage.getItem('glucotwin_sandbox') || null;
  }

  setSession(token, role, sandbox) {
    this.token = token;
    this.userRole = role;
    this.sandboxId = sandbox;
    localStorage.setItem('glucotwin_token', token);
    localStorage.setItem('glucotwin_role', role);
    if (sandbox) localStorage.setItem('glucotwin_sandbox', sandbox);
  }

  clearSession() {
    this.token = null;
    this.userRole = null;
    this.sandboxId = null;
    localStorage.removeItem('glucotwin_token');
    localStorage.removeItem('glucotwin_role');
    localStorage.removeItem('glucotwin_sandbox');
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle 401 unauthenticated
      if (response.status === 401) {
        this.clearSession();
        // Automatically attempt to acquire a demo session
        await this.createDemoSession();
        // Retry once with new token
        headers['Authorization'] = `Bearer ${this.token}`;
        const retryResp = await fetch(url, { ...options, headers });
        return await retryResp.json();
      }

      const json = await response.json();
      return json;
    } catch (err) {
      console.error(`API Request Failed: ${endpoint}`, err);
      throw err;
    }
  }

  async createDemoSession(clinicianName = 'Research Clinician') {
    const resp = await fetch(`${API_BASE}/auth/demo-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        clinician_name: clinicianName,
        requested_sandbox: 'sandbox-demo-t1d'
      })
    });
    const data = await resp.json();
    if (data.success) {
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

  async seedTelemetry(patientId, days = 7, seed = 42) {
    return this.request(`/patients/${patientId}/seed-telemetry`, {
      method: 'POST',
      body: JSON.stringify({ days, seed })
    });
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
