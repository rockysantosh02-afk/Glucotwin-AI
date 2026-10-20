"""
GlucoTwin AI - In-Silico Synthetic Patient & Telemetry Data Generator
Generates realistic physiological Type 1 Diabetes patient cohorts, normalized EHR records,
continuous 5-minute CGM telemetry streams, documented sensor artifacts, and the seven
canonical demo scenarios.

All outputs are strictly deterministic under fixed seeding, saving full provenance metadata.
Data is output to local directories kept out of Git.

Usage:
    python scripts/generate_demo_data.py --num-patients 80 --days 14 --seed 42
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# Add backend directory to sys.path so app modules can be loaded
current_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(current_dir)
backend_dir = os.path.join(repo_root, "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.services.synthetic_data import (
    SCENARIO_DEFINITIONS,
    SyntheticDataGenerator,
    SyntheticEHRRecord,
)


def run_generator(
    num_patients: int = 80,
    days: int = 14,
    seed: int = 42,
    output_dir: str = "data/demo_dataset",
    inject_artifacts: bool = True,
    export_csv: bool = True,
    export_json: bool = True
) -> dict:
    """
    Executes the full deterministic synthetic data generation pipeline.
    """
    if num_patients < 1:
        raise ValueError("num_patients must be at least 1")
    if days < 1 or days > 60:
        raise ValueError("days must be between 1 and 60")

    os.makedirs(output_dir, exist_ok=True)
    print(f"================================================================================")
    print(f"GlucoTwin AI - Synthetic Data Generation Pipeline (v{SyntheticDataGenerator.VERSION})")
    print(f"Seed: {seed} | Cohort Size: {num_patients} | Days: {days} | Interval: 5 min")
    print(f"Destination: {os.path.abspath(output_dir)}")
    print(f"Notice: Synthetic demonstration data exclusively. Not for clinical use.")
    print(f"================================================================================")

    # 1. Generate the 7 canonical demo scenarios first
    print("\n[1/4] Generating the 7 canonical clinical demonstration scenarios...")
    scenarios_data = SyntheticDataGenerator.generate_all_named_scenarios(days=days, seed=seed)
    scenario_keys = list(SCENARIO_DEFINITIONS.keys())

    all_ehr_records = []
    all_telemetry_dict = {}
    scenarios_meta = []

    for scen in scenarios_data:
        meta = scen["definition"]
        ehr = scen["ehr"]
        telemetry = scen["telemetry"]
        all_ehr_records.append(ehr)
        all_telemetry_dict[ehr.patient_code] = telemetry
        scenarios_meta.append(meta)
        print(f"  - [{meta['key']}] Patient {meta['patient_code']}: {meta['name']} (HbA1c={ehr.baseline_hba1c}%, {ehr.therapy_modality})")

    # 2. Generate remaining cohort members
    remaining_count = max(0, num_patients - len(scenarios_data))
    print(f"\n[2/4] Generating remaining cohort members ({remaining_count} synthetic patients)...")

    for i in range(1, remaining_count + 1):
        patient_idx = len(scenarios_data) + i
        patient_seed = seed + patient_idx * 1337
        ehr = SyntheticDataGenerator.generate_ehr_record(
            patient_index=patient_idx,
            seed=patient_seed
        )
        telemetry = SyntheticDataGenerator.generate_telemetry(
            patient_profile=ehr,
            days=days,
            seed=patient_seed
        )

        # Inject realistic sensor artifacts into non-scenario patients (e.g. 35% of patients)
        if inject_artifacts and (i % 3 == 0 or i % 5 == 0):
            artifact_seed = patient_seed + 999
            telemetry = SyntheticDataGenerator.inject_sensor_artifacts(
                readings=telemetry,
                seed=artifact_seed
            )

        all_ehr_records.append(ehr)
        all_telemetry_dict[ehr.patient_code] = telemetry

    total_observations = sum(len(readings) for readings in all_telemetry_dict.values())
    print(f"  Generated {len(all_ehr_records)} synthetic patients with {total_observations:,} total CGM observations.")

    # 3. Export datasets
    exported_files = {}
    if export_csv:
        print("\n[3/4] Exporting normalized CSV datasets...")
        exported_files = SyntheticDataGenerator.export_cohort_to_csv(
            output_dir=output_dir,
            ehr_records=all_ehr_records,
            telemetry_dict=all_telemetry_dict,
            scenarios_meta=scenarios_meta
        )
        for label, path in exported_files.items():
            file_size_kb = os.path.getsize(path) / 1024.0
            print(f"  - {label}: {os.path.basename(path)} ({file_size_kb:.1f} KB)")

    # 4. Save Provenance Metadata
    print("\n[4/4] Writing provenance metadata (provenance.json)...")
    provenance = SyntheticDataGenerator.generate_provenance_metadata(
        seed=seed,
        num_patients=len(all_ehr_records),
        days=days,
        scenarios_included=scenario_keys,
        total_observations=total_observations
    )

    provenance_path = os.path.join(output_dir, "provenance.json")
    with open(provenance_path, mode="w", encoding="utf-8") as f:
        json.dump(provenance, f, indent=2)
    exported_files["provenance"] = provenance_path
    print(f"  - provenance.json saved ({os.path.getsize(provenance_path)} bytes)")

    print(f"\nSynthetic data generation completed successfully.")
    print(f"All outputs strictly kept in {output_dir} (ignored by Git).")
    print(f"================================================================================\n")

    return {
        "num_patients": len(all_ehr_records),
        "total_observations": total_observations,
        "scenarios_count": len(scenarios_meta),
        "exported_files": exported_files,
        "provenance": provenance
    }


def main():
    parser = argparse.ArgumentParser(
        description="GlucoTwin AI - Deterministic In-Silico Synthetic Data Generator"
    )
    parser.add_argument(
        "--num-patients",
        type=int,
        default=80,
        help="Number of synthetic patients to generate (recommended: 60 to 120, default: 80)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Days of continuous 5-minute CGM telemetry (recommended: 14 to 28, default: 14)"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Deterministic random seed (default: 42)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/demo_dataset",
        help="Output directory path for generated datasets (default: data/demo_dataset)"
    )
    parser.add_argument(
        "--no-artifacts",
        action="store_true",
        help="Disable injection of sensor artifacts in non-scenario patients"
    )

    args = parser.parse_args()

    run_generator(
        num_patients=args.num_patients,
        days=args.days,
        seed=args.seed,
        output_dir=args.output_dir,
        inject_artifacts=not args.no_artifacts
    )


if __name__ == "__main__":
    main()
