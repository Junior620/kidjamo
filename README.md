# Kidjamo - Système de Surveillance Médicale IoT pour la Drépanocytose

**Projet Tech4Good Cameroun - Lauréat Compétition Nationale 2024**

---

## Présentation du Projet

Kidjamo est une plateforme de surveillance médicale en temps réel conçue pour les patients atteints de drépanocytose. Le système combine des bracelets connectés IoT avec une infrastructure cloud AWS pour détecter précocement les crises vaso-occlusives et alerter automatiquement le personnel médical.

La drépanocytose touche environ 300 millions de personnes dans le monde, principalement en Afrique subsaharienne. Les crises peuvent survenir soudainement et nécessitent une intervention rapide. Kidjamo répond à ce besoin critique en offrant une surveillance continue et des alertes intelligentes.

---

## Architecture Technique

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Bracelets IoT  │────▶│   AWS IoT Core   │────▶│  Kinesis Data   │
│  (ESP8266/MPU)  │     │                  │     │    Streams      │
└─────────────────┘     └──────────────────┘     └────────┬────────┘
                                                          │
                        ┌─────────────────────────────────┼─────────────────────────────────┐
                        │                                 ▼                                 │
                        │  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐   │
                        │  │   Lambda    │───▶│   S3 Data Lake  │───▶│   AWS Glue      │   │
                        │  │  (Alertes)  │    │ (Bronze/Silver/ │    │  (ETL Jobs)     │   │
                        │  └─────────────┘    │     Gold)       │    └─────────────────┘   │
                        │         │           └─────────────────┘             │            │
                        │         ▼                                           ▼            │
                        │  ┌─────────────┐                          ┌─────────────────┐   │
                        │  │     SNS     │                          │   PostgreSQL    │   │
                        │  │ (Notifs)    │                          │    (RDS)        │   │
                        │  └─────────────┘                          └─────────────────┘   │
                        │         │                                           │            │
                        │         ▼                                           ▼            │
                        │  ┌─────────────┐                          ┌─────────────────┐   │
                        │  │   Médecins  │                          │   Dashboards    │   │
                        │  │  (SMS/Email)│                          │   (Streamlit)   │   │
                        │  └─────────────┘                          └─────────────────┘   │
                        │                                                                  │
                        └──────────────────────────── AWS Cloud ───────────────────────────┘
