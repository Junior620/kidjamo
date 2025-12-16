# 📡 ARCHITECTURE IoT → CLOUD → PIPELINE KIDJAMO

## 🔄 FLUX COMPLET DES DONNÉES

```
[Capteur IoT Patient] 
    ↓ (HTTPS/MQTT sécurisé)
[🌩️ NIVEAU CLOUD - INGESTION]
    ↓
[📦 VOTRE PIPELINE KIDJAMO]
    ↓
[🗄️ BASE DE DONNÉES]
    ↓
[🚨 ALERTES MÉDICALES]
```

## 🌩️ NIVEAU CLOUD - AVANT VOTRE PIPELINE

### **1. API GATEWAY (Point d'entrée)**
**Service :** AWS API Gateway / Azure API Management  
**Rôle :** Premier point de contact cloud
- ✅ Authentification des capteurs IoT
- ✅ Validation des certificats
- ✅ Rate limiting (éviter surcharge)
- ✅ Routage vers services appropriés

**Format reçu du capteur :**
```json
{
  "device_id": "device-001",
  "patient_id": "patient-123",
  "timestamp": "2025-08-18T10:30:00Z",
  "vitals": {
    "spo2": 94.2,
    "heart_rate": 85,
    "temperature": 37.1,
    "ambient_temp": 23.5,
    "respiratory_rate": 18,
    "hydration_pct": 82.5,
    "activity_level": 3,
    "pain_scale": 2
  },
  "metadata": {
    "battery_level": 78,
    "signal_quality": 95,
    "firmware_version": "v2.1.3"
  }
}
```

### **2. MESSAGE BROKER (File d'attente)**
**Service :** AWS SQS/Kinesis / Azure Service Bus  
**Rôle :** Buffer entre IoT et pipeline
- ✅ File d'attente haute disponibilité
- ✅ Déduplication des messages
- ✅ Retry automatique en cas d'échec
- ✅ Scaling automatique selon le volume

**Pourquoi nécessaire :**
- Les capteurs IoT envoient en continu
- Votre pipeline traite par batch
- Évite la perte de données si pipeline temporairement en panne

### **3. INGESTION SERVICE (Collecteur)**
**Service :** Fonction Lambda / Azure Functions  
**Rôle :** Préparer les données pour votre pipeline
- ✅ Validation format JSON
- ✅ Enrichissement avec métadonnées
- ✅ Stockage temporaire (Landing zone)
- ✅ Déclenchement de votre pipeline

## 📦 VOTRE PIPELINE KIDJAMO - NIVEAU 3

### **Étape LANDING** (Point d'entrée de votre pipeline)
**C'est ICI que votre pipeline commence !**

```python
# ingestion/jobs/01_to_raw.py
def process_iot_data():
    # Récupère les données depuis la Landing zone
    raw_data = read_from_landing_zone()
    
    # Votre pipeline commence ici
    validated_data = validate_iot_data(raw_data)
    store_to_raw(validated_data)
```

### **Architecture physique recommandée :**

#### **🔧 OPTION A : Architecture Serverless (Recommandée)**
```
[Capteur IoT] 
    ↓ HTTPS POST
[AWS API Gateway] 
    ↓ Trigger
[AWS Lambda - Ingestion] 
    ↓ Store to
[AWS S3 - Landing Zone] 
    ↓ Event Trigger
[🚀 VOTRE PIPELINE Kidjamo]
    ↓ Process & Store
[PostgreSQL RDS/Aurora]
    ↓ Alerts
[AWS SNS → Teams médicales]
```

**Avantages :**
- ✅ Scaling automatique
- ✅ Pas de serveurs à gérer
- ✅ Paiement à l'usage
- ✅ Haute disponibilité native

#### **🖥️ OPTION B : Architecture Container (Alternative)**
```
[Capteur IoT] 
    ↓ HTTPS POST
[Load Balancer] 
    ↓
[API Container - Ingestion] 
    ↓ Kafka/RabbitMQ
[🚀 Pipeline Container Kidjamo]
    ↓
[PostgreSQL Container/Cloud]
```

## 🔧 CONFIGURATION CAPTEUR IoT

### **Configuration réseau du capteur :**
```json
{
  "cloud_endpoint": "https://api.kidjamo.health/v1/vitals",
  "auth_method": "certificate",
  "transmission_interval": 30,
  "batch_size": 10,
  "retry_policy": {
    "max_retries": 3,
    "backoff_ms": 1000
  },
  "emergency_thresholds": {
    "spo2_critical": 85,
    "temp_critical": 39.0
  }
}
```

