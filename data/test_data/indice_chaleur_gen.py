#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Générateur de dataset 'Indice de chaleur' (Heat Index) pour 100k lignes.
- Calcule l'indice de chaleur NOAA (Rothfusz) en °C à partir de T(°C) et HR(%).
- Ajoute des features utiles: dew point, vent, wet-bulb approx, WBGT (ombre/soleil),
  catégorie d'alerte, lat/lon réalistes (Afrique de l'Ouest/Centrale), contexte urbain.
- Simule un cycle jour/nuit + saison léger, avec corrélations cohérentes.

Usage :
  python gen_heat_index_100k.py --out heat_index_100k.csv --rows 100000 --seed 42
"""

import argparse
import math
import random
import uuid
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


# -------------------------------
# Paramètres par défaut
# -------------------------------
DEFAULT_ROWS = 100_000
REGIONS = [
    # (pays, code, (lat_min, lat_max), (lon_min, lon_max))
    ("Cameroon", "CM", (2.0, 7.0), (9.0, 15.0)),
    ("Senegal", "SN", (12.0, 16.5), (-17.5, -12.0)),
    ("Cote d'Ivoire", "CI", (4.0, 9.0), (-8.0, -2.5)),
    ("Benin", "BJ", (6.3, 12.0), (1.0, 3.9)),
    ("Togo", "TG", (6.0, 11.0), (0.8, 1.8)),
]

URBAN_RURAL = [("urban", 0.55), ("rural", 0.45)]
SHADE_SUN = [("shade", 0.6), ("sun", 0.4)]  # exposition


# -------------------------------
# Utilitaires physiques / météo
# -------------------------------
def c_to_f(tc: float) -> float:
    return tc * 9.0 / 5.0 + 32.0

def f_to_c(tf: float) -> float:
    return (tf - 32.0) * 5.0 / 9.0

def dew_point_c(t_c: float, rh_pct: float) -> float:
    """Magnus-Tetens (approx) pour point de rosée, T en °C, HR en %."""
    a, b = 17.27, 237.7
    rh = max(1e-6, min(100.0, rh_pct)) / 100.0
    alpha = (a * t_c) / (b + t_c) + math.log(rh)
    td = (b * alpha) / (a - alpha)
    return float(td)

def wet_bulb_c_stull(t_c: float, rh_pct: float) -> float:
    """
    Approximation de Stull (2011) du wet-bulb (°C), erreur typique ±1°C.
    """
    rh = max(1e-6, min(100.0, rh_pct))
    tw = (t_c * math.atan(0.151977 * math.sqrt(rh + 8.313659)) +
          math.atan(t_c + rh) - math.atan(rh - 1.676331) +
          0.00391838 * rh ** 1.5 * math.atan(0.023101 * rh) - 4.686035)
    return float(tw)

def wbgt_shade_c(t_c: float, rh_pct: float) -> float:
    """
    Approx WBGT 'shade' (sans soleil direct) ~ 0.67*Tw + 0.33*T + 0.02
    """
    tw = wet_bulb_c_stull(t_c, rh_pct)
    return float(0.67 * tw + 0.33 * t_c + 0.02)

def wbgt_sun_c(t_c: float, rh_pct: float) -> float:
    """
    Approx WBGT 'sun' : WBGT_shade + pénalité due au rayonnement solaire (≈ +2 à +5°C).
    On ajoute un incrément dépendant du vent (faible vent => pénalité plus forte).
    """
    base = wbgt_shade_c(t_c, rh_pct)
    # pénalité moyenne ~ 3°C
    return float(base + 3.0)

def heat_index_c_noaa(t_c: float, rh_pct: float) -> float:
    """
    Indice de chaleur NOAA (Rothfusz) en °C.
    Implémentation en suivant les recommandations NWS :
      - Si T_F < 80°F, formule simplifiée
      - Sinon, régression + ajustements (RH faible/forte).
    """
    rh = max(1e-6, min(100.0, rh_pct))
    tf = c_to_f(t_c)

    if tf < 80.0:
        # Formule simple (Steadman/NWS) pour conditions modérées
        hi_f = 0.5 * (tf + 61.0 + ((tf - 68.0) * 1.2) + (rh * 0.094))
        hi_f = (hi_f + tf) / 2.0
        return f_to_c(hi_f)

    # Rothfusz regression (T en F, RH en %)
    c1 = -42.379
    c2 = 2.04901523
    c3 = 10.14333127
    c4 = -0.22475541
    c5 = -0.00683783
    c6 = -0.05481717
    c7 = 0.00122874
    c8 = 0.00085282
    c9 = -0.00000199

    hi_f = (c1 + c2*tf + c3*rh + c4*tf*rh + c5*(tf**2) + c6*(rh**2) +
            c7*(tf**2)*rh + c8*tf*(rh**2) + c9*(tf**2)*(rh**2))

    # Ajustements NWS
    if (rh < 13.0) and (80.0 <= tf <= 112.0):
        adj = ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(tf - 95.0)) / 17.0)
        hi_f -= adj
    if (rh > 85.0) and (80.0 <= tf <= 87.0):
        adj = ((rh - 85.0) / 10.0) * ((87.0 - tf) / 5.0)
        hi_f += adj

    return f_to_c(hi_f)

def hi_category(hi_c: float) -> str:
    """
    Catégories NOAA en °C (conversion des seuils °F vers °C).
      - <26.7 : "normal"
      - [26.7, 32.2) : "caution"
      - [32.2, 39.4) : "extreme_caution"
      - [39.4, 51.1) : "danger"
      - >=51.1 : "extreme_danger"
    """
    if hi_c < 26.7:
        return "normal"
    elif hi_c < 32.2:
        return "caution"
    elif hi_c < 39.4:
        return "extreme_caution"
    elif hi_c < 51.1:
        return "danger"
    else:
        return "extreme_danger"


# -------------------------------
# Génération réaliste
# -------------------------------
def sample_region():
    country, code, (la, lb), (lo, up) = random.choice(REGIONS)
    lat = round(random.uniform(la, lb), 5)
    lon = round(random.uniform(lo, up), 5)
    return country, code, lat, lon

def diurnal_temp(base_c: float, hour: int) -> float:
    """
    Cycle jour/nuit : sinusoïde douce, max ~14:30, min ~05:30.
    """
    # Décaler la sinusoïde pour max vers 14h (phase ~ +8h)
    angle = 2 * math.pi * ((hour - 14) % 24) / 24.0
    # amplitude ~ 4 à 7°C selon la journée
    amp = random.uniform(4.0, 7.0)
    return base_c - 0.5 * amp * math.cos(angle)

def simulate_row(anchor_dt: datetime) -> dict:
    # Région & contexte
    country, code, lat, lon = sample_region()
    urban = random.choices([u for u, _ in URBAN_RURAL], weights=[w for _, w in URBAN_RURAL], k=1)[0]
    exposure = random.choices([m for m, _ in SHADE_SUN], weights=[w for _, w in SHADE_SUN], k=1)[0]

    # Heure locale simplifiée (UTC+0 pour dataset; tu peux ajouter TZ si besoin)
    hour = anchor_dt.hour

    # Base saison/jour (tropiques chauds, petite variabilité jour à jour)
    # Température moyenne du jour (à midi à l'ombre)
    daily_mean = random.uniform(27.0, 31.0)  # climat chaud
    base_temp = diurnal_temp(daily_mean, hour)
    # Effet urbain (îlot de chaleur) +0.0–1.2°C
    if urban == "urban":
        base_temp += random.uniform(0.2, 1.2)

    # Humidité relative (plus élevée la nuit)
    rh_base_day = random.uniform(45.0, 70.0)
    rh = rh_base_day + (8.0 if hour < 7 or hour > 19 else 0.0)
    rh += random.uniform(-5.0, 5.0)
    rh = max(10.0, min(100.0, rh))

    # Vent (m/s), plus faible la nuit
    wind = abs(np.random.normal(2.0 if 8 <= hour <= 18 else 1.2, 0.8))
    wind = round(float(max(0.0, min(10.0, wind))), 2)

    # Temp ambiante finale + petite variabilité
    t_air = base_temp + np.random.normal(0.0, 0.6)
    t_air = float(round(max(15.0, min(45.0, t_air)), 1))

    # Calculs thermo
    t_dew = round(dew_point_c(t_air, rh), 1)
    hi_c = round(heat_index_c_noaa(t_air, rh), 1)
    tw_c = round(wet_bulb_c_stull(t_air, rh), 1)
    wbgt_sh = round(wbgt_shade_c(t_air, rh), 1)
    wbgt_sn = round(wbgt_sun_c(t_air, rh), 1)
    cat = hi_category(hi_c)

    # Pénalité soleil : légère hausse de HI proxy si exposition "sun"
    hi_exp = hi_c + (1.0 if exposure == "sun" else 0.0)

    return {
        "row_id": str(uuid.uuid4()),
        "timestamp": anchor_dt.isoformat().replace("+00:00", "Z"),
        "country": country,
        "country_code": code,
        "lat": lat,
        "lon": lon,
        "context": urban,              # urban / rural
        "exposure": exposure,          # shade / sun
        "air_temp_c": t_air,
        "rel_humidity_pct": round(float(rh), 1),
        "wind_mps": wind,
        "dew_point_c": t_dew,
        "heat_index_c": round(hi_exp, 1),
        "hi_category": cat,
        "wet_bulb_c": tw_c,
        "wbgt_shade_c": wbgt_sh,
        "wbgt_sun_c": wbgt_sn,
        # Drapeau d’alerte utile côté app
        "alert_flag": 1 if cat in ("extreme_caution", "danger", "extreme_danger") else 0,
    }


# -------------------------------
# Générateur principal
# -------------------------------
def generate_heat_index_csv(out_path: str, n_rows: int, seed: int):
    random.seed(seed)
    np.random.seed(seed)

    # Fenêtre temporelle: 120 jours récents
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=120)

    rows = []
    # On parcourt des timestamps pseudo-réels: on échantillonne jours/heures
    for _ in range(n_rows):
        day_offset = random.randint(0, (end - start).days)
        hour = random.randint(0, 23)
        minute = random.choice([0, 5, 10, 15, 20, 30, 40, 50])  # granularité irrégulière
        ts = (start + timedelta(days=day_offset)).replace(hour=hour, minute=minute, second=0, microsecond=0, tzinfo=timezone.utc)
        rows.append(simulate_row(ts))

    # Sauvegarde
    df = pd.DataFrame(rows, columns=[
        "row_id","timestamp","country","country_code","lat","lon","context","exposure",
        "air_temp_c","rel_humidity_pct","wind_mps","dew_point_c",
        "heat_index_c","hi_category","wet_bulb_c","wbgt_shade_c","wbgt_sun_c","alert_flag"
    ])
    df.sort_values("timestamp", inplace=True)
    df.to_csv(out_path, index=False, encoding="utf-8")
    print(f"✅ Fichier écrit: {out_path}  ({len(df):,} lignes)")


# -------------------------------
# CLI
# -------------------------------
def main():
    parser = argparse.ArgumentParser(description="Génère un dataset Heat Index (100k lignes).")
    parser.add_argument("--out", type=str, default="heat_index_100k.csv", help="Chemin de sortie du CSV")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="Nombre de lignes à générer")
    parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire")
    args = parser.parse_args()

    generate_heat_index_csv(args.out, args.rows, args.seed)


if __name__ == "__main__":
    main()
