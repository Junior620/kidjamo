# 🔄 GUIDE COMPLET DE SIMULATION - PIPELINE IOT KIDJAMO
# =====================================================

## PRÉREQUIS
- Docker Desktop installé et en cours d'exécution
- Python 3.8+ installé
- Git installé
- Navigateur web (Chrome/Firefox recommandé)

## ÉTAPE 1: PRÉPARATION DE L'ENVIRONNEMENT (5 minutes)

### 1.1 Naviguer vers le dossier de la pipeline
```powershell
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local
```

### 1.2 Vérifier que Docker fonctionne
```powershell
docker --version
docker-compose --version
```

### 1.3 Activer l'environnement virtuel Python
```powershell
.\venv\Scripts\Activate.ps1
```

## ÉTAPE 2: DÉMARRER LES SERVICES KAFKA (3-5 minutes)

### 2.1 Aller dans le dossier Kafka
```powershell
cd kafka
```

### 2.2 Démarrer Kafka et Zookeeper
```powershell
docker-compose up -d
```

### 2.3 Vérifier que les conteneurs sont actifs
```powershell
docker-compose ps
```
**Résultat attendu:** Vous devriez voir 3 conteneurs (kafka, zookeeper, kafka-ui) avec le statut "Up"

### 2.4 Attendre que Kafka soit prêt
```powershell
Start-Sleep -Seconds 30
```

### 2.5 Retourner au dossier principal
```powershell
cd ..
```

## ÉTAPE 3: DÉMARRER L'API IOT D'INGESTION (2 minutes)

### 3.1 Ouvrir un nouveau terminal PowerShell
```powershell
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local
.\venv\Scripts\Activate.ps1
```

### 3.2 Démarrer l'API IoT
```powershell
python api\iot_ingestion_api.py
```
**Laissez ce terminal ouvert** - l'API IoT doit rester en cours d'exécution

## ÉTAPE 4: DÉMARRER LE PROCESSEUR DE STREAMING (2 minutes)

### 4.1 Ouvrir un troisième terminal PowerShell
```powershell
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local
.\venv\Scripts\Activate.ps1
```

### 4.2 Démarrer le processeur de streaming
```powershell
python streaming\stream_processor.py
```
**Laissez ce terminal ouvert** - le processeur doit rester en cours d'exécution

## ÉTAPE 5: DÉMARRER LE SIMULATEUR IOT (OPTIONNEL) (1 minute)

### 5.1 Ouvrir un quatrième terminal PowerShell
```powershell
cd D:\kidjamo-workspace\data\pipelines\iot_streaming\pipeline_iot_streaming_kafka_local
.\venv\Scripts\Activate.ps1
```

### 5.2 Démarrer le simulateur
```powershell
python simulator\iot_simulator.py
```
**Laissez ce terminal ouvert** - le simulateur génère des données automatiquement

## ÉTAPE 6: VÉRIFIER LES INTERFACES DE MONITORING (1 minute)

### 6.1 Ouvrir dans votre navigateur web:

1. **Kafka UI** : http://localhost:8090
   - Vérifiez que vous voyez les topics Kafka
   - Cherchez le topic "iot-raw-data"

2. **API IoT Health Check** : http://localhost:5000/health
   - Vous devriez voir un JSON avec le statut "healthy"

3. **API IoT Metrics** : http://localhost:5000/metrics
   - Vous devriez voir les métriques de l'API

## ÉTAPE 7: ENVOYER DES DONNÉES DE TEST MANUELLEMENT (2 minutes)

### 7.1 Utiliser curl pour envoyer des données IoT
```powershell
curl -X POST http://localhost:5000/api/iot/data `
  -H "Content-Type: application/json" `
  -d '{
    "patient_id": "123e4567-e89b-12d3-a456-426614174000",
    "device_id": "device_bracelet_001",
    "timestamp": "2025-08-19T10:00:00.000Z",
    "measurements": {
      "heart_rate": 95,
      "respiratory_rate": 20,
      "spo2": 94.5,
      "body_temperature": 37.8,
      "ambient_temperature": 28.0,
      "hydration_level": 75.2,
      "activity_level": 4,
      "heat_index": 32.1
    },
    "location": {
      "latitude": 14.6928,
      "longitude": -17.4467
    }
  }'
```

### 7.2 Alternative avec Postman:
- Méthode: POST
- URL: http://localhost:5000/api/iot/data
- Headers: Content-Type: application/json
- Body: Utilisez le JSON ci-dessus

## ÉTAPE 8: VÉRIFIER LE FLUX DE DONNÉES (5-10 minutes)

### 8.1 Dans Kafka UI (http://localhost:8090):
1. Allez dans "Topics" → "iot-raw-data"
2. Cliquez sur "Messages"
3. Vous devriez voir les messages JSON envoyés

### 8.2 Vérifier les fichiers du Data Lake:
```powershell
# Vérifier les données brutes
ls data_lake\raw\

# Vérifier les données bronze (nettoyées)
ls data_lake\bronze\

# Vérifier les données silver (enrichies)
ls data_lake\silver\

# Vérifier les données gold (agrégées)
ls data_lake\gold\
```

