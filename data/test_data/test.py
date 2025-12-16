import uuid, random, json
from datetime import datetime, timedelta, timezone
import pandas as pd
import numpy as np

# ------------------------------
# Paramètres de génération
# ------------------------------
OUT_PATH = "clinical_events_100k.csv"
N_EVENTS_TARGET = 100_000
N_PATIENTS = 1000
DAYS = 90
TZSHIFT = 1  # Afrique/Douala ~ UTC+1

random.seed(7)
np.random.seed(7)

EVENT_TYPES = [
    "crisis.alert.created",
    "crisis.pre_alert",
    "symptom.reported",
    "medication.reminder.sent",
    "medication.reminder.ack",
]
SYMPTOMS = ["pain","fatigue","fever","dizziness","nausea","breath_shortness","chest_pain"]
MEDS = ["Hydroxyurea 500mg","Folic Acid 5mg","Penicillin V 250mg","Paracetamol 1g","Ibuprofen 400mg"]
DOSES = ["1 capsule","1 tab","500 mg","2 tabs"]

HEADERS = [
    "event_id","event_ts","event_type","patient_id","producer","app_version",
    "device_id","trace_id","ingest_ts","tenant_id",
    "signals_hr_bpm","signals_skin_temp_c","signals_spo2_pct","signals_hydration_score",
    "rule_id","rule_reason_json",
    "geo_lat","geo_lon","geo_accuracy_m",
    "symptom","intensity_0_10","notes",
    "rx_id","medication_name","dose","schedule_time","taken_flag","ack_time",
]

# ------------------------------
# Fonctions utilitaires
# ------------------------------
def uuid4(): return str(uuid.uuid4())
def to_iso(dt): return dt.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
def clip(v,lo,hi): return max(lo, min(hi, v))

def gen_patients(n=1000):
    pts = []
    for i in range(n):
        pid = f"P-{i+1:05d}"
        adherence = random.uniform(0.6,0.9)
        crisis_lambda_week = random.uniform(0.05,0.5)
        devices = [f"BRACELET-{pid}-1"] + ([f"BRACELET-{pid}-2"] if random.random()<0.15 else [])
        app_version = f"{random.randint(1,3)}.{random.randint(0,9)}.{random.randint(0,9)}"
        n_rx = random.randint(1,3)
        rx = []
        for j in range(n_rx):
            rx.append({
                "rx_id": f"RX-{pid}-{j+1:02d}",
                "medication_name": random.choice(MEDS),
                "dose": random.choice(DOSES),
                "hours": sorted(random.sample([8,9,19,20,21], k=random.randint(1,2)))
            })
        pts.append({
            "patient_id": pid, "tenant_id": "tenant-1",
            "devices": devices, "app_version": app_version,
            "adherence": adherence, "crisis_lambda_week": crisis_lambda_week,
            "prescriptions": rx
        })
    return pts

def gen_signals(crisis=False):
    if crisis:
        hr = np.random.normal(135,15)
        spo2 = np.random.normal(90,3) - (hr-120)*0.03
        temp = np.random.normal(37.2,0.6)
        hyd = np.random.normal(38,15)
    else:
        hr = np.random.normal(85,15)
        spo2 = np.random.normal(97,1.5) - (hr-85)*0.01
        temp = np.random.normal(35.0,1.0)
        hyd = np.random.normal(60,18)
    return round(clip(hr,45,190),1), round(clip(temp,30,40),1), round(clip(spo2,80,100),1), round(clip(hyd,0,100),1)

def gen_geo():
    lat = round(random.uniform(2.0,13.0),6)
    lon = round(random.uniform(8.0,16.0),6)
    acc = random.choice([15,20,30,50,80,120,200,500])
    return lat,lon,acc

def rand_time_in_day(day_utc, hour_local, tzshift=1, jitter=10):
    base_local = day_utc.replace(hour=hour_local, minute=0, second=0, microsecond=0)
    base_utc = base_local - timedelta(hours=tzshift)
    return base_utc + timedelta(minutes=random.randint(-jitter,jitter))

