"""Weather monitoring persistence for case intelligence."""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import WeatherRiskBand
from app.db.base import Base, TimestampMixin, UUIDMixin


class WeatherSnapshot(UUIDMixin, Base):
    """A normalized forecast and warning payload captured for one case."""

    __tablename__ = "weather_snapshots"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    geocoding_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    forecast_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    warning_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    location_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
    )
    forecast_window_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    summary_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class HazardAssessment(UUIDMixin, TimestampMixin, Base):
    """Decision-ready hazard assessment for a case and its latest weather snapshot."""

    __tablename__ = "hazard_assessments"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    weather_snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weather_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    risk_band: Mapped[WeatherRiskBand] = mapped_column(
        SAEnum(WeatherRiskBand, name="hazard_assessment_risk_band_enum"),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    hazard_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    danger_for_community: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    can_be_solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    danger_on_volunteers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    heading: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason_codes_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    factors_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    providers_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    alert_emitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
