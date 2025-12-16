# 🚀 Guide de Démarrage Rapide - Pipeline IoT Streaming Kidjamo

## Vue d'ensemble

Cette pipeline simule et traite en temps réel les données de bracelets médicaux IoT pour le suivi de patients drépanocytaires.

```
📱 Bracelets Simulés → 🌐 API FastAPI → 📊 Kafka → ⚡ PySpark → 💾 Data Lake Local
```

## ⚡ Démarrage Express (5 minutes)

### 1. Prérequis
```bash
# Vérifier Docker
docker --version
docker-compose --version

# Vérifier Python
python --version  # 3.8+
```

### 2. Installation
```bash
# Cloner et naviguer
cd pipeline_iot_streaming_kafka_local

# Windows
.\start_pipeline.ps1 -WithSimulator

# Linux/Mac
chmod +x start_pipeline.sh
./start_pipeline.sh --with-simulator
```

### 3. Vérification
- **API**: http://localhost:8001/docs
- **Kafka UI**: http://localhost:8090
- **Santé**: http://localhost:8001/health

---

## 📊 Points d'accès

| Service | URL | Description |
|---------|-----|-------------|
| **API Documentation** | http://localhost:8001/docs | Interface Swagger |
| **API Health** | http://localhost:8001/health | Statut système |
| **Kafka UI** | http://localhost:8090 | Interface Kafka |
| **Monitoring** | `streamlit run monitoring/realtime_dashboard.py` | Dashboard temps réel |

---

## 🔄 Workflow de développement

### Cycle normal
```bash
# 1. Démarrer la pipeline
.\start_pipeline.ps1 -WithSimulator

# 2. Surveiller les logs
tail -f logs/api.log
tail -f logs/streaming.log
tail -f logs/simulator.log

# 3. Tester
python tests/test_integration.py

# 4. Arrêter proprement
.\stop_pipeline.ps1
```

### Redémarrage propre
```bash
# Arrêt avec nettoyage
.\stop_pipeline.ps1 -CleanData

# Redémarrage
.\start_pipeline.ps1 -CleanStart -WithSimulator
```

---

## 📁 Structure des données

```
data_lake/
├── raw/                    # Données brutes IoT
│   └── iot_measurements/
├── bronze/                 # Données nettoyées
│   ├── iot_aggregations/   # Agrégations 5min
│   ├── iot_alerts/         # Toutes alertes
│   └── device_status/      # Statut dispositifs
└── silver/                 # Données enrichies
    └── critical_alerts/    # Alertes critiques
```

---

## 🚨 Alertes automatiques

Le système génère automatiquement des alertes pour :

| Condition | Seuil | Gravité |
|-----------|-------|---------|
| **SpO2 critique** | < 90% | 🔴 CRITICAL |
| **Fréquence cardiaque** | < 50 ou > 150 bpm | 🔴 CRITICAL |
| **Fièvre élevée** | > 39°C | 🟠 HIGH |
| **Crise drépanocytaire** | SpO2 < 92% + T° > 38°C | 🔴 CRITICAL |

---

## 🔧 Configuration

### Seuils médicaux (config/.env)
```env
CRITICAL_SPO2_THRESHOLD=90
CRITICAL_HEART_RATE_MIN=50
CRITICAL_HEART_RATE_MAX=150
FEVER_THRESHOLD=38.0
```

### Simulateur
```env
SIMULATOR_PATIENTS_COUNT=5
SIMULATOR_INTERVAL_SECONDS=60
SIMULATOR_DURATION_MINUTES=30
```

---

## 📈 Monitoring en temps réel

### Dashboard Streamlit
```bash
# Lancer le dashboard
streamlit run monitoring/realtime_dashboard.py

# Accès: http://localhost:8501
```

**Fonctionnalités :**
- ✅ Graphiques temps réel SpO2/FC
- 🚨 Alertes par gravité
- 👥 État patients actifs
- 📊 Métriques qualité signal

---

## 🧪 Tests et validation

### Tests d'intégration
```bash
# Tests complets
python tests/test_integration.py

# Test de charge
pytest tests/test_integration.py::test_11_load_test -v
```

### Test manuel API
```bash
# Envoyer une mesure test
curl -X POST http://localhost:8001/iot/measurements \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "test-device",
    "patient_id": "test-patient",
    "timestamp": "2025-01-18T10:00:00",
    "measurements": {
      "freq_card": 75,
      "spo2_pct": 98.5,
      "temp_corp": 36.8
    }
  }'
```

---

## 🔍 Debugging

### Logs importants
```bash
# API
tail -f logs/api.log

# Streaming (erreurs critiques)
tail -f logs/streaming.log

# Kafka (connexions)
docker logs kidjamo-kafka

# Simulateur (données générées)
tail -f logs/simulator.log
```

### Commandes de diagnostic
```bash
# Vérifier topics Kafka
docker exec kidjamo-kafka kafka-topics --bootstrap-server localhost:9092 --list

# Voir messages en temps réel
docker exec kidjamo-kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic kidjamo-iot-measurements --from-beginning

# État des containers
docker ps
```

---

## ⚠️ Résolution de problèmes

### Problème: API non accessible
```bash
# Vérifier le port
netstat -an | findstr 8001

# Redémarrer
.\stop_pipeline.ps1
.\start_pipeline.ps1
```

### Problème: Kafka ne démarre pas
```bash
# Nettoyer volumes Docker
docker-compose -f kafka/docker-compose.yml down -v
docker system prune -f

# Redémarrer
.\start_pipeline.ps1
```

### Problème: Streaming n'écrit pas
```bash
# Vérifier checkpoints
ls checkpoints/

# Nettoyer et redémarrer
.\stop_pipeline.ps1 -CleanData
.\start_pipeline.ps1 -CleanStart
```

---

## 🎯 Prochaines étapes

1. **Intégration avec votre DB** : Remplacer le data lake local par PostgreSQL
2. **Alertes temps réel** : Intégrer avec votre système d'alertes
3. **Authentification** : Ajouter JWT/OAuth pour production
4. **Monitoring avancé** : Métriques Prometheus/Grafana
5. **Haute disponibilité** : Cluster Kafka multi-noeuds

---

## 📞 Support

En cas de problème :
1. Consulter les logs : `logs/`
2. Vérifier la santé : http://localhost:8001/health
3. Relancer les tests : `python tests/test_integration.py`
4. Redémarrage propre : `stop_pipeline.ps1 -CleanData && start_pipeline.ps1 -CleanStart`