```

---

## Structure du Projet

```
kidjamo-workspace/
│
├── api/                          # APIs REST et GraphQL
│   ├── graphql/                  # API GraphQL pour requêtes flexibles
│   ├── iot_ingestion/            # Endpoint d'ingestion IoT
│   └── rest_api/                 # API REST pour les applications mobiles
│
├── chat_bot/                     # Chatbot médical intelligent
│   ├── src/                      # Code source Lambda et Lex
│   ├── terraform/                # Infrastructure as Code
│   ├── web_interface/            # Interface web du chatbot
│   └── production/               # Configuration de production
│
├── dashboards/                   # Tableaux de bord Streamlit
│   ├── kidjamo_dashboards_main.py        # Application principale
│   ├── realtime_dashboard_streamlit.py   # Surveillance temps réel
│   ├── database_dashboard_streamlit.py   # Analyse historique
│   └── config.py                         # Configuration et seuils
│
├── data/                         # Schémas et configurations de données
│   ├── schemas/                  # Schémas de données (SQL, JSON)
│   ├── monitoring/               # Configuration monitoring
│   └── security/                 # Politiques de sécurité des données
│
├── infra/                        # Infrastructure Cloud
│   ├── terraform/                # Infrastructure AWS (IoT, Kinesis, S3...)
│   ├── cdk/                      # AWS CDK (alternative)
│   ├── lambda/                   # Fonctions Lambda
│   └── secret_manager/           # Gestion des secrets
│
├── ingestion/                    # Pipeline d'ingestion de données
│   ├── jobs/                     # Jobs ETL (Raw→Bronze→Silver→Gold)
│   │   ├── 01_to_raw.py
│   │   ├── 02_raw_to_bronze.py
│   │   ├── 03_bronze_to_silver.py
│   │   ├── 04_silver_to_gold.py
│   │   ├── generate_synthetic_data.py    # Générateur de données de test
│   │   └── offline_alerts_engine.py      # Moteur d'alertes hors-ligne
│   ├── config/                   # Configuration du pipeline
│   └── iot_streaming/            # Ingestion streaming temps réel
│
├── lambda/                       # Fonctions Lambda AWS
│   └── kidjamo_alert_processor_enhanced.py   # Traitement des alertes
│
├── orchestration/                # Orchestration des pipelines
│   ├── stepfunctions_state_machine.json  # AWS Step Functions
│   ├── deploy_orchestration.py           # Script de déploiement
│   └── monitor_pipeline.py               # Monitoring du pipeline
│
├── pipeline_ml/                  # Machine Learning Pipeline
│   ├── training/                 # Entraînement des modèles
│   ├── preprocessing/            # Préparation des données
│   ├── serving/                  # Serving des modèles
│   ├── explainability/           # Explicabilité ML (SHAP, LIME)
│   └── alert-engine/             # Moteur d'alertes ML
│
├── tests/                        # Tests automatisés
│   ├── unit/                     # Tests unitaires
│   ├── integration/              # Tests d'intégration
│   └── scenario_tests/           # Tests de scénarios médicaux
│
├── docs/                         # Documentation
│   ├── cahier_de_charge.md       # Spécifications du projet
│   └── diagramme/                # Diagrammes d'architecture
│
└── ops/                          # Operations et DevOps
    ├── compose/                  # Docker Compose
    ├── observability/            # Monitoring et logging
    └── scripts/                  # Scripts utilitaires
```

---

## Fonctionnalités Principales

### 1. Collecte de Données en Temps Réel
- Capteurs intégrés dans les bracelets connectés :
  - Fréquence cardiaque (BPM)
  - Saturation en oxygène (SpO2)
  - Température corporelle
  - Accéléromètre (détection de chutes)
- Transmission via WiFi/Bluetooth vers AWS IoT Core
- Ingestion streaming via Kinesis Data Streams

### 2. Système d'Alertes Intelligent
Les seuils médicaux sont adaptés aux patients drépanocytaires :

| Paramètre | Normal | Vigilance | Alerte | Urgence |
|-----------|--------|-----------|--------|---------|
| Température | 36.5-37.5°C | 37.6-37.9°C | >38°C | >39°C |
| Fréquence cardiaque | 60-100 BPM | 101-110 BPM | >111 BPM | >130 BPM |
| SpO2 | >95% | 93-94% | <92% | <90% |

### 3. Pipeline de Données (Médaillon)
Architecture Data Lake en quatre couches :
- **Raw** : Données brutes ingérées depuis les capteurs
- **Bronze** : Données nettoyées et dédupliquées
- **Silver** : Données transformées et enrichies
- **Gold** : Agrégations et features pour le ML

### 4. Dashboards de Surveillance
- **Temps Réel** : Visualisation live des signes vitaux
- **Historique** : Analyse des tendances sur le long terme
- **Alertes** : Suivi et gestion des alertes médicales

### 5. Chatbot Médical
- Assistance aux patients et familles
- Informations sur la drépanocytose
- Rappels de traitement
- Intégration Amazon Lex et Bedrock

---

## Technologies Utilisées

### Cloud AWS
- **IoT Core** : Connexion des bracelets
- **Kinesis Data Streams** : Ingestion temps réel
- **Lambda** : Traitement serverless
- **S3** : Data Lake
- **Glue** : Jobs ETL
- **Step Functions** : Orchestration
- **RDS PostgreSQL** : Base de données
- **SNS** : Notifications
- **Lex** : Chatbot NLU
- **Bedrock** : IA générative

### Backend
- Python 3.9+
- PySpark (traitement de données)
- Pandas, NumPy
- Boto3 (SDK AWS)

### Frontend
- Streamlit (dashboards)
- Plotly (visualisations)
- HTML/CSS/JavaScript

### Infrastructure
- Terraform
- AWS CDK
- Docker

### Machine Learning
- Scikit-learn
- XGBoost
- SHAP (explicabilité)

---

## Installation et Configuration

### Prérequis
- Python 3.9 ou supérieur
- Compte AWS avec accès programmatique
- Terraform >= 1.0
- Git

### 1. Cloner le Repository
```bash
git clone https://github.com/Junior620/kidjamo.git
cd kidjamo
```

### 2. Configurer l'Environnement
```bash
# Copier le template de configuration
cp .env.template .env

