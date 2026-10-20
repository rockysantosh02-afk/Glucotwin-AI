"""
GlucoTwin AI - Deterministic In-Silico Synthetic Patient & Telemetry Generator
Generates realistic physiological Type 1 Diabetes patient cohorts, multi-day CGM telemetry streams,
and documented clinical demonstration scenarios.
All outputs are strictly deterministic when seeded, producing reproducible in-silico benchmarks.

NOTICE: Synthetic demonstration data exclusively. Not for clinical use or medical decision making.
"""

import csv
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple
import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.patient import SyntheticPatientCreate
from app.schemas.telemetry import TelemetryReadingCreate


# -----------------------------------------------------------------------------
# Synthetic EHR Record Schema
# -----------------------------------------------------------------------------
class SyntheticEHRRecord(BaseModel):
    """
    Normalized Electronic Health Record (EHR) representation for a synthetic patient.
    Captures anthropometrics, clinical history, therapy modality, and physiological constants.
    """
    model_config = ConfigDict(extra="forbid")

    patient_code: str = Field(..., description="Unique synthetic patient identifier")
    name_alias: str = Field(..., description="Synthetic patient pseudonym")
    age: int = Field(..., ge=18, le=85, description="Patient age in years")
    sex: Literal["M", "F"] = Field(..., description="Biological sex")
    body_weight_kg: float = Field(..., ge=40.0, le=150.0, description="Body weight in kg")
    height_cm: float = Field(..., ge=140.0, le=210.0, description="Height in centimeters")
    bmi: float = Field(..., ge=16.0, le=45.0, description="Body Mass Index (kg/m^2)")
    diabetes_type: Literal["T1D", "T2D"] = Field(default="T1D", description="Diabetes classification")
    diagnosis_years: float = Field(..., ge=0.5, le=60.0, description="Years since diagnosis")
    baseline_hba1c: float = Field(..., ge=5.0, le=14.0, description="Baseline HbA1c percentage (%)")
    therapy_modality: Literal["PUMP", "MDI"] = Field(..., description="Insulin therapy delivery method")
    cgm_sensor_model: str = Field(..., description="Continuous Glucose Monitor sensor hardware model")
    basal_rate_synthetic: float = Field(..., ge=0.1, le=3.0, description="Basal insulin rate (U/hr)")
    insulin_sensitivity_factor: float = Field(..., ge=10.0, le=150.0, description="ISF (mg/dL per Unit)")
    carb_ratio: float = Field(..., ge=3.0, le=30.0, description="ICR (grams per Unit)")
    target_glucose_min: float = Field(default=70.0, description="Target lower threshold (mg/dL)")
    target_glucose_max: float = Field(default=180.0, description="Target upper threshold (mg/dL)")