### 8.3 Vérifier les logs:
```powershell
# Logs de l'API IoT
Get-Content logs\api.log -Tail 20

# Logs du processeur de streaming
Get-Content logs\streaming.log -Tail 20

# Logs du simulateur (si activé)
Get-Content logs\simulator.log -Tail 20
```

## ÉTAPE 9: SCENARIOS DE TEST AVANCÉS (10-15 minutes)

### 9.1 Test d'alerte de température élevée:
```powershell
curl -X POST http://localhost:5000/api/iot/data `
  -H "Content-Type: application/json" `
  -d '{
    "patient_id": "456e7890-e89b-12d3-a456-426614174001",
    "device_id": "device_bracelet_002",
    "timestamp": "2025-08-19T10:15:00.000Z",
    "measurements": {
      "heart_rate": 110,
      "respiratory_rate": 25,
      "spo2": 89.0,
      "body_temperature": 39.2,
      "ambient_temperature": 35.0,
      "hydration_level": 65.0,
      "activity_level": 1,
      "heat_index": 42.0
    }
  }'
```

### 9.2 Test de SpO2 faible (alerte critique):
```powershell
curl -X POST http://localhost:5000/api/iot/data `
  -H "Content-Type: application/json" `
  -d '{
    "patient_id": "789e0123-e89b-12d3-a456-426614174002",
    "device_id": "device_bracelet_003",
    "timestamp": "2025-08-19T10:30:00.000Z",
    "measurements": {
      "heart_rate": 120,
      "respiratory_rate": 28,
      "spo2": 85.0,
      "body_temperature": 38.5,
      "ambient_temperature": 32.0,
      "hydration_level": 55.0,
      "activity_level": 2,
      "heat_index": 38.5
    }
  }'
```

### 9.3 Test de déshydratation:
```powershell
curl -X POST http://localhost:5000/api/iot/data `
  -H "Content-Type: application/json" `
  -d '{
    "patient_id": "abc12345-e89b-12d3-a456-426614174003",
    "device_id": "device_bracelet_004",
    "timestamp": "2025-08-19T10:45:00.000Z",
    "measurements": {
      "heart_rate": 105,
      "respiratory_rate": 22,
      "spo2": 92.0,
      "body_temperature": 37.5,
      "ambient_temperature": 30.0,
      "hydration_level": 45.0,
      "activity_level": 3,
      "heat_index": 35.0
    }
  }'
```

## ÉTAPE 10: MONITORING ET OBSERVATION (CONTINU)

### 10.1 Surveiller en temps réel:
- **Kafka UI**: Messages en temps réel dans les topics
- **Logs des applications**: Activité de traitement
- **Dossiers du Data Lake**: Nouveaux fichiers créés
- **Métriques API**: Nombre de requêtes et erreurs

### 10.2 Indicateurs de succès à observer:
1. ✅ Messages visibles dans Kafka UI
2. ✅ Fichiers JSON créés dans data_lake/raw/
3. ✅ Fichiers traités dans data_lake/bronze/
4. ✅ Alertes générées pour valeurs critiques
5. ✅ Logs sans erreurs dans tous les services

## ÉTAPE 11: ARRÊTER LA SIMULATION

### 11.1 Arrêter les services Python:
- Appuyez sur `Ctrl+C` dans chaque terminal où un service Python tourne

### 11.2 Arrêter Kafka:
```powershell
cd kafka
docker-compose down
```

### 11.3 Nettoyer (optionnel):
```powershell
# Supprimer les volumes Kafka pour repartir à zéro
docker-compose down -v

# Nettoyer les données du Data Lake
Remove-Item -Recurse -Force data_lake\raw\*
Remove-Item -Recurse -Force data_lake\bronze\*
Remove-Item -Recurse -Force data_lake\silver\*
Remove-Item -Recurse -Force data_lake\gold\*
```

## DÉPANNAGE COURANT

### Problème: Kafka ne démarre pas
**Solution**: Vérifiez que Docker Desktop est démarré et que les ports 9092, 2181, 8090 ne sont pas utilisés

### Problème: API IoT ne répond pas
**Solution**: Vérifiez que l'environnement virtuel est activé et que le port 5000 est libre

### Problème: Pas de données dans le Data Lake
**Solution**: Vérifiez que tous les services sont démarrés et que Kafka reçoit les messages

### Problème: Erreurs dans les logs
**Solution**: Vérifiez les dépendances Python avec `pip list` dans l'environnement virtuel

## RÉSULTATS ATTENDUS

Après une simulation réussie, vous devriez avoir:
- Des messages IoT transitant en temps réel dans Kafka
- Des fichiers de données dans le Data Lake (raw → bronze → silver → gold)
- Des alertes générées pour les valeurs critiques
- Des métriques de performance dans l'API
- Un flux de données complet de bout en bout simulant un bracelet IoT réel

## TEMPS TOTAL ESTIMÉ
- **Première fois**: 30-45 minutes
- **Simulations suivantes**: 10-15 minutes
