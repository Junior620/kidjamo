# 📁 STRUCTURE REORGANISÉE - DATA PIPELINE KIDJAMO

## 🎯 Vue d'ensemble de la nouvelle organisation

Cette nouvelle structure dans `data/` centralise tous les composants du pipeline Kidjamo pour une meilleure organisation et maintenabilité.

## 📂 Structure détaillée

```
data/
├── configs/                    # Configuration centralisée
│   ├── medical_thresholds.json # Seuils médicaux par génotype
│   ├── settings.yaml          # Configuration générale
│   ├── .env                   # Variables d'environnement
│   └── .env.template          # Template pour configuration
│
├── pipelines/                  # Orchestration et exécution
│   ├── run_pipeline.py        # Point d'entrée principal
│   ├── requirements.txt       # Dépendances Python
│   ├── batch_etl/            # Traitement par batch
│   └── iot_streaming/        # Traitement temps réel
│
├── jobs/                      # Jobs de transformation
│   ├── 01_to_raw.py          # Landing → Raw
│   ├── 02_raw_to_bronze.py   # Raw → Bronze (validation)
│   ├── 03_bronze_to_silver.py # Bronze → Silver (enrichissement)
│   ├── 04_silver_to_gold.py  # Silver → Gold (agrégation)
│   ├── metrics_exporter.py   # Export métriques qualité
│   └── offline_alerts_engine.py # Moteur d'alertes
│
├── lake/                      # Data Lake multicouche
│   ├── landing/              # Données brutes IoT
│   ├── raw/                  # Données organisées par date
│   ├── bronze/               # Données validées
│   ├── silver/               # Données enrichies médicalement
│   └── gold/                 # Données agrégées pour dashboards
│
├── schemas/                   # Définitions de schémas
│   ├── medical_iot_schema.py # Schéma principal IoT médical
│   ├── sql/                  # Schémas SQL (PostgreSQL)
│   └── nosql/                # Schémas NoSQL (si nécessaire)
│
├── security/                  # Sécurité et pseudonymisation
│   ├── pseudonymization.py   # Pseudonymisation basique
│   └── pseudonymization_secure.py # Pseudonymisation avancée
│
├── test_data/                 # Données de test et simulation
│   ├── clinical_events_100k.csv # Événements cliniques simulés
│   ├── clinical_synth_100k.csv # Données synthétiques
│   ├── dataset_iot.py        # Générateur IoT
│   └── generatecsv.py        # Générateur CSV
│
├── quarantine/               # Données en quarantaine
│   └── ingestion_date=*/     # Partitionné par date
│
├── logs/                     # Logs d'exécution pipeline
├── evidence/                 # Rapports de qualité et tests
├── monitoring/               # Métriques et surveillance
├── migration/                # Scripts de migration DB
├── dbt/                     # Transformations dbt (Data Build Tool)
└── expectations/            # Tests de qualité (Great Expectations)
```

## 🔧 Utilisation de la nouvelle structure

### **Exécution du pipeline principal**
```bash
cd data/pipelines
python run_pipeline.py
```

### **Configuration d'environnement**
1. Copier `.env.template` vers `.env`
2. Remplir les variables d'environnement
3. Vérifier `configs/settings.yaml`

### **Tests et validation**
```bash
cd data/test_data
python dataset_iot.py --patients=100 --measurements=10000
```

## 🎯 Avantages de cette réorganisation

### **1. Centralisation**
- ✅ Tous les composants pipeline dans `data/`
- ✅ Configuration centralisée dans `configs/`
- ✅ Logs et monitoring unifiés

### **2. Séparation des responsabilités**
- ✅ `jobs/` : Logique de transformation
- ✅ `pipelines/` : Orchestration
- ✅ `lake/` : Stockage multicouche
- ✅ `security/` : Aspects sécurité

### **3. Maintenance simplifiée**
- ✅ Structure claire et navigable
- ✅ Dependencies isolées par composant
- ✅ Tests et evidence séparés

### **4. Évolutivité**
- ✅ Facilité d'ajout de nouveaux jobs
- ✅ Extension du data lake
- ✅ Intégration dbt et expectations

## 🚀 Prochaines étapes

1. **Validation** : Tester la nouvelle structure
2. **Configuration** : Adapter les chemins dans les scripts
3. **Documentation** : Mettre à jour les README spécifiques
4. **CI/CD** : Adapter les pipelines de déploiement

## 📞 Support

Pour toute question sur cette nouvelle structure :
- Consulter les README dans chaque sous-dossier
- Vérifier les logs dans `data/logs/`
- Examiner les métriques dans `data/evidence/`

---

**Date de réorganisation :** 18 août 2025  
**Version :** 2.0  
**Statut :** ✅ Migration complète réussie
