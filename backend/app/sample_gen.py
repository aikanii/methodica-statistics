from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .config import SAMPLE_DATA


def write_samples():
    SAMPLE_DATA.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)

    n = 720
    dates = pd.date_range("2024-01-01", periods=n // 3, freq="D")
    rows = []
    for loc, base, noise, traffic_mu in [
        ("Urban", 38, 12, 70),
        ("Rural", 18, 6, 18),
        ("Suburban", 27, 9, 42),
    ]:
        for i, d in enumerate(dates):
            season = {12: "Winter", 1: "Winter", 2: "Winter", 3: "Spring", 4: "Spring", 5: "Spring", 6: "Summer", 7: "Summer", 8: "Summer"}.get(
                d.month, "Autumn"
            )
            temp = {"Winter": 22, "Spring": 27, "Summer": 31, "Autumn": 28}[season] + rng.normal(0, 2.2)
            hum = np.clip(78 - 0.6 * (temp - 26) + rng.normal(0, 8), 30, 99)
            wind = np.clip(rng.gamma(2.2, 1.4), 0.2, 12)
            traffic = np.clip(rng.normal(traffic_mu, 12), 0, 100)
            pm25 = np.clip(base + 0.45 * (traffic - 40) / 10 + 0.35 * (temp - 26) - 0.8 * wind + rng.normal(0, noise), 2, 180)
            pm10 = np.clip(pm25 * rng.uniform(1.4, 2.1) + rng.normal(0, 5), 5, 300)
            rain = max(0, rng.normal(-1, 6))
            rows.append(
                {
                    "date": d.strftime("%Y-%m-%d"),
                    "location": loc,
                    "season": season,
                    "pm25": round(float(pm25), 2),
                    "pm10": round(float(pm10), 2),
                    "temperature": round(float(temp), 2),
                    "humidity": round(float(hum), 1),
                    "wind_speed": round(float(wind), 2),
                    "rainfall": round(float(rain), 2),
                    "traffic_index": round(float(traffic), 1),
                    "station_id": f"{loc[:3].upper()}-{100 + (i % 4)}",
                }
            )
    air = pd.DataFrame(rows)
    # inject quality issues
    air.loc[3:6, "pm25"] = np.nan
    air.loc[20, "humidity"] = 140  # impossible
    air.loc[40, "pm25"] = -5  # impossible
    air.loc[50, "location"] = "urban"  # case variant
    air.loc[51, "location"] = "Urban "
    air = pd.concat([air, air.iloc[[10, 11]]], ignore_index=True)
    air.to_csv(SAMPLE_DATA / "air_quality.csv", index=False)

    n = 260
    treat = rng.choice(["Control", "Intervention"], size=n)
    age = rng.integers(34, 78, size=n)
    sex = rng.choice(["Female", "Male"], size=n)
    bio = rng.normal(12, 3.5, size=n) + (treat == "Intervention") * 0.4
    baseline = rng.normal(48, 10, size=n)
    follow = baseline + rng.normal(1.5, 6, size=n) + (treat == "Intervention") * 4.8
    # survival: intervention longer
    log_t = rng.normal(4.1, 0.55, size=n) + (treat == "Intervention") * 0.35 - 0.01 * (age - 55)
    t = np.exp(log_t)
    # administrative censor at 180
    event = (t <= 180).astype(int)
    t = np.minimum(t, 180)
    clin = pd.DataFrame(
        {
            "patient_id": [f"P{i:04d}" for i in range(n)],
            "treatment": treat,
            "age": age,
            "sex": sex,
            "biomarker": np.round(bio, 2),
            "baseline_score": np.round(baseline, 1),
            "followup_score": np.round(follow, 1),
            "survival_days": np.round(t, 1),
            "event": event,
        }
    )
    clin.to_csv(SAMPLE_DATA / "clinical_trial.csv", index=False)

    n = 180
    latent = rng.normal(0, 1, size=n)
    items = {}
    for i in range(1, 9):
        items[f"item_{i}"] = np.clip(np.round(3.5 + 0.7 * latent + rng.normal(0, 0.7, size=n)), 1, 5).astype(int)
    items["group"] = rng.choice(["A", "B", "C"], size=n)
    pd.DataFrame(items).to_csv(SAMPLE_DATA / "survey_items.csv", index=False)
