import argparse
import csv
import json
import math
import random
import uuid
from datetime import datetime, timedelta, timezone

# ------------------------------
# Générateur de dataset évènementiel "wide CSV"
# ------------------------------

EVENT_TYPES = [
    "crisis.alert.created",
    "crisis.pre_alert",
    "symptom.reported",
    "medication.reminder.sent",
    "medication.reminder.ack",
]

SYMPTOMS = ["pain", "fatigue", "fever", "dizziness", "nausea", "breath_shortness", "chest_pain"]
MEDS = [
    ("Hydroxyurea 500mg", "1 capsule"),
    ("Folic Acid 5mg", "1 tab"),
    ("Penicillin V 250mg", "1 tab"),
    ("Paracetamol 1g", "1 tab"),
    ("Ibuprofen 400mg", "1 tab"),
]
CRISIS_RULES = [
    "R001_Tachy+Hypox",
    "R002_HypoxOnly",
    "R003_TempSpike",
    "R004_LowHydration",
]
PRE_RULES = ["PR001_Trend", "PR002_MultiWeakSignals", "PR003_LowHydration", "PR004_TempDrift"]

HEADERS = [
    # Enveloppe commune
    "event_id","event_ts","event_type","patient_id","producer","app_version",
    "device_id","trace_id","ingest_ts","tenant_id",
    # Signals / Rule / Geo
    "signals_hr_bpm","signals_skin_temp_c","signals_spo2_pct","signals_hydration_score",
    "rule_id","rule_reason_json",
    "geo_lat","geo_lon","geo_accuracy_m",
    # Symptom
    "symptom","intensity_0_10","notes",
    # Medication
    "rx_id","medication_name","dose","schedule_time","taken_flag","ack_time",
]

def rand_uuid():
    return str(uuid.uuid4())

def clip(v, lo, hi):
    return max(lo, min(hi, v))

def rand_time_in_day(dt, hour, jitter_min=10):
    base = dt.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    jitter = timedelta(minutes=random.randint(-jitter_min, jitter_min))
    return base + jitter

def to_iso(dt):
    # ISO 8601 en UTC
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def weighted_choice(pairs):
    # pairs = [(value, weight), ...]
    total = sum(w for _, w in pairs)
    r = random.uniform(0, total)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if r <= acc:
            return v
    return pairs[-1][0]

def generate_patients(n_patients, tenant_id="tenant-1"):
    patients = []
    for i in range(n_patients):
        pid = f"P-{i+1:05d}"
        # Hétérogénéité par patient
        crisis_lambda_week = random.uniform(0.05, 0.6)  # crises/sem en moyenne
        adherence = random.uniform(0.6, 0.9)           # proba d'adhérence médicamenteuse
        n_devices = 1 if random.random() < 0.8 else 2
        devices = [f"BRACELET-{pid}-{j+1}" for j in range(n_devices)]
        app_version = f"{random.randint(1,3)}.{random.randint(0,9)}.{random.randint(0,9)}"
        # 1-3 prescriptions
        n_rx = random.randint(1, 3)
        prescriptions = []
        for j in range(n_rx):
            med, dose = random.choice(MEDS)
            # 1-2 créneaux par jour (08h, 20h typiquement)
            times = sorted(random.sample([8, 9, 19, 20, 21], k=random.randint(1,2)))
            prescriptions.append({
                "rx_id": f"RX-{pid}-{j+1:02d}",
                "medication_name": med,
                "dose": dose,
                "hours": times
            })
        patients.append({
            "patient_id": pid,
            "tenant_id": tenant_id,
            "devices": devices,
            "app_version": app_version,
            "crisis_lambda_week": crisis_lambda_week,
            "adherence": adherence,
            "prescriptions": prescriptions
        })
    return patients

def gen_signals(crisis=False):
    # Valeurs corrélées de façon simple
    if crisis:
        hr = random.gauss(135, 15)
        spo2 = random.gauss(90, 3) - (hr - 120) * 0.03  # légère corrélation négative
        temp = random.gauss(37.2, 0.5)
        hyd = random.gauss(38, 15)
    else:
        hr = random.gauss(85, 15)
        spo2 = random.gauss(97, 1.5) - (hr - 85) * 0.01
        temp = random.gauss(35.0, 1.0)
        hyd = random.gauss(60, 18)
    return (
        round(clip(hr, 45, 190), 1),
        round(clip(temp, 30.0, 40.0), 1),
        round(clip(spo2, 80, 100), 1),
        round(clip(hyd, 0, 100), 1)
    )

