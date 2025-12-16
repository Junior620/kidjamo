# 📊 Semaine 1: Monitoring et Alertes Avancées (26 Août - 1 Septembre)

## 🎯 Objectif de la Semaine
Développer un système d'alertes composées et créer un dashboard PowerBI minimaliste pour le monitoring temps réel du pipeline IoT médical.

---

## 📅 **JOUR 1-2: Système d'Alertes Composées**

### **Étape A: Analyse des Alertes Existantes** (2h)

#### Structure Actuelle des Données
D'après l'analyse du système, nous avons actuellement :

**Table `measurements`:**
- `patient_id` (TEXT)
- `device_id` (TEXT) 
- `recorded_at` (TIMESTAMP)
- `freq_card` (INTEGER) - Fréquence cardiaque
- `freq_resp` (INTEGER) - Fréquence respiratoire
- `spo2_pct` (DOUBLE PRECISION) - Saturation oxygène
- `temp_corp` (DOUBLE PRECISION) - Température corporelle
- `temp_ambiante` (DOUBLE PRECISION) - Température ambiante
- `pct_hydratation` (DOUBLE PRECISION) - Pourcentage hydratation
- `activity` (INTEGER) - Niveau d'activité
- `heat_index` (DOUBLE PRECISION) - Index de chaleur
- `quality_flag` (TEXT) - Qualité signal

**Table `alerts`:**
- `id` (SERIAL PRIMARY KEY)
- `patient_id` (TEXT)
- `alert_type` (TEXT)
- `severity` (TEXT)
- `title` (TEXT)
- `message` (TEXT)
- `vitals_snapshot` (TEXT/JSON)
- `created_at` (TIMESTAMP)
- `ack_deadline` (TIMESTAMP)

### **Étape B: Créer le Moteur d'Alertes Composées** (6h)

#### 1. Structure des Fichiers à Créer
```bash
mkdir -p alerting/engines/
mkdir -p alerting/rules/
mkdir -p alerting/notifications/
```

#### 2. Fichier: `alerting/engines/composite_alerts.py`

**Alertes Composées à Implémenter:**

1. **Crise Drépanocytaire** (Priorité CRITIQUE)
   - SpO2 < 88% ET Température ≥ 38°C
   - Durée: Maintenue pendant 3 minutes
   - Action: Notification immédiate + escalade

2. **Détresse Cardiaque** (Priorité HAUTE)
   - FC > 100 bpm ET SpO2 < 90%
   - Durée: 2 mesures consécutives
   - Action: Alerte cardiaque

3. **Déshydratation Sévère** (Priorité MOYENNE)
   - Hydratation < 60% ET Activité < 10
   - Durée: 30 minutes
   - Action: Recommandation hydratation

4. **Hyperthermie d'Effort** (Priorité MOYENNE)
   - Température > 39°C ET Activit�� > 80
   - Heat Index > 40
   - Action: Repos immédiat

#### 3. Code de Base à Implémenter

```python
# alerting/engines/composite_alerts.py
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

@dataclass
class AlertRule:
    name: str
    conditions: List[Dict]
    duration_minutes: int
    severity: str
    action: str
    description: str

class CompositeAlertEngine:
    def __init__(self):
        self.rules = self._load_medical_rules()
        self.patient_history = {}  # Cache des dernières mesures
    
    def _load_medical_rules(self) -> List[AlertRule]:
        """Charge les règles médicales définies"""
        return [
            AlertRule(
                name="crise_drepanocytaire",
                conditions=[
                    {"field": "spo2_pct", "operator": "<", "value": 88.0},
                    {"field": "temp_corp", "operator": ">=", "value": 38.0}
                ],
                duration_minutes=3,
                severity="CRITICAL",
                action="immediate_notification",
                description="Possible crise drépanocytaire - Intervention urgente requise"
            ),
            # ... autres règles
        ]
    
    def evaluate_measurements(self, patient_id: str, measurements: Dict) -> List[Dict]:
        """Évalue les mesures contre toutes les règles composées"""
        triggered_alerts = []
        
        # Mise à jour historique patient
        self._update_patient_history(patient_id, measurements)
        
        # Évaluation de chaque règle
        for rule in self.rules:
            if self._evaluate_rule(patient_id, rule):
                alert = self._create_composite_alert(patient_id, rule, measurements)
                triggered_alerts.append(alert)
        
        return triggered_alerts
```