# ------------------------------
# Génération principale
# ------------------------------
def generate_events():
    end_dt = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=DAYS)
    patients = gen_patients(N_PATIENTS)

    rows, count = [], 0

    for d in range(DAYS):
        if count >= N_EVENTS_TARGET: break
        day_utc = (start_dt + timedelta(days=d)).replace(tzinfo=timezone.utc)
        daily_pts = random.sample(patients, k=min(len(patients), max(60, int(len(patients)*0.35))))
        for P in daily_pts:
            if count >= N_EVENTS_TARGET: break
            pid, tenant, device, appv, trace = P["patient_id"], P["tenant_id"], random.choice(P["devices"]), P["app_version"], uuid4()

            # ---------------- Medication sent & ack
            for rx in P["prescriptions"]:
                for hh in rx["hours"]:
                    ts = rand_time_in_day(day_utc, hh, tzshift=TZSHIFT, jitter=10)
                    row_sent = {
                        "event_id": uuid4(), "event_ts": to_iso(ts), "event_type":"medication.reminder.sent",
                        "patient_id": pid, "producer":"scheduler", "app_version": appv,
                        "device_id": device, "trace_id": trace, "ingest_ts": to_iso(ts+timedelta(seconds=random.randint(1,180))),
                        "tenant_id": tenant, "signals_hr_bpm":"", "signals_skin_temp_c":"", "signals_spo2_pct":"",
                        "signals_hydration_score":"", "rule_id":"", "rule_reason_json":"",
                        "geo_lat":"", "geo_lon":"", "geo_accuracy_m":"",
                        "symptom":"", "intensity_0_10":"", "notes":"",
                        "rx_id": rx["rx_id"], "medication_name": rx["medication_name"], "dose": rx["dose"],
                        "schedule_time": f"{int(hh):02d}:00", "taken_flag":"", "ack_time":""
                    }
                    rows.append(row_sent); count+=1
                    if count>=N_EVENTS_TARGET: break

                    # ack
                    if random.random() < P["adherence"] and count < N_EVENTS_TARGET:
                        delay = max(0,int(abs(np.random.normal(12,15))))
                        ack_ts = ts + timedelta(minutes=delay)
                        row_ack = row_sent.copy()
                        row_ack.update({
                            "event_id": uuid4(), "event_ts": to_iso(ack_ts), "event_type":"medication.reminder.ack",
                            "producer":"mobile.app", "ingest_ts": to_iso(ack_ts+timedelta(seconds=random.randint(1,180))),
                            "taken_flag":"true", "ack_time": to_iso(ack_ts)
                        })
                        rows.append(row_ack); count+=1

            # ---------------- Crisis
            lam_day = P["crisis_lambda_week"]/7.0
            if random.random() < lam_day and count < N_EVENTS_TARGET:
                crisis_ts = rand_time_in_day(day_utc, random.randint(0,23), tzshift=TZSHIFT, jitter=20)
                # pre-alert
                if random.random() < 0.6 and count < N_EVENTS_TARGET:
                    pre_ts = crisis_ts - timedelta(minutes=random.randint(15,120))
                    hr,temp,spo2,hyd = gen_signals(crisis=False)
                    rows.append({
                        "event_id": uuid4(), "event_ts": to_iso(pre_ts), "event_type":"crisis.pre_alert",
                        "patient_id": pid, "producer":"iot.gateway", "app_version": appv, "device_id": device,
                        "trace_id": trace, "ingest_ts": to_iso(pre_ts+timedelta(seconds=random.randint(1,180))),
                        "tenant_id": tenant, "signals_hr_bpm": hr, "signals_skin_temp_c": temp,
                        "signals_spo2_pct": spo2, "signals_hydration_score": hyd,
                        "rule_id": random.choice(["PR001_Trend","PR002_MultiWeakSignals","PR003_LowHydration","PR004_TempDrift"]),
                        "rule_reason_json": json.dumps(["trend anomaly","multi weak signals"]),
                        "geo_lat":"", "geo_lon":"", "geo_accuracy_m":"",
                        "symptom":"", "intensity_0_10":"", "notes":"",
                        "rx_id":"", "medication_name":"", "dose":"", "schedule_time":"",
                        "taken_flag":"", "ack_time":""
                    }); count+=1

                # crisis.alert.created
                hr,temp,spo2,hyd = gen_signals(crisis=True)
                lat,lon,acc = gen_geo()
                rows.append({
                    "event_id": uuid4(), "event_ts": to_iso(crisis_ts), "event_type":"crisis.alert.created",
                    "patient_id": pid, "producer":"iot.gateway", "app_version": appv, "device_id": device,
                    "trace_id": trace, "ingest_ts": to_iso(crisis_ts+timedelta(seconds=random.randint(1,180))),
                    "tenant_id": tenant, "signals_hr_bpm": hr, "signals_skin_temp_c": temp,
                    "signals_spo2_pct": spo2, "signals_hydration_score": hyd,
                    "rule_id": random.choice(["R001_Tachy+Hypox","R002_HypoxOnly","R003_TempSpike","R004_LowHydration"]),
                    "rule_reason_json": json.dumps(["hr_bpm>120 for 5m","spo2_pct<92"]),
                    "geo_lat": lat, "geo_lon": lon, "geo_accuracy_m": acc,
                    "symptom":"", "intensity_0_10":"", "notes":"",
                    "rx_id":"", "medication_name":"", "dose":"", "schedule_time":"",
                    "taken_flag":"", "ack_time":""
                }); count+=1

    # Sort + export
    rows.sort(key=lambda r: r["event_ts"])
    pd.DataFrame(rows, columns=HEADERS).to_csv(OUT_PATH, index=False, encoding="utf-8")
    print(f"✅ Dataset généré : {OUT_PATH} ({len(rows)} lignes)")

if __name__ == "__main__":
    generate_events()
