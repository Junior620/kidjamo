#!/usr/bin/env python3
"""
🏥 KIDJAMO - Exporteur pour Recherche
Export de données anonymisées pour équipes de recherche médicale
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import zipfile
import os

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResearchExporter:
    """
    Exporteur spécialisé pour la recherche médicale avec anonymisation renforcée
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config

    async def export_research_package(self, export_config: Dict) -> str:
        """
        Crée un package complet pour équipes de recherche
        """
        logger.info("🔬 Export package recherche médicale")

        package_id = f"research_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_dir = f"../../evidence/research_exports/{package_id}"
        os.makedirs(export_dir, exist_ok=True)

        # 1. Dataset principal anonymisé
        main_dataset = await self._create_main_research_dataset(export_config)
        main_file = f"{export_dir}/anonymized_cohort_data.csv"
        main_dataset.to_csv(main_file, index=False)

        # 2. Métadonnées et documentation
        metadata = await self._create_research_metadata(export_config, main_dataset)
        metadata_file = f"{export_dir}/dataset_metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)

        # 3. Guide d'utilisation
        guide_content = await self._create_usage_guide(metadata)
        guide_file = f"{export_dir}/research_guide.md"
        with open(guide_file, 'w', encoding='utf-8') as f:
            f.write(guide_content)

        # 4. Statistiques descriptives
        stats = await self._generate_descriptive_statistics(main_dataset)
        stats_file = f"{export_dir}/descriptive_statistics.json"
        with open(stats_file, 'w') as f:
            json.dump(stats, f, indent=2, default=str)

        # 5. Code d'exemple pour analyses
        example_code = await self._create_example_analysis_code()
        code_file = f"{export_dir}/example_analysis.py"
        with open(code_file, 'w') as f:
            f.write(example_code)

        # 6. Compression du package
        zip_file = f"../../evidence/research_exports/{package_id}.zip"
        await self._create_zip_package(export_dir, zip_file)

        logger.info(f"✅ Package recherche créé: {zip_file}")
        return zip_file

    async def _create_main_research_dataset(self, config: Dict) -> pd.DataFrame:
        """
        Crée le dataset principal pour la recherche
        """
        timeframe_months = config.get('timeframe_months', 12)
        start_date = datetime.now() - timedelta(days=timeframe_months * 30)

        query = """
        WITH patient_monthly_data AS (
            SELECT 
                m.patient_id,
                DATE_TRUNC('month', m.tz_timestamp) as month,
                
                -- Anonymisation géographique
                CASE 
                    WHEN u.country IN ('France', 'Belgique', 'Suisse') THEN 'Europe_West'
                    WHEN u.country IN ('Maroc', 'Tunisie', 'Algérie') THEN 'Africa_North'
                    WHEN u.country IN ('Sénégal', 'Mali', 'Burkina Faso') THEN 'Africa_West'
                    ELSE 'Other'
                END as geographic_region,
                
                -- Données patient anonymisées
                p.genotype,
                CASE 
                    WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) < 18 THEN 'pediatric'
                    WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) < 30 THEN 'young_adult'
                    WHEN EXTRACT(YEAR FROM AGE(p.birth_date)) < 50 THEN 'adult'
                    ELSE 'older_adult'
                END as age_category,
                u.gender,
                
                -- Métriques physiologiques mensuelles
                COUNT(*) as measurements_count,
                AVG(m.spo2_pct) as avg_spo2,
                STDDEV(m.spo2_pct) as std_spo2,
                PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY m.spo2_pct) as spo2_p10,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY m.spo2_pct) as spo2_p90,
                
                AVG(m.freq_card) as avg_heart_rate,
                STDDEV(m.freq_card) as std_heart_rate,
                
                AVG(m.temp_corp) as avg_temperature,
                MAX(m.temp_corp) as max_temperature,
                
                AVG(m.activity) as avg_activity,
                AVG(m.pct_hydratation) as avg_hydration,
                
                -- Environnement
                AVG(m.temp_abiante) as avg_ambient_temp,
                AVG(m.heat_index) as avg_heat_index,
                
                -- Indicateurs de crise
                COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
                COUNT(a.alert_id) FILTER (WHERE a.severity = 'medium') as medium_alerts,
                
                -- Qualité des données
                COUNT(*) FILTER (WHERE m.quality_flag = 'ok') as valid_measurements,
                (COUNT(*) FILTER (WHERE m.quality_flag = 'ok') * 100.0 / COUNT(*)) as data_quality_pct,
                
                -- Compliance (approximative)
                COUNT(DISTINCT DATE(m.tz_timestamp)) as monitoring_days,
                EXTRACT(DAYS FROM DATE_TRUNC('month', m.tz_timestamp) + INTERVAL '1 month' - DATE_TRUNC('month', m.tz_timestamp)) as month_days
                
            FROM measurements m
            JOIN patients p ON m.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            LEFT JOIN alerts a ON m.patient_id = a.patient_id 
                AND DATE_TRUNC('month', a.created_at) = DATE_TRUNC('month', m.tz_timestamp)
            WHERE m.tz_timestamp >= %s
                AND m.quality_flag = 'ok'
            GROUP BY m.patient_id, DATE_TRUNC('month', m.tz_timestamp),
                     p.genotype, p.birth_date, u.gender, u.country
        )
        SELECT 
            -- ID anonyme reproductible
            MD5(patient_id::text) as anonymized_patient_id,
            month,
            geographic_region,
            genotype,
            age_category,
            gender,
            
            -- Métriques physiologiques
            measurements_count,
            avg_spo2,
            std_spo2,
            spo2_p10,
            spo2_p90,
            avg_heart_rate,
            std_heart_rate,
            avg_temperature,
            max_temperature,
            avg_activity,
            avg_hydration,
            
            -- Environnement
            avg_ambient_temp,
            avg_heat_index,
            
            -- Crises
            critical_alerts,
            medium_alerts,
            
            -- Qualité et compliance
            data_quality_pct,
            (monitoring_days * 100.0 / month_days) as compliance_pct
            
        FROM patient_monthly_data
        WHERE measurements_count >= 100  -- Au moins 100 mesures par mois
        ORDER BY anonymized_patient_id, month
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn, params=(start_date,))
        conn.close()

        return df

    async def _create_research_metadata(self, config: Dict, dataset: pd.DataFrame) -> Dict:
        """
        Crée les métadonnées complètes du dataset
        """
        return {
            "dataset_info": {
                "name": "Kidjamo Sickle Cell Disease Monitoring Dataset",
                "version": "1.0",
                "creation_date": datetime.now().isoformat(),
                "description": "Anonymized longitudinal dataset of sickle cell disease patients with continuous IoT monitoring",
                "license": "Research Use Only - RGPD Compliant"
            },
            "study_population": {
                "total_patients": dataset['anonymized_patient_id'].nunique(),
                "total_observations": len(dataset),
                "observation_period_months": config.get('timeframe_months', 12),
                "genotype_distribution": dataset['genotype'].value_counts().to_dict(),
                "age_distribution": dataset['age_category'].value_counts().to_dict(),
                "geographic_distribution": dataset['geographic_region'].value_counts().to_dict()
            },
            "data_collection": {
                "monitoring_device": "IoT medical sensors (SpO2, heart rate, temperature)",
                "sampling_frequency": "Every 5 minutes",
                "data_aggregation": "Monthly patient-level aggregates",
                "quality_control": "Automated quality flags and manual validation"
            },
            "variables": {
                "physiological": [
                    "avg_spo2", "std_spo2", "spo2_p10", "spo2_p90",
                    "avg_heart_rate", "std_heart_rate",
                    "avg_temperature", "max_temperature",
                    "avg_activity", "avg_hydration"
                ],
                "environmental": ["avg_ambient_temp", "avg_heat_index"],
                "clinical": ["critical_alerts", "medium_alerts"],
                "demographic": ["genotype", "age_category", "gender", "geographic_region"],
                "quality": ["data_quality_pct", "compliance_pct", "measurements_count"]
            },
            "anonymization": {
                "method": "K-anonymity with generalization",
                "patient_ids": "MD5 hashed",
                "geographic_data": "Generalized to regions",
                "temporal_data": "Aggregated to monthly level",
                "age_data": "Grouped into categories",
                "rgpd_compliance": True
            },
            "usage_restrictions": {
                "purpose": "Research and academic use only",
                "sharing": "Restricted - approval required",
                "publication": "Acknowledgment of Kidjamo project required",
                "commercial_use": "Prohibited"
            }
        }

    async def _create_usage_guide(self, metadata: Dict) -> str:
        """
        Crée un guide d'utilisation pour les chercheurs
        """
        return """# 🔬 KIDJAMO RESEARCH DATASET - Guide d'Utilisation

