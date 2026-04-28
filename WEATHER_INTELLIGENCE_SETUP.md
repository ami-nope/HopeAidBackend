# Weather Intelligence Setup

This feature is wired to work immediately with free fallbacks and optional production providers.

## Default working stack

- Geocoding: `Open-Meteo`
- Forecast: `Open-Meteo`
- Official warnings: disabled until you add an IMD feed
- AI text + decisions: disabled until you add a Gemini key

With only the defaults, the backend will:

- geocode case `location_name` values
- fetch forecast data for resolved coordinates
- compute deterministic weather risk
- create or resolve weather alerts
- show expandable alert details in the frontend

## Environment variables

Paste these into `.env` based on `.env.example`:

- `ENABLE_WEATHER_INTELLIGENCE=true`
- `GEOCODING_PROVIDER=open_meteo`
- `OPEN_METEO_GEOCODING_URL=https://geocoding-api.open-meteo.com/v1/search`
- `OPEN_METEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast`
- `WEATHER_MONITOR_FORECAST_HOURS=12`
- `WEATHER_MONITOR_CLEAR_INTERVAL_MINUTES=180`
- `WEATHER_MONITOR_WATCH_INTERVAL_MINUTES=60`
- `WEATHER_MONITOR_ELEVATED_INTERVAL_MINUTES=30`
- `WEATHER_MONITOR_SEVERE_INTERVAL_MINUTES=30`

### Optional provider slots

- `MAPPLS_API_KEY=`
- `MAPPLS_CLIENT_ID=`
- `MAPPLS_CLIENT_SECRET=`
- `MAPPLS_BASE_URL=https://atlas.mappls.com`

- `WEATHER_WARNING_PROVIDER=none`
- `IMD_WARNINGS_URL_TEMPLATE=`
- `IMD_API_KEY=`

- `GEMINI_API_KEY=`
- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta`

## Which APIs this backend expects

### Geocoding

Current built-in fallback:

- `GET https://geocoding-api.open-meteo.com/v1/search`

Recommended India production replacement:

- Mappls / MapmyIndia geocoding endpoint
- Paste credentials into `MAPPLS_*`
- Replace the geocoder implementation when you finalize the exact auth flow

### Forecast

Current built-in forecast:

- `GET https://api.open-meteo.com/v1/forecast`

Used hourly fields:

- `precipitation_probability`
- `precipitation`
- `weather_code`
- `wind_speed_10m`
- `wind_gusts_10m`

### Official warnings

The IMD client is template-driven because different feeds use different access patterns.

Paste the confirmed IMD district warning URL into:

- `IMD_WARNINGS_URL_TEMPLATE`

Expected placeholders:

- `{state}`
- `{district}`

Example shape:

- `https://your-imd-feed.example/{state}/{district}`

### Gemini

The Gemini client calls:

- `POST {GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}`

Gemini is used only for this JSON contract:

- `danger_for_community`
- `can_be_solved`
- `danger_on_volunteers`
- `heading`
- `description`
- `solution`
- `full_text`

## Tables added

- `weather_snapshots`
- `hazard_assessments`

Existing table extended:

- `cases`

New case columns:

- `geocode_status`
- `geocode_provider`
- `geocode_confidence`
- `district`
- `state`
- `weather_risk_band`
- `last_weather_checked_at`
- `next_weather_check_at`

## Manual backend endpoints

- `POST /api/v1/cases/{case_id}/refresh-location`
- `POST /api/v1/cases/{case_id}/weather-intelligence`
- `POST /api/v1/cases/weather-intelligence/run`
- `POST /api/v1/alerts/intelligence/run`

## Supabase / Postgres

Run:

```bash
alembic upgrade head
```

If your database predates Alembic history in this repo, baseline it carefully before applying production migrations.
