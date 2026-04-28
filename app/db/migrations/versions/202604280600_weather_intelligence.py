"""Add weather intelligence tables and case monitoring fields.

Revision ID: 202604280600
Revises: None
Create Date: 2026-04-28 06:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "202604280600"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    geocode_status_enum = sa.Enum(
        "not_requested",
        "pending",
        "resolved",
        "failed",
        "manual_review",
        name="geocode_status_enum",
    )
    geocode_status_enum.create(bind, checkfirst=True)

    weather_risk_band_enum = sa.Enum(
        "clear",
        "watch",
        "elevated",
        "severe",
        name="weather_risk_band_enum",
    )
    weather_risk_band_enum.create(bind, checkfirst=True)

    hazard_risk_band_enum = sa.Enum(
        "clear",
        "watch",
        "elevated",
        "severe",
        name="hazard_assessment_risk_band_enum",
    )
    hazard_risk_band_enum.create(bind, checkfirst=True)

    op.execute("ALTER TYPE alert_type_enum ADD VALUE IF NOT EXISTS 'weather_risk'")

    op.add_column(
        "cases",
        sa.Column(
            "geocode_status",
            geocode_status_enum,
            nullable=False,
            server_default="not_requested",
        ),
    )
    op.add_column("cases", sa.Column("geocode_provider", sa.String(length=50), nullable=True))
    op.add_column("cases", sa.Column("geocode_confidence", sa.Numeric(5, 2), nullable=True))
    op.add_column("cases", sa.Column("district", sa.String(length=150), nullable=True))
    op.add_column("cases", sa.Column("state", sa.String(length=150), nullable=True))
    op.add_column("cases", sa.Column("weather_risk_band", weather_risk_band_enum, nullable=True))
    op.add_column("cases", sa.Column("last_weather_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cases", sa.Column("next_weather_check_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_cases_geocode_status"), "cases", ["geocode_status"], unique=False)
    op.create_index(op.f("ix_cases_district"), "cases", ["district"], unique=False)
    op.create_index(op.f("ix_cases_state"), "cases", ["state"], unique=False)
    op.create_index(op.f("ix_cases_weather_risk_band"), "cases", ["weather_risk_band"], unique=False)
    op.create_index(op.f("ix_cases_next_weather_check_at"), "cases", ["next_weather_check_at"], unique=False)

    op.create_table(
        "weather_snapshots",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("geocoding_provider", sa.String(length=50), nullable=True),
        sa.Column("forecast_provider", sa.String(length=50), nullable=False),
        sa.Column("warning_provider", sa.String(length=50), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("location_label", sa.String(length=255), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("forecast_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_weather_snapshots_case_id"), "weather_snapshots", ["case_id"], unique=False)
    op.create_index(op.f("ix_weather_snapshots_collected_at"), "weather_snapshots", ["collected_at"], unique=False)
    op.create_index(op.f("ix_weather_snapshots_organization_id"), "weather_snapshots", ["organization_id"], unique=False)

    op.create_table(
        "hazard_assessments",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weather_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("risk_band", hazard_risk_band_enum, nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("hazard_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("danger_for_community", sa.Boolean(), nullable=False),
        sa.Column("can_be_solved", sa.Boolean(), nullable=False),
        sa.Column("danger_on_volunteers", sa.Boolean(), nullable=False),
        sa.Column("heading", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("solution", sa.Text(), nullable=True),
        sa.Column("reason_codes_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("factors_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("providers_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("prompt_version", sa.String(length=20), nullable=True),
        sa.Column("alert_emitted", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["weather_snapshot_id"], ["weather_snapshots.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hazard_assessments_case_id"), "hazard_assessments", ["case_id"], unique=False)
    op.create_index(op.f("ix_hazard_assessments_organization_id"), "hazard_assessments", ["organization_id"], unique=False)
    op.create_index(op.f("ix_hazard_assessments_risk_band"), "hazard_assessments", ["risk_band"], unique=False)
    op.create_index(op.f("ix_hazard_assessments_weather_snapshot_id"), "hazard_assessments", ["weather_snapshot_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hazard_assessments_weather_snapshot_id"), table_name="hazard_assessments")
    op.drop_index(op.f("ix_hazard_assessments_risk_band"), table_name="hazard_assessments")
    op.drop_index(op.f("ix_hazard_assessments_organization_id"), table_name="hazard_assessments")
    op.drop_index(op.f("ix_hazard_assessments_case_id"), table_name="hazard_assessments")
    op.drop_table("hazard_assessments")

    op.drop_index(op.f("ix_weather_snapshots_organization_id"), table_name="weather_snapshots")
    op.drop_index(op.f("ix_weather_snapshots_collected_at"), table_name="weather_snapshots")
    op.drop_index(op.f("ix_weather_snapshots_case_id"), table_name="weather_snapshots")
    op.drop_table("weather_snapshots")

    op.drop_index(op.f("ix_cases_next_weather_check_at"), table_name="cases")
    op.drop_index(op.f("ix_cases_weather_risk_band"), table_name="cases")
    op.drop_index(op.f("ix_cases_state"), table_name="cases")
    op.drop_index(op.f("ix_cases_district"), table_name="cases")
    op.drop_index(op.f("ix_cases_geocode_status"), table_name="cases")
    op.drop_column("cases", "next_weather_check_at")
    op.drop_column("cases", "last_weather_checked_at")
    op.drop_column("cases", "weather_risk_band")
    op.drop_column("cases", "state")
    op.drop_column("cases", "district")
    op.drop_column("cases", "geocode_confidence")
    op.drop_column("cases", "geocode_provider")
    op.drop_column("cases", "geocode_status")

    bind = op.get_bind()
    sa.Enum(name="hazard_assessment_risk_band_enum").drop(bind, checkfirst=True)
    sa.Enum(name="weather_risk_band_enum").drop(bind, checkfirst=True)
    sa.Enum(name="geocode_status_enum").drop(bind, checkfirst=True)