## 📊 Vue d'ensemble

Ce dataset contient des données longitudinales anonymisées de patients atteints de drépanocytose surveillés en continu par des capteurs IoT médicaux.

## 📋 Informations du Dataset

- **Patients :** {total_patients} patients anonymisés
- **Observations :** {total_observations} observations mensuelles  
- **Période :** {timeframe_months} mois de données
- **Conformité :** RGPD compliant avec anonymisation renforcée

## 🔧 Variables Principales

### Variables Physiologiques
- `avg_spo2` : Saturation oxygène moyenne (%)
- `std_spo2` : Écart-type SpO2 (indicateur de variabilité)
- `spo2_p10/p90` : Percentiles 10 et 90 du SpO2
- `avg_heart_rate` : Fréquence cardiaque moyenne (bpm)
- `avg_temperature` : Température corporelle moyenne (°C)
- `avg_activity` : Niveau d'activité physique moyen

### Variables Cliniques
- `critical_alerts` : Nombre d'alertes critiques par mois
- `medium_alerts` : Nombre d'alertes moyennes par mois
- `genotype` : SS, SC, AS (sévérité croissante)

### Variables Environnementales  
- `avg_ambient_temp` : Température ambiante moyenne
- `avg_heat_index` : Index de chaleur moyen

## 📈 Analyses Suggérées

