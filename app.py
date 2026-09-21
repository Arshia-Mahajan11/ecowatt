from flask import Flask, render_template, request
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score

from data_loader import load_real_dataset

app = Flask(__name__)
TARIFF = 7.0  # illustrative INR/kWh; replace with user's actual tariff
INTERVALS_PER_DAY = 144  # the dataset is sampled every 10 minutes (24 * 6)
DAYS_PER_MONTH = 30

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------
# REAL DATASET
# UCI Appliances Energy Prediction: 19,735 real observations
# collected at 10-minute intervals in a monitored building.
# ---------------------------------------------------------
df = load_real_dataset()

if df.empty:
    raise RuntimeError(
        "Loaded dataset has 0 rows. Delete the 'data' folder and rerun "
        "'python app.py' on a stable internet connection."
    )

# Pandas 2.x can reject mixed date strings such as
# "2016-01-11 17:00:00" / ISO-style variants. "mixed" lets pandas
# parse the public UCI dataset robustly across versions.
try:
    df["date"] = pd.to_datetime(df["date"], format="mixed", errors="coerce")
except TypeError:
    # Compatibility with older pandas versions.
    df["date"] = pd.to_datetime(df["date"], errors="coerce")

df = df.dropna(subset=["date"])
if df.empty:
    raise RuntimeError(
        "Every 'date' value failed to parse, leaving 0 rows. This usually "
        "means the cached CSV is corrupted — delete the 'data' folder and "
        "rerun 'python app.py'."
    )

df["hour"] = df["date"].dt.hour
df["dayofweek"] = df["date"].dt.dayofweek
df["month"] = df["date"].dt.month

feature_cols = [
    "hour", "dayofweek", "month",
    "T1", "RH_1", "T2", "RH_2", "T_out", "RH_out",
    "Windspeed", "Visibility", "lights"
]
target_col = "Appliances"

df = df[feature_cols + [target_col]].dropna()
if df.empty:
    raise RuntimeError(
        "No complete rows remained after selecting model features. Delete "
        "the 'data' folder and rerun 'python app.py'."
    )

# Keep training fast while retaining a large real sample.
train_df = df.sample(min(16000, len(df)), random_state=42)