### **Étape C: Système de Notifications** (4h)

#### 1. Fichier: `alerting/notifications/notification_service.py`

**Types de Notifications à Implémenter:**
- Email (simulation locale avec fichiers)
- SMS (simulation avec logs)
- Dashboard Push (WebSocket local)
- Escalade automatique (si non accusé réception)

```python
# alerting/notifications/notification_service.py
class NotificationService:
    def __init__(self):
        self.channels = {
            "email": self._send_email_simulation,
            "sms": self._send_sms_simulation,
            "dashboard": self._send_dashboard_push,
            "escalation": self._handle_escalation
        }
    
    async def send_alert(self, alert: Dict, channels: List[str]):
        """Envoie une alerte via les canaux spécifiés"""
        for channel in channels:
            if channel in self.channels:
                await self.channels[channel](alert)
```

---

## 📅 **JOUR 3-4: Dashboard PowerBI Local**

### **Étape D: Préparation des Données pour PowerBI** (4h)

#### 1. Source de Données: Vue PostgreSQL Agrégée

**Créer des vues SQL optimisées pour PowerBI:**

```sql
-- Vue: measurements_dashboard
CREATE OR REPLACE VIEW measurements_dashboard AS
SELECT 
    patient_id,
    device_id,
    recorded_at,
    DATE_TRUNC('minute', recorded_at) as minute_bucket,
    DATE_TRUNC('hour', recorded_at) as hour_bucket,
    freq_card,
    freq_resp,
    spo2_pct,
    temp_corp,
    pct_hydratation,
    activity,
    quality_flag,
    -- KPIs calculés
    CASE 
        WHEN spo2_pct < 88 THEN 'CRITIQUE'
        WHEN spo2_pct < 90 THEN 'BAS'
        WHEN spo2_pct >= 95 THEN 'NORMAL'
        ELSE 'MODERE'
    END as spo2_status,
    CASE 
        WHEN temp_corp >= 38.5 THEN 'FIEVRE_HAUTE'
        WHEN temp_corp >= 38.0 THEN 'FIEVRE'
        WHEN temp_corp <= 36.0 THEN 'HYPOTHERMIE'
        ELSE 'NORMAL'
    END as temp_status,
    CASE 
        WHEN freq_card > 180 THEN 'TACHYCARDIE_SEVERE'
        WHEN freq_card > 150 THEN 'TACHYCARDIE'
        WHEN freq_card < 50 THEN 'BRADYCARDIE'
        ELSE 'NORMAL'
    END as cardiac_status
FROM measurements
WHERE recorded_at >= NOW() - INTERVAL '24 hours';

-- Vue: alerts_dashboard  
CREATE OR REPLACE VIEW alerts_dashboard AS
SELECT 
    id,
    patient_id,
    alert_type,
    severity,
    title,
    message,
    created_at,
    DATE_TRUNC('hour', created_at) as hour_bucket,
    ack_deadline,
    CASE 
        WHEN ack_deadline IS NULL THEN 'PENDING'
        WHEN ack_deadline < NOW() THEN 'OVERDUE'
        ELSE 'ACKNOWLEDGED'
    END as ack_status,
    -- Temps de réponse
    EXTRACT(EPOCH FROM (COALESCE(ack_deadline, NOW()) - created_at))/60 as response_time_minutes
FROM alerts
WHERE created_at >= NOW() - INTERVAL '7 days';

-- Vue: patients_status (temps réel)
CREATE OR REPLACE VIEW patients_status AS
SELECT 
    patient_id,
    COUNT(*) as total_measurements,
    MAX(recorded_at) as last_measurement,
    AVG(spo2_pct) as avg_spo2,
    AVG(freq_card) as avg_heart_rate,
    AVG(temp_corp) as avg_temperature,
    COUNT(CASE WHEN spo2_pct < 88 THEN 1 END) as critical_spo2_count,
    COUNT(CASE WHEN temp_corp >= 38 THEN 1 END) as fever_count,
    -- Status global patient
    CASE 
        WHEN MAX(recorded_at) < NOW() - INTERVAL '10 minutes' THEN 'DISCONNECTED'
        WHEN COUNT(CASE WHEN spo2_pct < 88 THEN 1 END) > 0 THEN 'CRITICAL'
        WHEN COUNT(CASE WHEN temp_corp >= 38 THEN 1 END) > 0 THEN 'WARNING'
        ELSE 'STABLE'
    END as patient_status
FROM measurements 
WHERE recorded_at >= NOW() - INTERVAL '2 hours'
GROUP BY patient_id;
```