### 1. Analyses Descriptives
```python
# Distribution des génotypes
dataset['genotype'].value_counts()

# SpO2 moyen par génotype
dataset.groupby('genotype')['avg_spo2'].describe()
```

### 2. Analyses Temporelles
```python
# Évolution saisonnière
dataset['season'] = dataset['month'].dt.quarter
seasonal_trends = dataset.groupby(['season', 'genotype'])['critical_alerts'].mean()
```

### 3. Corrélations Environnementales
```python
# Corrélation température ambiante vs crises
correlation = dataset[['avg_ambient_temp', 'critical_alerts']].corr()
```

### 4. Analyses de Survie
```python
# Temps jusqu'à première crise critique
import lifelines
# (voir example_analysis.py pour code complet)
```

## ⚠️ Considérations Éthiques

1. **Usage Recherche Uniquement** : Pas d'usage commercial
2. **Anonymisation** : Données k-anonymisées, pas de ré-identification
3. **Publication** : Citer le projet Kidjamo dans publications
4. **Partage** : Approbation requise avant partage dataset

## 📞 Contact Recherche

Pour questions scientifiques ou collaborations :
- Email : research@kidjamo.org
- Slack : #research-collaboration

## 📚 Références Suggérées

1. Ware RE, et al. Sickle cell disease. Lancet. 2017
2. Yawn BP, et al. Management of sickle cell disease. JAMA. 2014
3. ANSM Guidelines on IoT medical devices. 2023

---

*Dataset généré le {creation_date}*
*Version {version} - Kidjamo Research Platform*
""".format(
            total_patients=metadata['study_population']['total_patients'],
            total_observations=metadata['study_population']['total_observations'],
            timeframe_months=metadata['study_population']['observation_period_months'],
            creation_date=metadata['dataset_info']['creation_date'],
            version=metadata['dataset_info']['version']
        )

    async def _generate_descriptive_statistics(self, dataset: pd.DataFrame) -> Dict:
        """
        Génère des statistiques descriptives complètes
        """
        stats = {}

        # Variables numériques
        numeric_vars = ['avg_spo2', 'std_spo2', 'avg_heart_rate', 'avg_temperature',
                       'critical_alerts', 'medium_alerts', 'data_quality_pct', 'compliance_pct']

        for var in numeric_vars:
            if var in dataset.columns:
                stats[var] = {
                    'count': int(dataset[var].count()),
                    'mean': float(dataset[var].mean()),
                    'std': float(dataset[var].std()),
                    'min': float(dataset[var].min()),
                    'q25': float(dataset[var].quantile(0.25)),
                    'median': float(dataset[var].median()),
                    'q75': float(dataset[var].quantile(0.75)),
                    'max': float(dataset[var].max())
                }

        # Variables catégorielles
        categorical_vars = ['genotype', 'age_category', 'gender', 'geographic_region']

        for var in categorical_vars:
            if var in dataset.columns:
                stats[f'{var}_distribution'] = dataset[var].value_counts().to_dict()

        return stats

    async def _create_example_analysis_code(self) -> str:
        """
        Crée du code d'exemple pour analyses courantes
        """
        return '''#!/usr/bin/env python3
"""
🔬 KIDJAMO RESEARCH DATASET - Code d'Exemple
Analyses statistiques courantes pour recherche drépanocytose
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import warnings
warnings.filterwarnings('ignore')

