"""Open-Meteo forecast client used for hourly weather monitoring."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from app.core.config import settings


class OpenMeteoForecastClient:
    def fetch_forecast(self, latitude: float, longitude: float) -> dict:
        response = httpx.get(
            settings.OPEN_METEO_FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "forecast_days": 2,
                "timezone": "auto",
                "hourly": ",".join(
                    [
                        "temperature_2m",
                        "precipitation_probability",
                        "precipitation",
                        "weather_code",
                        "wind_speed_10m",
                        "wind_gusts_10m",
                    ]
                ),
            },
            timeout=settings.GEOCODING_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        return self._summarize(payload)

    def _summarize(self, payload: dict) -> dict:
        hourly = payload.get("hourly") or {}
        times = hourly.get("time") or []
        window = min(len(times), settings.WEATHER_MONITOR_FORECAST_HOURS)
        if window == 0:
            return {
                "window_hours": 0,
                "times": [],
                "peak_precipitation_probability": 0.0,
                "peak_precipitation": 0.0,
                "total_precipitation": 0.0,
                "peak_wind_speed": 0.0,
                "peak_wind_gust": 0.0,
                "weather_codes": [],
                "forecast_window_end": None,
                "raw": payload,
            }

        def _slice(key: str) -> list[float]:
            values = hourly.get(key) or []
            return [float(value or 0) for value in values[:window]]

        precip_probability = _slice("precipitation_probability")
        precipitation = _slice("precipitation")
        wind_speed = _slice("wind_speed_10m")
        wind_gust = _slice("wind_gusts_10m")
        weather_codes = [int(value or 0) for value in (hourly.get("weather_code") or [])[:window]]

        forecast_window_end: Optional[datetime] = None
        try:
            forecast_window_end = datetime.fromisoformat(times[window - 1])
        except (ValueError, IndexError):
            forecast_window_end = None

        return {
            "window_hours": window,
            "times": times[:window],
            "peak_precipitation_probability": max(precip_probability, default=0.0),
            "peak_precipitation": max(precipitation, default=0.0),
            "total_precipitation": round(sum(precipitation), 2),
            "peak_wind_speed": max(wind_speed, default=0.0),
            "peak_wind_gust": max(wind_gust, default=0.0),
            "weather_codes": sorted(set(weather_codes)),
            "forecast_window_end": forecast_window_end.isoformat() if forecast_window_end else None,
            "raw": payload,
        }