#### 2. API Endpoint pour PowerBI

**Fichier: `api/powerbi_endpoints.py`**

```python
@app.get("/powerbi/measurements")
async def get_measurements_for_powerbi():
    """Endpoint optimisé pour PowerBI - Données des 24 dernières heures"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM measurements_dashboard ORDER BY recorded_at DESC LIMIT 10000")
        data = cur.fetchall()
        columns = [desc[0] for desc in cur.description]
    
    return {
        "data": [dict(zip(columns, row)) for row in data],
        "last_updated": datetime.now().isoformat(),
        "record_count": len(data)
    }

@app.get("/powerbi/alerts")
async def get_alerts_for_powerbi():
    """Endpoint pour alertes PowerBI"""
    # Similaire pour les alertes
    
@app.get("/powerbi/kpis")
async def get_kpis_for_powerbi():
    """KPIs temps réel pour PowerBI"""
    conn = get_db_connection()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 
                COUNT(DISTINCT patient_id) as active_patients,
                COUNT(*) as total_measurements_24h,
                COUNT(CASE WHEN spo2_pct < 88 THEN 1 END) as critical_alerts_24h,
                AVG(spo2_pct) as avg_spo2_24h,
                AVG(freq_card) as avg_heart_rate_24h,
                AVG(temp_corp) as avg_temperature_24h
            FROM measurements 
            WHERE recorded_at >= NOW() - INTERVAL '24 hours'
        """)
        kpis = cur.fetchone()
    
    return dict(zip([desc[0] for desc in cur.description], kpis))
```

### **Étape E: Spécifications Dashboard PowerBI Minimaliste** (6h)

#### **🎯 KPIs Principaux (Cartes)**

1. **Patients Actifs** 
   - Nombre de patients connectés (dernières 10 min)
   - Code couleur: Vert > 5, Orange 2-5, Rouge < 2

2. **Alertes Critiques Actives**
   - Nombre d'alertes non accusées
   - Code couleur: Rouge > 5, Orange 1-5, Vert = 0

3. **SpO2 Moyen (24h)**
   - Moyenne SpO2 toutes mesures
   - Code couleur: Vert �� 95%, Orange 90-94%, Rouge < 90%

4. **Fréquence Cardiaque Moyenne**
   - Moyenne FC 24h
   - Code couleur: Vert 60-100, Orange hors plage, Rouge > 180

5. **Température Corporelle Moyenne**
   - Moyenne température corporelle 24h
   - Code couleur: Vert 36-37.5°C, Orange 37.5-38°C, Rouge > 38°C

6. **Température Ambiante Moyenne**
   - Moyenne température environnement 24h
   - Code couleur: Vert 18-25°C, Orange 25-30°C, Rouge > 30°C ou < 15°C

7. **Hydratation Moyenne**
   - Moyenne pourcentage hydratation 24h
   - Code couleur: Vert ≥ 70%, Orange 60-69%, Rouge < 60%

8. **Niveau d'Activité Moyen**
   - Moyenne activité patients 24h
   - Code couleur: Vert 30-70, Orange 10-29 ou 71-90, Rouge < 10 ou > 90

