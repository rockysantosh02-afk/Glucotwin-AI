"""
GlucoTwin AI - Test Suite: Deterministic In-Silico Synthetic Data Generator
Verifies mathematical determinism, physiological constraints, demographic bounds, and CGM trajectory properties.
"""

from datetime import datetime, timezone
import pytest
from app.services.synthetic_data import SyntheticDataGenerator


def test_synthetic_patient_profile_bounds():
    """Verifies that generated synthetic patient profiles strictly adhere to clinical bounds."""
    for idx in range(1, 25):
        profile = SyntheticDataGenerator.generate_patient_profile(patient_index=idx, seed=100 + idx)
        
        # Patient code prefix
        assert profile.patient_code.startswith("SYN-")
        assert profile.diabetes_type == "T1D"
        
        # Age: 18 - 85 years
        assert 18 <= profile.age <= 85
        
        # Body weight: 40.0 - 150.0 kg
        assert 40.0 <= profile.body_weight_kg <= 150.0
        
        # Basal rate: 0.1 - 3.0 U/hr
        assert 0.1 <= profile.basal_rate_synthetic <= 3.0
        
        # Insulin Sensitivity Factor (ISF): 10.0 - 150.0 mg/dL/U
        assert 10.0 <= profile.insulin_sensitivity_factor <= 150.0
        
        # Insulin to Carb Ratio (ICR): 3.0 - 30.0 g/U
        assert 3.0 <= profile.carb_ratio <= 30.0
        
        # Target glycemic bounds
        assert profile.target_glucose_min >= 70.0
        assert profile.target_glucose_max <= 180.0
        assert profile.target_glucose_max > profile.target_glucose_min


def test_generator_determinism():
    """Verifies that the same seed produces 100% identical patient profiles and telemetry streams."""
    cohort_a = SyntheticDataGenerator.generate_cohort(count=5, seed=777)
    cohort_b = SyntheticDataGenerator.generate_cohort(count=5, seed=777)

    assert len(cohort_a) == len(cohort_b) == 5
    for pa, pb in zip(cohort_a, cohort_b):
        assert pa.patient_code == pb.patient_code
        assert pa.age == pb.age
        assert pa.body_weight_kg == pb.body_weight_kg
        assert pa.basal_rate_synthetic == pb.basal_rate_synthetic
        assert pa.insulin_sensitivity_factor == pb.insulin_sensitivity_factor
        assert pa.carb_ratio == pb.carb_ratio

    # Telemetry determinism
    p = cohort_a[0]
    tel_a = SyntheticDataGenerator.generate_telemetry(patient_profile=p, days=2, seed=888)
    tel_b = SyntheticDataGenerator.generate_telemetry(patient_profile=p, days=2, seed=888)

    assert len(tel_a) == len(tel_b) == 2 * 288
    for ra, rb in zip(tel_a, tel_b):
        assert ra.timestamp == rb.timestamp
        assert ra.glucose_mg_dl == rb.glucose_mg_dl
        assert ra.rate_of_change == rb.rate_of_change
        assert ra.meal_carbs_grams == rb.meal_carbs_grams
        assert ra.bolus_synthetic_units == rb.bolus_synthetic_units
        assert ra.activity_minutes == rb.activity_minutes


def test_generator_variation_across_seeds():
    """Verifies that distinct seeds produce diverse metabolic profiles."""
    p1 = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=111)
    p2 = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=222)

    # Different seeds should produce distinct physiological values
    assert (p1.body_weight_kg != p2.body_weight_kg) or (p1.age != p2.age) or (p1.insulin_sensitivity_factor != p2.insulin_sensitivity_factor)


def test_synthetic_telemetry_dynamics_and_bounds():
    """Verifies that multi-day synthetic CGM time-series respects physiological constraints."""
    profile = SyntheticDataGenerator.generate_patient_profile(patient_index=1, seed=42)
    start_time = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    
    # 7 days of telemetry
    readings = SyntheticDataGenerator.generate_telemetry(
        patient_profile=profile,
        days=7,
        seed=42,
        step_minutes=5,
        start_time=start_time
    )

    expected_count = 7 * 288
    assert len(readings) == expected_count

    meal_count = 0
    bolus_count = 0
    activity_count = 0

    for i, r in enumerate(readings):
        # 1. Monotonically increasing time steps at 5-minute intervals
        if i > 0:
            dt_seconds = (r.timestamp - readings[i-1].timestamp).total_seconds()
            assert dt_seconds == 300.0  # 5 minutes

        # 2. Glucose within physiological bounds [40.0, 500.0] mg/dL
        assert 40.0 <= r.glucose_mg_dl <= 500.0

        # 3. Rate of change within realistic bounds [-10.0, +10.0] mg/dL/min
        assert -10.0 <= r.rate_of_change <= 10.0

        # 4. Count events
        if r.meal_carbs_grams > 0.0:
            meal_count += 1
            assert 0.0 <= r.meal_carbs_grams <= 300.0

        if r.bolus_synthetic_units > 0.0:
            bolus_count += 1
            assert 0.0 <= r.bolus_synthetic_units <= 50.0

        if r.activity_minutes > 0.0:
            activity_count += 1
            assert 0.0 <= r.activity_minutes <= 360.0
            assert r.activity_intensity in (1, 2, 3)

    # Over 7 days, there must be realistic numbers of meals (e.g. 21+ meals)
    assert meal_count >= 21
    assert bolus_count >= 20
    assert activity_count >= 3
