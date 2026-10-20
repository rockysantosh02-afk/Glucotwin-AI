"""
GlucoTwin AI - Physical Unit Conversion & Validation Standards
Provides mathematically rigorous, bidirectional unit conversion and bounds validation
strictly adhering to the single configuration specification (docs/config_specification.md).

Conversion Standard:
1 mmol/L = 18.0182 mg/dL
"""

import math
from typing import Literal

# Canonical conversion factor according to clinical consensus and config specification
GLUCOSE_MMOL_CONVERSION_FACTOR = 18.0182

# Physiological validity boundaries
GLUCOSE_MIN_MGDL = 40.0
GLUCOSE_MAX_MGDL = 500.0
GLUCOSE_MIN_MMOLL = round(GLUCOSE_MIN_MGDL / GLUCOSE_MMOL_CONVERSION_FACTOR, 2)  # ~2.22 mmol/L
GLUCOSE_MAX_MMOLL = round(GLUCOSE_MAX_MGDL / GLUCOSE_MMOL_CONVERSION_FACTOR, 2)  # ~27.75 mmol/L

CARBS_MIN_GRAMS = 0.0
CARBS_MAX_GRAMS = 300.0

BOLUS_MIN_UNITS = 0.0
BOLUS_MAX_UNITS = 50.0

ACTIVITY_MIN_MINUTES = 0.0
ACTIVITY_MAX_MINUTES = 360.0
ACTIVITY_INTENSITY_MIN = 0
ACTIVITY_INTENSITY_MAX = 3


def mgdl_to_mmoll(mg_dl: float) -> float:
    """
    Converts glucose concentration from mg/dL to mmol/L.
    Rounded to 2 decimal places.
    Formula: mmol/L = mg/dL / 18.0182
    """
    if math.isnan(mg_dl) or math.isinf(mg_dl):
        raise ValueError("Invalid numeric value for glucose conversion")
    return round(mg_dl / GLUCOSE_MMOL_CONVERSION_FACTOR, 2)


def mmoll_to_mgdl(mmol_l: float) -> float:
    """
    Converts glucose concentration from mmol/L to mg/dL.
    Rounded to 1 decimal place.
    Formula: mg/dL = mmol/L * 18.0182
    """
    if math.isnan(mmol_l) or math.isinf(mmol_l):
        raise ValueError("Invalid numeric value for glucose conversion")
    return round(mmol_l * GLUCOSE_MMOL_CONVERSION_FACTOR, 1)


def normalize_glucose_to_mgdl(value: float, unit: str) -> float:
    """
    Validates and normalizes a glucose reading to canonical mg/dL.
    Accepts units: 'mg/dL', 'mg/dl', 'mmol/L', 'mmol/l'.
    Raises ValueError on unknown unit or physiological out-of-bounds.
    """
    cleaned_unit = unit.strip().lower()
    if cleaned_unit in ("mg/dl", "mgdl"):
        val_mgdl = round(value, 1)
    elif cleaned_unit in ("mmol/l", "mmoll"):
        val_mgdl = mmoll_to_mgdl(value)
    else:
        raise ValueError(
            f"Unsupported glucose unit: '{unit}'. Allowed units are 'mg/dL' or 'mmol/L'."
        )

    if val_mgdl < GLUCOSE_MIN_MGDL or val_mgdl > GLUCOSE_MAX_MGDL:
        raise ValueError(
            f"Glucose reading {val_mgdl} mg/dL is outside physiological bounds "
            f"[{GLUCOSE_MIN_MGDL}, {GLUCOSE_MAX_MGDL}] mg/dL."
        )

    return val_mgdl


def normalize_carbs_to_grams(value: float, unit: str = "g") -> float:
    """
    Validates and normalizes carbohydrate intake mass to grams.
    Accepts units: 'g', 'grams', 'gram'.
    """
    cleaned_unit = unit.strip().lower()
    if cleaned_unit not in ("g", "grams", "gram"):
        raise ValueError(
            f"Unsupported carbohydrate unit: '{unit}'. Allowed unit is 'g' or 'grams'."
        )
    val = round(value, 1)
    if val < CARBS_MIN_GRAMS or val > CARBS_MAX_GRAMS:
        raise ValueError(
            f"Carbohydrate mass {val} g is outside bounds [{CARBS_MIN_GRAMS}, {CARBS_MAX_GRAMS}] g."
        )
    return val


def normalize_bolus_to_units(value: float, unit: str = "U") -> float:
    """
    Validates and normalizes synthetic insulin bolus to units.
    Accepts units: 'u', 'units', 'unit'.
    """
    cleaned_unit = unit.strip().lower()
    if cleaned_unit not in ("u", "units", "unit"):
        raise ValueError(
            f"Unsupported insulin unit: '{unit}'. Allowed unit is 'U' or 'units'."
        )
    val = round(value, 2)
    if val < BOLUS_MIN_UNITS or val > BOLUS_MAX_UNITS:
        raise ValueError(
            f"Insulin bolus {val} U is outside bounds [{BOLUS_MIN_UNITS}, {BOLUS_MAX_UNITS}] U."
        )
    return val


def normalize_activity_to_minutes(value: float, unit: str = "min") -> float:
    """
    Validates and normalizes physical activity duration to minutes.
    Accepts units: 'min', 'minutes', 'minute'.
    """
    cleaned_unit = unit.strip().lower()
    if cleaned_unit not in ("min", "minutes", "minute"):
        raise ValueError(
            f"Unsupported activity duration unit: '{unit}'. Allowed unit is 'min' or 'minutes'."
        )
    val = round(value, 1)
    if val < ACTIVITY_MIN_MINUTES or val > ACTIVITY_MAX_MINUTES:
        raise ValueError(
            f"Activity duration {val} min is outside bounds [{ACTIVITY_MIN_MINUTES}, {ACTIVITY_MAX_MINUTES}] min."
        )
    return val