9. **Temps de Réponse Alertes**
   - Temps moyen de réponse aux alertes (minutes)
   - Code couleur: Vert < 5 min, Orange 5-15 min, Rouge > 15 min

#### **📊 Graphiques Essentiels (Chaque Mesure Séparée)**

1. **Saturation Oxygène (SpO2) - Ligne Temps Réel**
   - Axe X: Temps (dernières 4 heures, refresh 1 min)
   - Axe Y: SpO2 (%) - Échelle 70-100%
   - Lignes de seuil: Rouge < 88%, Orange < 90%, Vert ≥ 95%
   - Multiple patients en couleurs différentes

2. **Fréquence Cardiaque - Ligne Temps Réel**
   - Axe X: Temps (dernières 4 heures)
   - Axe Y: FC (bpm) - Échelle 40-200 bpm
   - Zones de seuil: Rouge > 180 ou < 50, Orange 150-180, Vert 60-100
   - Affichage par patient avec légende

3. **Température Corporelle - Ligne Temps Réel**
   - Axe X: Temps (dernières 4 heures)
   - Axe Y: Température (°C) - Échelle 35-42°C
   - Zones: Rouge > 38.5°C, Orange 38-38.5°C, Vert 36-37.5°C
   - Alarme visuelle si > 39°C

4. **Température Ambiante - Ligne Temps Réel**
   - Axe X: Temps (dernières 4 heures)
   - Axe Y: Température ambiante (°C) - Échelle 10-35°C
   - Zones: Rouge > 30°C ou < 15°C, Orange 25-30°C, Vert 18-25°C
   - Indicateur confort environnemental

5. **Fréquence Respiratoire - Ligne Temps Réel**
   - Axe X: Temps (dernières 4 heures)
   - Axe Y: FR (cycles/min) - Échelle 10-40
   - Zones: Rouge > 30 ou < 12, Orange 25-30, Vert 12-20
   - Corrélation avec autres vitaux

6. **Hydratation - Ligne Temps Réel**
   - Axe X: Temps (dernières 4 heures)
   - Axe Y: Hydratation (%) - Échelle 40-100%
   - Zones: Rouge < 60%, Orange 60-69%, Vert ≥ 70%
   - Tendance déshydratation

7. **Niveau d'Activité - Barres Temps Réel**
   - Axe X: Temps (dernières 4 heures, buckets 15 min)
   - Axe Y: Activité (0-100)
   - Zones: Rouge > 90 (suractivité), Orange < 10 (inactivité), Vert 30-70
   - Pattern activité/repos

8. **Index de Chaleur - Gauge/Jauge**
   - Indicateur type speedometer (0-50)
   - Zones: Rouge > 40, Orange 35-40, Vert < 35
   - Calcul basé sur température + humidité

9. **Distribution des Alertes (Barres)**
   - Axe X: Type d'alerte (SpO2, Temperature Corp, FC, Temp Ambiante, Hydratation)
   - Axe Y: Nombre d'alertes
   - Couleurs par sévérité (Rouge=Critical, Orange=High, Jaune=Medium)

10. **Status Patients (Donut)**
    - Répartition: Stable, Warning, Critical, Disconnected
    - Couleurs: Vert, Orange, Rouge, Gris
    - Pourcentages affichés

11. **Heatmap Activité par Heure et Patient**
    - Axe X: Heures (0-23)
    - Axe Y: Patient ID
    - Couleur: Intensité des mesures reçues (blanc=0, bleu foncé=max)
    - Pattern sommeil/éveil visible

#### **📋 Tableaux de Données**

1. **Tableau Patients Actifs**
   ```
   Patient ID | Last Update | SpO2 | FC | Temp Corp | Temp Amb | Hydrat | Activity | Status | Alerts
   PAT-001   | 12:34:56   | 96%  | 75 | 37.2°C   | 22.1°C   | 72%    | 45       | Stable | 0
   PAT-002   | 12:34:45   | 85%  | 185| 38.5°C   | 28.3°C   | 58%    | 15       | Critical| 3
   PAT-003   | 12:34:30   | 92%  | 68 | 36.8°C   | 21.5°C   | 68%    | 80       | Warning | 1
   ```

