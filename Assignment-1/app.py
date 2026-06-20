from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import pandas as pd
import numpy as np
import joblib
import requests
from datetime import datetime, timedelta
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MODEL = joblib.load("models/demand_model.pkl")
FEATURE_COLS = joblib.load("models/feature_names.pkl")
HIST = pd.read_csv("data/cleaned_load.csv", parse_dates=["Datetime"]).set_index("Datetime").sort_index()
HOLIDAYS = pd.read_csv("data/local_holidays.csv", parse_dates=["date"], dayfirst=True)

def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {"latitude": 23.79, "longitude": 86.43,
              "hourly": "temperature_2m,relative_humidity_2m,cloud_cover,wind_speed_10m",
              "timezone": "Asia/Kolkata", "forecast_days": 2}
    r = requests.get(url, params=params).json()
    idx = pd.to_datetime(r["hourly"]["time"])
    return pd.DataFrame({"Temperature": r["hourly"]["temperature_2m"],
                         "Humidity": r["hourly"]["relative_humidity_2m"],
                         "CloudCover": r["hourly"]["cloud_cover"],
                         "WindSpeed": r["hourly"]["wind_speed_10m"]}, index=idx)

def get_timestamps():
    now = datetime.now().replace(second=0, microsecond=0)
    start = now - timedelta(minutes=now.minute % 10)
    return pd.date_range(start, periods=144, freq="10min")

@app.get("/forecast")
def forecast():
    ts = get_timestamps()
    weather = fetch_weather().resample("10min").ffill().reindex(ts).ffill()
    
    X = pd.DataFrame(index=ts)
    X["hour"] = X.index.hour
    X["minute"] = X.index.minute
    X["dayofweek"] = X.index.dayofweek
    X["month"] = X.index.month
    
    holiday_dates = HOLIDAYS["date"].dt.date.values
    X["is_holiday"] = [int(d in holiday_dates) for d in X.index.date]
    
    holiday_type_map = dict(zip(HOLIDAYS["date"].dt.date, HOLIDAYS["type"]))
    X["holiday_type"] = [holiday_type_map.get(d, "none") for d in X.index.date]
    X["holiday_type"] = X["holiday_type"].map({"none":0, "national":1, "festive":2, "industrial":3, "local":4}).astype(int)
    
    for col in ["Temperature", "Humidity", "WindSpeed", "CloudCover"]:
        X[col] = weather[col].values
    
    power_cols = ["F1_132KV_PowerConsumption", "F2_132KV_PowerConsumption", "F3_132KV_PowerConsumption"]
    for col in power_cols:
        if len(HIST) >= 144:
            X[f"{col}_lag1d"] = HIST[col].iloc[-144]
        else:
            X[f"{col}_lag1d"] = HIST[col].mean()
        if len(HIST) >= 1008:
            X[f"{col}_lag7d"] = HIST[col].iloc[-1008]
        else:
            X[f"{col}_lag7d"] = HIST[col].mean()
        X[f"{col}_rolling24h"] = HIST[col].iloc[-144:].mean()
    
    X = X[FEATURE_COLS]
    preds = MODEL.predict(X)
    
    return {
        "timestamps": ts.strftime("%Y-%m-%d %H:%M").tolist(),
        "F1": preds[:, 0].tolist(),
        "F2": preds[:, 1].tolist(),
        "F3": preds[:, 2].tolist()
    }

@app.get("/context")
def context():
    ts = get_timestamps()
    weather = fetch_weather().resample("10min").ffill().reindex(ts).ffill()
    return {"timestamps": ts.strftime("%Y-%m-%d %H:%M").tolist(),
            "Temperature": weather["Temperature"].tolist(),
            "Humidity": weather["Humidity"].tolist(),
            "CloudCover": weather["CloudCover"].tolist(),
            "WindSpeed": weather["WindSpeed"].tolist(),
            "Holidays": [{"name": str(HOLIDAYS[HOLIDAYS["date"].dt.date == d]["holiday_name"].iloc[0]) 
                          if d in HOLIDAYS["date"].dt.date.values else None} 
                         for d in ts.date]}

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")