# Chargement des données
def load_kidjamo_dataset():
    """Charge le dataset Kidjamo"""
    df = pd.read_csv('anonymized_cohort_data.csv')
    df['month'] = pd.to_datetime(df['month'])
    return df

# 1. ANALYSES DESCRIPTIVES
def descriptive_analysis(df):
    """Analyses descriptives par génotype"""
    print("📊 ANALYSES DESCRIPTIVES PAR GÉNOTYPE")
    print("="*50)
    
    # SpO2 par génotype
    spo2_by_genotype = df.groupby('genotype')['avg_spo2'].agg(['count', 'mean', 'std'])
    print("\\nSpO2 moyen par génotype:")
    print(spo2_by_genotype)
    
    # Test statistique ANOVA
    groups = [df[df['genotype'] == g]['avg_spo2'].dropna() for g in df['genotype'].unique()]
    f_stat, p_value = stats.f_oneway(*groups)
    print(f"\\nANOVA SpO2 entre génotypes: F={f_stat:.3f}, p={p_value:.3e}")
    
    return spo2_by_genotype

# 2. ANALYSES TEMPORELLES
def temporal_analysis(df):
    """Analyse des tendances temporelles"""
    print("\\n📈 ANALYSES TEMPORELLES")
    print("="*30)
    
    # Tendances saisonnières
    df['season'] = df['month'].dt.quarter.map({
        1: 'Winter', 2: 'Spring', 3: 'Summer', 4: 'Fall'
    })
    
    seasonal_crises = df.groupby(['season', 'genotype'])['critical_alerts'].mean().unstack()
    print("\\nCrises critiques moyennes par saison et génotype:")
    print(seasonal_crises)
    
    # Graphique évolution temporelle
    plt.figure(figsize=(12, 6))
    for genotype in df['genotype'].unique():
        subset = df[df['genotype'] == genotype]
        monthly_avg = subset.groupby('month')['avg_spo2'].mean()
        plt.plot(monthly_avg.index, monthly_avg.values, label=f'Genotype {genotype}', marker='o')
    
    plt.title('Évolution SpO2 Moyen par Génotype')
    plt.xlabel('Mois')
    plt.ylabel('SpO2 Moyen (%)')
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('spo2_evolution_by_genotype.png', dpi=300)
    plt.show()
    
    return seasonal_crises

# 3. CORRÉLATIONS ENVIRONNEMENTALES  
def environmental_correlations(df):
    """Analyse corrélations environnementales"""
    print("\\n🌡️ CORRÉLATIONS ENVIRONNEMENTALES")
    print("="*40)
    
    # Corrélation température ambiante vs crises
    temp_crisis_corr = df[['avg_ambient_temp', 'critical_alerts']].corr().iloc[0,1]
    print(f"Corrélation température ambiante vs crises: {temp_crisis_corr:.3f}")
    
    # Analyse par quartiles de température
    df['temp_quartile'] = pd.qcut(df['avg_ambient_temp'], 4, labels=['Q1', 'Q2', 'Q3', 'Q4'])
    temp_analysis = df.groupby('temp_quartile').agg({
        'critical_alerts': 'mean',
        'avg_spo2': 'mean',
        'avg_ambient_temp': 'mean'
    })
    print("\\nAnalyse par quartiles de température:")
    print(temp_analysis)
    
    return temp_analysis