2. **Tableau Alertes Récentes**
   ```
   Time     | Patient | Type        | Severity | Message                    | Vitaux Snapshot           | Status
   12:34:56 | PAT-002 | SpO2       | Critical | SpO2 85% - Urgent          | FC:185, T°:38.5, H:58%    | Pending
   12:33:12 | PAT-002 | Composite  | Critical | Crise possible             | Multiple vitaux critiques  | Pending
   12:32:45 | PAT-003 | Temp Amb   | Medium   | Environnement chaud 28°C   | T°Amb:28.3°C              | Acknowledged
   ```

3. **Tableau Tendances par Mesure (Dernière Heure)**
   ```
   Mesure           | Min    | Max    | Moyenne | Écart-Type | Tendance | Patients Affectés
   SpO2 (%)         | 82     | 98     | 93.2    | 4.1        | ↓ Stable | 12/15
   FC (bpm)         | 58     | 195    | 78.5    | 18.3       | ↑ +2%    | 15/15
   Temp Corp (°C)   | 36.1   | 39.2   | 37.1    | 0.8        | ↑ +0.3°C | 15/15
   Temp Amb (°C)    | 18.5   | 31.2   | 23.4    | 3.2        | ↑ +1.1°C | 15/15
   Hydratation (%)  | 45     | 85     | 67.8    | 9.4        | ↓ -2%    | 14/15
   Activité (0-100) | 5      | 92     | 41.2    | 22.1       | ↓ Stable | 15/15
   ```

#### **🎨 Layout Dashboard PowerBI Multi-Pages**

**Page 1: Vue d'Ensemble (Page Principale)**
```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 🏥 PIPELINE IOT KIDJAMO - MONITORING TEMPS RÉEL                                    │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ [Patients: 15] [Alertes: 3] [SpO2: 93%] [FC: 78] [T°Corp: 37.1] [T°Amb: 23.4]     │
│ [Hydratation: 68%] [Activité: 41] [Réponse: 4.2min]                               │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────────────┐ │
│ │ SpO2 Global │ │ FC Global   │ │ Temp Corp   │ │    Status Patients              │ │
│ │  (Ligne)    │ │  (Ligne)    │ │  (Ligne)    │ │      (Donut)                    │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┐ ┌─────────────────────────────────────────────────┐ │
│ │    Patients Actifs          │ │           Alertes Récentes                      │ │
│ │       (Tableau)             │ │            (Tableau)                            │ │
│ └─────────────────────��───────┘ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Page 2: Vitaux Détaillés**
```
┌────────────────────────────────────────────────���────────────────────────────────────┐
│ 📊 VITAUX DÉTAILLÉS - ANALYSE PAR MESURE                                           │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────────────────┐ │
│ │ Temp Amb    │ │ Hydratation │ │ Freq Resp   │ │    Index Chaleur                │ │
│ │  (Ligne)    │ │  (Ligne)    │ │  (Ligne)    │ │     (Gauge)                     │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌───────────────────────────────────────────────────┐ │
│ │ Activité    │ │ Alertes     │ │         Heatmap Activité                          │ │
│ │  (Barres)   │ │Distribution │ │        (Heure x Patient)                         │ │
│ └─────────────┘ └─────────────┘ └───────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

**Page 3: Analytics et Tendances**
```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│ 📈 ANALYTICS ET TENDANCES - DERNIÈRES 24H                                          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────┐ ┌─────────────────────────────────────────────────┐ │
│ │    Tendances par Mesure     │ │         Corrélations Vitaux                     │ │
│ │        (Tableau)            │ │      (Matrice/Scatter)                          │ │
│ └─────────────────────────────┘ └─────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────────────────────────────────────────────────────────────┐ │
│ │                     Prédictions et Alertes Préventives                           │ │
│ │                              (En développement)                                  │ │
│ └───────────────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
```
