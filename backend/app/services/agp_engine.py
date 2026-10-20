"""
GlucoTwin AI - Ambulatory Glucose Profile (AGP) & Glycemic Metrics Engine (Tier 2: Derived)
Implements International Consensus on Time in Range (ATTD / ADA 2019) standards.
Calculates mean glucose, standard deviation, %CV, GMI, glycemic range distributions, and modal percentiles.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.schemas.metrics import (
    ClinicalTargetsMet,
    GlycemicMetricsResponse,
    GlycemicRanges,
    HourlyPercentile,
)


class AGPEngine:
    """
    Consensus Ambulatory Glucose Profile calculation engine.
    """

    @classmethod
    def calculate_metrics(
        cls,
        patient_id: str,
        patient_code: Optional[str],
        readings: List[Any],
        window_start: datetime,
        window_end: datetime
    ) -> GlycemicMetricsResponse:
        """
        Calculates consensus AGP metrics from a list of telemetry records.
        """
        if not readings:
            # Return zeroed response if no readings available
            ranges = GlycemicRanges(
                tir_percentage=0.0,
                tar_level1_percentage=0.0,
                tar_level2_percentage=0.0,
                tbr_level1_percentage=0.0,
                tbr_level2_percentage=0.0
            )
            targets = ClinicalTargetsMet(
                tir_above_70=False,
                tbr_below_4=True,
                cv_below_36=False
            )
            return GlycemicMetricsResponse(
                patient_id=patient_id,
                patient_code=patient_code,
                window_start=window_start,
                window_end=window_end,
                total_readings=0,
                cgm_active_percentage=0.0,
                mean_glucose_mg_dl=0.0,
                standard_deviation=0.0,
                cv_percentage=0.0,
                gmi_percentage=0.0,
                ranges=ranges,
                clinical_targets_met=targets,
                hourly_percentiles=[]
            )

        # Extract glucose values and timestamps
        glucose_values = np.array([float(r.glucose_mg_dl) for r in readings], dtype=np.float64)
        n = len(glucose_values)

        # Calculate active percentage
        # Expected readings based on 5-minute intervals
        duration_minutes = max(5.0, (window_end - window_start).total_seconds() / 60.0)
        expected_readings = max(1, int(duration_minutes / 5.0))
        cgm_active = round(min(100.0, (n / expected_readings) * 100.0), 1)

        # 1. Mean Glucose
        mean_g = float(np.mean(glucose_values))

        # 2. Standard Deviation
        sd_g = float(np.std(glucose_values, ddof=1)) if n > 1 else 0.0

        # 3. Coefficient of Variation (%CV = SD / Mean * 100)
        cv = (sd_g / mean_g * 100.0) if mean_g > 0.0 else 0.0

        # 4. Glucose Management Indicator (GMI = 3.31 + 0.02392 * Mean)
        # Bergenstal et al. Diabetes Care 2018
        gmi = 3.31 + 0.02392 * mean_g

        # 5. Glycemic Range Percentages
        # Levels according to International Consensus:
        # Severe Hypoglycemia (Level 2): < 54.0 mg/dL
        # Hypoglycemia (Level 1): 54.0 <= g < 70.0 mg/dL
        # In Range (TIR): 70.0 <= g <= 180.0 mg/dL
        # Hyperglycemia (Level 1): 180.0 < g <= 250.0 mg/dL
        # Severe Hyperglycemia (Level 2): > 250.0 mg/dL
        count_tbr2 = np.sum(glucose_values < 54.0)
        count_tbr1 = np.sum((glucose_values >= 54.0) & (glucose_values < 70.0))
        count_tir = np.sum((glucose_values >= 70.0) & (glucose_values <= 180.0))
        count_tar1 = np.sum((glucose_values > 180.0) & (glucose_values <= 250.0))
        count_tar2 = np.sum(glucose_values > 250.0)

        tbr2_pct = round(float(count_tbr2 / n * 100.0), 1)
        tbr1_pct = round(float(count_tbr1 / n * 100.0), 1)
        tir_pct = round(float(count_tir / n * 100.0), 1)
        tar1_pct = round(float(count_tar1 / n * 100.0), 1)
        tar2_pct = round(float(count_tar2 / n * 100.0), 1)

        ranges = GlycemicRanges(
            tir_percentage=tir_pct,
            tar_level1_percentage=tar1_pct,
            tar_level2_percentage=tar2_pct,
            tbr_level1_percentage=tbr1_pct,
            tbr_level2_percentage=tbr2_pct
        )

        # 6. Clinical Targets Evaluation
        targets = ClinicalTargetsMet(
            tir_above_70=(tir_pct >= 70.0),
            tbr_below_4=((tbr1_pct + tbr2_pct) <= 4.0),
            cv_below_36=(cv <= 36.0)
        )

        # 7. Hourly / Modal Day Percentiles (0 to 23 hours)
        hourly_buckets: Dict[int, List[float]] = {h: [] for h in range(24)}
        for r in readings:
            ts = r.timestamp
            h = ts.hour if hasattr(ts, "hour") else 0
            hourly_buckets[h].append(float(r.glucose_mg_dl))

        hourly_percentiles: List[HourlyPercentile] = []
        global_p = np.percentile(glucose_values, [10, 25, 50, 75, 90])

        for h in range(24):
            vals = hourly_buckets[h]
            if len(vals) >= 3:
                p10, p25, p50, p75, p90 = np.percentile(vals, [10, 25, 50, 75, 90])
            else:
                p10, p25, p50, p75, p90 = global_p

            hourly_percentiles.append(
                HourlyPercentile(
                    hour=h,
                    p10=round(float(p10), 1),
                    p25=round(float(p25), 1),
                    p50=round(float(p50), 1),
                    p75=round(float(p75), 1),
                    p90=round(float(p90), 1)
                )
            )

        return GlycemicMetricsResponse(
            patient_id=patient_id,
            patient_code=patient_code,
            window_start=window_start,
            window_end=window_end,
            total_readings=n,
            cgm_active_percentage=cgm_active,
            mean_glucose_mg_dl=round(mean_g, 1),
            standard_deviation=round(sd_g, 1),
            cv_percentage=round(cv, 1),
            gmi_percentage=round(gmi, 1),
            ranges=ranges,
            clinical_targets_met=targets,
            hourly_percentiles=hourly_percentiles
        )
