"""initial schema for glucotwin ai

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=30), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('demo_clinician', 'clinician', 'admin', 'researcher', 'clinician_observer', 'auditor')",
            name='ck_users_valid_role'
        ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. synthetic_patients
    op.create_table(
        'synthetic_patients',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('patient_code', sa.String(length=30), nullable=False),
        sa.Column('diabetes_type', sa.String(length=10), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('body_weight_kg', sa.Float(), nullable=False),
        sa.Column('basal_rate_synthetic', sa.Float(), nullable=False),
        sa.Column('insulin_sensitivity_factor', sa.Float(), nullable=False),
        sa.Column('carb_ratio', sa.Float(), nullable=False),
        sa.Column('target_glucose_min', sa.Float(), nullable=False),
        sa.Column('target_glucose_max', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("diabetes_type IN ('T1D', 'T2D')", name='ck_patients_diabetes_type'),
        sa.CheckConstraint('age >= 18 AND age <= 85', name='ck_patients_age_range'),
        sa.CheckConstraint('body_weight_kg >= 40.0 AND body_weight_kg <= 150.0', name='ck_patients_weight_range'),
        sa.CheckConstraint('basal_rate_synthetic >= 0.1 AND basal_rate_synthetic <= 3.0', name='ck_patients_basal_range'),
        sa.CheckConstraint('insulin_sensitivity_factor >= 10.0 AND insulin_sensitivity_factor <= 150.0', name='ck_patients_isf_range'),
        sa.CheckConstraint('carb_ratio >= 3.0 AND carb_ratio <= 30.0', name='ck_patients_icr_range'),
        sa.CheckConstraint('target_glucose_min >= 70.0', name='ck_patients_target_min'),
        sa.CheckConstraint('target_glucose_max <= 180.0', name='ck_patients_target_max'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_synthetic_patients_patient_code'), 'synthetic_patients', ['patient_code'], unique=True)

    # 3. telemetry_records (Tier 1: Observed)
    op.create_table(
        'telemetry_records',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('glucose_mg_dl', sa.Float(), nullable=False),
        sa.Column('rate_of_change', sa.Float(), nullable=True),
        sa.Column('sensor_status', sa.String(length=20), nullable=False),
        sa.Column('meal_carbs_grams', sa.Float(), nullable=True),
        sa.Column('bolus_synthetic_units', sa.Float(), nullable=True),
        sa.Column('activity_minutes', sa.Float(), nullable=True),
        sa.Column('activity_intensity', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('glucose_mg_dl >= 40.0 AND glucose_mg_dl <= 500.0', name='ck_telemetry_glucose_bounds'),
        sa.CheckConstraint("sensor_status IN ('OK', 'CALIBRATING', 'NOISE', 'ERROR')", name='ck_telemetry_sensor_status'),
        sa.CheckConstraint('meal_carbs_grams >= 0.0 AND meal_carbs_grams <= 300.0', name='ck_telemetry_carbs_bounds'),
        sa.CheckConstraint('bolus_synthetic_units >= 0.0 AND bolus_synthetic_units <= 50.0', name='ck_telemetry_bolus_bounds'),
        sa.CheckConstraint('activity_minutes >= 0.0 AND activity_minutes <= 360.0', name='ck_telemetry_activity_minutes'),
        sa.CheckConstraint('activity_intensity >= 0 AND activity_intensity <= 3', name='ck_telemetry_activity_intensity'),
        sa.ForeignKeyConstraint(['patient_id'], ['synthetic_patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patient_id', 'timestamp', name='uq_patient_timestamp')
    )
    op.create_index(op.f('ix_telemetry_records_patient_id'), 'telemetry_records', ['patient_id'], unique=False)
    op.create_index(op.f('ix_telemetry_records_timestamp'), 'telemetry_records', ['timestamp'], unique=False)
    op.create_index('ix_telemetry_patient_time', 'telemetry_records', ['patient_id', sa.text('timestamp DESC')], unique=False)

    # 4. glycemic_metrics (Tier 2: Derived)
    op.create_table(
        'glycemic_metrics',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=False),
        sa.Column('window_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('window_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('total_readings', sa.Integer(), nullable=False),
        sa.Column('cgm_active_percentage', sa.Float(), nullable=False),
        sa.Column('mean_glucose_mg_dl', sa.Float(), nullable=False),
        sa.Column('standard_deviation', sa.Float(), nullable=False),
        sa.Column('cv_percentage', sa.Float(), nullable=False),
        sa.Column('gmi_percentage', sa.Float(), nullable=False),
        sa.Column('tir_percentage', sa.Float(), nullable=False),
        sa.Column('tar_level1_percentage', sa.Float(), nullable=False),
        sa.Column('tar_level2_percentage', sa.Float(), nullable=False),
        sa.Column('tbr_level1_percentage', sa.Float(), nullable=False),
        sa.Column('tbr_level2_percentage', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('total_readings >= 1', name='ck_metrics_total_readings'),
        sa.CheckConstraint('cgm_active_percentage >= 0.0 AND cgm_active_percentage <= 100.0', name='ck_metrics_cgm_active'),
        sa.CheckConstraint('mean_glucose_mg_dl > 0.0', name='ck_metrics_mean_glucose'),
        sa.CheckConstraint('standard_deviation >= 0.0', name='ck_metrics_std_dev'),
        sa.CheckConstraint('cv_percentage >= 0.0', name='ck_metrics_cv'),
        sa.CheckConstraint('gmi_percentage >= 4.0 AND gmi_percentage <= 18.0', name='ck_metrics_gmi'),
        sa.CheckConstraint('tir_percentage >= 0.0 AND tir_percentage <= 100.0', name='ck_metrics_tir'),
        sa.CheckConstraint('tar_level1_percentage >= 0.0 AND tar_level1_percentage <= 100.0', name='ck_metrics_tar1'),
        sa.CheckConstraint('tar_level2_percentage >= 0.0 AND tar_level2_percentage <= 100.0', name='ck_metrics_tar2'),
        sa.CheckConstraint('tbr_level1_percentage >= 0.0 AND tbr_level1_percentage <= 100.0', name='ck_metrics_tbr1'),
        sa.CheckConstraint('tbr_level2_percentage >= 0.0 AND tbr_level2_percentage <= 100.0', name='ck_metrics_tbr2'),
        sa.ForeignKeyConstraint(['patient_id'], ['synthetic_patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_glycemic_metrics_patient_id'), 'glycemic_metrics', ['patient_id'], unique=False)
    op.create_index(op.f('ix_glycemic_metrics_window_start'), 'glycemic_metrics', ['window_start'], unique=False)
    op.create_index(op.f('ix_glycemic_metrics_window_end'), 'glycemic_metrics', ['window_end'], unique=False)

    # 5. forecast_runs (Tier 3: Predicted)
    op.create_table(
        'forecast_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=False),
        sa.Column('run_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('model_version', sa.String(length=50), nullable=False),
        sa.Column('horizon_minutes', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('trajectory_json', sa.Text(), nullable=True),
        sa.Column('uncertainty_lower_json', sa.Text(), nullable=True),
        sa.Column('uncertainty_upper_json', sa.Text(), nullable=True),
        sa.Column('abstention_code', sa.String(length=50), nullable=True),
        sa.Column('abstention_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('horizon_minutes IN (15, 30, 45, 60)', name='ck_forecast_horizon'),
        sa.CheckConstraint("status IN ('completed', 'abstained', 'failed')", name='ck_forecast_status'),
        sa.ForeignKeyConstraint(['patient_id'], ['synthetic_patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_forecast_runs_patient_id'), 'forecast_runs', ['patient_id'], unique=False)
    op.create_index(op.f('ix_forecast_runs_run_timestamp'), 'forecast_runs', ['run_timestamp'], unique=False)

    # 6. simulation_scenarios (Tier 4: Hypothetical)
    op.create_table(
        'simulation_scenarios',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=False),
        sa.Column('scenario_name', sa.String(length=100), nullable=False),
        sa.Column('simulation_duration_min', sa.Integer(), nullable=False),
        sa.Column('perturbation_params_json', sa.Text(), nullable=False),
        sa.Column('baseline_trajectory_json', sa.Text(), nullable=True),
        sa.Column('simulated_trajectory_json', sa.Text(), nullable=False),
        sa.Column('tir_delta_percentage', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('simulation_duration_min >= 60 AND simulation_duration_min <= 1440', name='ck_sim_duration_bounds'),
        sa.ForeignKeyConstraint(['patient_id'], ['synthetic_patients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_simulation_scenarios_patient_id'), 'simulation_scenarios', ['patient_id'], unique=False)

    # 7. audit_logs
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=36), nullable=True),
        sa.Column('guardrail_triggered', sa.Boolean(), nullable=False),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_action'), 'audit_logs', ['action'], unique=False)
    op.create_index(op.f('ix_audit_logs_guardrail_triggered'), 'audit_logs', ['guardrail_triggered'], unique=False)
    op.create_index(op.f('ix_audit_logs_timestamp'), 'audit_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('simulation_scenarios')
    op.drop_table('forecast_runs')
    op.drop_table('glycemic_metrics')
    op.drop_table('telemetry_records')
    op.drop_table('synthetic_patients')
    op.drop_table('users')