### **Logique embarquée minimale (IoT) :**
```python
# Code simple dans le capteur IoT
def send_vitals_to_cloud():
    vitals = collect_sensor_data()
    
    # Validation basique locale
    if vitals["spo2"] < 85:
        send_emergency_alert()  # Alerte immédiate
    
    # Envoi normal vers cloud
    payload = format_json(vitals)
    response = post_to_api(payload)
    
    if response.status != 200:
        store_locally_for_retry(payload)
```

## 📊 RÉPARTITION DES RESPONSABILITÉS

### **🔧 CAPTEUR IoT (Local)**
- ✅ Collecte données vitales
- ✅ Validation format basique
- ✅ Transmission sécurisée
- ✅ Alertes urgence immédiate (SpO2 < 85%)
- ✅ Gestion déconnexion temporaire

### **🌩️ CLOUD INGESTION (Avant pipeline)**
- ✅ Réception sécurisée
- ✅ Authentification device
- ✅ Rate limiting / DDoS protection
- ✅ File d'attente haute disponibilité
- ✅ Stockage temporaire (Landing)

### **📦 VOTRE PIPELINE KIDJAMO**
- ✅ Validation métier complète
- ✅ Enrichissement médical
- ✅ Calculs d'index (chaleur, hydratation)
- ✅ Détection patterns complexes
- ✅ Alertes médicales intelligentes
- ✅ Stockage base de données
- ✅ Vues matérialisées et analytics

### **🗄️ BASE DE DONNÉES**
- ✅ Stockage sécurisé et conforme RGPD
- ✅ Partitioning et performance
- ✅ Audit trail complet
- ✅ Backup et haute disponibilité

## 🚀 DÉPLOIEMENT RECOMMANDÉ

### **Phase 1 : MVP (Minimal Viable Product)**
```
[Capteur] → [API Gateway] → [Lambda] → [S3] → [Pipeline Local] → [PostgreSQL]
```

### **Phase 2 : Production Scale**
```
[Capteurs 100+] → [API Gateway + WAF] → [Kinesis Stream] → [Pipeline ECS] → [RDS Aurora] → [SNS Alerts]
```

### **Phase 3 : Enterprise**
```
[Capteurs 1000+] → [Multi-Region] → [Kafka] → [Pipeline K8s] → [Aurora Global] → [ML Predictions]
```

## ⚡ PERFORMANCE ATTENDUE

### **Latence bout en bout :**
- 🔧 **Capteur → Cloud** : 1-3 secondes
- 🌩️ **Ingestion Cloud** : 100-500ms
- 📦 **Pipeline Kidjamo** : 2-10 secondes
- 🚨 **Alerte générée** : **< 15 secondes total**

### **Débit supporté :**
- 📊 **1000 capteurs** × 1 mesure/30s = **33 messages/seconde**
- 📊 **Scaling** : jusqu'à 10,000 capteurs facilement

## 🛠️ OUTILS DE DÉVELOPPEMENT/DEBUG

### **Simulation locale pour tests :**
```python
# simulate_iot_data.py
def simulate_iot_device():
    fake_data = {
        "device_id": "sim-001",
        "patient_id": "test-patient",
        "vitals": generate_realistic_vitals(),
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Envoyer vers votre API de test
    requests.post("https://test-api.kidjamo.health/vitals", json=fake_data)
```

### **Monitoring en temps réel :**
- 📊 **CloudWatch/Azure Monitor** : Métriques infrastructure
- 📊 **Grafana Dashboard** : Métriques médicales
- 📊 **Alertmanager** : Alertes système
- 📊 **Logs centralisés** : ELK Stack ou Splunk

## 🎯 RÉSUMÉ SIMPLIFIÉ

**Votre pipeline Kidjamo s'exécute dans le cloud, PAS dans l'IoT.**

**Flux simplifié :**
1. 🔧 **Capteur IoT** collecte et envoie
2. 🌩️ **Services cloud** reçoivent et stockent temporairement  
3. 📦 **Votre pipeline** traite et analyse
4. 🗄️ **Base de données** stocke le résultat
5. 🚨 **Alertes** partent vers les équipes médicales

**Votre responsabilité :** Pipeline (étapes 3-5)  
**Responsabilité infrastructure cloud :** Étapes 1-2 + hosting