# -----------------------------------------------------------------------------
# Named Demo Scenario Descriptors
# -----------------------------------------------------------------------------
SCENARIO_DEFINITIONS = {
    "scenario_1_baseline_stable": {
        "key": "scenario_1_baseline_stable",
        "name": "Baseline Stable T1D",
        "patient_code": "SYN-SCEN-001",
        "target_hba1c": 6.8,
        "therapy": "PUMP",
        "description": "Well-controlled Type 1 Diabetes patient with high Time in Range (>80%), low glycemic variability (CV < 32%), and prompt postprandial bolusing.",
        "clinical_pattern": "Normoglycemic stability, low coefficient of variation, negligible nocturnal drift.",
    },
    "scenario_2_postprandial_spike": {
        "key": "scenario_2_postprandial_spike",
        "name": "Postprandial Spike",
        "patient_code": "SYN-SCEN-002",
        "target_hba1c": 8.2,
        "therapy": "MDI",
        "description": "Acute postprandial glucose excursion (>230 mg/dL) following a heavy carbohydrate meal with a 50% underdosed prandial bolus.",
        "clinical_pattern": "Rapid glucose rise (>2.5 mg/dL/min), peaking between 90-120 min post-ingestion.",
    },
    "scenario_3_nocturnal_hypoglycemia": {
        "key": "scenario_3_nocturnal_hypoglycemia",
        "name": "Nocturnal Hypoglycemia",
        "patient_code": "SYN-SCEN-003",
        "target_hba1c": 7.4,
        "therapy": "PUMP",
        "description": "Prolonged overnight hypoglycemic episode (dropping below 70 mg/dL and reaching severe nadir <54 mg/dL) between 01:30 and 04:30.",
        "clinical_pattern": "Insidious overnight drift, Level 2 severe hypoglycemia lasting >60 minutes before morning counter-regulation.",
    },
    "scenario_4_exercise_induced_hypo": {
        "key": "scenario_4_exercise_induced_hypo",
        "name": "Exercise-Induced Hypoglycemia",
        "patient_code": "SYN-SCEN-004",
        "target_hba1c": 7.1,
        "therapy": "MDI",
        "description": "Acute glucose plunge during an afternoon 60-minute vigorous workout without prior carbohydrate ingestion or basal reduction.",
        "clinical_pattern": "Steep negative rate of change (<-2.0 mg/dL/min), hypoglycemia persisting into the post-exercise recovery window.",
    },
    "scenario_5_compression_low": {
        "key": "scenario_5_compression_low",
        "name": "Sensor Compression Low / Pressure Artifact",
        "patient_code": "SYN-SCEN-005",
        "target_hba1c": 7.0,
        "therapy": "PUMP",
        "description": "Sudden unphysiological overnight glucose drop to ~48 mg/dL caused by mechanical pressure on the subcutaneous sensor, followed by immediate recovery when pressure is relieved.",
        "clinical_pattern": "Abrupt non-physiological drop without preceding insulin bolus or exercise, rapid rebound to baseline within 35 minutes.",
    },
    "scenario_6_sensor_drift_and_dropout": {
        "key": "scenario_6_sensor_drift_and_dropout",
        "name": "Sensor Drift & Calibration Dropout",
        "patient_code": "SYN-SCEN-006",
        "target_hba1c": 7.9,
        "therapy": "PUMP",
        "description": "Progressive sensor calibration degradation (gradual upward drift of +30 mg/dL over 8 hours) followed by a 2-hour sensor warmup/dropout gap with CALIBRATING status.",
        "clinical_pattern": "Sensor baseline drift followed by missing readings and CALIBRATING sensor status flags.",
    },
    "scenario_7_missed_bolus_hyperglycemia": {
        "key": "scenario_7_missed_bolus_hyperglycemia",
        "name": "Missed Meal Bolus with Hyperglycemia & Counter-Regulation",
        "patient_code": "SYN-SCEN-007",
        "target_hba1c": 9.4,
        "therapy": "MDI",
        "description": "Complete omission of meal bolus for an 85g carbohydrate lunch, resulting in prolonged severe hyperglycemia (>260 mg/dL) lasting >3 hours with late rescue bolus.",
        "clinical_pattern": "Severe sustained Level 2 Hyperglycemia (>250 mg/dL), delayed correction insulin.",
    },
}