X = train_df[feature_cols]
y = train_df[target_col]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model = RandomForestRegressor(
    n_estimators=160,
    max_depth=16,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

test_pred = model.predict(X_test)
MAE = mean_absolute_error(y_test, test_pred)
R2 = r2_score(y_test, test_pred)

# Anomaly model uses real observations + actual appliance energy.
anomaly_features = feature_cols + [target_col]
anomaly_train = train_df[anomaly_features]
anomaly_model = IsolationForest(
    n_estimators=160,
    contamination=0.06,
    random_state=42
)
anomaly_model.fit(anomaly_train)

# Typical hourly appliance consumption from the real dataset.
hourly_profile = (
    df.groupby("hour")[target_col]
      .mean()
      .reindex(range(24))
      .interpolate()
      .fillna(df[target_col].mean())
)

# Typical weekly pattern (0=Mon ... 6=Sun) from the real dataset.
weekly_profile = (
    df.groupby("dayofweek")[target_col]
      .mean()
      .reindex(range(7))
      .interpolate()
      .fillna(df[target_col].mean())
)
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Real model explainability: which inputs actually drive the RandomForest's
# predictions, straight from the trained model (not hand-picked / fake).
_importances = model.feature_importances_
FEATURE_LABELS = {
    "hour": "Hour of day", "dayofweek": "Day of week", "month": "Month",
    "T1": "Kitchen temp", "RH_1": "Kitchen humidity",
    "T2": "Living temp", "RH_2": "Living humidity",
    "T_out": "Outdoor temp", "RH_out": "Outdoor humidity",
    "Windspeed": "Wind speed", "Visibility": "Visibility", "lights": "Lighting load"
}
feature_importance = sorted(
    [{"feature": FEATURE_LABELS.get(f, f), "importance": round(float(i), 4)}
     for f, i in zip(feature_cols, _importances)],
    key=lambda r: r["importance"], reverse=True
)

def safe_float(data, key, default):
    try:
        return float(data.get(key, default))
    except (TypeError, ValueError):
        return float(default)

def predict_for(hour, dayofweek, month, t1, rh1, t2, rh2, tout, rhout,
                wind, visibility, lights):
    x = pd.DataFrame([{
        "hour": hour, "dayofweek": dayofweek, "month": month,
        "T1": t1, "RH_1": rh1, "T2": t2, "RH_2": rh2,
        "T_out": tout, "RH_out": rhout,
        "Windspeed": wind, "Visibility": visibility, "lights": lights
    }])
    return float(model.predict(x)[0]), x

@app.route("/")
def index():
    defaults = {
        "hour": 19, "dayofweek": 2, "month": 4,
        "t1": 21.0, "rh1": 40.0, "t2": 20.0, "rh2": 40.0,
        "tout": 10.0, "rhout": 60.0, "wind": 4.0,
        "visibility": 30.0, "lights": 20.0
    }
    return render_template(
        "index.html",
        defaults=defaults,
        mae=round(MAE, 1),
        r2=round(R2, 3),
        rows=len(df),
        tariff=TARIFF,
        feature_importance=feature_importance,
        weekly_labels=DAY_NAMES,
        weekly_values=[round(float(v) / 1000, 3) for v in weekly_profile]
    )

@app.route("/predict", methods=["POST"])
def predict():
    data = request.get_json(silent=True) or request.form

    hour = int(safe_float(data, "hour", 19)) % 24
    dayofweek = int(safe_float(data, "dayofweek", 2)) % 7
    month = int(safe_float(data, "month", 4))
    t1 = safe_float(data, "t1", 21)
    rh1 = safe_float(data, "rh1", 40)
    t2 = safe_float(data, "t2", 20)
    rh2 = safe_float(data, "rh2", 40)
    tout = safe_float(data, "tout", 10)
    rhout = safe_float(data, "rhout", 60)
    wind = safe_float(data, "wind", 4)
    visibility = safe_float(data, "visibility", 30)
    lights = safe_float(data, "lights", 20)
    cut_pct = min(max(safe_float(data, "cut_pct", 10), 1), 50)

    predicted_wh, x = predict_for(
        hour, dayofweek, month, t1, rh1, t2, rh2,
        tout, rhout, wind, visibility, lights
    )
    predicted_kwh = predicted_wh / 1000

    # The model's prediction is compared with the real dataset's typical
    # consumption for the selected hour.
    baseline_wh = float(hourly_profile.loc[hour])
    above_baseline = ((predicted_wh - baseline_wh) / baseline_wh) * 100

    # Score the predicted observation against the anomaly model.
    anomaly_row = x.copy()
    anomaly_row[target_col] = predicted_wh
    anomaly_flag = int(anomaly_model.predict(anomaly_row[anomaly_features])[0]) == -1

    unusual = anomaly_flag or above_baseline > 50
    status = "High / Unusual" if unusual else ("Elevated" if above_baseline > 20 else "Normal")

    # Real measured lights are available. The remaining predicted appliance
    # energy is presented as "Other appliances" rather than inventing AC data.
    lights_wh = max(lights, 0)
    other_wh = max(predicted_wh - lights_wh, 0)

    breakdown = {
        "Lights": round(lights_wh / 1000, 3),
        "Other appliances": round(other_wh / 1000, 3)
    }

    # predicted_kwh is energy per 10-minute interval, so scale by the number
    # of intervals in a day (144), not hours in a day (24).
    monthly_kwh = predicted_kwh * INTERVALS_PER_DAY * DAYS_PER_MONTH
    monthly_cost = monthly_kwh * TARIFF

    # A transparent simulation based on the measured lighting input and the
    # user-chosen reduction percentage (default 10%, adjustable 1-50%).
    saving_kwh = (lights_wh / 1000) * (cut_pct / 100) * INTERVALS_PER_DAY * DAYS_PER_MONTH
    saving_rupees = saving_kwh * TARIFF

    if unusual:
        recommendation = (
            "Unusual energy demand detected. Compare the current load with "
            "the household's normal pattern and check high-use appliances."
        )
    elif lights > 30:
        recommendation = (
            "Lighting is relatively high in this scenario. Consider reducing "
            "unnecessary lighting or switching to efficient LED lighting."
        )
    else:
        recommendation = (
            "Consumption is close to the learned baseline. Keep monitoring "
            "hourly patterns to identify future peaks."
        )

    # 24-hour real-data profile scaled to the current environmental scenario.
    trend = []
    for h in range(24):
        p, _ = predict_for(
            h, dayofweek, month, t1, rh1, t2, rh2,
            tout, rhout, wind, visibility, lights
        )
        trend.append(round(p / 1000, 3))

    return {
        "predicted": round(predicted_kwh, 3),
        "baseline": round(baseline_wh / 1000, 3),
        "above_baseline": round(above_baseline, 1),
        "status": status,
        "anomaly": "Unusual" if unusual else "Normal",
        "monthly_cost": round(monthly_cost),
        "breakdown": breakdown,
        "major_contributor": max(breakdown, key=breakdown.get),
        "recommendation": recommendation,
        "saving_kwh": round(saving_kwh, 2),
        "saving_rupees": round(saving_rupees),
        "cut_pct": cut_pct,
        "trend_hours": list(range(24)),
        "trend": trend,
        "mae": round(MAE, 1),
        "r2": round(R2, 3),
        "rows": len(df),
        "data_source": "UCI Appliances Energy Prediction dataset",
        "tariff": TARIFF,
        "feature_importance": feature_importance,
        "weekly_labels": DAY_NAMES,
        "weekly_values": [round(float(v) / 1000, 3) for v in weekly_profile]
    }

if __name__ == "__main__":
    app.run(debug=True)

    

