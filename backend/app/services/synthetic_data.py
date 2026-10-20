"""
GlucoTwin AI - Deterministic In-Silico Synthetic Patient & Telemetry Generator
Generates realistic physiological Type 1 Diabetes patient cohorts and multi-day CGM telemetry streams.
All outputs are strictly deterministic when seeded, producing reproducible in-silico benchmarks.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
import numpy as np

from app.schemas.patient import SyntheticPatientCreate
from app.schemas.telemetry import TelemetryReadingCreate


class SyntheticDataGenerator:
    """
    In-silico physiological generator for Type 1 Diabetes patient cohorts
    and continuous glucose monitoring (CGM) telemetry.
    """

    @classmethod
    def generate_patient_profile(
        cls,
        patient_index: int = 1,
        seed: Optional[int] = None
    ) -> SyntheticPatientCreate:
        """
        Generates a clinically realistic synthetic Type 1 Diabetes patient profile.
        Uses deterministic seeding derived from patient index if seed is not explicitly passed.
        """
        effective_seed = seed if seed is not None else (42 + patient_index * 1337)
        rng = np.random.RandomState(effective_seed)

        patient_code = f"SYN-T1D-{patient_index:03d}"

        # 1. Age: 19 to 72 years
        age = int(rng.randint(19, 73))

        # 2. Body Weight: 52.0 to 105.0 kg (normal to moderately overweight)
        body_weight_kg = round(float(rng.uniform(52.0, 105.0)), 1)

        # 3. Total Daily Dose (TDD) ~ 0.45 to 0.75 U/kg for T1D
        tdd_per_kg = float(rng.uniform(0.45, 0.75))
        tdd = tdd_per_kg * body_weight_kg

        # 4. Basal Rate: ~45-50% of TDD distributed across 24 hours
        basal_daily = tdd * float(rng.uniform(0.44, 0.50))
        basal_hourly = round(float(basal_daily / 24.0), 2)
        basal_hourly = max(0.2, min(2.5, basal_hourly))

        # 5. Insulin Sensitivity Factor (ISF): Rule of 1800 / TDD (mg/dL per unit)
        raw_isf = 1800.0 / tdd
        # Add slight variation (+/- 10%)
        isf = round(float(raw_isf * rng.uniform(0.9, 1.1)), 1)
        isf = max(15.0, min(120.0, isf))

        # 6. Insulin-to-Carb Ratio (ICR): Rule of 500 / TDD (grams per unit)
        raw_icr = 500.0 / tdd
        icr = round(float(raw_icr * rng.uniform(0.9, 1.1)), 1)
        icr = max(5.0, min(25.0, icr))

        return SyntheticPatientCreate(
            patient_code=patient_code,
            diabetes_type="T1D",
            age=age,
            body_weight_kg=body_weight_kg,
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
    def generate_telemetry(
        cls,
        patient_profile: Any,
        days: int = 14,
        seed: int = 42,
        step_minutes: int = 5,
        start_time: Optional[datetime] = None
    ) -> List[TelemetryReadingCreate]:
        """
        Generates continuous CGM telemetry at discrete 5-minute sampling intervals.
        Simulates:
        - Fasting glucose homeostasis around 105-120 mg/dL.
        - Circadian dawn phenomenon (elevated glucose between 04:00 - 08:00).
        - Meal carbohydrate intake events (breakfast, lunch, dinner, occasional snacks).
        - Matched and slightly mismatched synthetic prandial boluses.
        - Physical exercise sessions with acute glucose drops.
        - Subcutaneous gastrointestinal and insulin analog absorption dynamics.
        - Physiological bounds clamping [40.0, 500.0] mg/dL.
        - Backward difference glucose velocity (rate of change in mg/dL/min).
        """
        rng = np.random.RandomState(seed)

        if start_time is None:
            # Default to a standardized reference date (UTC)
            start_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        elif start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        # Total discrete steps
        steps_per_day = int((24 * 60) / step_minutes)  # 288 steps/day
        total_steps = days * steps_per_day

        # Patient metabolic constants
        isf = float(getattr(patient_profile, "insulin_sensitivity_factor", 45.0))
        icr = float(getattr(patient_profile, "carb_ratio", 10.0))
        basal_rate = float(getattr(patient_profile, "basal_rate_synthetic", 0.8))

        # Expected glucose impact per gram of carbohydrate (mg/dL per gram)
        carb_impact_factor = isf / icr

        # Initialize event schedules over the time horizon
        meal_events = {}  # step_idx -> carbs_grams
        bolus_events = {}  # step_idx -> bolus_units
        activity_events = {}  # step_idx -> (duration_min, intensity)

        for d in range(days):
            day_offset = d * steps_per_day

            # 1. Breakfast: ~07:00 - 08:30 (step 84 - 102)
            bf_time = day_offset + rng.randint(84, 103)
            bf_carbs = round(float(rng.uniform(35.0, 65.0)), 1)
            meal_events[bf_time] = bf_carbs
            # Bolus with 90-110% accuracy
            bf_bolus = round((bf_carbs / icr) * float(rng.uniform(0.92, 1.08)), 2)
            bolus_events[bf_time] = bf_bolus

            # 2. Lunch: ~12:00 - 13:30 (step 144 - 162)
            lu_time = day_offset + rng.randint(144, 163)
            lu_carbs = round(float(rng.uniform(45.0, 80.0)), 1)
            meal_events[lu_time] = lu_carbs
            lu_bolus = round((lu_carbs / icr) * float(rng.uniform(0.90, 1.10)), 2)
            bolus_events[lu_time] = lu_bolus

            # 3. Dinner: ~18:30 - 20:00 (step 222 - 240)
            dn_time = day_offset + rng.randint(222, 241)
            dn_carbs = round(float(rng.uniform(55.0, 95.0)), 1)
            meal_events[dn_time] = dn_carbs
            dn_bolus = round((dn_carbs / icr) * float(rng.uniform(0.90, 1.05)), 2)
            bolus_events[dn_time] = dn_bolus

            # 4. Optional Afternoon/Evening Snack (prob ~ 0.45)
            if rng.uniform(0, 1) < 0.45:
                snack_time = day_offset + rng.randint(180, 200)
                snack_carbs = round(float(rng.uniform(15.0, 30.0)), 1)
                meal_events[snack_time] = snack_carbs
                # Sometimes unbolused (prob ~ 0.3) or bolused
                if rng.uniform(0, 1) > 0.3:
                    bolus_events[snack_time] = round(snack_carbs / icr, 2)

            # 5. Exercise schedule (3 to 4 days per week)
            if d % 2 == 0 or (d % 3 == 0 and d > 0):
                # Exercise either at 10:30 AM (step 126) or 17:00 PM (step 204)
                ex_step = day_offset + (126 if rng.uniform(0, 1) < 0.3 else 204)
                ex_duration = float(rng.choice([30.0, 45.0, 60.0]))
                ex_intensity = int(rng.choice([1, 2]))
                activity_events[ex_step] = (ex_duration, ex_intensity)

        # Baseline glucose equilibrium
        current_glucose = 112.0 + float(rng.uniform(-5.0, 8.0))
        readings: List[TelemetryReadingCreate] = []

        # Absorption kinetics:
        # Carbs: gamma/biexponential distribution peaking at ~45 min (tau_m = 9 steps)
        tau_m = 9.0  # 45 minutes / 5
        # Insulin: gamma/biexponential distribution peaking at ~60 min (tau_i = 12 steps)
        tau_i = 12.0  # 60 minutes / 5

        # Active absorption queues: list of dicts { 'remaining_units', 'elapsed_steps', 'total_impact', 'tau' }
        active_carbs = []
        active_insulins = []
        active_exercises = []

        prev_glucose = current_glucose

        for k in range(total_steps):
            current_time = start_time + timedelta(minutes=k * step_minutes)
            minute_of_day = (k * step_minutes) % 1440

            # 1. Ingest new events
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

            # 2. Compute dynamic rate of change from active processes
            delta_glucose = 0.0

            # (a) Carbohydrate absorption flux
            new_active_carbs = []
            for c in active_carbs:
                t_el = c["elapsed"]
                tau = c["tau"]
                # d/dt [ t/tau * exp(-t/tau) ] = (1/tau - t/tau^2) exp(-t/tau)
                # Fraction absorbed in this step:
                frac = (t_el / (tau ** 2)) * np.exp(-t_el / tau)
                delta_glucose += c["total_impact"] * frac
                c["elapsed"] += 1.0
                if c["elapsed"] < 60:  # absorb over ~5 hours
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
                if ins["elapsed"] < 72:  # action over ~6 hours
                    new_active_ins.append(ins)
            active_insulins = new_active_ins

            # (c) Exercise consumption flux
            new_active_ex = []
            for ex in active_exercises:
                if ex["elapsed_steps"] < ex["duration_steps"]:
                    # During exercise: direct glucose drop proportional to intensity
                    drop = 1.6 * ex["intensity"]  # ~1.6 - 3.2 mg/dL per 5 min
                    delta_glucose -= drop
                elif ex["elapsed_steps"] < ex["duration_steps"] + 18:
                    # Post-exercise recovery window: slight persistent reduction
                    delta_glucose -= 0.4 * ex["intensity"]
                ex["elapsed_steps"] += 1
                if ex["elapsed_steps"] < ex["duration_steps"] + 24:
                    new_active_ex.append(ex)
            active_exercises = new_active_ex

            # (d) Circadian baseline / Dawn phenomenon
            # Peak at 06:30 (390 min), trough at 17:00 (1020 min)
            circadian_phase = (minute_of_day - 390) * (2 * np.pi / 1440.0)
            circadian_drift = 0.35 * np.cos(circadian_phase)
            delta_glucose += circadian_drift

            # (e) Homeostatic basal restoring force toward baseline 112 mg/dL
            restoring_pull = -0.015 * (current_glucose - 112.0)
            delta_glucose += restoring_pull

            # (f) Small Gaussian sensor noise
            noise = float(rng.normal(0.0, 0.4))
            delta_glucose += noise

            # Update glucose state
            current_glucose += delta_glucose

            # Clamp strictly to physiological validity bounds [40.0, 500.0]
            current_glucose = float(np.clip(current_glucose, 40.0, 500.0))

            # Backward difference velocity (mg/dL/min)
            velocity = (current_glucose - prev_glucose) / step_minutes if k > 0 else 0.0
            velocity = round(float(velocity), 2)
            prev_glucose = current_glucose

            reading = TelemetryReadingCreate(
                timestamp=current_time,
                glucose_mg_dl=round(current_glucose, 1),
                rate_of_change=velocity,
                sensor_status="OK",
                meal_carbs_grams=step_carbs,
                bolus_synthetic_units=step_bolus,
                activity_minutes=act_mins,
                activity_intensity=act_int
            )
            readings.append(reading)

        return readings
