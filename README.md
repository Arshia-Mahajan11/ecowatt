# EcoWatt AI — Real Data Edition (V4, Competition Ready)

A machine-learning energy intelligence dashboard trained on **real, public**
appliance-energy measurements (UCI *Appliances Energy Prediction* dataset —
19,735 observations, 10-minute intervals from a monitored low-energy
building).

## What's new in this build

- **Fixed project layout** — Flask needs `templates/` and `static/`
  folders; the previous drop had `index.html` / `style.css` loose in the
  project root, so the app could not actually run. That's corrected here.
- **Real model explainability** — a live bar chart of the trained Random
  Forest's `feature_importances_`, so the "AI" claim is backed by an
  inspectable, honest artifact instead of a black box.
- **Weekly usage pattern** — a chart of real average appliance energy by
  day of week, straight from the dataset (`groupby("dayofweek")`).
- **Adjustable savings simulator** — a slider (1–50%) instead of a fixed
  10% assumption, so judges/users can see the model react live.
- **Problem / Approach / Impact strip** at the top for pitching (SDG 7 —
  Affordable & Clean Energy, SDG 12 — Responsible Consumption).

## Project structure

```
ecowatt/
├── app.py                # Flask app: trains RF + IsolationForest, serves API
├── data_loader.py        # Downloads + caches the UCI dataset
├── requirements.txt
├── templates/
│   └── index.html        # Dashboard UI (Jinja + vanilla JS + Chart.js)
├── static/
│   └── style.css
└── data/                 # auto-created; holds the cached CSV after first run
```

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**

On first run, `ucimlrepo` downloads the dataset once and caches it at
`data/energydata_complete.csv`; every run after that is instant and works
offline.

## Honesty notes (say these out loud in the demo — judges respect it)

- This is **real public research data**, not a live household feed and not
  Indian household data. Say that up front; it builds credibility instead
  of costing it.
- The ₹7/kWh tariff is illustrative — swap `TARIFF` in `app.py` for a real
  slab rate before presenting numbers as personal estimates.
- The dataset has no dedicated AC-hours column, so AC load is **not**
  fabricated. Only the measured `lights` variable is broken out; the rest
  of the predicted appliance draw is honestly labeled "Other appliances."

## Suggested pitch structure for the judging round

1. **Problem** (10s): people don't know where their electricity goes or
   when it turns unusual until the bill arrives.
2. **Live demo**: adjust the control panel, hit Run, walk through the KPI
   cards → 24h forecast → anomaly flag → savings slider.
3. **Model transparency**: point at the feature-importance chart — "this
   isn't hardcoded, it's the trained model's own weights" — and the
   R²/MAE numbers on real held-out data.
4. **Path to production**: swap the UCI dataset for a smart-meter feed via
   the same `feature_cols` schema; the model and API don't need to change.

## Source

UCI Machine Learning Repository — Appliances Energy Prediction
DOI: 10.24432/C5VC8G