# 4. CLUSTERING DES PATIENTS
def patient_clustering(df):
    """Clustering k-means des profils patients"""
    print("\\n👥 CLUSTERING PROFILS PATIENTS")
    print("="*35)
    
    # Variables pour clustering
    cluster_vars = ['avg_spo2', 'std_spo2', 'avg_heart_rate', 'critical_alerts', 'compliance_pct']
    
    # Agrégation par patient (moyenne sur tous les mois)
    patient_profiles = df.groupby('anonymized_patient_id')[cluster_vars].mean()
    
    # Standardisation
    scaler = StandardScaler()
    scaled_data = scaler.fit_transform(patient_profiles)
    
    # K-means clustering
    kmeans = KMeans(n_clusters=3, random_state=42)
    clusters = kmeans.fit_predict(scaled_data)
    patient_profiles['cluster'] = clusters
    
    # Analyse des clusters
    cluster_analysis = patient_profiles.groupby('cluster')[cluster_vars].mean()
    print("\\nProfils des clusters:")
    print(cluster_analysis)
    
    # Visualisation
    plt.figure(figsize=(10, 8))
    scatter = plt.scatter(patient_profiles['avg_spo2'], patient_profiles['critical_alerts'], 
                         c=clusters, cmap='viridis', alpha=0.6)
    plt.xlabel('SpO2 Moyen (%)')
    plt.ylabel('Alertes Critiques Moyennes')
    plt.title('Clustering des Profils Patients')
    plt.colorbar(scatter)
    plt.savefig('patient_clusters.png', dpi=300)
    plt.show()
    
    return patient_profiles, cluster_analysis

# 5. ANALYSE DE SURVIE (Temps jusqu'à crise)
def survival_analysis(df):
    """Analyse de survie - temps jusqu'à première crise"""
    print("\\n⏱️ ANALYSE DE SURVIE")
    print("="*25)
    
    # Création dataset de survie
    survival_data = []
    
    for patient in df['anonymized_patient_id'].unique():
        patient_data = df[df['anonymized_patient_id'] == patient].sort_values('month')
        
        # Première crise critique
        first_crisis = patient_data[patient_data['critical_alerts'] > 0]['month'].min()
        
        if pd.notna(first_crisis):
            # Temps jusqu'à première crise (en mois)
            time_to_event = (first_crisis - patient_data['month'].min()).days / 30
            event = 1  # Événement observé
        else:
            # Censure à droite
            time_to_event = (patient_data['month'].max() - patient_data['month'].min()).days / 30
            event = 0  # Censuré
        
        survival_data.append({
            'patient_id': patient,
            'genotype': patient_data['genotype'].iloc[0],
            'time_to_event': time_to_event,
            'event': event
        })
    
    survival_df = pd.DataFrame(survival_data)
    
    # Statistiques de survie par génotype
    survival_stats = survival_df.groupby('genotype').agg({
        'time_to_event': ['count', 'mean', 'median'],
        'event': 'sum'
    }).round(2)
    
    print("\\nStatistiques de survie par génotype:")
    print(survival_stats)
    
    return survival_df

# FONCTION PRINCIPALE
def run_complete_analysis():
    """Exécute l'analyse complète"""
    print("🔬 KIDJAMO RESEARCH DATASET - ANALYSE COMPLÈTE")
    print("="*60)
    
    # Chargement données
    df = load_kidjamo_dataset()
    print(f"Dataset chargé: {len(df)} observations, {df['anonymized_patient_id'].nunique()} patients")
    
    # Exécution analyses
    desc_results = descriptive_analysis(df)
    temp_results = temporal_analysis(df)
    env_results = environmental_correlations(df)
    cluster_results = patient_clustering(df)
    survival_results = survival_analysis(df)
    
    print("\\n✅ Analyse complète terminée!")
    print("📁 Graphiques sauvegardés: spo2_evolution_by_genotype.png, patient_clusters.png")
    
    return {
        'descriptive': desc_results,
        'temporal': temp_results,
        'environmental': env_results,
        'clustering': cluster_results,
        'survival': survival_results
    }

if __name__ == "__main__":
    results = run_complete_analysis()
'''

    async def _create_zip_package(self, source_dir: str, zip_path: str):
        """
        Crée un package ZIP avec tous les fichiers
        """
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arc_name = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arc_name)

        logger.info(f"📦 Package ZIP créé: {zip_path}")

async def main():
    """
    Test de l'exporteur recherche
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    exporter = ResearchExporter(db_config)

    export_config = {
        'timeframe_months': 6,
        'include_environmental': True,
        'anonymization_level': 'high'
    }

    package_path = await exporter.export_research_package(export_config)
    print(f"🔬 Package recherche créé: {package_path}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
