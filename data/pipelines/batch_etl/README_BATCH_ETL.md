# 🏭 BATCH ETL - Pipeline de Traitement par Lots
## Kidjamo Medical Data Pipeline

## 🎯 **Rôle du dossier batch_etl**

Le dossier `batch_etl` contient les composants pour le **traitement par lots (batch processing)** des données médicales IoT, complémentaire au traitement temps réel.

## 📋 **Différence avec le Pipeline Temps Réel**

| Aspect | **Temps Réel** | **Batch ETL** |
|--------|----------------|---------------|
| **Fréquence** | Continu (secondes) | Périodique (heures/jours) |
| **Volume** | Petites données | Gros volumes |
| **Latence** | < 2 minutes | 30min - 24h |
| **Usage** | Alertes critiques | Analyses historiques |
| **Ressources** | Optimisé vitesse | Optimisé coût |

## 🔄 **Cas d'Usage du Batch ETL**

### **1. Analyses Historiques Approfondies**
- Calcul de tendances sur 3-6 mois
- Corrélations entre traitements et évolution
- Détection de patterns saisonniers
- Rapports médicaux périodiques

### **2. Retraitement de Données**
- Correction rétroactive d'anomalies détectées
- Application de nouveaux algorithmes sur historique
- Nettoyage massif de données corrompues
- Migration entre versions de schémas

### **3. Agrégations Complexes**
- Calculs statistiques lourds (percentiles, médians complexes)
- Création de features ML sur grandes fenêtres temporelles
- Consolidation multi-patients pour recherche
- Export de datasets pour analyses externes

### **4. Optimisation des Performances**
- Précomputation de vues matérialisées
- Reconstruction d'index de base de données
- Archivage de données anciennes
- Compression et optimisation stockage

## 🏗️ **Architecture Prévue**

```
batch_etl/
├── orchestrators/              # Orchestration des jobs batch
│   ├── daily_aggregations.py   # Agrégations journalières
│   ├── weekly_reports.py       # Rapports hebdomadaires
│   └── monthly_analytics.py    # Analyses mensuelles
│
├── processors/                 # Logique de traitement
│   ├── historical_trends.py    # Calcul tendances historiques
│   ├── quality_metrics.py      # Métriques qualité sur large fenêtre
│   ├── patient_profiles.py     # Profils patients consolidés
│   └── research_datasets.py    # Datasets pour recherche
│
├── exporters/                  # Export vers systèmes externes
│   ├── medical_reports.py      # Rapports médicaux PDF
│   ├── research_export.py      # Export pour chercheurs
│   └── dashboard_cache.py      # Cache pour dashboards
│
├── maintenance/                # Maintenance système
│   ├── data_archiving.py       # Archivage données anciennes
│   ├── index_optimization.py   # Optimisation index DB
│   └── cleanup_routines.py     # Nettoyage automatique
│
└── config/                     # Configuration batch
    ├── batch_schedules.yaml    # Planning des jobs
    ├── resource_limits.yaml    # Limites ressources
    └── retention_policies.yaml # Politiques de rétention
```

## ⚙️ **Intégration avec l'Écosystème**

### **Pipeline Global**
```
IoT Sensors → [TEMPS RÉEL] → Alertes Immédiates
     ↓
Data Lake → [BATCH ETL] → Analyses & Rapports
```

### **Déclencheurs Batch**
- **Cron quotidien** : 02:00 AM (analyses journalières)
- **Cron hebdomadaire** : Dimanche 01:00 AM (rapports)
- **Cron mensuel** : 1er du mois 00:00 AM (analytics)
- **Événementiel** : Après migration/correction massive

## 📊 **Exemples Concrets d'Usage**

### **1. Rapport Médical Hebdomadaire**
```python
# weekly_reports.py
def generate_patient_weekly_report(patient_id, week_start):
    """
    Génère un rapport médical complet sur 7 jours
    - Évolution SpO2, température, activité
    - Corrélations avec traitements
    - Recommandations automatiques
    """
```

### **2. Détection Tendances Saisonnières**
```python
# historical_trends.py
def detect_seasonal_patterns(patient_cohort, timeframe_months=12):
    """
    Détecte des patterns saisonniers dans les crises
    - Analyse sur 12 mois minimum
    - Corrélations météo/environnement
    - Prédictions préventives
    """
```

### **3. Export Recherche Anonymisé**
```python
# research_datasets.py
def create_research_dataset(criteria, anonymization_level="high"):
    """
    Crée un dataset pour recherche médicale
    - Pseudonymisation complète
    - Agrégations statistiques
    - Format standard recherche
    """
```

## 🕐 **Planification Recommandée**

### **Jobs Quotidiens (02:00 AM)**
- Agrégation métriques qualité 24h
- Calcul moyennes/tendances journalières
- Nettoyage données temporaires
- Backup incrémental

### **Jobs Hebdomadaires (Dimanche 01:00 AM)**
- Rapports médicaux patients
- Analyses de cohérence multi-jours
- Optimisation index database
- Export dashboards managers

### **Jobs Mensuels (1er du mois 00:00 AM)**
- Analyses épidémiologiques
- Rapports recherche & développement
- Archivage données > 6 mois
- Audit complet qualité données

## 🔧 **Outils et Technologies**

### **Orchestration**
- **Apache Airflow** ou **Prefect** pour scheduling
- **dbt** pour transformations SQL complexes
- **Great Expectations** pour validation qualité

### **Processing**
- **Pandas** pour manipulations DataFrames
- **Polars** pour gros volumes (plus rapide)
- **DuckDB** pour analytics locales rapides
- **PostgreSQL** pour agrégations SQL

### **Monitoring**
- Métriques d'exécution (durée, ressources)
- Alertes en cas d'échec
- Dashboard de suivi jobs batch
- Audit trail complet

## 🎯 **Bénéfices Attendus**

### **Performance**
- Décharge le pipeline temps réel
- Optimise l'utilisation des ressources
- Évite les surcharges pendant les pics

### **Qualité**
- Analyses plus approfondies possible
- Retraitement rétroactif en cas de bugs
- Validation croisée temps réel vs batch

### **Valeur Métier**
- Rapports médicaux automatisés
- Insights pour amélioration continue
- Support recherche et développement
- Conformité audit et régulation

---

**Date de création :** 18 août 2025  
**Version :** 1.0  
**Statut :** 📋 Spécification - Implémentation prévue
