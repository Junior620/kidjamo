# Documentation dbt - Projet Kidjamo

## Vue d'ensemble
dbt (Data Build Tool) transforme vos données IoT brutes en insights médicaux exploitables pour le suivi des patients drépanocytaires.

## Architecture des modèles

### 🔄 **Staging** (Raw → Bronze)
- `stg_measurements.sql` : Nettoie et valide les données des capteurs IoT
- `stg_patients.sql` : Enrichit les profils patients avec âge, groupes de risque

### ⚙️ **Intermediate** (Bronze → Silver) 
- `int_measurements_hourly.sql` : Agrège les mesures par heure avec statistiques

### 📊 **Marts** (Silver → Gold)
- `medical_dashboard_realtime.sql` : Dashboard temps réel pour équipes médicales

## Fonctionnalités médicales spécialisées

### 🏥 **Seuils adaptatifs par âge/génotype**
```sql
-- Exemple : SpO2 critique pour enfant SS = 92% vs adulte AS = 90%
{{ get_medical_thresholds(age_years, genotype, 'spo2') }}
```

### 🚨 **Détection automatique de crises**
- Combinaison SpO2 < 90% + Température > 38°C = ALERTE CRITIQUE
- Adaptation selon le génotype (SS plus strict que AS)

### 📈 **Analyse de tendances**
- Comparaison 24h pour détecter dégradations
- Scoring de risque dynamique (0-100)

### 🔒 **Conformité GDPR**
- Pseudonymisation automatique des données sensibles
- Traçabilité complète des transformations

## Tests de qualité automatisés

### ✅ **Validation physiologique**
- SpO2 entre 70-100%
- Fréquence cardiaque selon l'âge
- Température corporelle plausible

### 🔍 **Détection d'anomalies**
- Valeurs en dehors de 2 écarts-types
- Qualité des signaux des capteurs
- Cohérence temporelle des mesures

## Utilisation pratique

### 📱 **Pour les équipes médicales**
```sql
-- Vue dashboard temps réel
SELECT patient_id, risk_level, alert_status, current_spo2
FROM medical_dashboard_realtime 
WHERE risk_level = 'HIGH'
```

### 📊 **Pour les rapports**
- Agrégations quotidiennes/hebdomadaires
- Statistiques par service médical
- Tendances épidémiologiques

### 🔧 **Pour les développeurs**
- Tests automatisés à chaque déploiement
- Documentation auto-générée
- Lineage des données tracé

## Commandes dbt essentielles

```bash
# Installation des dépendances
dbt deps

# Tests de qualité
dbt test

# Construction des modèles
dbt run

# Documentation
dbt docs generate
dbt docs serve

# Déploiement production
dbt run --target prod
```

## Monitoring et alertes

- **Echecs de tests** → Alerte équipe technique
- **Données manquantes** → Notification médicale
- **Dérive de qualité** → Investigation automatique

Cette architecture dbt garantit la fiabilité et la traçabilité de vos données médicales critiques.
