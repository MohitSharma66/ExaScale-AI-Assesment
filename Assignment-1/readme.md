# APU Power Demand Forecasting PoC

## Run with Docker
docker build -t demand-forecast .
docker run -p 8000:8000 demand-forecast

Open http://localhost:8000

## Endpoints
- /forecast  → 24-hour load prediction (144 blocks, 10-min intervals)
- /context   → weather + local holiday data for forecast period

## Data Sources
- Weather: Open-Meteo API (Dhanbad, Jharkhand)
- Holidays: Self-sourced local holidays for Dhanbad/Jharkhand