# 🏥 SIMULATEUR MASSIF IoT PATIENTS KIDJAMO

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture du système](#architecture-du-système)
3. [Composants principaux](#composants-principaux)
4. [Installation et prérequis](#installation-et-prérequis)
5. [Exécution manuelle étape par étape](#exécution-manuelle-étape-par-étape)
6. [Configuration avancée](#configuration-avancée)
7. [Monitoring et alertes](#monitoring-et-alertes)
8. [Dépannage](#dépannage)
9. [Exemples d'utilisation](#exemples-dutilisation)

---

## 🎯 Vue d'ensemble

Ce simulateur massif génère des données IoT médicales réalistes pour **50+ patients virtuels** atteints de drépanocytose, avec :

- **Mesures physiologiques toutes les 5 secondes** (SpO2, FC, température, etc.)
- **Détection automatique d'alertes médicales** critiques
- **Notifications SMS et Email** en temps réel
- **Dashboard interactif** pour surveillance temps réel
- **Simulation continue 24h** avec gestion des crises drépanocytaires

### 🎪 Cas d'usage principaux

- **Tests de charge** du système IoT médical
- **Validation des algorithmes** de détection d'alertes
- **Formation du personnel** médical sur interface de monitoring
- **Démonstrations** clients et investisseurs
- **Développement et débogage** des pipelines de données

---

## 🏗️ Architecture du système

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   50+ PATIENTS  │    │  BASE DONNÉES    │    │   DASHBOARD     │
│   VIRTUELS      │───▶│   PostgreSQL     │───▶│   Streamlit     │
│                 │    │                  │    │                 │
│ • Profils réels │    │ • Patients       │    │ • Graphiques    │
│ • Cycles circa- │    │ • Measurements   │    │ • Filtres       │
│ • Crises médi-  │    │ • Alerts         │    │ • KPIs          │
│   cales         │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌────────▼────────┐             │
         └─────────────▶│  MOTEUR ALERTES │◀────────────┘
                        │                 │
                        │ • Seuils médi-  │
                        │   caux          │
                        │ • Notifications │
                        │ • Escalation    │
                        └─────────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │     NOTIFICATIONS        │
                    │                          │
                    │ 📱 SMS → +237695607089   │
                    │ 📧 Email → christian...  │
                    └──────────────────────────┘
```

---

## 🧩 Composants principaux

### 1. **Générateur de Patients** (`PatientGenerator`)
- Crée 50+ profils patients diversifiés
- Génotypes : SS (45%), SC (30%), AS (20%), Sβ0 (5%)
- Âges : 5-65 ans avec distribution réaliste
- Paramètres physiologiques de base selon âge/génotype

### 2. **Simulateur Physiologique** (`PhysiologicalSimulator`)
- Génère mesures toutes les 5 secondes
- Cycles circadiens (variations jour/nuit)
- Facteurs environnementaux (température ambiante)
- Simulation de crises drépanocytaires
- Bruit physiologique réaliste

### 3. **Moteur d'Alertes** (`AlertEngine`)
- Analyse en temps réel des mesures
- Seuils médicaux adaptés au génotype
- Détection de patterns multi-paramètres
- Système de cooldown (évite spam)
- Classification par gravité (info/warn/alert/critical)

### 4. **Service de Notifications** (`NotificationService`)
- SMS via Twilio vers +237695607089
- Emails SMTP vers christianouragan@gmail.com
- Circuit breaker (désactivation si échecs répétés)
- Templates adaptés selon gravité

### 5. **Gestionnaire Base de Données** (`DatabaseManager`)
- Insertion batch haute performance (1000 mesures/lot)
- Gestion des connexions PostgreSQL
- Flush automatique selon seuils/timeout
- Tables : patients, measurements, alerts

### 6. **Dashboard Temps Réel** (`realtime_dashboard_advanced.py`)
- Interface Streamlit responsive
- Filtres multi-critères (génotype, âge, alertes)
- Graphiques Plotly interactifs
- Auto-refresh configurable
- Vue détaillée par patient

---

## 💻 Installation et prérequis

### Prérequis système
```bash
# PostgreSQL 12+ avec base 'kidjamo'
# Python 3.8+
# 4GB RAM minimum (8GB recommandé)
# Connexion internet (notifications)
```

### Installation des dépendances
```bash
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local

# Installation packages Python
pip install -r requirements_massive_simulation.txt

# Ou installation manuelle des packages critiques
pip install streamlit plotly pandas psycopg2-binary twilio requests
```

### Configuration base de données
```sql
-- Vérifier que les tables existent dans PostgreSQL
SELECT tablename FROM pg_tables WHERE schemaname = 'public' 
AND tablename IN ('patients', 'measurements', 'alerts', 'users');

-- Si manquantes, exécuter le schéma :
-- \i D:\kidjamo-workspace\data\schemas\sql\kidjamo_main_database_v2.sql
```

### Configuration notifications (optionnel)
```json
// Éditer config/massive_simulation_config.json
{
  "notifications": {
    "sms": {
      "account_sid": "VOTRE_TWILIO_SID",
      "auth_token": "VOTRE_TWILIO_TOKEN", 
      "from_number": "VOTRE_NUMERO_TWILIO"
    },
    "email": {
      "username": "votre.email@gmail.com",
      "password": "mot_de_passe_application"
    }
  }
}
```

---

## 🛠️ Exécution manuelle étape par étape

### Étape 1 : Préparation de l'environnement

```bash
# 1.1 - Naviguer vers le dossier du projet
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local

# 1.2 - Activer environnement virtuel (si existant)
# Windows
venv\Scripts\activate
# Linux/MacOS  
source venv/bin/activate

# 1.3 - Vérifier connexion base de données
python -c "import psycopg2; conn=psycopg2.connect(host='localhost',port='5432',database='kidjamo-db',user='postgres',password='kidjamo@'); print('✅ DB OK'); conn.close()"
```

**🎯 But de cette étape :** S'assurer que l'environnement est prêt et que la base de données est accessible.

### Étape 2 : Test des modules individuels

```bash
# 2.1 - Test du générateur de patients
python -c "
from simulator.massive_patient_simulator_combined import PatientGenerator
gen = PatientGenerator()
patients = gen.generate_patient_batch(5)
print(f'✅ Généré {len(patients)} patients de test')
for p in patients[:2]:
    print(f'  - {p.first_name} {p.last_name}, {p.age}ans, {p.genotype}')
"

# 2.2 - Test du simulateur physiologique  
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
gen = PatientGenerator()
sim = PhysiologicalSimulator()
patient = gen.generate_patient_batch(1)[0]
measurement = sim.generate_measurement(patient, datetime.now())
print(f'✅ Mesure générée: SpO2={measurement.spo2_percent}%, FC={measurement.heart_rate_bpm}bpm')
"

# 2.3 - Test du moteur d'alertes
python -c "
from simulator.massive_patient_simulator_combined import *
from datetime import datetime
# Simulation mesure critique
measurement = MeasurementRecord(
    measurement_id=None, patient_id='test', device_id='test',
    message_id='test', recorded_at=datetime.now(), received_at=datetime.now(),
    heart_rate_bpm=85, respiratory_rate_min=18, spo2_percent=85.0,
    temperature_celsius=39.2, ambient_temp_celsius=28.0, hydration_percent=35.0,
    activity_level=2, heat_index_celsius=39.5, pain_scale=8,
    battery_percent=25, signal_quality=75
)
patient = PatientProfile(
    patient_id='test', user_id='test', first_name='Test', last_name='Patient',
    age=25, gender='M', genotype='SS', weight_kg=70.0, height_cm=175.0,
    device_id='test', base_heart_rate=75, base_spo2_range=(92,96),
    base_temperature=36.8, base_respiratory_rate=16, base_hydration=70.0
)
engine = AlertEngine(None)
alerts = engine.analyze_measurement(measurement, patient)
print(f'✅ {len(alerts)} alertes détectées pour mesures critiques')
for alert in alerts:
    print(f'  - {alert.severity}: {alert.title}')
"
```

**🎯 But de cette étape :** Vérifier que tous les modules fonctionnent individuellement avant l'intégration.

### Étape 3 : Démarrage du dashboard (optionnel)

```bash
# 3.1 - Lancer le dashboard en arrière-plan
# Terminal séparé ou nouvelle session
streamlit run monitoring/realtime_dashboard_advanced.py --server.port 8501 --server.address 0.0.0.0

# 3.2 - Vérifier accès dashboard
# Ouvrir http://localhost:8501 dans le navigateur
# Vous devriez voir l'interface KIDJAMO IoT Dashboard
```

**🎯 But de cette étape :** Démarrer l'interface de monitoring pour visualiser les données en temps réel.

### Étape 4 : Test rapide avec 5 patients

```bash
# 4.1 - Test simulation courte (5 patients, 5 minutes)
python massive_simulation_integration.py \
    --patients 5 \
    --duration 0.083 \
    --test-alerts \
    --db-host localhost \
    --db-port 5432 \
    --db-name kidjamo-db \
    --db-user postgres \
    --db-password kidjamo@ \

# 4.2 - Observer les logs en temps réel
# Vous devriez voir :
# - Création de 5 patients
# - Insertion en base de données
# - Génération de mesures toutes les 5 secondes  
# - Détection d'alertes (si crises simulées)
# - Métriques de performance
```

**🎯 But de cette étape :** Valider le fonctionnement complet sur un échantillon réduit avant la simulation massive.

### Étape 5 : Vérification des données en base

```sql
-- 5.1 - Connecter à PostgreSQL et vérifier les patients créés
psql -h localhost -p 5432 -d kidjamo -U postgres

-- 5.2 - Vérifier insertion patients
SELECT COUNT(*) as nb_patients FROM patients;
SELECT p.patient_id, u.first_name, u.last_name, p.genotype, 
       EXTRACT(YEAR FROM AGE(p.birth_date)) as age
FROM patients p 
JOIN users u ON p.user_id = u.user_id 
ORDER BY u.first_name;

-- 5.3 - Vérifier mesures générées
SELECT COUNT(*) as nb_measurements FROM measurements;
SELECT patient_id, recorded_at, heart_rate_bpm, spo2_percent, 
       temperature_celsius, pain_scale
FROM measurements 
ORDER BY recorded_at DESC 
LIMIT 10;

-- 5.4 - Vérifier alertes (si générées)
SELECT COUNT(*) as nb_alerts FROM alerts;
SELECT a.patient_id, u.first_name, u.last_name, a.severity, 
       a.title, a.created_at
FROM alerts a
JOIN patients p ON a.patient_id = p.patient_id
JOIN users u ON p.user_id = u.user_id
ORDER BY a.created_at DESC;
```

**🎯 But de cette étape :** Confirmer que les données sont correctement insérées et structurées en base.

### Étape 6 : Simulation massive complète

```bash
# 6.1 - Lancement simulation 50 patients, 24h
python massive_simulation_integration.py \
    --patients 50 \
    --duration 24 \
    --test-alerts \
    --config-file config/massive_simulation_config.json

# 6.2 - Monitoring en temps réel
# Ouvrir plusieurs terminaux pour :
# - Logs simulation : tail -f massive_simulation.log
# - Dashboard web : http://localhost:8501  
# - Monitoring base : psql et requêtes périodiques

# 6.3 - Commandes de contrôle pendant l'exécution
# Ctrl+C : Arrêt propre avec sauvegarde
# ps aux | grep python : Voir processus actifs
# htop : Monitoring ressources système
```

**🎯 But de cette étape :** Lancer la simulation massive complète pour les tests de charge et validation système.

### Étape 7 : Arrêt et analyse des résultats

```bash
# 7.1 - Arrêt propre (Ctrl+C ou fin automatique)
# Le système génère automatiquement :
# - Flush final de toutes les données en base
# - Rapport de session dans reports/
# - Statistiques finales dans les logs

# 7.2 - Analyse des rapports générés
ls -la reports/
cat reports/final_report_*.json

# 7.3 - Vérification volumes de données
psql -h localhost -p 5432 -d kidjamo -U postgres -c "
SELECT 
    (SELECT COUNT(*) FROM patients) as patients,
    (SELECT COUNT(*) FROM measurements) as measurements,
    (SELECT COUNT(*) FROM alerts) as alerts,
    (SELECT COUNT(*) FROM alerts WHERE severity='critical') as critical_alerts;
"
```

**🎯 But de cette étape :** Analyser les résultats et valider que les objectifs de simulation ont été atteints.

---

## ⚙️ Configuration avancée

### Personnalisation des seuils médicaux

```json
// config/massive_simulation_config.json
{
  "medical_thresholds": {
    "spo2_critical_ss": 85,        // SpO2 critique drépanocytose SS
    "spo2_critical_general": 88,   // SpO2 critique général  
    "temperature_fever": 38.0,     // Seuil fièvre
    "heart_rate_tachycardia_adult": 120,  // Tachycardie adulte
    "pain_severe": 7,              // Douleur sévère
    "dehydration_threshold": 40,   // Déshydratation critique
    "battery_critical": 15         // Batterie critique
  }
}
```

### Optimisation des performances

```json
{
  "performance": {
    "thread_pool_size": 50,        // Threads patients simultanés
    "memory_limit_mb": 2048,       // Limite mémoire
    "batch_size": 1000,            // Taille lots insertion DB
    "flush_interval_seconds": 30   // Fréquence flush DB
  }
}
```

### Configuration notifications avancée

```json
{
  "notifications": {
    "sms": {
      "enabled": true,
      "cooldown_minutes": 5,       // Anti-spam SMS
      "max_per_hour": 20           // Limite horaire
    },
    "email": {
      "enabled": true,
      "template": "advanced",      // Template HTML riche
      "include_vitals_chart": true // Graphique intégré
    }
  }
}
```

---

## 📊 Monitoring et alertes

### Types d'alertes médicales

| Type | Seuil | Gravité | Action |
|------|-------|---------|---------|
| **SpO2 Critique** | < 85% (SS) / < 88% | Critical | SMS + Email immédiat |
| **Fièvre Élevée** | ≥ 39.5°C | Critical | Surveillance renforcée |
| **Crise Suspectée** | Multi-paramètres | Critical | Protocole d'urgence |
| **Douleur Sévère** | ≥ 7/10 | Alert | Antalgie adaptée |
| **Déshydratation** | < 40% | Alert | Réhydratation |
| **Batterie Faible** | < 15% | Warn | Recharge dispositif |

### Métriques système surveillées

```bash
# Métriques temps réel affichées toutes les minutes
📊 MÉTRIQUES TEMPS RÉEL:
   ⏱️  Uptime: 2.3h
   👥 Workers actifs: 50/50
   📈 Mesures totales: 138,240
   🚨 Alertes totales: 23
   ⚡ Taux mesures: 60,000/h (attendu: 60,000/h)
   📊 Efficacité: 100.0%
   🔥 Patients en crise: 3/50
```

### Dashboard - Fonctionnalités détaillées

#### Vue Patients
- **Tableau global** avec statut temps réel
- **Filtres** : génotype, âge, alertes actives
- **Sélection multiple** pour analyses comparatives
- **Codes couleur** selon gravité des paramètres

#### Vue Analyses  
- **Graphiques multi-patients** synchronisés
- **Évolution temporelle** des signes vitaux
- **Corrélations** entre paramètres
- **Zoom/pan** interactif sur les données

#### Vue Alertes
- **Dashboard temps réel** des alertes actives
- **Répartition par gravité** (camembert)
- **Historique détaillé** avec contexte médical
- **Actions recommandées** selon protocoles

---

## 🔧 Dépannage

### Problèmes courants

#### 1. Erreur connexion PostgreSQL
```bash
# Symptômes : "connection refused" ou "authentication failed"
# Solutions :
# - Vérifier que PostgreSQL est démarré
sudo service postgresql start  # Linux
net start postgresql-x64-12    # Windows

# - Vérifier paramètres connexion
psql -h localhost -p 5432 -d kidjamo -U postgres

# - Créer base si manquante
createdb -h localhost -p 5432 -U postgres kidjamo
```

#### 2. Modules Python manquants
```bash
# Symptômes : "ModuleNotFoundError: No module named '...'"
# Solution : Réinstaller dépendances
pip install -r requirements_massive_simulation.txt

# Installation packages individuels si échec
pip install streamlit plotly pandas psycopg2-binary twilio
```

#### 3. Dashboard Streamlit ne démarre pas
```bash
# Symptômes : Port 8501 occupé ou erreur Streamlit
# Solutions :
# - Tuer processus existant
pkill -f streamlit  # Linux/MacOS
taskkill /F /IM python.exe  # Windows (attention : tue tous Python)

# - Changer port
streamlit run monitoring/realtime_dashboard_advanced.py --server.port 8502

# - Mode debug
streamlit run monitoring/realtime_dashboard_advanced.py --logger.level debug
```

#### 4. Performance dégradée
```bash
# Symptômes : Efficacité < 90%, workers arrêtés
# Solutions :
# - Réduire nombre patients
python massive_simulation_integration.py --patients 25

# - Augmenter intervalle flush DB  
# Éditer config : "flush_interval_seconds": 60

# - Monitoring ressources
htop  # Linux/MacOS
taskmgr  # Windows
```

#### 5. Notifications non reçues
```bash
# SMS Twilio
# - Vérifier crédits compte Twilio
# - Tester numéro source validé
# - Consulter logs Twilio Console

# Email SMTP
# - Vérifier mot de passe application (pas mot de passe compte)
# - Tester avec Gmail : https://myaccount.google.com/apppasswords
# - Vérifier anti-spam/quarantaine
```

### Logs et debugging

```bash
# Logs principaux
tail -f massive_simulation.log     # Logs temps réel
grep "ERROR" massive_simulation.log # Erreurs seulement
grep "🚨" massive_simulation.log    # Alertes générées

# Logs détaillés par composant
export PYTHONPATH=$PYTHONPATH:.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Puis relancer simulation
"

# Base de données - Requêtes diagnostiques
psql -h localhost -p 5432 -d kidjamo -U postgres -c "
SELECT 
  schemaname, tablename, n_tup_ins as insertions, n_tup_upd as updates
FROM pg_stat_user_tables 
WHERE tablename IN ('patients', 'measurements', 'alerts');
"
```

---

## 🚀 Exemples d'utilisation

### Exemple 1 : Test de charge système
```bash
# Objectif : Valider 100 patients simultanés pendant 2h
python massive_simulation_integration.py \
    --patients 100 \
    --duration 2 \
    --no-dashboard \
    > test_charge_100_patients.log 2>&1 &

# Monitoring ressources
watch -n 30 'ps aux | grep python && free -h && df -h'
```

### Exemple 2 : Validation alertes critiques
```bash
# Objectif : Générer alertes pour validation protocoles
python massive_simulation_integration.py \
    --patients 10 \
    --duration 1 \
    --test-alerts

# Forcer déclenchement crises supplémentaires
python -c "
from simulator.massive_patient_simulator_combined import *
controller = MassivePatientSimulationController(10)
controller.initialize_patients()
controller.start_simulation()
controller.force_crisis_simulation(5)  # 5 crises forcées
input('Appuyez sur Entrée pour arrêter...')
controller.stop_simulation()
"
```

### Exemple 3 : Démo client/investisseur
```bash
# Objectif : Présentation interactive avec dashboard
python massive_simulation_integration.py \
    --patients 25 \
    --duration 0 \
    --test-alerts \
    --config-file config/demo_config.json

# Avec configuration démo spéciale :
{
  "simulation": {
    "patient_count": 25,
    "crisis_test_patients": 2,
    "enable_demo_scenarios": true
  },
  "notifications": {
    "sms": { "enabled": false },
    "email": { "enabled": false }
  }
}
```

### Exemple 4 : Formation personnel médical
```bash
# Objectif : Scénarios pédagogiques variés
python massive_simulation_integration.py \
    --patients 15 \
    --duration 4 \
    --config-file config/formation_config.json

# Avec scénarios programmés :
# - Crise drépanocytaire évolutive
# - Épisode infectieux avec fièvre
# - Déshydratation progressive  
# - Problèmes techniques dispositifs
```

---

## 📈 Données attendues

### Volume de données généré

| Durée | Patients | Mesures | Alertes estimées | Taille DB |
|-------|----------|---------|------------------|-----------|
| 1h | 50 | 36,000 | 5-15 | ~50 MB |
| 6h | 50 | 216,000 | 20-50 | ~300 MB |
| 24h | 50 | 864,000 | 50-200 | ~1.2 GB |
| 7j | 50 | 6,048,000 | 300-1000 | ~8 GB |

### Répartition alertes typique (24h, 50 patients)

- **Critical (🔴)** : 5-15 alertes (SpO2 critique, crises)
- **Alert (🟠)** : 20-40 alertes (fièvre, douleur sévère)  
- **Warn (🟡)** : 30-60 alertes (batterie, signal faible)
- **Info (🔵)** : 50-100 alertes (informatives)

### Performance système optimale

- **Efficacité mesures** : 95-100%
- **Latence insertions DB** : < 100ms par batch
- **Temps réponse dashboard** : < 2s
- **Délai notifications** : < 30s pour alertes critiques

---

## 🏁 Conclusion

Ce système de simulation massive permet de :

✅ **Tester la robustesse** de votre infrastructure IoT médicale  
✅ **Valider les algorithmes** de détection d'alertes  
✅ **Former le personnel** sur les outils de monitoring  
✅ **Démontrer les capacités** du système KIDJAMO  
✅ **Optimiser les performances** avant déploiement réel  

Le simulateur génère des données médicalement cohérentes avec des patterns réalistes de drépanocytose, permettant une validation complète des workflows de surveillance de patients.

---

**📞 Support :** Pour toute question ou problème, consultez les logs détaillés et la section dépannage de ce README.
