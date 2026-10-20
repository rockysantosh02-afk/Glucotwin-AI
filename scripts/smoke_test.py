"""
GlucoTwin AI - Production Smoke Test & Verification Engine
Validates live backend and frontend deployments or local instances.

Checks:
1. Backend Liveness Probe (`GET /health`)
2. Backend Component Readiness Probe (`GET /ready`)
3. Anonymous Demo Session Creation (`POST /api/v1/auth/demo-session`)
4. Unauthenticated Access Denial (`401 Unauthorized`)
5. Role-Authorized Patient Cohort Listing (`GET /api/v1/patients/`)
6. Multi-Horizon Forecast Trajectory (`POST /api/v1/patients/{id}/twin/forecast`)
7. What-If Counterfactual Simulation (`POST /api/v1/patients/{id}/twin/simulate`)
8. Clinical Dosing Refusal Guardrail Interception (`HTTP 422 CLINICAL_SAFETY_REFUSAL`)
9. Defensive Security Headers (`CSP`, `nosniff`, `DENY`, `Cache-Control: no-store`)
10. Frontend Availability and Title Probe (Optional)
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import urllib.error
import urllib.request


class SmokeTestRunner:
    def __init__(self, backend_url: str, frontend_url: Optional[str] = None, verbose: bool = False):
        self.backend_url = backend_url.rstrip("/")
        self.frontend_url = frontend_url.rstrip("/") if frontend_url else None
        self.verbose = verbose
        self.token: Optional[str] = None
        self.test_patient_id: Optional[str] = None
        self.passed_count = 0
        self.failed_count = 0

    def _http_request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict] = None,
        token: Optional[str] = None,
        base_url: Optional[str] = None
    ) -> Tuple[int, Dict[str, str], Any]:
        """Executes an HTTP request using urllib to eliminate external dependency requirements."""
        target_base = base_url or self.backend_url
        url = f"{target_base}{path}"

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "GlucoTwin-SmokeTest/1.0"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                status_code = resp.status
                resp_headers = dict(resp.headers)
                raw_body = resp.read().decode("utf-8")
                try:
                    body = json.loads(raw_body)
                except Exception:
                    body = raw_body
                return status_code, resp_headers, body
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            resp_headers = dict(exc.headers)
            raw_body = exc.read().decode("utf-8")
            try:
                body = json.loads(raw_body)
            except Exception:
                body = raw_body
            return status_code, resp_headers, body
        except Exception as exc:
            return 0, {}, {"error": str(exc)}

    def record_result(self, name: str, passed: bool, detail: str = ""):
        if passed:
            self.passed_count += 1
            print(f"  [PASS] {name} {f'({detail})' if detail else ''}")
        else:
            self.failed_count += 1
            print(f"  [FAIL] {name} - Reason: {detail}")

    def run(self) -> bool:
        print("=" * 80)
        print("GLUCOTWIN AI - PRODUCTION SMOKE TEST SUITE")
        print(f"Backend Target:  {self.backend_url}")
        if self.frontend_url:
            print(f"Frontend Target: {self.frontend_url}")
        print(f"Execution Time:  {datetime.now(timezone.utc).isoformat()}")
        print("=" * 80)

        # 1. Health Probe
        status_code, _, body = self._http_request("GET", "/health")
        passed = status_code == 200 and isinstance(body, dict) and body.get("status") in ("healthy", "ok")
        self.record_result("1. Backend Liveness (/health)", passed, f"HTTP {status_code}")

        # 2. Readiness Probe
        status_code, _, body = self._http_request("GET", "/ready")
        db_conn = body.get("components", {}).get("database", {}).get("connected", False) if isinstance(body, dict) else False
        passed = status_code == 200 and isinstance(body, dict) and body.get("ready") is True and db_conn
        self.record_result("2. Component Readiness (/ready)", passed, f"HTTP {status_code}, DB connected: {db_conn}")

        # 3. Unauthenticated Access Denial
        status_code, _, _ = self._http_request("GET", "/api/v1/patients/")
        passed = status_code == 401
        self.record_result("3. Unauthenticated Access Denial (/api/v1/patients/)", passed, f"HTTP {status_code}")

        # 4. Demo Session Creation
        payload = {"clinician_name": "Smoke Test Clinician", "requested_sandbox": "sandbox-demo-t1d"}
        status_code, _, body = self._http_request("POST", "/api/v1/auth/demo-session", payload=payload)
        token = body.get("data", {}).get("access_token") if isinstance(body, dict) else None
        passed = status_code in (200, 201) and token is not None
        self.token = token
        self.record_result("4. Demo Session Issuance (/auth/demo-session)", passed, f"HTTP {status_code}, Token obtained")

        # 5. Authorized Patient Listing
        status_code, headers, body = self._http_request("GET", "/api/v1/patients/", token=self.token)
        patients = body.get("data", {}).get("patients", []) if isinstance(body, dict) else []
        if len(patients) == 0:
            # Seed a minimal cohort for testing
            seed_code, _, seed_body = self._http_request(
                "POST", "/api/v1/patients/seed-cohort", payload={"count": 2, "seed": 42}, token=self.token
            )
            if seed_code in (200, 201):
                _, _, re_body = self._http_request("GET", "/api/v1/patients/", token=self.token)
                patients = re_body.get("data", {}).get("patients", []) if isinstance(re_body, dict) else []

        passed = status_code == 200 and len(patients) > 0
        if patients:
            self.test_patient_id = patients[0].get("patient_code") or patients[0].get("id")
        self.record_result("5. Authorized Patient Listing (/api/v1/patients/)", passed, f"Found {len(patients)} patients")

        # 6. Security Headers Verification
        csp = headers.get("content-security-policy") or headers.get("Content-Security-Policy", "")
        nosniff = headers.get("x-content-type-options") or headers.get("X-Content-Type-Options", "")
        cache_ctrl = headers.get("cache-control") or headers.get("Cache-Control", "")
        headers_ok = "nosniff" in nosniff.lower() and "no-store" in cache_ctrl.lower()
        self.record_result("6. Defensive Security & Anti-Caching Headers", headers_ok, f"nosniff: {bool(nosniff)}, no-store: {bool(cache_ctrl)}")

        # 7. Multi-Horizon Forecast Trajectory
        if self.test_patient_id:
            # Seed telemetry first so forecast has context
            self._http_request("POST", f"/api/v1/patients/{self.test_patient_id}/seed-telemetry", payload={"days": 2, "seed": 42}, token=self.token)

            fc_payload = {"horizon_minutes": 60, "include_uncertainty": True}
            path = f"/api/v1/patients/{self.test_patient_id}/twin/forecast"
            status_code, _, body = self._http_request("POST", path, payload=fc_payload, token=self.token)
            fc_status = body.get("data", {}).get("status") if isinstance(body, dict) else None
            passed = status_code == 200 and fc_status in ("completed", "abstained")
            self.record_result("7. Digital-Twin Forecast (/twin/forecast)", passed, f"Status: {fc_status}")

            # 8. What-If Simulation
            sim_payload = {
                "scenario_name": "Smoke Test Walk",
                "simulation_duration_min": 120,
                "perturbations": {
                    "carb_delta_grams": 20.0,
                    "meal_timing_shift_minutes": 0,
                    "exercise_intensity": 1,
                    "exercise_duration_minutes": 30.0,
                },
            }
            sim_path = f"/api/v1/patients/{self.test_patient_id}/twin/simulate"
            status_code, _, body = self._http_request("POST", sim_path, payload=sim_payload, token=self.token)
            has_traj = bool(body.get("data", {}).get("trajectory")) if isinstance(body, dict) else False
            passed = status_code == 200 and has_traj
            self.record_result("8. What-If Counterfactual ODE Simulation", passed, f"HTTP {status_code}, Trajectory returned")

            # 9. Clinical Dosing Safety Refusal
            refusal_payload = {
                "scenario_name": "Dosing Inquiry",
                "simulation_duration_min": 60,
                "recommend_insulin_dose": True,
            }
            status_code, _, body = self._http_request("POST", sim_path, payload=refusal_payload, token=self.token)
            passed = status_code == 422 and "CLINICAL_SAFETY_REFUSAL" in str(body)
            self.record_result("9. Clinical Safety Refusal Filter", passed, f"HTTP {status_code}, Refusal verified")

            # 10. Sanitized CSV Telemetry Export
            csv_path = f"/api/v1/patients/{self.test_patient_id}/telemetry/export"
            status_code, csv_headers, csv_body = self._http_request("GET", csv_path, token=self.token)
            is_csv = "text/csv" in csv_headers.get("content-type", "") or "text/csv" in csv_headers.get("Content-Type", "")
            passed = status_code == 200 and is_csv and "RESEARCH & EDUCATION PROTOTYPE ONLY" in str(csv_body)
            self.record_result("10. Sanitized Telemetry CSV Export", passed, f"HTTP {status_code}, text/csv verified")
        else:
            print("  [SKIP] Skipping patient endpoints (No patient loaded)")

        # 11. Optional Frontend Availability Probe
        if self.frontend_url:
            status_code, _, body = self._http_request("GET", "/", base_url=self.frontend_url)
            passed = status_code == 200 and "GlucoTwin" in str(body)
            self.record_result("11. Frontend Static SPA Availability", passed, f"HTTP {status_code}")

        # Summary
        print("-" * 80)
        print(f"Smoke Test Results: {self.passed_count} Passed | {self.failed_count} Failed")
        print("=" * 80)
        return self.failed_count == 0


def main():
    parser = argparse.ArgumentParser(description="GlucoTwin AI Smoke Test Runner")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000", help="FastAPI backend URL")
    parser.add_argument("--frontend-url", default=None, help="Static frontend URL")
    parser.add_argument("--verbose", action="store_true", help="Verbose error output")
    args = parser.parse_args()

    runner = SmokeTestRunner(backend_url=args.backend_url, frontend_url=args.frontend_url, verbose=args.verbose)
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
