"""Geocoding, weather monitoring, hazard scoring, and AI-backed alert generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    AlertStatus,
    AlertType,
    CaseStatus,
    GeocodeStatus,
    RecipientType,
    UrgencyLevel,
    WeatherRiskBand,
)
from app.core.logging import get_logger
from app.integrations.geocoding.open_meteo_client import OpenMeteoGeocodingClient
from app.integrations.llm.gemini_client import generate_weather_alert_decision
from app.integrations.weather.imd_client import IMDWarningsClient
from app.integrations.weather.open_meteo_client import OpenMeteoForecastClient
from app.models.alert import Alert
from app.models.case import Case
from app.models.weather_intelligence import HazardAssessment, WeatherSnapshot

logger = get_logger(__name__)

ACTIVE_MONITOR_CASE_STATUSES = {
    CaseStatus.new,
    CaseStatus.verified,
    CaseStatus.assigned,
    CaseStatus.in_progress,
}
THUNDERSTORM_CODES = {95, 96, 99}
HEAVY_RAIN_CODES = {61, 63, 65, 66, 67, 80, 81, 82}


@dataclass
class CaseRunResult:
    geocoded: bool = False
    alert_written: bool = False
    alert_resolved: bool = False
    skipped: bool = False
    snapshot: WeatherSnapshot | None = None
    assessment: HazardAssessment | None = None


class WeatherIntelligenceService:
    def __init__(self, db: Session):
        self.db = db
        self.geocoder = OpenMeteoGeocodingClient()
        self.forecast_client = OpenMeteoForecastClient()
        self.warning_client = IMDWarningsClient()

    def refresh_case_location(self, case: Case) -> bool:
        if case.latitude is not None and case.longitude is not None:
            case.geocode_status = GeocodeStatus.resolved
            case.next_weather_check_at = case.next_weather_check_at or datetime.now(UTC)
            return False

        if not case.location_name:
            case.geocode_status = GeocodeStatus.not_requested
            case.next_weather_check_at = None
            return False

        try:
            result = self.geocoder.geocode(case.location_name)
        except Exception as exc:
            case.geocode_status = GeocodeStatus.failed
            logger.warning("Case geocoding failed", case_id=str(case.id), error=str(exc))
            return False

        if not result:
            case.geocode_status = GeocodeStatus.manual_review
            case.next_weather_check_at = None
            return False

        case.latitude = result["latitude"]
        case.longitude = result["longitude"]
        case.district = result.get("district")
        case.state = result.get("state")
        case.geocode_provider = result.get("provider")
        case.geocode_confidence = result.get("confidence")
        case.geocode_status = (
            GeocodeStatus.resolved
            if (result.get("confidence") or 0) >= 65
            else GeocodeStatus.manual_review
        )
        case.next_weather_check_at = datetime.now(UTC)
        return True

    def run_case_monitor(self, case: Case) -> CaseRunResult:
        result = CaseRunResult()
        if not settings.ENABLE_WEATHER_INTELLIGENCE:
            result.skipped = True
            return result

        if case.status not in ACTIVE_MONITOR_CASE_STATUSES:
            result.skipped = True
            return result

        if case.latitude is None or case.longitude is None:
            result.geocoded = self.refresh_case_location(case)

        if case.latitude is None or case.longitude is None:
            result.skipped = True
            return result

        forecast = self.forecast_client.fetch_forecast(float(case.latitude), float(case.longitude))
        warnings = self.warning_client.fetch_warnings(case.state, case.district)
        snapshot = self._create_snapshot(case, forecast, warnings)
        assessment = self._create_assessment(case, snapshot, forecast, warnings)

        case.weather_risk_band = assessment.risk_band
        case.last_weather_checked_at = datetime.now(UTC)
        case.next_weather_check_at = self._next_check_time(assessment.risk_band)

        if assessment.danger_for_community or assessment.danger_on_volunteers:
            result.alert_written = self._upsert_weather_alert(case, assessment)
            assessment.alert_emitted = True
        else:
            result.alert_resolved = self._resolve_active_weather_alert(case)
            assessment.alert_emitted = False

        result.snapshot = snapshot
        result.assessment = assessment
        return result

    def scan_due_cases(self, organization_id=None, limit: Optional[int] = None) -> dict[str, int]:
        query = select(Case).where(Case.status.in_(ACTIVE_MONITOR_CASE_STATUSES))
        query = query.where(Case.next_weather_check_at.is_not(None))
        query = query.where(Case.next_weather_check_at <= datetime.now(UTC))
        if organization_id is not None:
            query = query.where(Case.organization_id == organization_id)

        query = query.order_by(Case.next_weather_check_at.asc()).limit(
            limit or settings.WEATHER_MONITOR_CASE_SCAN_LIMIT
        )
        cases = self.db.execute(query).scalars().all()

        counts = {
            "scanned_cases": len(cases),
            "assessed_cases": 0,
            "alerts_created_or_updated": 0,
            "alerts_resolved": 0,
            "geocoded_cases": 0,
            "skipped_cases": 0,
        }

        for case in cases:
            try:
                result = self.run_case_monitor(case)
            except Exception as exc:
                counts["skipped_cases"] += 1
                logger.warning("Weather scan failed for case", case_id=str(case.id), error=str(exc))
                continue

            if result.geocoded:
                counts["geocoded_cases"] += 1
            if result.skipped:
                counts["skipped_cases"] += 1
                continue

            counts["assessed_cases"] += 1
            if result.alert_written:
                counts["alerts_created_or_updated"] += 1
            if result.alert_resolved:
                counts["alerts_resolved"] += 1

        return counts

    def _create_snapshot(
        self,
        case: Case,
        forecast: dict,
        warnings: list[dict],
    ) -> WeatherSnapshot:
        forecast_window_end = None
        raw_end = forecast.get("forecast_window_end")
        if raw_end:
            forecast_window_end = datetime.fromisoformat(raw_end)

        snapshot = WeatherSnapshot(
            organization_id=case.organization_id,
            case_id=case.id,
            geocoding_provider=case.geocode_provider,
            forecast_provider="open_meteo",
            warning_provider=settings.WEATHER_WARNING_PROVIDER if warnings else None,
            latitude=float(case.latitude),
            longitude=float(case.longitude),
            location_label=case.location_name,
            forecast_window_end=forecast_window_end,
            summary_json={
                key: value
                for key, value in forecast.items()
                if key != "raw"
            },
            raw_json={
                "forecast": forecast.get("raw"),
                "warnings": warnings,
            },
        )
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def _create_assessment(
        self,
        case: Case,
        snapshot: WeatherSnapshot,
        forecast: dict,
        warnings: list[dict],
    ) -> HazardAssessment:
        factors = self._compute_factors(case, forecast, warnings)
        ai_payload = self._build_ai_payload(case, factors, warnings)
        ai_result = generate_weather_alert_decision(ai_payload)
        decision = self._finalize_decision(case, factors, warnings, ai_result)

        assessment = HazardAssessment(
            organization_id=case.organization_id,
            case_id=case.id,
            weather_snapshot_id=snapshot.id,
            risk_band=factors["risk_band"],
            severity=factors["severity"],
            hazard_score=factors["hazard_score"],
            danger_for_community=decision["danger_for_community"],
            can_be_solved=decision["can_be_solved"],
            danger_on_volunteers=decision["danger_on_volunteers"],
            heading=decision["heading"],
            description=decision["description"],
            full_text=decision["full_text"],
            solution=decision["solution"],
            reason_codes_json={"codes": factors["reason_codes"], "warnings": warnings},
            factors_json=factors["metrics"],
            providers_json={
                "geocoding": case.geocode_provider,
                "forecast": "open_meteo",
                "warnings": settings.WEATHER_WARNING_PROVIDER if warnings else "none",
                "llm": decision.get("model_used"),
            },
            model_used=decision.get("model_used"),
            prompt_version=decision.get("prompt_version"),
            alert_emitted=False,
        )
        self.db.add(assessment)
        self.db.flush()
        return assessment

    def _compute_factors(self, case: Case, forecast: dict, warnings: list[dict]) -> dict:
        metrics = {
            "peak_precipitation_probability": float(forecast.get("peak_precipitation_probability") or 0),
            "peak_precipitation": float(forecast.get("peak_precipitation") or 0),
            "total_precipitation": float(forecast.get("total_precipitation") or 0),
            "peak_wind_speed": float(forecast.get("peak_wind_speed") or 0),
            "peak_wind_gust": float(forecast.get("peak_wind_gust") or 0),
            "official_warning_count": len(warnings),
            "case_urgency": case.urgency_level.value,
            "people_affected": case.number_of_people_affected,
        }
        weather_codes = set(forecast.get("weather_codes") or [])
        warning_text = " ".join(self._warning_text(item) for item in warnings).lower()

        reason_codes: list[str] = []
        hazard_score = 0.0

        official_warning_score = self._official_warning_score(warning_text)
        if official_warning_score:
            hazard_score += official_warning_score
            reason_codes.append("official_warning")

        if weather_codes & THUNDERSTORM_CODES:
            hazard_score += 25
            reason_codes.append("thunderstorm")

        if weather_codes & HEAVY_RAIN_CODES:
            hazard_score += 10
            reason_codes.append("rain_signal")

        if metrics["peak_precipitation_probability"] >= 80:
            hazard_score += 15
            reason_codes.append("high_precipitation_probability")
        elif metrics["peak_precipitation_probability"] >= 60:
            hazard_score += 8
            reason_codes.append("elevated_precipitation_probability")

        if metrics["total_precipitation"] >= 20 or metrics["peak_precipitation"] >= 10:
            hazard_score += 20
            reason_codes.append("heavy_rain")
        elif metrics["total_precipitation"] >= 8:
            hazard_score += 10
            reason_codes.append("moderate_rain")

        if metrics["peak_wind_gust"] >= 55:
            hazard_score += 20
            reason_codes.append("dangerous_wind_gusts")
        elif metrics["peak_wind_gust"] >= 40:
            hazard_score += 10
            reason_codes.append("strong_wind_gusts")

        if case.urgency_level == UrgencyLevel.critical:
            hazard_score += 15
            reason_codes.append("critical_case")
        elif case.urgency_level == UrgencyLevel.high:
            hazard_score += 10
            reason_codes.append("high_urgency_case")

        if case.number_of_people_affected >= 50:
            hazard_score += 12
            reason_codes.append("large_affected_group")
        elif case.number_of_people_affected >= 10:
            hazard_score += 6
            reason_codes.append("multi_person_case")

        hazard_score = round(min(hazard_score, 100.0), 2)

        if hazard_score >= 75:
            risk_band = WeatherRiskBand.severe
            severity = "critical"
        elif hazard_score >= 50:
            risk_band = WeatherRiskBand.elevated
            severity = "high"
        elif hazard_score >= 25:
            risk_band = WeatherRiskBand.watch
            severity = "medium"
        else:
            risk_band = WeatherRiskBand.clear
            severity = "low"

        return {
            "hazard_score": hazard_score,
            "risk_band": risk_band,
            "severity": severity,
            "reason_codes": reason_codes,
            "metrics": metrics,
        }

    def _build_ai_payload(self, case: Case, factors: dict, warnings: list[dict]) -> dict:
        return {
            "case": {
                "title": case.title,
                "location_name": case.location_name,
                "district": case.district,
                "state": case.state,
                "urgency_level": case.urgency_level.value,
                "status": case.status.value,
                "people_affected": case.number_of_people_affected,
                "disaster_type": case.disaster_type.value if case.disaster_type else None,
            },
            "hazard": {
                "risk_band": factors["risk_band"].value,
                "severity": factors["severity"],
                "hazard_score": factors["hazard_score"],
                "reason_codes": factors["reason_codes"],
                "metrics": factors["metrics"],
            },
            "official_warnings": warnings,
        }

    def _finalize_decision(
        self,
        case: Case,
        factors: dict,
        warnings: list[dict],
        ai_result: Optional[dict],
    ) -> dict:
        decision = self._fallback_decision(case, factors, warnings)

        if ai_result:
            decision.update(
                {
                    "danger_for_community": bool(ai_result.get("danger_for_community")),
                    "can_be_solved": bool(ai_result.get("can_be_solved")),
                    "danger_on_volunteers": bool(ai_result.get("danger_on_volunteers")),
                    "heading": ai_result.get("heading"),
                    "description": ai_result.get("description"),
                    "solution": ai_result.get("solution"),
                    "full_text": ai_result.get("full_text"),
                    "model_used": ai_result.get("model_used"),
                    "prompt_version": ai_result.get("prompt_version"),
                }
            )

        if not (decision["danger_for_community"] or decision["danger_on_volunteers"]):
            decision["heading"] = None
            decision["description"] = None
            decision["full_text"] = None

        if not decision["can_be_solved"]:
            decision["solution"] = None

        if (decision["danger_for_community"] or decision["danger_on_volunteers"]) and not decision["heading"]:
            decision["heading"] = self._fallback_heading(case, factors)
        if (decision["danger_for_community"] or decision["danger_on_volunteers"]) and not decision["description"]:
            decision["description"] = self._fallback_description(case, factors)
        if (decision["danger_for_community"] or decision["danger_on_volunteers"]) and not decision["full_text"]:
            decision["full_text"] = self._fallback_full_text(case, factors)
        if decision["can_be_solved"] and not decision["solution"]:
            decision["solution"] = self._fallback_solution(factors)

        return decision

    def _fallback_decision(self, case: Case, factors: dict, warnings: list[dict]) -> dict:
        metrics = factors["metrics"]
        community_risk = (
            factors["risk_band"] in {WeatherRiskBand.elevated, WeatherRiskBand.severe}
            or metrics["official_warning_count"] > 0
        )
        volunteer_risk = (
            "thunderstorm" in factors["reason_codes"]
            or metrics["peak_wind_gust"] >= 45
            or metrics["total_precipitation"] >= 12
        )
        can_be_solved = not (
            factors["risk_band"] == WeatherRiskBand.severe
            and metrics["official_warning_count"] > 0
            and case.urgency_level == UrgencyLevel.critical
        )

        return {
            "danger_for_community": community_risk,
            "can_be_solved": can_be_solved,
            "danger_on_volunteers": volunteer_risk,
            "heading": self._fallback_heading(case, factors) if (community_risk or volunteer_risk) else None,
            "description": self._fallback_description(case, factors) if (community_risk or volunteer_risk) else None,
            "solution": self._fallback_solution(factors) if can_be_solved else None,
            "full_text": self._fallback_full_text(case, factors) if (community_risk or volunteer_risk) else None,
            "model_used": None,
            "prompt_version": None,
        }

    def _fallback_heading(self, case: Case, factors: dict) -> str:
        if "official_warning" in factors["reason_codes"]:
            return f"Official weather warning near {case.location_name or case.case_number}"
        if "thunderstorm" in factors["reason_codes"]:
            return f"Thunderstorm risk around {case.location_name or case.case_number}"
        if "dangerous_wind_gusts" in factors["reason_codes"]:
            return f"Volunteer travel risk near {case.location_name or case.case_number}"
        return f"Weather may disrupt response for {case.location_name or case.case_number}"

    def _fallback_description(self, case: Case, factors: dict) -> str:
        metrics = factors["metrics"]
        return (
            f"Risk band {factors['risk_band'].value} with rain probability at "
            f"{metrics['peak_precipitation_probability']:.0f}% and wind gusts up to "
            f"{metrics['peak_wind_gust']:.0f} km/h for {case.location_name or case.case_number}."
        )

    def _fallback_full_text(self, case: Case, factors: dict) -> str:
        metrics = factors["metrics"]
        return (
            f"Weather intelligence flagged the case at {case.location_name or case.case_number} as "
            f"{factors['risk_band'].value}. The next {settings.WEATHER_MONITOR_FORECAST_HOURS} hours show "
            f"precipitation probability up to {metrics['peak_precipitation_probability']:.0f}%, "
            f"total expected rain of {metrics['total_precipitation']:.1f} mm, and wind gusts up to "
            f"{metrics['peak_wind_gust']:.0f} km/h. Review field travel, community exposure, and assignment timing."
        )

    def _fallback_solution(self, factors: dict) -> str:
        if factors["risk_band"] == WeatherRiskBand.severe:
            return "Delay field deployment, shift coordination indoors, and reassess after the warning window."
        if factors["risk_band"] == WeatherRiskBand.elevated:
            return "Proceed only with protected volunteers, shorter routes, and a 30-minute weather recheck."
        return "Continue monitoring and keep volunteers informed before dispatch."

    def _upsert_weather_alert(self, case: Case, assessment: HazardAssessment) -> bool:
        existing_alert = self.db.execute(
            select(Alert).where(
                Alert.case_id == case.id,
                Alert.type == AlertType.weather_risk,
                Alert.status == AlertStatus.active,
            )
        ).scalars().first()

        metadata = {
            "kind": "weather_intelligence",
            "heading": assessment.heading,
            "description": assessment.description,
            "full_text": assessment.full_text,
            "solution": assessment.solution,
            "severity": assessment.severity,
            "risk_band": assessment.risk_band.value,
            "decisions": {
                "danger_for_community": assessment.danger_for_community,
                "can_be_solved": assessment.can_be_solved,
                "danger_on_volunteers": assessment.danger_on_volunteers,
            },
            "providers": assessment.providers_json,
            "weather": assessment.factors_json,
            "assessment_id": str(assessment.id),
        }

        if existing_alert:
            existing_alert.message = assessment.description or existing_alert.message
            existing_alert.recipient_type = RecipientType.admin
            existing_alert.metadata_json = metadata
            return True

        alert = Alert(
            organization_id=case.organization_id,
            case_id=case.id,
            type=AlertType.weather_risk,
            message=assessment.description or "Weather conditions may affect this case.",
            recipient_type=RecipientType.admin,
            metadata_json=metadata,
        )
        self.db.add(alert)
        return True

    def _resolve_active_weather_alert(self, case: Case) -> bool:
        existing_alert = self.db.execute(
            select(Alert).where(
                Alert.case_id == case.id,
                Alert.type == AlertType.weather_risk,
                Alert.status == AlertStatus.active,
            )
        ).scalars().first()
        if not existing_alert:
            return False

        existing_alert.status = AlertStatus.resolved
        existing_alert.resolved_at = datetime.now(UTC)
        return True

    def _next_check_time(self, risk_band: WeatherRiskBand) -> datetime:
        minutes = settings.WEATHER_MONITOR_CLEAR_INTERVAL_MINUTES
        if risk_band == WeatherRiskBand.watch:
            minutes = settings.WEATHER_MONITOR_WATCH_INTERVAL_MINUTES
        elif risk_band == WeatherRiskBand.elevated:
            minutes = settings.WEATHER_MONITOR_ELEVATED_INTERVAL_MINUTES
        elif risk_band == WeatherRiskBand.severe:
            minutes = settings.WEATHER_MONITOR_SEVERE_INTERVAL_MINUTES
        return datetime.now(UTC) + timedelta(minutes=minutes)

    def _official_warning_score(self, text: str) -> float:
        if not text:
            return 0.0
        if "red" in text:
            return 45.0
        if "orange" in text:
            return 35.0
        if "yellow" in text:
            return 20.0
        if "warning" in text or "alert" in text:
            return 15.0
        return 0.0

    def _warning_text(self, item: dict) -> str:
        chunks = []
        for value in item.values():
            if isinstance(value, str):
                chunks.append(value)
        return " ".join(chunks)