# Éditer le fichier .env avec vos credentials AWS
# AWS_ACCESS_KEY_ID=your_key
# AWS_SECRET_ACCESS_KEY=your_secret
# AWS_REGION=eu-west-1
```

### 3. Installer les Dépendances
```bash
# Pour les dashboards
cd dashboards
pip install -r requirements.txt

# Pour l'ingestion
cd ../ingestion
pip install -r requirements.txt
```

### 4. Déployer l'Infrastructure
```bash
cd infra/terraform
terraform init
terraform plan
terraform apply
```

### 5. Lancer les Dashboards
```bash
cd dashboards
streamlit run kidjamo_dashboards_main.py
```

---

## Utilisation

### Générer des Données de Test
```bash
cd ingestion/jobs
python generate_synthetic_data.py
```

Ce script génère :
- `iot_measurements.csv` : Mesures IoT simulées
- `clinical_events.csv` : Événements cliniques
- `heat_index.csv` : Données environnementales
- `ml_features.csv` : Features pour le ML
- `patients.csv` : Profils patients

### Exécuter le Pipeline ETL
```bash
# Localement
cd ingestion/jobs
python 01_to_raw.py
python 02_raw_to_bronze.py
python 03_bronze_to_silver.py
python 04_silver_to_gold.py

# Via AWS Step Functions (en production)
cd orchestration
python deploy_orchestration.py
```

### Monitorer le Pipeline
```bash
cd orchestration
python monitor_pipeline.py
```

---

## Tests

```bash
# Exécuter tous les tests
cd tests
python -m pytest

# Tests spécifiques
python -m pytest test_medical_iot_simulator_alerts.py -v
```

---

## Configuration des Alertes

Le fichier de seuils médicaux se trouve dans `lambda/kidjamo_alert_processor_enhanced.py` :

```python
MEDICAL_THRESHOLDS = {
    "temperature": {
        "normal": [36.5, 37.5],
        "vigilance": [37.6, 37.9],
        "alert": 38.0,
        "emergency": 39.0,
        "hypothermia": 35.0
    },
    "heart_rate": {
        "normal": [60, 100],
        "vigilance": [101, 110],
        "alert": 111,
        "emergency": 130,
        "bradycardia": 50
    },
    "spo2": {
        "normal": 95,
        "vigilance": [93, 94],
        "alert": 92,
        "emergency": 90,
        "critical": 88
    }
}
```

---

## Sécurité et Conformité

- Chiffrement des données au repos (S3, RDS) et en transit (TLS 1.2+)
- Authentification via AWS IAM et Cognito
- Logs d'audit CloudTrail
- Conformité RGPD pour les données de santé
- Isolation réseau via VPC

---

## Équipe

Projet développé par l'équipe Kidjamo dans le cadre du programme Tech4Good Cameroun.

---

## Contribution

1. Fork le repository
2. Créer une branche feature (`git checkout -b feature/nouvelle-fonctionnalite`)
3. Commit les changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push la branche (`git push origin feature/nouvelle-fonctionnalite`)
5. Créer une Pull Request

---

## Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

---

## Contact

- Repository : [https://github.com/Junior620/kidjamo](https://github.com/Junior620/kidjamo)
- Email : christianouragan@gmail.com

---

*Kidjamo - Parce que chaque vie compte.*