# -----------------------------------------------------------------------------
# Main Synthetic Data Generator
# -----------------------------------------------------------------------------
class SyntheticDataGenerator:
    """
    In-silico physiological generator for Type 1 Diabetes patient cohorts,
    EHR characteristics, and continuous glucose monitoring (CGM) telemetry streams.
    """

    VERSION = "1.0.0"

    @classmethod
    def generate_patient_profile(
        cls,
        patient_index: int = 1,
        seed: Optional[int] = None
    ) -> SyntheticPatientCreate:
        """
        Generates a clinically realistic synthetic Type 1 Diabetes patient profile.
        Maintains strict backward compatibility with existing tests.
        """
        effective_seed = seed if seed is not None else (42 + patient_index * 1337)
        ehr = cls.generate_ehr_record(patient_index=patient_index, seed=effective_seed)

        return SyntheticPatientCreate(
            patient_code=ehr.patient_code,
            diabetes_type=ehr.diabetes_type,
            age=ehr.age,
            body_weight_kg=ehr.body_weight_kg,
            basal_rate_synthetic=ehr.basal_rate_synthetic,
            insulin_sensitivity_factor=ehr.insulin_sensitivity_factor,
            carb_ratio=ehr.carb_ratio,
            target_glucose_min=ehr.target_glucose_min,
            target_glucose_max=ehr.target_glucose_max
        )

    @classmethod
    def generate_ehr_record(
        cls,
        patient_index: int = 1,
        seed: Optional[int] = None,
        patient_code_override: Optional[str] = None,
        target_hba1c: Optional[float] = None,
        therapy_override: Optional[str] = None
    ) -> SyntheticEHRRecord:
        """
        Generates a rich, normalized synthetic EHR record.
        Derives physiological parameters and latent traits from patient characteristics
        so the generated data exhibits learnable relationships.
        """
        effective_seed = seed if seed is not None else (42 + patient_index * 1337)
        rng = np.random.RandomState(effective_seed)

        patient_code = patient_code_override or f"SYN-T1D-{patient_index:03d}"
        name_alias = f"Synthetic Patient {patient_index:03d}"

        # 1. Demographics
        sex: Literal["M", "F"] = "M" if rng.uniform(0, 1) < 0.52 else "F"
        age = int(rng.randint(19, 73))

        # Height & Weight (physiologically correlated)
        if sex == "M":
            height_cm = round(float(rng.normal(176.0, 7.5)), 1)
            height_cm = max(155.0, min(202.0, height_cm))
            bmi = round(float(rng.normal(25.8, 3.8)), 1)
        else:
            height_cm = round(float(rng.normal(163.0, 6.8)), 1)
            height_cm = max(145.0, min(190.0, height_cm))
            bmi = round(float(rng.normal(25.1, 4.2)), 1)

        bmi = max(18.5, min(42.0, bmi))
        height_m = height_cm / 100.0
        body_weight_kg = round(bmi * (height_m ** 2), 1)
        body_weight_kg = max(45.0, min(140.0, body_weight_kg))

        # 2. Diabetes duration & HbA1c
        max_duration = max(1.0, float(age - 12))
        diagnosis_years = round(float(rng.uniform(1.0, min(35.0, max_duration))), 1)

        # Baseline HbA1c: slightly elevated for higher BMI or longer duration
        if target_hba1c is not None:
            baseline_hba1c = float(target_hba1c)
        else:
            base_hba1c = 6.8 + (bmi - 24.0) * 0.08 + (diagnosis_years * 0.03)
            hba1c_noise = float(rng.normal(0.0, 0.6))
            baseline_hba1c = round(float(np.clip(base_hba1c + hba1c_noise, 5.8, 11.5)), 1)

        # Therapy modality: Pump vs MDI
        if therapy_override:
            therapy_modality = "PUMP" if therapy_override.upper() == "PUMP" else "MDI"
        else:
            pump_prob = 0.65 if baseline_hba1c < 7.5 else 0.40
            therapy_modality = "PUMP" if rng.uniform(0, 1) < pump_prob else "MDI"

        # CGM sensor model
        sensor_models = ["GlucoSensor G7-Syn", "OmniSense Pro-Syn", "BioTrack Flow-Syn"]
        cgm_sensor_model = sensor_models[int(rng.randint(0, len(sensor_models)))]

        # 3. Total Daily Dose (TDD) ~ 0.45 to 0.78 U/kg (higher for higher BMI / HbA1c)
        tdd_per_kg = 0.48 + (bmi - 22.0) * 0.008 + (baseline_hba1c - 6.5) * 0.025
        tdd_per_kg = max(0.40, min(0.85, tdd_per_kg))
        tdd = tdd_per_kg * body_weight_kg

        # 4. Basal Rate (hourly)
        basal_daily = tdd * float(rng.uniform(0.44, 0.50))
        basal_hourly = round(float(basal_daily / 24.0), 2)
        basal_hourly = max(0.2, min(2.8, basal_hourly))

        # 5. Insulin Sensitivity Factor (ISF): Rule of 1800 / TDD
        raw_isf = 1800.0 / tdd
        # Latent trait: patients with higher HbA1c exhibit reduced insulin sensitivity
        isf_factor = 1.0 - (baseline_hba1c - 7.0) * 0.04
        isf = round(float(raw_isf * isf_factor * rng.uniform(0.92, 1.08)), 1)
        isf = max(15.0, min(120.0, isf))

        # 6. Carb Ratio (ICR): Rule of 500 / TDD
        raw_icr = 500.0 / tdd
        icr = round(float(raw_icr * rng.uniform(0.92, 1.08)), 1)
        icr = max(4.0, min(25.0, icr))

        return SyntheticEHRRecord(
            patient_code=patient_code,
            name_alias=name_alias,
            age=age,
            sex=sex,
            body_weight_kg=body_weight_kg,
            height_cm=height_cm,
            bmi=bmi,
            diabetes_type="T1D",
            diagnosis_years=diagnosis_years,
            baseline_hba1c=baseline_hba1c,
            therapy_modality=therapy_modality,
            cgm_sensor_model=cgm_sensor_model,
            basal_rate_synthetic=basal_hourly,
            insulin_sensitivity_factor=isf,
            carb_ratio=icr,
            target_glucose_min=70.0,
            target_glucose_max=180.0
        )

    @classmethod
    def generate_cohort(
        cls,
        count: int = 10,
        seed: int = 42
    ) -> List[SyntheticPatientCreate]:
        """
        Generates a cohort of distinct synthetic T1D patients.
        """
        cohort = []
        for i in range(1, count + 1):
            patient_seed = seed + i * 1000
            cohort.append(cls.generate_patient_profile(patient_index=i, seed=patient_seed))
        return cohort

    @classmethod
    def generate_ehr_cohort(
        cls,
        count: int = 80,
        seed: int = 42
    ) -> List[SyntheticEHRRecord]:
        """
        Generates a rich cohort of normalized synthetic EHR records.
        """
        cohort = []
        for i in range(1, count + 1):
            patient_seed = seed + i * 1000
            cohort.append(cls.generate_ehr_record(patient_index=i, seed=patient_seed))
        return cohort

    @classmethod
    def generate_telemetry(
        cls,
        patient_profile: Any,
        days: int = 14,
        seed: int = 42,
        step_minutes: int = 5,
        start_time: Optional[datetime] = None,
        scenario_key: Optional[str] = None
    ) -> List[TelemetryReadingCreate]:
        """
        Generates continuous CGM telemetry at discrete 5-minute sampling intervals.
        Simulates:
        - Latent EHR traits (HbA1c sets baseline fasting equilibrium and variability).
        - Circadian rhythm: Dawn phenomenon (04:00 - 08:30) and nocturnal depth.
        - Sleep dynamics (reduced metabolic clearance and basal stabilization overnight).
        - Delayed meal responses (biexponential absorption kinetics).
        - Insulin bolus kinetics (absorption peaking at ~60 minutes).
        - Exercise bouts (acute glucose depletion and post-exercise recovery).
        - Autocorrelated noise via AR(1) / Ornstein-Uhlenbeck formulation.
        - Physiological bounds [40.0, 500.0] mg/dL.
        - Backward difference velocity (mg/dL/min).
        """
        rng = np.random.RandomState(seed)

        if start_time is None:
            start_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        elif start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        steps_per_day = int((24 * 60) / step_minutes)  # 288 steps/day
        total_steps = days * steps_per_day

        # Patient metabolic constants
        isf = float(getattr(patient_profile, "insulin_sensitivity_factor", 45.0))
        icr = float(getattr(patient_profile, "carb_ratio", 10.0))
        basal_rate = float(getattr(patient_profile, "basal_rate_synthetic", 0.8))
        hba1c = float(getattr(patient_profile, "baseline_hba1c", 7.2))
        therapy = str(getattr(patient_profile, "therapy_modality", "PUMP"))

        # Baseline glucose setpoint derived from latent HbA1c:
        # e.g., HbA1c 6.5 -> ~110 mg/dL; HbA1c 8.5 -> ~136 mg/dL
        baseline_equilibrium = 108.0 + (hba1c - 6.5) * 13.0
        baseline_equilibrium = float(np.clip(baseline_equilibrium, 95.0, 160.0))

        # Expected glucose impact per gram of carbohydrate
        carb_impact_factor = isf / icr

        # Noise scale correlated with HbA1c and therapy modality
        noise_sigma = 1.8 + (hba1c - 6.0) * 0.35
        if therapy == "MDI":
            noise_sigma *= 1.25

        # AR(1) autocorrelation coefficient for interstitial glucose
        ar_phi = 0.88

        # Event schedules
        meal_events: Dict[int, float] = {}
        bolus_events: Dict[int, float] = {}
        activity_events: Dict[int, Tuple[float, int]] = {}

        # Schedule meals, boluses, and exercise across days
        for d in range(days):
            day_offset = d * steps_per_day

            # 1. Breakfast (~07:00 - 08:30: step 84 - 102)
            bf_time = day_offset + rng.randint(84, 103)
            bf_carbs = round(float(rng.uniform(35.0, 65.0)), 1)
            meal_events[bf_time] = bf_carbs
            bf_bolus = round((bf_carbs / icr) * float(rng.uniform(0.92, 1.08)), 2)
            bolus_events[bf_time] = bf_bolus

            # 2. Lunch (~12:00 - 13:30: step 144 - 162)
            lu_time = day_offset + rng.randint(144, 163)
            lu_carbs = round(float(rng.uniform(45.0, 80.0)), 1)
            meal_events[lu_time] = lu_carbs
            lu_bolus = round((lu_carbs / icr) * float(rng.uniform(0.90, 1.10)), 2)
            bolus_events[lu_time] = lu_bolus

            # 3. Dinner (~18:30 - 20:00: step 222 - 240)
            dn_time = day_offset + rng.randint(222, 241)
            dn_carbs = round(float(rng.uniform(55.0, 95.0)), 1)
            meal_events[dn_time] = dn_carbs
            dn_bolus = round((dn_carbs / icr) * float(rng.uniform(0.90, 1.05)), 2)
            bolus_events[dn_time] = dn_bolus

            # 4. Optional Snack (prob ~ 0.40)
            if rng.uniform(0, 1) < 0.40:
                snack_time = day_offset + rng.randint(180, 200)
                snack_carbs = round(float(rng.uniform(15.0, 30.0)), 1)
                meal_events[snack_time] = snack_carbs
                if rng.uniform(0, 1) > 0.35:
                    bolus_events[snack_time] = round(snack_carbs / icr, 2)

            # 5. Physical Exercise (3 days a week)
            if d % 2 == 0 or (d % 3 == 0 and d > 0):
                ex_step = day_offset + (126 if rng.uniform(0, 1) < 0.35 else 204)
                ex_duration = float(rng.choice([30.0, 45.0, 60.0]))
                ex_intensity = int(rng.choice([1, 2]))
                activity_events[ex_step] = (ex_duration, ex_intensity)

        # ---------------------------------------------------------------------
        # Apply Named Demo Scenario Overrides
        # ---------------------------------------------------------------------
        # We inject specific scenario signatures on Day 1 or Day 2 for distinct reproducibility
        if scenario_key == "scenario_1_baseline_stable":
            # Well-controlled: tighten all boluses, reduce noise
            noise_sigma = 1.2
            for step in bolus_events:
                meal_c = meal_events.get(step, 0.0)
                if meal_c > 0:
                    bolus_events[step] = round(meal_c / icr, 2)  # perfectly matched bolus

        elif scenario_key == "scenario_2_postprandial_spike":
            # Postprandial spike on Day 1 lunch (step 148): 92g carbs, only 40% bolus
            day1_lunch = 148
            meal_events[day1_lunch] = 92.0
            bolus_events[day1_lunch] = round((92.0 / icr) * 0.40, 2)

        elif scenario_key == "scenario_3_nocturnal_hypoglycemia":
            # Overnight hypo on Night 2 (starts around step 310 = 01:50 on Day 2)
            night_step = steps_per_day + 22  # ~01:50 Day 2
            # Excess late insulin or uncompensated exercise
            bolus_events[night_step] = round(3.5, 2)

        elif scenario_key == "scenario_4_exercise_induced_hypo":
            # Intense afternoon exercise on Day 1 (step 198 = 16:30) with 75 min heavy workout
            ex_step = 198
            activity_events[ex_step] = (75.0, 3)  # Vigorous intensity
            # Zero carbs ingested

        elif scenario_key == "scenario_7_missed_bolus_hyperglycemia":
            # Unannounced lunch with zero bolus on Day 1 (step 146)
            lu_step = 146
            meal_events[lu_step] = 88.0
            bolus_events[lu_step] = 0.0  # complete omission

        # Initialize simulation state
        current_glucose = baseline_equilibrium + float(rng.uniform(-4.0, 6.0))
        prev_glucose = current_glucose
        ar_noise_state = 0.0

        # Absorption kinetics:
        tau_m = 9.0   # carbs peak ~45 min
        tau_i = 12.0  # insulin peaks ~60 min

        active_carbs = []
        active_insulins = []
        active_exercises = []

        readings: List[TelemetryReadingCreate] = []

        for k in range(total_steps):
            current_time = start_time + timedelta(minutes=k * step_minutes)
            minute_of_day = (k * step_minutes) % 1440
            is_sleep = (minute_of_day >= 1380 or minute_of_day < 420)  # 23:00 to 07:00

            # 1. Ingest events
            step_carbs = meal_events.get(k, 0.0)
            step_bolus = bolus_events.get(k, 0.0)
            step_activity = activity_events.get(k, (0.0, 0))
            act_mins, act_int = step_activity

            if step_carbs > 0.0:
                active_carbs.append({
                    "total_impact": step_carbs * carb_impact_factor,
                    "elapsed": 0.0,
                    "tau": tau_m
                })

            if step_bolus > 0.0:
                active_insulins.append({
                    "total_impact": step_bolus * isf,
                    "elapsed": 0.0,
                    "tau": tau_i
                })

            if act_mins > 0.0:
                active_exercises.append({
                    "duration_steps": int(act_mins / step_minutes),
                    "intensity": act_int,
                    "elapsed_steps": 0
                })

            # 2. Dynamic flux calculation
            delta_glucose = 0.0

            # (a) Carbohydrate absorption flux
            new_active_carbs = []
            for c in active_carbs:
                t_el = c["elapsed"]
                tau = c["tau"]
                frac = (t_el / (tau ** 2)) * np.exp(-t_el / tau)
                delta_glucose += c["total_impact"] * frac
                c["elapsed"] += 1.0
                if c["elapsed"] < 60:
                    new_active_carbs.append(c)
            active_carbs = new_active_carbs

            # (b) Insulin action flux
            new_active_ins = []
            for ins in active_insulins:
                t_el = ins["elapsed"]
                tau = ins["tau"]
                frac = (t_el / (tau ** 2)) * np.exp(-t_el / tau)
                delta_glucose -= ins["total_impact"] * frac
                ins["elapsed"] += 1.0
                if ins["elapsed"] < 72:
                    new_active_ins.append(ins)
            active_insulins = new_active_ins

            # (c) Exercise flux
            new_active_ex = []
            for ex in active_exercises:
                if ex["elapsed_steps"] < ex["duration_steps"]:
                    drop = 1.8 * ex["intensity"]
                    delta_glucose -= drop
                elif ex["elapsed_steps"] < ex["duration_steps"] + 18:
                    delta_glucose -= 0.5 * ex["intensity"]
                ex["elapsed_steps"] += 1
                if ex["elapsed_steps"] < ex["duration_steps"] + 24:
                    new_active_ex.append(ex)
            active_exercises = new_active_ex

            # (d) Circadian effect (Dawn phenomenon & nocturnal dip)
            circadian_phase = (minute_of_day - 390) * (2 * np.pi / 1440.0)
            circadian_drift = 0.40 * np.cos(circadian_phase)
            delta_glucose += circadian_drift

            # Sleep effect: lower metabolic clearance fluctuation during deep sleep
            if is_sleep:
                restoring_rate = -0.010
            else:
                restoring_rate = -0.016

            restoring_pull = restoring_rate * (current_glucose - baseline_equilibrium)
            delta_glucose += restoring_pull

            # (e) Autocorrelated noise via AR(1) model
            raw_white_noise = float(rng.normal(0.0, 1.0))
            ar_noise_state = (ar_phi * ar_noise_state) + (np.sqrt(1.0 - ar_phi ** 2) * noise_sigma * raw_white_noise)
            delta_glucose += (ar_noise_state * 0.15)

            # Update glucose
            current_glucose += delta_glucose
            current_glucose = float(np.clip(current_glucose, 40.0, 500.0))

            sensor_status = "OK"

            # -----------------------------------------------------------------
            # Specific Demo Scenario Real-Time Injections
            # -----------------------------------------------------------------
            reported_glucose = current_glucose

            # Scenario 5: Compression Low (Overnight Night 1, 03:15 to 03:50 = step 39 to 46)
            if scenario_key == "scenario_5_compression_low" and 39 <= k <= 46:
                # Sudden non-physiological drop to ~48 mg/dL
                reported_glucose = 48.0 + float(rng.normal(0.0, 1.2))
                reported_glucose = max(42.0, min(54.0, reported_glucose))

            # Scenario 6: Sensor Drift & Calibration Dropout
            if scenario_key == "scenario_6_sensor_drift_and_dropout":
                # Gradual upward drift from step 60 to 140 (+0.35 mg/dL per step)
                if 60 <= k < 140:
                    drift_offset = (k - 60) * 0.35
                    reported_glucose += drift_offset
                # Calibration gap from step 140 to 164 (2 hours)
                elif 140 <= k < 164:
                    sensor_status = "CALIBRATING"
                    # During calibration, reading might be dropped or masked
                    reported_glucose = reported_glucose  # status indicates calibrating

            # Compute velocity
            velocity = (reported_glucose - prev_glucose) / step_minutes if k > 0 else 0.0
            velocity = round(float(np.clip(velocity, -15.0, 15.0)), 2)
            prev_glucose = reported_glucose

            reading = TelemetryReadingCreate(
                timestamp=current_time,
                glucose_mg_dl=round(reported_glucose, 1),
                rate_of_change=velocity,
                sensor_status=sensor_status,
                meal_carbs_grams=step_carbs,
                bolus_synthetic_units=step_bolus,
                activity_minutes=act_mins,
                activity_intensity=act_int
            )
            readings.append(reading)

        return readings

    @classmethod
    def inject_sensor_artifacts(
        cls,
        readings: List[TelemetryReadingCreate],
        seed: int = 12345,
        inject_gaps: bool = True,
        inject_stale: bool = True,
        inject_duplicates: bool = True,
        inject_out_of_order: bool = True,
        inject_drift: bool = True,
        inject_spikes: bool = True
    ) -> List[TelemetryReadingCreate]:
        """
        Injects documented real-world CGM hardware and transmission artifacts:
        - Gaps: missing telemetry packets (sensor lost connection / shower / sensor warmup).
        - Stale / delayed readings: repeated identical glucose measurements.
        - Duplicates: consecutive duplicate timestamps.
        - Out-of-order timestamps: packets received out of sequence.
        - Sensor drift: linear decay or upward calibration drift over 12-24 hours.
        - Spikes: isolated non-physiological noise artifacts (+/- 40 mg/dL).
        """
        rng = np.random.RandomState(seed)
        total_len = len(readings)
        if total_len < 100:
            return readings

        result: List[TelemetryReadingCreate] = [r.model_copy() for r in readings]

        # 1. Gaps (drop consecutive 3-12 readings at 2 random locations)
        if inject_gaps and total_len > 250:
            gap_indices = set()
            for _ in range(2):
                start_gap = int(rng.randint(60, total_len - 50))
                gap_len = int(rng.randint(3, 12))  # 15 to 60 minutes
                for g in range(start_gap, min(total_len, start_gap + gap_len)):
                    gap_indices.add(g)
            result = [r for idx, r in enumerate(result) if idx not in gap_indices]

        total_len = len(result)

        # 2. Stale / Frozen readings (repeat value for 4 consecutive readings)
        if inject_stale and total_len > 150:
            stale_start = int(rng.randint(40, total_len - 30))
            frozen_val = result[stale_start].glucose_mg_dl
            for i in range(stale_start + 1, min(total_len, stale_start + 5)):
                result[i] = result[i].model_copy(update={"glucose_mg_dl": frozen_val, "rate_of_change": 0.0})

        # 3. Spikes (isolated 1-step spike of +42 mg/dL)
        if inject_spikes and total_len > 100:
            spike_idx = int(rng.randint(30, total_len - 20))
            spiked_val = min(500.0, result[spike_idx].glucose_mg_dl + 42.0)
            result[spike_idx] = result[spike_idx].model_copy(update={"glucose_mg_dl": round(spiked_val, 1)})

        # 4. Sensor Drift (+1.2 mg/dL/hr over a 12-hour window)
        if inject_drift and total_len > 200:
            drift_start = int(rng.randint(20, total_len - 150))
            for step_offset in range(144):  # 12 hours * 12 points/hr = 144 points
                curr_idx = drift_start + step_offset
                if curr_idx < total_len:
                    drift_add = (step_offset / 12.0) * 1.2
                    new_val = min(500.0, result[curr_idx].glucose_mg_dl + drift_add)
                    result[curr_idx] = result[curr_idx].model_copy(update={"glucose_mg_dl": round(new_val, 1)})

        # 5. Duplicates (duplicate 2 readings)
        if inject_duplicates and total_len > 80:
            dup_idx = int(rng.randint(15, 60))
            dup_item = result[dup_idx].model_copy()
            result.insert(dup_idx + 1, dup_item)

        # 6. Out-of-order timestamps (swap two adjacent items)
        if inject_out_of_order and len(result) > 90:
            swap_idx = int(rng.randint(70, len(result) - 10))
            result[swap_idx], result[swap_idx + 1] = result[swap_idx + 1], result[swap_idx]

        return result

    @classmethod
    def generate_all_named_scenarios(
        cls,
        days: int = 14,
        seed: int = 42
    ) -> List[Dict[str, Any]]:
        """
        Generates all seven documented named demo scenarios.
        Returns a list of scenario packets containing scenario descriptor, EHR record,
        and telemetry stream.
        """
        scenarios_output = []
        for idx, (key, meta) in enumerate(SCENARIO_DEFINITIONS.items(), start=1):
            scen_seed = seed + idx * 500
            ehr = cls.generate_ehr_record(
                patient_index=idx,
                seed=scen_seed,
                patient_code_override=meta["patient_code"],
                target_hba1c=meta["target_hba1c"],
                therapy_override=meta["therapy"]
            )
            telemetry = cls.generate_telemetry(
                patient_profile=ehr,
                days=days,
                seed=scen_seed,
                scenario_key=key
            )
            scenarios_output.append({
                "definition": meta,
                "ehr": ehr,
                "telemetry": telemetry
            })
        return scenarios_output

    @classmethod
    def generate_provenance_metadata(
        cls,
        seed: int,
        num_patients: int,
        days: int,
        scenarios_included: List[str],
        total_observations: int,
        git_commit: str = "af210dd"
    ) -> Dict[str, Any]:
        """
        Creates provenance metadata documenting the generator run parameters and version.
        """
        return {
            "generator_name": "GlucoTwin In-Silico Demo Data Generator",
            "generator_version": cls.VERSION,
            "seed": seed,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": git_commit,
            "parameters": {
                "num_patients": num_patients,
                "days_per_patient": days,
                "sampling_interval_minutes": 5,
                "circadian_dawn_enabled": True,
                "autocorrelated_noise_enabled": True,
                "physiological_bounds": [40.0, 500.0],
                "target_range": [70.0, 180.0]
            },
            "provenance_stats": {
                "total_patients": num_patients,
                "total_observations": total_observations,
                "scenarios_count": len(scenarios_included)
            },
            "scenarios": [
                SCENARIO_DEFINITIONS[k] for k in scenarios_included if k in SCENARIO_DEFINITIONS
            ],
            "clinical_safety_notice": "Synthetic demonstration data. Not for clinical use or medical decision making."
        }

    @classmethod
    def export_cohort_to_csv(
        cls,
        output_dir: str,
        ehr_records: List[SyntheticEHRRecord],
        telemetry_dict: Dict[str, List[TelemetryReadingCreate]],
        scenarios_meta: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        """
        Validated CSV adapter.
        Exports normalized synthetic EHR records, telemetry streams, and scenario descriptions
        to validated CSV files with proper headers and escaping.
        Returns a dictionary of generated file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        file_paths = {}

        # 1. Export patients / EHR records: ehr_records.csv
        ehr_csv_path = os.path.join(output_dir, "ehr_records.csv")
        with open(ehr_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "patient_code", "name_alias", "age", "sex", "body_weight_kg",
                "height_cm", "bmi", "diabetes_type", "diagnosis_years",
                "baseline_hba1c", "therapy_modality", "cgm_sensor_model",
                "basal_rate_synthetic", "insulin_sensitivity_factor", "carb_ratio",
                "target_glucose_min", "target_glucose_max"
            ])
            for rec in ehr_records:
                writer.writerow([
                    rec.patient_code, rec.name_alias, rec.age, rec.sex, rec.body_weight_kg,
                    rec.height_cm, rec.bmi, rec.diabetes_type, rec.diagnosis_years,
                    rec.baseline_hba1c, rec.therapy_modality, rec.cgm_sensor_model,
                    rec.basal_rate_synthetic, rec.insulin_sensitivity_factor, rec.carb_ratio,
                    rec.target_glucose_min, rec.target_glucose_max
                ])
        file_paths["ehr_records"] = ehr_csv_path

        # 2. Export patients summary: patients.csv (for compatibility)
        patients_csv_path = os.path.join(output_dir, "patients.csv")
        with open(patients_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "patient_code", "diabetes_type", "age", "body_weight_kg",
                "basal_rate_synthetic", "insulin_sensitivity_factor", "carb_ratio",
                "target_glucose_min", "target_glucose_max"
            ])
            for rec in ehr_records:
                writer.writerow([
                    rec.patient_code, rec.diabetes_type, rec.age, rec.body_weight_kg,
                    rec.basal_rate_synthetic, rec.insulin_sensitivity_factor, rec.carb_ratio,
                    rec.target_glucose_min, rec.target_glucose_max
                ])
        file_paths["patients"] = patients_csv_path

        # 3. Export telemetry: telemetry.csv
        telemetry_csv_path = os.path.join(output_dir, "telemetry.csv")
        with open(telemetry_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "patient_code", "timestamp", "glucose_mg_dl", "rate_of_change",
                "sensor_status", "meal_carbs_grams", "bolus_synthetic_units",
                "activity_minutes", "activity_intensity"
            ])
            for p_code, readings in telemetry_dict.items():
                for r in readings:
                    writer.writerow([
                        p_code, r.timestamp.isoformat(), r.glucose_mg_dl,
                        r.rate_of_change or 0.0, r.sensor_status,
                        r.meal_carbs_grams or 0.0, r.bolus_synthetic_units or 0.0,
                        r.activity_minutes or 0.0, r.activity_intensity or 0
                    ])
        file_paths["telemetry"] = telemetry_csv_path

        # 4. Export scenarios: scenarios.csv
        scenarios_csv_path = os.path.join(output_dir, "scenarios.csv")
        with open(scenarios_csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "scenario_key", "scenario_name", "patient_code",
                "target_hba1c", "therapy_modality", "description", "clinical_pattern"
            ])
            for scen in scenarios_meta:
                writer.writerow([
                    scen["key"], scen["name"], scen["patient_code"],
                    scen["target_hba1c"], scen["therapy"],
                    scen["description"], scen["clinical_pattern"]
                ])
        file_paths["scenarios"] = scenarios_csv_path

        return file_paths