def gen_geo():
    # Cameroun approx: lat 2–13, lon 8–16
    lat = random.uniform(2.0, 13.0)
    lon = random.uniform(8.0, 16.0)
    acc = random.choice([15, 20, 30, 50, 80, 120, 200, 500])
    return round(lat, 6), round(lon, 6), acc

def maybe_null(value, p_null):
    return "" if random.random() < p_null else value

def main():
    parser = argparse.ArgumentParser(description="Génère un CSV d'événements cliniques synthétiques (wide format).")
    parser.add_argument("--out", type=str, default="clinical_events.csv", help="Chemin du fichier CSV de sortie")
    parser.add_argument("--patients", type=int, default=250, help="Nombre de patients")
    parser.add_argument("--days", type=int, default=60, help="Horizon temporel en jours")
    parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire pour reproductibilité")
    parser.add_argument("--tzshift_hours", type=int, default=1, help="Décalage local vs UTC (ex: Afrique/Douala ~ UTC+1)")
    args = parser.parse_args()

    random.seed(args.seed)

    start_date = datetime.now(timezone.utc) - timedelta(days=args.days)
    patients = generate_patients(args.patients)

    rows = []
    # Génération jour par jour
    for d in range(args.days):
        day = start_date + timedelta(days=d)
        for P in patients:
            pid = P["patient_id"]
            tenant_id = P["tenant_id"]
            device_id = random.choice(P["devices"])
            app_version = P["app_version"]
            trace_id = rand_uuid()

            # 1) medication.reminder.sent (selon prescriptions)
            for rx in P["prescriptions"]:
                for h in rx["hours"]:
                    sent_ts = rand_time_in_day(day, h - args.tzshift_hours, jitter_min=10)  # converti en UTC approx
                    event_id = rand_uuid()
                    rows.append({
                        "event_id": event_id,
                        "event_ts": to_iso(sent_ts),
                        "event_type": "medication.reminder.sent",
                        "patient_id": pid,
                        "producer": "scheduler",
                        "app_version": app_version,
                        "device_id": device_id,
                        "trace_id": trace_id,
                        "ingest_ts": to_iso(sent_ts + timedelta(seconds=random.randint(1, 120))),
                        "tenant_id": tenant_id,
                        "signals_hr_bpm": "",
                        "signals_skin_temp_c": "",
                        "signals_spo2_pct": "",
                        "signals_hydration_score": "",
                        "rule_id": "",
                        "rule_reason_json": "",
                        "geo_lat": "",
                        "geo_lon": "",
                        "geo_accuracy_m": "",
                        "symptom": "",
                        "intensity_0_10": "",
                        "notes": "",
                        "rx_id": rx["rx_id"],
                        "medication_name": rx["medication_name"],
                        "dose": rx["dose"],
                        "schedule_time": f"{h:02d}:00",
                        "taken_flag": "",
                        "ack_time": "",
                    })

                    # 2) medication.reminder.ack (adhérence par patient)
                    if random.random() < P["adherence"]:
                        delay_min = int(abs(random.gauss(12, 15)))  # mode ~0-30 min
                        ack_ts = sent_ts + timedelta(minutes=delay_min)
                        rows.append({
                            "event_id": rand_uuid(),
                            "event_ts": to_iso(ack_ts),
                            "event_type": "medication.reminder.ack",
                            "patient_id": pid,
                            "producer": "mobile.app",
                            "app_version": app_version,
                            "device_id": device_id,
                            "trace_id": trace_id,
                            "ingest_ts": to_iso(ack_ts + timedelta(seconds=random.randint(1, 120))),
                            "tenant_id": tenant_id,
                            "signals_hr_bpm": "",
                            "signals_skin_temp_c": "",
                            "signals_spo2_pct": "",
                            "signals_hydration_score": "",
                            "rule_id": "",
                            "rule_reason_json": "",
                            "geo_lat": "",
                            "geo_lon": "",
                            "geo_accuracy_m": "",
                            "symptom": "",
                            "intensity_0_10": "",
                            "notes": "",
                            "rx_id": rx["rx_id"],
                            "medication_name": rx["medication_name"],
                            "dose": rx["dose"],
                            "schedule_time": f"{h:02d}:00",
                            "taken_flag": "true",
                            "ack_time": to_iso(ack_ts),
                        })
                    else:
                        # Optionnel: un ack manqué (false) de temps en temps
                        if random.random() < 0.15:
                            miss_ts = sent_ts + timedelta(hours=random.uniform(1, 6))
                            rows.append({
                                "event_id": rand_uuid(),
                                "event_ts": to_iso(miss_ts),
                                "event_type": "medication.reminder.ack",
                                "patient_id": pid,
                                "producer": "mobile.app",
                                "app_version": app_version,
                                "device_id": device_id,
                                "trace_id": trace_id,
                                "ingest_ts": to_iso(miss_ts + timedelta(seconds=random.randint(1, 120))),
                                "tenant_id": tenant_id,
                                "signals_hr_bpm": "",
                                "signals_skin_temp_c": "",
                                "signals_spo2_pct": "",
                                "signals_hydration_score": "",
                                "rule_id": "",
                                "rule_reason_json": "",
                                "geo_lat": "",
                                "geo_lon": "",
                                "geo_accuracy_m": "",
                                "symptom": "",
                                "intensity_0_10": "",
                                "notes": "",
                                "rx_id": rx["rx_id"],
                                "medication_name": rx["medication_name"],
                                "dose": rx["dose"],
                                "schedule_time": f"{h:02d}:00",
                                "taken_flag": "false",
                                "ack_time": to_iso(miss_ts),
                            })

            # 3) crises (Poisson hebdo -> approx quotidienne)
            lam_day = P["crisis_lambda_week"] / 7.0
            n_crises = 1 if random.random() < lam_day else 0  # rare -> 0/1
            for _ in range(n_crises):
                h = random.randint(0, 23)
                crisis_ts = rand_time_in_day(day, h, jitter_min=20)

                # pre_alert avant 15–120 min (60%)
                if random.random() < 0.6:
                    pre_ts = crisis_ts - timedelta(minutes=random.randint(15, 120))
                    hr, t, sp, hyd = gen_signals(crisis=False)
                    rows.append({
                        "event_id": rand_uuid(),
                        "event_ts": to_iso(pre_ts),
                        "event_type": "crisis.pre_alert",
                        "patient_id": pid,
                        "producer": "iot.gateway",
                        "app_version": app_version,
                        "device_id": device_id,
                        "trace_id": trace_id,
                        "ingest_ts": to_iso(pre_ts + timedelta(seconds=random.randint(1, 180))),
                        "tenant_id": tenant_id,
                        "signals_hr_bpm": str(hr) if random.random() < 0.9 else "",
                        "signals_skin_temp_c": str(t) if random.random() < 0.6 else "",
                        "signals_spo2_pct": str(sp) if random.random() < 0.8 else "",
                        "signals_hydration_score": str(hyd) if random.random() < 0.5 else "",
                        "rule_id": random.choice(PRE_RULES),
                        "rule_reason_json": json.dumps(["trend anomaly","multi weak signals"]),
                        "geo_lat": "",
                        "geo_lon": "",
                        "geo_accuracy_m": "",
                        "symptom": "",
                        "intensity_0_10": "",
                        "notes": "",
                        "rx_id": "",
                        "medication_name": "",
                        "dose": "",
                        "schedule_time": "",
                        "taken_flag": "",
                        "ack_time": "",
                    })

                # crisis.alert.created
                hr, t, sp, hyd = gen_signals(crisis=True)
                lat, lon, acc = gen_geo()
                rows.append({
                    "event_id": rand_uuid(),
                    "event_ts": to_iso(crisis_ts),
                    "event_type": "crisis.alert.created",
                    "patient_id": pid,
                    "producer": "iot.gateway",
                    "app_version": app_version,
                    "device_id": device_id,
                    "trace_id": trace_id,
                    "ingest_ts": to_iso(crisis_ts + timedelta(seconds=random.randint(1, 180))),
                    "tenant_id": tenant_id,
                    "signals_hr_bpm": hr,
                    "signals_skin_temp_c": t,
                    "signals_spo2_pct": sp,
                    "signals_hydration_score": hyd,
                    "rule_id": random.choice(CRISIS_RULES),
                    "rule_reason_json": json.dumps(["hr_bpm>120 for 5m","spo2_pct<92"]),
                    "geo_lat": lat,
                    "geo_lon": lon,
                    "geo_accuracy_m": acc,
                    "symptom": "",
                    "intensity_0_10": "",
                    "notes": "",
                    "rx_id": "",
                    "medication_name": "",
                    "dose": "",
                    "schedule_time": "",
                    "taken_flag": "",
                    "ack_time": "",
                })

                # symptom autour de la crise (70%)
                if random.random() < 0.7:
                    offset_min = random.randint(-120, 120)
                    symp_ts = crisis_ts + timedelta(minutes=offset_min)
                    rows.append({
                        "event_id": rand_uuid(),
                        "event_ts": to_iso(symp_ts),
                        "event_type": "symptom.reported",
                        "patient_id": pid,
                        "producer": "mobile.app",
                        "app_version": app_version,
                        "device_id": device_id,
                        "trace_id": trace_id,
                        "ingest_ts": to_iso(symp_ts + timedelta(seconds=random.randint(1, 120))),
                        "tenant_id": tenant_id,
                        "signals_hr_bpm": "",
                        "signals_skin_temp_c": "",
                        "signals_spo2_pct": "",
                        "signals_hydration_score": "",
                        "rule_id": "",
                        "rule_reason_json": "",
                        "geo_lat": "",
                        "geo_lon": "",
                        "geo_accuracy_m": "",
                        "symptom": random.choice(SYMPTOMS),
                        "intensity_0_10": round(clip(random.gauss(5.5, 2.5), 0, 10), 1),
                        "notes": "auto-report",
                        "rx_id": "",
                        "medication_name": "",
                        "dose": "",
                        "schedule_time": "",
                        "taken_flag": "",
                        "ack_time": "",
                    })

            # 4) symptômes indépendants (faible)
            if random.random() < 0.15:
                h = random.randint(7, 22)
                ts = rand_time_in_day(day, h, jitter_min=45)
                rows.append({
                    "event_id": rand_uuid(),
                    "event_ts": to_iso(ts),
                    "event_type": "symptom.reported",
                    "patient_id": pid,
                    "producer": "mobile.app",
                    "app_version": app_version,
                    "device_id": device_id,
                    "trace_id": trace_id,
                    "ingest_ts": to_iso(ts + timedelta(seconds=random.randint(1, 120))),
                    "tenant_id": tenant_id,
                    "signals_hr_bpm": "",
                    "signals_skin_temp_c": "",
                    "signals_spo2_pct": "",
                    "signals_hydration_score": "",
                    "rule_id": "",
                    "rule_reason_json": "",
                    "geo_lat": "",
                    "geo_lon": "",
                    "geo_accuracy_m": "",
                    "symptom": random.choice(SYMPTOMS),
                    "intensity_0_10": round(clip(random.gauss(4.0, 2.0), 0, 10), 1),
                    "notes": "",
                    "rx_id": "",
                    "medication_name": "",
                    "dose": "",
                    "schedule_time": "",
                    "taken_flag": "",
                    "ack_time": "",
                })

    # Trier par timestamp pour un CSV plus lisible
    rows.sort(key=lambda r: r["event_ts"])

    # Écriture CSV
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        for r in rows:
            # stringify tout sauf valeurs numériques déjà prêtes
            out = {}
            for k in HEADERS:
                v = r.get(k, "")
                if isinstance(v, float):
                    out[k] = f"{v:.1f}"
                else:
                    out[k] = v
            writer.writerow(out)

    print(f"OK - {len(rows)} lignes écrites dans {args.out}")

if __name__ == "__main__":
    main()
