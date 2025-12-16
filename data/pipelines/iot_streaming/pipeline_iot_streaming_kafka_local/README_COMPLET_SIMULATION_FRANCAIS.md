# 🏥 SIMULATEUR IOT PATIENTS KIDJAMO - GUIDE COMPLET EN FRANÇAIS

## 📋 Table des Matières

1. [Vue d'ensemble de la simulation](#vue-densemble-de-la-simulation)
2. [Architecture et composants](#architecture-et-composants)
3. [Prérequis et installation](#prérequis-et-installation)
4. [Étapes d'exécution manuelle détaillées](#étapes-dexécution-manuelle-détaillées)
5. [Fonctionnement de chaque composant](#fonctionnement-de-chaque-composant)
6. [Résolution des problèmes courants](#résolution-des-problèmes-courants)
7. [Tests et validation](#tests-et-validation)
8. [Monitoring et surveillance](#monitoring-et-surveillance)

---

## 🎯 Vue d'ensemble de la simulation

Ce simulateur IoT médical génère des données physiologiques réalistes pour des patients virtuels atteints de drépanocytose. Il simule un environnement hospitalier complet avec :

### **Objectifs principaux :**
- **Simulation de 50+ patients virtuels** avec profils médicaux diversifiés
- **Génération de données IoT** toutes les 5 secondes pendant 24h
- **Détection automatique d'alertes** médicales critiques
- **Notifications en temps réel** (SMS + Email)
- **Dashboard interactif** pour surveillance médicale
- **Tests de charge** du système IoT

### **Cas d'usage pratiques :**
- 🧪 **Tests de performance** des pipelines de données
- 👨‍⚕️ **Formation du personnel** médical
- 🎪 **Démonstrations** clients et investisseurs
- 🔧 **Développement et débogage** des algorithmes d'alerte
- 📊 **Validation** des tableaux de bord médicaux

---

## 🏗️ Architecture et composants

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIMULATEUR IOT PATIENTS                     │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
    ┌───────────▼────┐ ┌────────▼────┐ ┌────────▼────┐
    │  GÉNÉRATEUR    │ │ SIMULATEUR  │ │   MOTEUR    │
    │   PATIENTS     │ │PHYSIOLOGIQUE│ │  D'ALERTES  │
    │                │ │             │ │             │
    │ • 50+ profils  │ │ • SpO2, FC  │ │ • Seuils    │
    │ • Génotypes    │ │ • Temp, FR  │ │ • Critères  │
    │ • Âges/Poids   │ │ • Cycles    │ │ • Actions   │
    └──────────────��─┘ └─────────────┘ └─────────────┘
                │               │               │
                └───────────────┼───────────────┘
                                │
    ┌─────────────────────────────────────────────────────────┐
    │                 SORTIES SYSTÈME                         │
    ├─────────────────┬─────────────────┬─────────────────────┤
    │  BASE DONNÉES   │  NOTIFICATIONS  │     DASHBOARD       │
    │                 │                 │                     │
    │ • PostgreSQL    │ • SMS Twilio    │ • Streamlit         │
    │ • Measurements  │ ��� Email SMTP    │ • Graphiques        │
    │ • Alerts        │ • Temps réel    │ • Filtres           │
    │ • Patients      │ • Circuit break │ • KPIs              │
    └─────────────────┴─────────────────┴─────────────────────┘
```

### **Composants principaux :**

1. **📝 Générateur de Patients** (`PatientGenerator`)
   - Crée des profils patients réalistes
   - Génotypes de drépanocytose (SS, SC, AS, Sβ0)
   - Paramètres physiologiques individualisés

2. **🫀 Simulateur Physiologique** (`PhysiologicalSimulator`)
   - Génère les mesures vitales (SpO2, FC, température)
   - Simule les cycles circadiens
   - Modélise les crises drépanocytaires

3. **🚨 Moteur d'Alertes** (`AlertEngine`)
   - Analyse les seuils médicaux en temps réel
   - Détecte les anomalies critiques
   - Propose des actions médicales

4. **🗄️ Gestionnaire de Base de Données** (`DatabaseManager`)
   - Insertion batch haute performance
   - Gestion des connexions PostgreSQL
   - Optimisation mémoire

5. **📱 Service de Notifications** (`NotificationService`)
   - SMS via Twilio
   - Emails via SMTP
   - Circuit breaker anti-spam

---

## 💻 Prérequis et installation

### **Logiciels requis :**
- **Python 3.8+** avec pip
- **PostgreSQL 12+** en cours d'exécution
- **Docker** (optionnel pour Kafka)
- **Git** pour clonage du projet

### **Services externes (optionnels) :**
- **Compte Twilio** pour SMS
- **Serveur SMTP** pour emails (Gmail, Outlook, etc.)
- **Kafka** pour streaming (optionnel)

### **Installation étape par étape :**

```powershell
# 1. Naviguer vers le dossier du projet
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local

# 2. Créer environnement virtuel Python (si pas encore fait)
python -m venv venv

# 3. Activer l'environnement virtuel
venv\Scripts\activate

# 4. Installer les dépendances Python
pip install -r requirements.txt

# 5. Installer les dépendances du simulateur massif
pip install -r requirements_massive_simulation.txt

# 6. Vérifier que PostgreSQL fonctionne
python -c "import psycopg2; print('✅ PostgreSQL disponible')"
```

---

## 🔧 Étapes d'exécution manuelle détaillées

### **ÉTAPE 1 : Préparation de l'environnement (5 minutes)**

#### **🎯 But de cette étape :**
Vérifier que tous les composants système sont prêts et configurés correctement.

```powershell
# 1.1 - Naviguer vers le répertoire principal
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local

# 1.2 - Activer l'environnement virtuel Python
venv\Scripts\activate

# 1.3 - Vérifier la version Python
python --version
# Résultat attendu : Python 3.8 ou supérieur

# 1.4 - Tester la connexion PostgreSQL (PROBLÈME D'ENCODAGE RÉSOLU)
$env:PGCLIENTENCODING = "UTF8"
python -c "import psycopg2; import os; os.environ['PGCLIENTENCODING'] = 'UTF8'; conn=psycopg2.connect(host='localhost',port='5432',database='kidjamo',user='postgres',password='password'); print('✅ DB OK'); conn.close()"

# 1.5 - Vérifier les modules du simulateur
python -c "from simulator.massive_patient_simulator_combined import PatientGenerator; print('✅ Simulateur OK')"
```

#### **💡 Que fait cette étape :**
- Active l'environnement Python isolé
- **Résout le problème d'encodage UTF-8** en définissant `PGCLIENTENCODING=UTF8`
- Vérifie que PostgreSQL est accessible
- Confirme que les modules du simulateur sont chargés

---

### **ÉTAPE 2 : Test du générateur de patients (3 minutes)**

#### **🎯 But de cette étape :**
Valider que le générateur peut créer des profils patients réalistes avec les caractéristiques de la drépanocytose.

```powershell
# 2.1 - Tester la génération de patients
python -c "
from simulator.massive_patient_simulator_combined import PatientGenerator
gen = PatientGenerator()
patients = gen.generate_patient_batch(5)
print(f'✅ Généré {len(patients)} patients de test')
for p in patients:
    print(f'  - {p.first_name} {p.last_name}, {p.age}ans, génotype {p.genotype}')
"

# 2.2 - Examiner les détails d'un patient
python -c "
from simulator.massive_patient_simulator_combined import PatientGenerator
gen = PatientGenerator()
patient = gen.generate_patient_batch(1)[0]
print(f'Patient détaillé :')
print(f'  Nom: {patient.first_name} {patient.last_name}')
print(f'  Âge: {patient.age} ans')
print(f'  Genre: {patient.gender}')
print(f'  Génotype: {patient.genotype}')
print(f'  Poids: {patient.weight_kg} kg')
print(f'  Taille: {patient.height_cm} cm')
print(f'  FC de base: {patient.base_heart_rate} bpm')
print(f'  SpO2 de base: {patient.base_spo2_range}%')
print(f'  Device ID: {patient.device_id}')
"
```

#### **💡 Que fait cette étape :**
- Génère 5 patients virtuels avec des profils variés
- Affiche leurs caractéristiques principales (nom, âge, génotype)
- Montre les paramètres physiologiques individualisés
- Valide que chaque génotype a ses propres seuils médicaux

---

### **ÉTAPE 3 : Test du simulateur physiologique (5 minutes)**

#### **🎯 But de cette étape :**
Vérifier que le simulateur peut générer des mesures physiologiques réalistes pour chaque patient.

```powershell
# 3.1 - Tester une mesure simple
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
gen = PatientGenerator()
sim = PhysiologicalSimulator()
patient = gen.generate_patient_batch(1)[0]
measurement = sim.generate_measurement(patient, datetime.now())
print(f'✅ Mesure générée pour {patient.first_name}:')
print(f'  SpO2: {measurement.spo2_percent}%')
print(f'  Fréquence cardiaque: {measurement.heart_rate_bpm} bpm')
print(f'  Température: {measurement.temperature_celsius}°C')
print(f'  Fréquence respiratoire: {measurement.respiratory_rate_min}/min')
print(f'  Hydratation: {measurement.hydration_percent}%')
print(f'  Douleur: {measurement.pain_scale}/10')
print(f'  Batterie: {measurement.battery_percent}%')
"

# 3.2 - Simuler plusieurs mesures dans le temps
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime, timedelta
import time

gen = PatientGenerator()
sim = PhysiologicalSimulator()
patient = gen.generate_patient_batch(1)[0]

print(f'Simulation de 5 mesures pour {patient.first_name} {patient.last_name} (génotype {patient.genotype}):')
print('Heure    | SpO2  | FC   | Temp | Douleur')
print('---------|-------|------|------|--------')

for i in range(5):
    timestamp = datetime.now() + timedelta(seconds=i*5)
    measurement = sim.generate_measurement(patient, timestamp)
    print(f'{timestamp.strftime(\"%H:%M:%S\")} | {measurement.spo2_percent:4.1f}% | {measurement.heart_rate_bpm:3d} | {measurement.temperature_celsius:4.1f}°C | {measurement.pain_scale}/10')
    time.sleep(1)  # Pause pour voir l'évolution
"
```

#### **💡 Que fait cette étape :**
- Génère une mesure physiologique complète
- Affiche toutes les variables vitales simulées
- Teste la variation temporelle des mesures
- Montre l'adaptation aux caractéristiques du génotype

---

### **ÉTAPE 4 : Test du moteur d'alertes (5 minutes)**

#### **🎯 But de cette étape :**
Valider que le système détecte correctement les situations médicales critiques et génère des alertes appropriées.

```powershell
# 4.1 - Tester la détection d'alertes normales
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime

gen = PatientGenerator()
sim = PhysiologicalSimulator()
notification_service = NotificationService()  # IMPORTANT: Créer d'abord le service
alert_engine = AlertEngine(notification_service)  # Passer le service à AlertEngine

patient = gen.generate_patient_batch(1)[0]
measurement = sim.generate_measurement(patient, datetime.now())

print(f'Test d\'alertes pour {patient.first_name} (génotype {patient.genotype}):')
print(f'Mesures: SpO2={measurement.spo2_percent}%, FC={measurement.heart_rate_bpm}bpm, Temp={measurement.temperature_celsius}°C')

alerts = alert_engine.analyze_measurement(measurement, patient)
if alerts:
    print(f'🚨 {len(alerts)} alerte(s) détectée(s):')
    for alert in alerts:
        print(f'  - {alert.severity.upper()}: {alert.title}')
        print(f'    {alert.message}')
else:
    print('✅ Aucune alerte - Signes vitaux normaux')
"

# 4.2 - Forcer une situation critique pour tester les alertes
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime

gen = PatientGenerator()
notification_service = NotificationService()  # IMPORTANT: Service de notifications requis
alert_engine = AlertEngine(notification_service)

# Créer un patient SS (plus vulnérable)
patient = gen.generate_patient_batch(1)[0]
while patient.genotype != 'SS':
    patient = gen.generate_patient_batch(1)[0]

# Simuler une mesure critique artificielle
measurement = MeasurementRecord(
    measurement_id=None,
    patient_id=patient.patient_id,
    device_id=patient.device_id,
    message_id=str(uuid.uuid4()),
    recorded_at=datetime.now(),
    received_at=datetime.now(),
    heart_rate_bpm=130,  # Tachycardie
    respiratory_rate_min=28,  # Tachypnée  
    spo2_percent=83.0,  # SpO2 critique
    temperature_celsius=38.8,  # Fièvre
    ambient_temp_celsius=22.0,
    hydration_percent=35.0,  # Déshydratation
    activity_level=1,
    heat_index_celsius=22.0,
    pain_scale=8,  # Douleur sévère
    battery_percent=85,
    signal_quality=95
)

print(f'🚨 Test de situation CRITIQUE pour {patient.first_name} (génotype {patient.genotype}):')
print(f'Mesures critiques: SpO2={measurement.spo2_percent}%, FC={measurement.heart_rate_bpm}bpm')
print(f'                   Temp={measurement.temperature_celsius}°C, Douleur={measurement.pain_scale}/10')

alerts = alert_engine.analyze_measurement(measurement, patient)
print(f'\\n🚨 {len(alerts)} ALERTE(S) GÉNÉRÉE(S):')
for alert in alerts:
    print(f'\\n[{alert.severity.upper()}] {alert.alert_type}')
    print(f'Titre: {alert.title}')
    print(f'Message: {alert.message}')
    print(f'Actions suggérées: {alert.suggested_actions}')
"
```

#### **💡 Que fait cette étape :**
- Teste la détection d'alertes en conditions normales
- Force une situation critique pour valider les seuils
- Montre les différents types d'alertes (SpO2, tachycardie, fièvre, douleur)
- Vérifie que les actions médicales appropriées sont suggérées

---

### **ÉTAPE 5 : Test des notifications (5 minutes)**

#### **🎯 But de cette étape :**
Vérifier que le système peut envoyer des notifications (même si les services externes ne sont pas configurés).

```powershell
# 5.1 - Tester le service de notifications (mode simulation)
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
import asyncio

# Créer les objets
gen = PatientGenerator()
patient = gen.generate_patient_batch(1)[0]
notification_service = NotificationService()

# Créer une alerte de test
alert = AlertRecord(
    alert_id=None,
    patient_id=patient.patient_id,
    alert_type='spo2_critical',
    severity='critical',
    title='SpO2 Critique Détectée',
    message='SpO2 dangereusement bas détecté',
    vitals_snapshot={'spo2': 82, 'heart_rate': 125, 'temperature': 38.5},
    trigger_conditions=['SpO2 < 85%', 'Génotype SS'],
    suggested_actions=['Oxygène immédiat', 'Appeler médecin'],
    created_at=datetime.now()
)

print(f'Test des notifications pour {patient.first_name} {patient.last_name}:')
print(f'Type d\'alerte: {alert.alert_type} ({alert.severity})')

# Générer le contenu SMS
sms_content = notification_service._format_sms_alert(alert, patient)
print(f'\\n📱 Contenu SMS généré:')
print('=' * 50)
print(sms_content)

# Générer le contenu Email  
email_content = notification_service._format_email_alert(alert, patient)
print(f'\\n📧 Email HTML généré (extrait):')
print('=' * 50)
print(email_content[:500] + '...')

print(f'\\n✅ Notifications formatées avec succès')
print(f'Note: Envoi réel nécessite configuration Twilio/SMTP')
"
```

#### **💡 Que fait cette étape :**
- Génère le contenu des notifications SMS et Email
- Montre le formatage des alertes médicales
- Teste le service sans envoi réel (évite les erreurs de configuration)
- Valide que toutes les informations médicales sont incluses

---

### **ÉTAPE 6 : Test d'intégration base de données (10 minutes)**

#### **🎯 But de cette étape :**
Vérifier que le système peut sauvegarder les données dans PostgreSQL et récupérer l'historique.

```powershell
# 6.1 - Tester la connexion et création des tables
python -c "
from simulator.massive_patient_simulator_combined import DatabaseManager
db = DatabaseManager()

if db.connection:
    print('✅ Connexion PostgreSQL réussie')
    
    # Tester une requête simple
    cursor = db.connection.cursor()
    cursor.execute('SELECT version();')
    version = cursor.fetchone()
    print(f'Version PostgreSQL: {version[0][:50]}...')
    cursor.close()
else:
    print('❌ Échec connexion PostgreSQL')
    print('Vérifiez que PostgreSQL fonctionne et que la base \\\"kidjamo\\\" existe')
"

# 6.2 - Simuler l'insertion de données patients et mesures
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
import uuid

# Créer les instances
gen = PatientGenerator()
sim = PhysiologicalSimulator()
db = DatabaseManager()

if not db.connection:
    print('❌ Pas de connexion DB - Skip test')
    exit()

# Générer quelques patients et mesures
patients = gen.generate_patient_batch(3)
print(f'Génération de {len(patients)} patients pour test DB...')

for i, patient in enumerate(patients):
    print(f'\\nPatient {i+1}: {patient.first_name} {patient.last_name} (génotype {patient.genotype})')
    
    # Générer 3 mesures pour ce patient
    for j in range(3):
        timestamp = datetime.now()
        measurement = sim.generate_measurement(patient, timestamp)
        
        print(f'  Mesure {j+1}: SpO2={measurement.spo2_percent}%, FC={measurement.heart_rate_bpm}bpm')
        
        # Ajouter au buffer (simulation)
        db.measurement_buffer.append(measurement.to_db_record())
        
        if len(db.measurement_buffer) >= 5:  # Flush petit batch
            print(f'  💾 Simulation flush {len(db.measurement_buffer)} mesures vers DB')
            db.measurement_buffer.clear()

print(f'\\n✅ Test simulation base de données terminé')
print(f'Note: Pour insertion réelle, utilisez db.insert_measurements_batch()')
"
```

#### **💡 Que fait cette étape :**
- Teste la connexion PostgreSQL avec l'encodage UTF-8 corrigé
- Vérifie la version de la base de données
- Simule l'insertion batch de patients et mesures
- Montre le mécanisme de buffer pour les performances

---

### **ÉTAPE 7 : Simulation complète courte durée (15 minutes)**

#### **🎯 But de cette étape :**
Exécuter une simulation complète avec tous les composants intégrés pendant une courte période.

```powershell
# 7.1 - Lancer une simulation de 5 patients pendant 2 minutes
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime, timedelta
import time
import threading

print('🚀 DÉMARRAGE SIMULATION COMPLÈTE - 5 patients, 2 minutes')
print('=' * 60)

# Configuration simulation courte
NUM_PATIENTS = 5
DURATION_MINUTES = 2
MEASUREMENT_INTERVAL = 10  # Une mesure toutes les 10 secondes

# Créer les composants
gen = PatientGenerator()
sim = PhysiologicalSimulator()
alert_engine = AlertEngine()
notification_service = NotificationService()

# Générer les patients
patients = gen.generate_patient_batch(NUM_PATIENTS)
print(f'\\n👥 Patients générés:')
for i, p in enumerate(patients, 1):
    print(f'  {i}. {p.first_name} {p.last_name}, {p.age}ans, génotype {p.genotype}')

# Variables de suivi
total_measurements = 0
total_alerts = 0
start_time = datetime.now()
end_time = start_time + timedelta(minutes=DURATION_MINUTES)

print(f'\\n⏰ Simulation de {start_time.strftime(\"%H:%M:%S\")} à {end_time.strftime(\"%H:%M:%S\")}')
print(f'📊 Mesures toutes les {MEASUREMENT_INTERVAL} secondes')
print('\\nDémarrage...')
print('Temps    | Patient              | SpO2  | FC   | Temp | Alertes')
print('---------|----------------------|-------|------|------|--------')

# Boucle principale de simulation
while datetime.now() < end_time:
    current_time = datetime.now()
    
    for patient in patients:
        # Générer mesure
        measurement = sim.generate_measurement(patient, current_time)
        total_measurements += 1
        
        # Analyser alertes
        alerts = alert_engine.analyze_measurement(measurement, patient)
        alert_count = len(alerts)
        total_alerts += alert_count
        
        # Afficher résumé
        alert_indicator = f'🚨{alert_count}' if alert_count > 0 else '✅'
        patient_name = f'{patient.first_name} {patient.last_name}'[:20].ljust(20)
        
        print(f'{current_time.strftime(\"%H:%M:%S\")} | {patient_name} | {measurement.spo2_percent:4.1f}% | {measurement.heart_rate_bpm:3d} | {measurement.temperature_celsius:4.1f}°C | {alert_indicator}')
        
        # Si alertes critiques, afficher détails
        if alerts:
            for alert in alerts:
                if alert.severity in ['critical', 'alert']:
                    print(f'         └─ {alert.severity.upper()}: {alert.title}')
    
    # Pause avant prochaine mesure
    time.sleep(MEASUREMENT_INTERVAL)

# Statistiques finales
elapsed = datetime.now() - start_time
print(f'\\n📈 STATISTIQUES SIMULATION:')
print(f'  ⏱️  Durée: {elapsed.total_seconds():.1f} secondes')
print(f'  📊 Total mesures: {total_measurements}')
print(f'  🚨 Total alertes: {total_alerts}')
print(f'  📈 Taux alertes: {(total_alerts/total_measurements*100):.1f}%')
print(f'  ⚡ Mesures/seconde: {total_measurements/elapsed.total_seconds():.1f}')

print(f'\\n✅ Simulation terminée avec succès!')
"
```

#### **��� Que fait cette étape :**
- Exécute une vraie simulation avec 5 patients pendant 2 minutes
- Génère des mesures toutes les 10 secondes pour chaque patient  
- Analyse les alertes en temps réel
- Affiche un tableau de bord en temps réel dans la console
- Fournit des statistiques de performance finales

---

## 🧩 Fonctionnement de chaque composant

### **1. 📝 PatientGenerator - Générateur de Patients**

**Rôle :** Crée des profils patients virtuels avec des caractéristiques médicales réalistes.

**Fonctionnement interne :**
- Génère des noms français aléatoires (masculins/féminins)
- Attribue des âges entre 5 et 80 ans
- Assigne des génotypes de drépanocytose avec leurs caractéristiques :
  - **SS** : Forme sévère, SpO2 base 92-96%, crises fréquentes
  - **SC** : Forme modérée, SpO2 base 94-98%, crises occasionnelles  
  - **AS** : Porteur sain, SpO2 base 96-100%, très rares crises
  - **Sβ0** : Forme sévère, SpO2 base 93-97%, crises fréquentes

**Paramètres individualisés :**
- Fréquence cardiaque de base adaptée à l'âge
- Gammes de SpO2 selon le génotype
- Poids et taille corrélés à l'âge
- Identifiants uniques pour traçabilité

### **2. 🫀 PhysiologicalSimulator - Simulateur Physiologique**

**Rôle :** Génère des mesures vitales réalistes qui évoluent dans le temps.

**Algorithmes utilisés :**
- **Cycles circadiens** : Variation naturelle selon l'heure (température plus basse la nuit)
- **Variabilité physiologique** : Fluctuations normales autour des valeurs de base
- **Corrélations médicales** : Cohérence entre les signes vitaux (FC élevée → SpO2 peut baisser)
- **Simulation de crises** : Déclenchement aléatoire de crises drépanocytaires

**Variables simulées :**
- SpO2 (%) avec adaptation au génotype
- Fréquence cardiaque (bpm) avec variabilité d'âge
- Température corporelle (°C) avec cycles jour/nuit
- Fréquence respiratoire (/min) corrélée au stress
- Hydratation (%) avec variation d'activité
- Douleur (0-10) avec pics lors des crises
- Qualité signal et batterie du dispositif IoT

### **3. 🚨 AlertEngine - Moteur d'Alertes**

**Rôle :** Analyse les mesures en temps réel et détecte les situations médicales critiques.

**Seuils de déclenchement :**
- **SpO2 critique** : <85% pour génotype SS, <88% pour autres
- **Tachycardie** : >120 bpm adulte, >140 bpm enfant
- **Bradycardie** : <50 bpm
- **Fièvre** : >38.0°C (fièvre), >39.5°C (fièvre élevée)
- **Tachypnée** : >24/min adulte, >30/min enfant
- **Déshydratation** : <40%
- **Douleur sévère** : >7/10

**Types d'alertes générées :**
- **INFO** : Surveillance simple
- **WARN** : Situation à surveiller
- **ALERT** : Intervention rapide recommandée
- **CRITICAL** : Urgence médicale immédiate

### **4. 📱 NotificationService - Service de Notifications**

**Rôle :** Envoie des alertes via SMS et Email avec protection anti-spam.

**Fonctionnalités avancées :**
- **Circuit breaker** : Désactive temporairement si trop d'échecs
- **Formatage adapté** : SMS courts, emails détaillés avec HTML
- **Escalation** : SMS uniquement pour alertes critiques
- **Template médical** : Inclusion de tous les signes vitaux et actions

**Configuration requise :**
```python
# Variables d'environnement pour SMS Twilio
TWILIO_ACCOUNT_SID=your_sid
TWILIO_AUTH_TOKEN=your_token  
TWILIO_FROM_NUMBER=+1234567890

# Variables d'environnement pour Email SMTP
SMTP_USERNAME=your_email@gmail.com
SMTP_PASSWORD=your_app_password
```

### **5. 🗄️ DatabaseManager - Gestionnaire de Base de Données**

**Rôle :** Optimise les insertions en base pour les hautes performances.

**Optimisations techniques :**
- **Insertion batch** : Groupe 1000 mesures avant insertion
- **Prepared statements** : Évite la recompilation SQL
- **Connection pooling** : Réutilise les connexions
- **Gestion mémoire** : Buffer limité pour éviter l'explosion RAM

**Tables PostgreSQL utilisées :**
- `patients` : Profils patients
- `iot_measurements` : Mesures physiologiques
- `alerts` : Alertes médicales générées
- `device_status` : État des dispositifs IoT

---

## ⚠️ Résolution des problèmes courants

### **Problème 1 : Erreur UTF-8 PostgreSQL**

**Symptôme :**
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe9 in position 103
```

**Solution :**
```powershell
# Définir l'encodage avant connexion
$env:PGCLIENTENCODING = "UTF8"
python -c "import os; os.environ['PGCLIENTENCODING'] = 'UTF8'; import psycopg2; conn=psycopg2.connect(...)"
```

### **Problème 2 : Module math non trouvé**

**Symptôme :**
```
NameError: name 'math' is not defined
```

**Solution :** ✅ **DÉJÀ CORRIGÉ** - L'import du module `math` a été ajouté au fichier principal.

### **Problème 3 : Import simulator échoue**

**Symptôme :**
```
ModuleNotFoundError: No module named 'simulator'
```

**Solution :**
```powershell
# Exécuter depuis le répertoire parent, pas depuis le dossier simulator/
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local
python -c "from simulator.massive_patient_simulator_combined import PatientGenerator"
```

### **Problème 4 : Connexion PostgreSQL échoue**

**Diagnostic :**
```powershell
# Vérifier que PostgreSQL fonctionne
postgres --version
pg_isready -h localhost -p 5432

# Vérifier la base de données
psql -h localhost -U postgres -c "\l" | findstr kidjamo
```

**Solutions :**
- Créer la base : `createdb -h localhost -U postgres kidjamo`
- Vérifier mot de passe dans `DB_CONFIG`
- Redémarrer PostgreSQL si nécessaire

### **Problème 5 : Dépendances manquantes**

**Solution :**
```powershell
# Installer toutes les dépendances
pip install psycopg2-binary twilio kafka-python requests streamlit pandas plotly
```

---

## 🧪 Tests et validation

### **Tests unitaires rapides**

```powershell
# Test 1 : Génération patients
python -c "
from simulator.massive_patient_simulator_combined import PatientGenerator
gen = PatientGenerator()
patients = gen.generate_patient_batch(10)
genotypes = [p.genotype for p in patients]
print(f'✅ Génotypes générés: {set(genotypes)}')
assert len(patients) == 10
print('✅ Test génération patients OK')
"

# Test 2 : Cohérence mesures physiologiques
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime

gen = PatientGenerator()
sim = PhysiologicalSimulator()
patient = gen.generate_patient_batch(1)[0]

# Générer 10 mesures
measures = []
for i in range(10):
    m = sim.generate_measurement(patient, datetime.now())
    measures.append(m)

# Vérifier cohérence
spo2_values = [m.spo2_percent for m in measures]
hr_values = [m.heart_rate_bpm for m in measures]

print(f'SpO2 range: {min(spo2_values):.1f}% - {max(spo2_values):.1f}%')
print(f'HR range: {min(hr_values)} - {max(hr_values)} bpm')

# Assertions
assert all(80 <= s <= 100 for s in spo2_values), 'SpO2 hors limites'
assert all(40 <= h <= 180 for h in hr_values), 'FC hors limites'
print('✅ Test cohérence mesures OK')
"

# Test 3 : Détection alertes
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime

alert_engine = AlertEngine()

# Créer une mesure critique forcée
critical_measurement = MeasurementRecord(
    measurement_id=None, patient_id='test', device_id='test',
    message_id='test', recorded_at=datetime.now(), received_at=datetime.now(),
    heart_rate_bpm=140, respiratory_rate_min=30, spo2_percent=82.0,
    temperature_celsius=39.0, ambient_temp_celsius=22.0, hydration_percent=30.0,
    activity_level=1, heat_index_celsius=22.0, pain_scale=9,
    battery_percent=85, signal_quality=95
)

# Patient SS pour test
patient = PatientProfile(
    patient_id='test', user_id='test', first_name='Test', last_name='Patient',
    age=25, gender='M', genotype='SS', weight_kg=70, height_cm=175,
    device_id='test', base_heart_rate=80, base_spo2_range=(92, 96),
    base_temperature=36.5, base_respiratory_rate=18, base_hydration=80.0
)

alerts = alert_engine.analyze_measurement(critical_measurement, patient)
print(f'✅ {len(alerts)} alertes détectées pour situation critique')
assert len(alerts) >= 3, 'Pas assez d\'alertes pour situation critique'
print('✅ Test détection alertes OK')
"
```

### **Test de performance**

```powershell
# Test charge : 100 patients, 1000 mesures
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
import time

start_time = time.time()

# Générer 100 patients
gen = PatientGenerator()
patients = gen.generate_patient_batch(100)

# Générer 10 mesures par patient
sim = PhysiologicalSimulator()
total_measures = 0

for patient in patients:
    for i in range(10):
        measurement = sim.generate_measurement(patient, datetime.now())
        total_measures += 1

end_time = time.time()
duration = end_time - start_time

print(f'✅ Performance test:')
print(f'  - {len(patients)} patients générés')  
print(f'  - {total_measures} mesures générées')
print(f'  - Durée: {duration:.2f} secondes')
print(f'  - Mesures/seconde: {total_measures/duration:.1f} mesures/sec')

assert total_measures == 1000, 'Nombre mesures incorrect'
assert duration < 30, 'Performance trop lente'
print('✅ Test performance OK')
"
```

---

## 📊 Monitoring et surveillance

### **Scripts de surveillance continue**

```powershell
# Monitoring en temps réel des alertes
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime, timedelta
import time

print('🔍 MONITORING ALERTES EN TEMPS RÉEL')
print('Ctrl+C pour arrêter')
print()

gen = PatientGenerator()  
sim = PhysiologicalSimulator()
alert_engine = AlertEngine()

# 10 patients de test
patients = gen.generate_patient_batch(10)
alert_counts = {'info': 0, 'warn': 0, 'alert': 0, 'critical': 0}

try:
    while True:
        current_time = datetime.now()
        
        for patient in patients:
            measurement = sim.generate_measurement(patient, current_time)
            alerts = alert_engine.analyze_measurement(measurement, patient)
            
            for alert in alerts:
                alert_counts[alert.severity] += 1
                
                if alert.severity in ['alert', 'critical']:
                    print(f'{current_time.strftime(\"%H:%M:%S\")} 🚨 {alert.severity.upper()}: {patient.first_name} - {alert.title}')
        
        # Afficher compteurs toutes les 30 secondes
        if current_time.second == 0 or current_time.second == 30:
            print(f'{current_time.strftime(\"%H:%M:%S\")} 📊 Alertes: INFO={alert_counts[\"info\"]} WARN={alert_counts[\"warn\"]} ALERT={alert_counts[\"alert\"]} CRITICAL={alert_counts[\"critical\"]}')
        
        time.sleep(5)

except KeyboardInterrupt:
    print(f'\\n✅ Monitoring arrêté. Total alertes: {sum(alert_counts.values())}')
"
```

### **Dashboard de performance**

```powershell
# Statistiques détaillées de simulation
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
import time
from collections import defaultdict

print('📈 ANALYSE PERFORMANCE SIMULATEUR')
print('=' * 50)

# Mesurer performance génération
start = time.time()
gen = PatientGenerator()
patients = gen.generate_patient_batch(50)
gen_time = time.time() - start

print(f'👥 Génération 50 patients: {gen_time:.3f}s ({50/gen_time:.1f} patients/sec)')

# Analyser répartition génotypes
genotype_counts = defaultdict(int)
age_groups = {'0-18': 0, '19-40': 0, '41-65': 0, '65+': 0}

for patient in patients:
    genotype_counts[patient.genotype] += 1
    
    if patient.age <= 18:
        age_groups['0-18'] += 1
    elif patient.age <= 40:
        age_groups['19-40'] += 1  
    elif patient.age <= 65:
        age_groups['41-65'] += 1
    else:
        age_groups['65+'] += 1

print(f'\\n🧬 Répartition génotypes:')
for genotype, count in genotype_counts.items():
    print(f'  {genotype}: {count} patients ({count/50*100:.1f}%)')

print(f'\\n👶 Répartition âges:')
for group, count in age_groups.items():
    print(f'  {group} ans: {count} patients ({count/50*100:.1f}%)')

# Mesurer performance génération mesures
start = time.time()
sim = PhysiologicalSimulator()
measurements = []

for patient in patients[:10]:  # Test sur 10 patients
    for i in range(5):  # 5 mesures chacun
        m = sim.generate_measurement(patient, datetime.now())
        measurements.append(m)

measure_time = time.time() - start
total_measures = len(measurements)

print(f'\\n📊 Génération {total_measures} mesures: {measure_time:.3f}s ({total_measures/measure_time:.1f} mesures/sec)')

# Analyser qualité des mesures
spo2_by_genotype = defaultdict(list)
for i, measurement in enumerate(measurements):
    patient = patients[i // 5]  # Retrouver le patient
    spo2_by_genotype[patient.genotype].append(measurement.spo2_percent)

print(f'\\n🩺 SpO2 moyen par génotype:')
for genotype, spo2_values in spo2_by_genotype.items():
    if spo2_values:
        avg_spo2 = sum(spo2_values) / len(spo2_values)
        print(f'  {genotype}: {avg_spo2:.1f}% (sur {len(spo2_values)} mesures)')

print(f'\\n✅ Analyse terminée - Performance optimale!')
"
```

---

## 🚀 Utilisation avancée

### **Simulation massive 24h**

Pour lancer une vraie simulation de 50+ patients pendant 24h :

```powershell
# Utiliser le script d'intégration complète
python massive_simulation_integration.py --patients 50 --duration 24 --notifications

# Ou utiliser le script de démarrage batch
start_massive_simulation.bat
```

### **Intégration avec dashboard Streamlit**

```powershell
# Démarrer le dashboard interactif
streamlit run monitoring/dashboard_streamlit.py --server.port 8501

# Accéder au dashboard : http://localhost:8501
```

### **Configuration notifications réelles**

```powershell
# Variables d'environnement pour production
set TWILIO_ACCOUNT_SID=your_account_sid
set TWILIO_AUTH_TOKEN=your_auth_token
set TWILIO_FROM_NUMBER=+1234567890
set SMTP_USERNAME=your_email@domain.com
set SMTP_PASSWORD=your_app_password
```

---

## 📞 Support et dépannage

### **Contacts :**
- **Email technique :** christianouragan@gmail.com
- **SMS alertes :** +237695607089

### **Logs et diagnostics :**
- **Logs application :** `logs/massive_simulation.log`
- **Logs base de données :** PostgreSQL logs
- **Métriques temps réel :** Dashboard Streamlit

### **Ressources utiles :**
- Documentation PostgreSQL : https://www.postgresql.org/docs/
- Guide Twilio SMS : https://www.twilio.com/docs/sms
- Streamlit docs : https://docs.streamlit.io/

---

**🏥 Ce simulateur reproduit fidèlement un environnement médical IoT pour la drépanocytose, permettant des tests complets et une formation réaliste du personnel soignant.**
