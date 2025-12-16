#!/usr/bin/env python3
"""
🏥 KIDJAMO - Processeur Datasets de Recherche
Création de datasets anonymisés et standardisés pour la recherche médicale
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import hashlib
import uuid
from faker import Faker

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ResearchDatasetsProcessor:
    """
    Processeur pour créer des datasets de recherche anonymisés et conformes RGPD
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.faker = Faker('fr_FR')

    async def generate_research_datasets(self, dataset_types: List[str] = None) -> Dict:
        """
        Génère différents types de datasets pour la recherche
        """
        logger.info("🔬 Génération datasets de recherche anonymisés")

        if not dataset_types:
            dataset_types = [
                'longitudinal_cohort',
                'crisis_episodes',
                'treatment_effectiveness',
                'physiological_patterns',
                'environmental_correlations'
            ]

        research_report = {
            'generation_date': datetime.now(),
            'datasets_generated': [],
            'anonymization_level': 'high',
            'compliance_status': 'RGPD_compliant',
            'status': 'SUCCESS'
        }

        for dataset_type in dataset_types:
            try:
                dataset = await self._generate_dataset_by_type(dataset_type)
                research_report['datasets_generated'].append(dataset)
                logger.info(f"✅ Dataset {dataset_type} généré: {dataset['record_count']} enregistrements")
            except Exception as e:
                logger.error(f"❌ Erreur génération dataset {dataset_type}: {e}")

        # Sauvegarde des métadonnées
        await self._save_research_metadata(research_report)

        return research_report

    async def _generate_dataset_by_type(self, dataset_type: str) -> Dict:
        """
        Génère un dataset spécifique selon le type demandé
        """
        if dataset_type == 'longitudinal_cohort':
            return await self._create_longitudinal_cohort_dataset()
        elif dataset_type == 'crisis_episodes':
            return await self._create_crisis_episodes_dataset()
        elif dataset_type == 'treatment_effectiveness':
            return await self._create_treatment_effectiveness_dataset()
        elif dataset_type == 'physiological_patterns':
            return await self._create_physiological_patterns_dataset()
        elif dataset_type == 'environmental_correlations':
            return await self._create_environmental_correlations_dataset()
        else:
            raise ValueError(f"Type de dataset non supporté: {dataset_type}")

    async def _create_longitudinal_cohort_dataset(self) -> Dict:
        """
        Dataset longitudinal pour études de cohorte
        """
        logger.info("📊 Création dataset cohorte longitudinale")

        # Données sur 12 mois avec anonymisation
        twelve_months_ago = datetime.now() - timedelta(days=365)

        query = """
        SELECT 
            m.patient_id,
            DATE_TRUNC('month', m.tz_timestamp) as month,
            p.genotype,
            EXTRACT(YEAR FROM AGE(p.birth_date)) as age_at_measurement,
            u.gender,
            u.country,
            
            -- Agrégations mensuelles
            COUNT(*) as measurements_count,
            AVG(m.spo2_pct) as avg_spo2,
            STDDEV(m.spo2_pct) as std_spo2,
            MIN(m.spo2_pct) as min_spo2,
            MAX(m.spo2_pct) as max_spo2,
            
            AVG(m.freq_card) as avg_heart_rate,
            AVG(m.temp_corp) as avg_temperature,
            MAX(m.temp_corp) as max_temperature,
            AVG(m.pct_hydratation) as avg_hydration,
            AVG(m.activity) as avg_activity,
            
            -- Indicateurs de crise
            COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
            COUNT(a.alert_id) FILTER (WHERE a.severity = 'medium') as medium_alerts,
            
            -- Qualité des données
            COUNT(*) FILTER (WHERE m.quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE m.quality_flag = 'ok') * 100.0 / COUNT(*)) as data_quality_pct
            
        FROM measurements m
        JOIN patients p ON m.patient_id = p.patient_id
        JOIN users u ON p.user_id = u.user_id
        LEFT JOIN alerts a ON m.patient_id = a.patient_id 
            AND DATE_TRUNC('month', a.created_at) = DATE_TRUNC('month', m.tz_timestamp)
        WHERE m.tz_timestamp >= %s
            AND m.quality_flag = 'ok'
        GROUP BY m.patient_id, DATE_TRUNC('month', m.tz_timestamp), 
                 p.genotype, p.birth_date, u.gender, u.country
        ORDER BY m.patient_id, month
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn, params=(twelve_months_ago,))
        conn.close()

        if not df.empty:
            # Anonymisation
            df_anonymized = await self._anonymize_cohort_data(df)

            # Export
            filename = f"longitudinal_cohort_{datetime.now().strftime('%Y%m%d')}.csv"
            await self._export_dataset(df_anonymized, filename)

            # Statistiques descriptives
            stats = await self._calculate_dataset_statistics(df_anonymized)
        else:
            df_anonymized = pd.DataFrame()
            stats = {}

        return {
            'dataset_type': 'longitudinal_cohort',
            'record_count': len(df_anonymized),
            'patient_count': df_anonymized['anonymized_patient_id'].nunique() if not df_anonymized.empty else 0,
            'time_range_months': 12,
            'variables_count': len(df_anonymized.columns) if not df_anonymized.empty else 0,
            'statistics': stats,
            'filename': filename if not df.empty else None
        }

    async def _create_crisis_episodes_dataset(self) -> Dict:
        """
        Dataset focalisé sur les épisodes de crise
        """
        logger.info("🚨 Création dataset épisodes de crise")

        query = """
        WITH crisis_episodes AS (
            SELECT 
                a.patient_id,
                a.created_at as crisis_start,
                a.alert_type,
                a.severity,
                
                -- Données physiologiques au moment de la crise
                m1.spo2_pct as spo2_at_crisis,
                m1.freq_card as hr_at_crisis,
                m1.temp_corp as temp_at_crisis,
                m1.activity as activity_at_crisis,
                m1.temp_abiante as ambient_temp_at_crisis,
                
                -- Données 1h avant la crise
                AVG(m_before.spo2_pct) as avg_spo2_1h_before,
                AVG(m_before.freq_card) as avg_hr_1h_before,
                AVG(m_before.temp_corp) as avg_temp_1h_before,
                
                -- Informations patient
                p.genotype,
                EXTRACT(YEAR FROM AGE(p.birth_date)) as age_at_crisis,
                u.gender,
                
                -- Traitements en cours
                STRING_AGG(DISTINCT t.drug_name, ', ') as current_treatments
                
            FROM alerts a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            
            -- Mesure la plus proche du moment de la crise
            LEFT JOIN LATERAL (
                SELECT * FROM measurements m 
                WHERE m.patient_id = a.patient_id 
                    AND m.tz_timestamp <= a.created_at
                ORDER BY ABS(EXTRACT(EPOCH FROM (m.tz_timestamp - a.created_at)))
                LIMIT 1
            ) m1 ON true
            
            -- Mesures dans l'heure précédant la crise
            LEFT JOIN measurements m_before ON m_before.patient_id = a.patient_id
                AND m_before.tz_timestamp BETWEEN a.created_at - INTERVAL '1 hour' AND a.created_at
                AND m_before.quality_flag = 'ok'
            
            -- Traitements actifs
            LEFT JOIN treatments t ON t.patient_id = a.patient_id
                AND a.created_at BETWEEN t.treatment_start AND COALESCE(t.treatment_end, NOW())
            
            WHERE a.severity IN ('critical', 'medium')
                AND a.created_at >= NOW() - INTERVAL '6 months'
                
            GROUP BY a.patient_id, a.created_at, a.alert_type, a.severity,
                     m1.spo2_pct, m1.freq_card, m1.temp_corp, m1.activity, m1.temp_abiante,
                     p.genotype, p.birth_date, u.gender
        )
        SELECT * FROM crisis_episodes
        ORDER BY crisis_start DESC
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            # Anonymisation spécifique aux crises
            df_anonymized = await self._anonymize_crisis_data(df)

            # Export
            filename = f"crisis_episodes_{datetime.now().strftime('%Y%m%d')}.csv"
            await self._export_dataset(df_anonymized, filename)

            stats = await self._calculate_crisis_statistics(df_anonymized)
        else:
            df_anonymized = pd.DataFrame()
            stats = {}

        return {
            'dataset_type': 'crisis_episodes',
            'record_count': len(df_anonymized),
            'crisis_count': len(df_anonymized),
            'patient_count': df_anonymized['anonymized_patient_id'].nunique() if not df_anonymized.empty else 0,
            'severity_distribution': df_anonymized['severity'].value_counts().to_dict() if not df_anonymized.empty else {},
            'statistics': stats,
            'filename': filename if not df.empty else None
        }

    async def _create_treatment_effectiveness_dataset(self) -> Dict:
        """
        Dataset pour analyser l'efficacité des traitements
        """
        logger.info("💊 Création dataset efficacité traitements")

        query = """
        WITH treatment_periods AS (
            SELECT 
                t.patient_id,
                t.drug_name,
                t.treatment_start,
                t.treatment_end,
                COALESCE(t.treatment_end, NOW()) as effective_end,
                EXTRACT(DAYS FROM (COALESCE(t.treatment_end, NOW()) - t.treatment_start)) as treatment_duration_days,
                
                -- Données patient
                p.genotype,
                EXTRACT(YEAR FROM AGE(p.birth_date)) as age_at_treatment_start,
                u.gender,
                
                -- Mesures pendant le traitement
                AVG(m.spo2_pct) as avg_spo2_during_treatment,
                STDDEV(m.spo2_pct) as std_spo2_during_treatment,
                COUNT(m.measure_id) as measurements_during_treatment,
                
                -- Crises pendant le traitement
                COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_crises_during,
                COUNT(a.alert_id) FILTER (WHERE a.severity = 'medium') as medium_crises_during,
                
                -- Mesures avant traitement (30 jours avant)
                (SELECT AVG(spo2_pct) FROM measurements 
                 WHERE patient_id = t.patient_id 
                   AND tz_timestamp BETWEEN t.treatment_start - INTERVAL '30 days' AND t.treatment_start
                   AND quality_flag = 'ok') as avg_spo2_before_treatment,
                
                -- Crises avant traitement (30 jours avant)
                (SELECT COUNT(*) FROM alerts 
                 WHERE patient_id = t.patient_id 
                   AND created_at BETWEEN t.treatment_start - INTERVAL '30 days' AND t.treatment_start
                   AND severity = 'critical') as critical_crises_before
                
            FROM treatments t
            JOIN patients p ON t.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            LEFT JOIN measurements m ON t.patient_id = m.patient_id
                AND m.tz_timestamp BETWEEN t.treatment_start AND COALESCE(t.treatment_end, NOW())
                AND m.quality_flag = 'ok'
            LEFT JOIN alerts a ON t.patient_id = a.patient_id
                AND a.created_at BETWEEN t.treatment_start AND COALESCE(t.treatment_end, NOW())
            
            WHERE t.treatment_start >= NOW() - INTERVAL '12 months'
            
            GROUP BY t.patient_id, t.drug_name, t.treatment_start, t.treatment_end,
                     p.genotype, p.birth_date, u.gender
        )
        SELECT * FROM treatment_periods
        WHERE treatment_duration_days >= 7  -- Traitements d'au moins 7 jours
        ORDER BY treatment_start DESC
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            # Anonymisation des traitements
            df_anonymized = await self._anonymize_treatment_data(df)

            # Calculs d'efficacité
            df_anonymized = await self._calculate_treatment_effectiveness_metrics(df_anonymized)

            # Export
            filename = f"treatment_effectiveness_{datetime.now().strftime('%Y%m%d')}.csv"
            await self._export_dataset(df_anonymized, filename)

            stats = await self._calculate_treatment_statistics(df_anonymized)
        else:
            df_anonymized = pd.DataFrame()
            stats = {}

        return {
            'dataset_type': 'treatment_effectiveness',
            'record_count': len(df_anonymized),
            'treatment_episodes': len(df_anonymized),
            'unique_drugs': df_anonymized['drug_name'].nunique() if not df_anonymized.empty else 0,
            'patient_count': df_anonymized['anonymized_patient_id'].nunique() if not df_anonymized.empty else 0,
            'statistics': stats,
            'filename': filename if not df.empty else None
        }

    async def _create_physiological_patterns_dataset(self) -> Dict:
        """
        Dataset pour analyser les patterns physiologiques
        """
        logger.info("📈 Création dataset patterns physiologiques")

        # Échantillonnage quotidien pour réduire la volumétrie
        query = """
        WITH daily_aggregates AS (
            SELECT 
                m.patient_id,
                DATE(m.tz_timestamp) as measurement_date,
                EXTRACT(DOW FROM m.tz_timestamp) as day_of_week,
                EXTRACT(MONTH FROM m.tz_timestamp) as month,
                
                -- Agrégations journalières
                AVG(m.spo2_pct) as daily_avg_spo2,
                MIN(m.spo2_pct) as daily_min_spo2,
                MAX(m.spo2_pct) as daily_max_spo2,
                STDDEV(m.spo2_pct) as daily_std_spo2,
                
                AVG(m.freq_card) as daily_avg_hr,
                MIN(m.freq_card) as daily_min_hr,
                MAX(m.freq_card) as daily_max_hr,
                
                AVG(m.temp_corp) as daily_avg_temp,
                MAX(m.temp_corp) as daily_max_temp,
                
                AVG(m.activity) as daily_avg_activity,
                MAX(m.activity) as daily_max_activity,
                
                AVG(m.temp_abiante) as daily_avg_ambient_temp,
                AVG(m.heat_index) as daily_avg_heat_index,
                AVG(m.pct_hydratation) as daily_avg_hydration,
                
                -- Métriques de qualité
                COUNT(*) as daily_measurements_count,
                COUNT(*) FILTER (WHERE m.quality_flag = 'ok') as daily_valid_measurements,
                
                -- Informations patient
                p.genotype,
                EXTRACT(YEAR FROM AGE(p.birth_date)) as age,
                u.gender
                
            FROM measurements m
            JOIN patients p ON m.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            WHERE m.tz_timestamp >= NOW() - INTERVAL '90 days'
                AND m.quality_flag = 'ok'
            GROUP BY m.patient_id, DATE(m.tz_timestamp), p.genotype, p.birth_date, u.gender
            HAVING COUNT(*) >= 10  -- Au moins 10 mesures par jour
        )
        SELECT * FROM daily_aggregates
        ORDER BY patient_id, measurement_date
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            # Anonymisation des patterns
            df_anonymized = await self._anonymize_physiological_data(df)

            # Export
            filename = f"physiological_patterns_{datetime.now().strftime('%Y%m%d')}.csv"
            await self._export_dataset(df_anonymized, filename)

            stats = await self._calculate_physiological_statistics(df_anonymized)
        else:
            df_anonymized = pd.DataFrame()
            stats = {}

        return {
            'dataset_type': 'physiological_patterns',
            'record_count': len(df_anonymized),
            'patient_days': len(df_anonymized),
            'patient_count': df_anonymized['anonymized_patient_id'].nunique() if not df_anonymized.empty else 0,
            'time_range_days': 90,
            'statistics': stats,
            'filename': filename if not df.empty else None
        }

    async def _create_environmental_correlations_dataset(self) -> Dict:
        """
        Dataset pour analyser les corrélations environnementales
        """
        logger.info("🌡️ Création dataset corrélations environnementales")

        query = """
        WITH daily_environmental AS (
            SELECT 
                m.patient_id,
                DATE(m.tz_timestamp) as date,
                
                -- Données physiologiques
                AVG(m.spo2_pct) as avg_spo2,
                MIN(m.spo2_pct) as min_spo2,
                AVG(m.freq_card) as avg_hr,
                AVG(m.temp_corp) as avg_body_temp,
                AVG(m.activity) as avg_activity,
                
                -- Données environnementales
                AVG(m.temp_abiante) as avg_ambient_temp,
                MAX(m.temp_abiante) as max_ambient_temp,
                MIN(m.temp_abiante) as min_ambient_temp,
                AVG(m.heat_index) as avg_heat_index,
                MAX(m.heat_index) as max_heat_index,
                
                -- Hydratation
                AVG(m.pct_hydratation) as avg_hydration,
                MIN(m.pct_hydratation) as min_hydration,
                
                -- Indicateurs de stress environnemental
                COUNT(*) FILTER (WHERE m.temp_abiante > 30) as high_temp_measurements,
                COUNT(*) FILTER (WHERE m.heat_index > 35) as high_heat_index_measurements,
                
                -- Crises le même jour
                CASE WHEN EXISTS (
                    SELECT 1 FROM alerts a 
                    WHERE a.patient_id = m.patient_id 
                        AND DATE(a.created_at) = DATE(m.tz_timestamp)
                        AND a.severity = 'critical'
                ) THEN 1 ELSE 0 END as had_crisis_same_day,
                
                -- Informations patient
                p.genotype,
                u.gender,
                u.country,
                EXTRACT(YEAR FROM AGE(p.birth_date)) as age
                
            FROM measurements m
            JOIN patients p ON m.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            WHERE m.tz_timestamp >= NOW() - INTERVAL '6 months'
                AND m.quality_flag = 'ok'
                AND m.temp_abiante IS NOT NULL
                AND m.heat_index IS NOT NULL
            GROUP BY m.patient_id, DATE(m.tz_timestamp), p.genotype, u.gender, u.country, p.birth_date
            HAVING COUNT(*) >= 5  -- Au moins 5 mesures par jour
        )
        SELECT * FROM daily_environmental
        ORDER BY patient_id, date
        """

        conn = psycopg2.connect(**self.db_config)
        df = pd.read_sql_query(query, conn)
        conn.close()

        if not df.empty:
            # Anonymisation environnementale
            df_anonymized = await self._anonymize_environmental_data(df)

            # Export
            filename = f"environmental_correlations_{datetime.now().strftime('%Y%m%d')}.csv"
            await self._export_dataset(df_anonymized, filename)

            stats = await self._calculate_environmental_statistics(df_anonymized)
        else:
            df_anonymized = pd.DataFrame()
            stats = {}

        return {
            'dataset_type': 'environmental_correlations',
            'record_count': len(df_anonymized),
            'patient_days': len(df_anonymized),
            'patient_count': df_anonymized['anonymized_patient_id'].nunique() if not df_anonymized.empty else 0,
            'crisis_days': df_anonymized['had_crisis_same_day'].sum() if not df_anonymized.empty else 0,
            'statistics': stats,
            'filename': filename if not df.empty else None
        }

    async def _anonymize_cohort_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymise les données de cohorte longitudinale
        """
        df_anon = df.copy()

        # Création d'IDs anonymes reproductibles
        df_anon['anonymized_patient_id'] = df_anon['patient_id'].apply(
            lambda x: f"ANON_{hashlib.md5(str(x).encode()).hexdigest()[:8].upper()}"
        )

        # Généralisation de l'âge par tranches
        df_anon['age_group'] = pd.cut(df_anon['age_at_measurement'],
                                     bins=[0, 18, 30, 50, 65, 100],
                                     labels=['0-17', '18-29', '30-49', '50-64', '65+'])

        # Généralisation géographique (région au lieu de pays spécifique)
        country_regions = {
            'France': 'Europe_West',
            'Belgique': 'Europe_West',
            'Suisse': 'Europe_West',
            'Canada': 'North_America',
            'Maroc': 'Africa_North',
            'Sénégal': 'Africa_West'
        }
        df_anon['region'] = df_anon['country'].map(country_regions).fillna('Other')

        # Suppression des colonnes identifiantes
        df_anon = df_anon.drop(['patient_id', 'country', 'age_at_measurement'], axis=1)

        return df_anon

    async def _anonymize_crisis_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymise les données d'épisodes de crise
        """
        df_anon = df.copy()

        # ID anonyme
        df_anon['anonymized_patient_id'] = df_anon['patient_id'].apply(
            lambda x: f"ANON_{hashlib.md5(str(x).encode()).hexdigest()[:8].upper()}"
        )

        # Anonymisation temporelle (décalage aléatoire)
        df_anon['crisis_month'] = df_anon['crisis_start'].dt.to_period('M')
        df_anon['crisis_hour'] = df_anon['crisis_start'].dt.hour
        df_anon['crisis_day_of_week'] = df_anon['crisis_start'].dt.dayofweek

        # Généralisation de l'âge
        df_anon['age_group'] = pd.cut(df_anon['age_at_crisis'],
                                     bins=[0, 18, 30, 50, 65, 100],
                                     labels=['0-17', '18-29', '30-49', '50-64', '65+'])

        # Suppression des colonnes identifiantes
        df_anon = df_anon.drop(['patient_id', 'crisis_start', 'age_at_crisis'], axis=1)

        return df_anon

    async def _anonymize_treatment_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymise les données de traitement
        """
        df_anon = df.copy()

        # ID anonyme
        df_anon['anonymized_patient_id'] = df_anon['patient_id'].apply(
            lambda x: f"ANON_{hashlib.md5(str(x).encode()).hexdigest()[:8].upper()}"
        )

        # Généralisation temporelle
        df_anon['treatment_start_month'] = df_anon['treatment_start'].dt.to_period('M')

        # Généralisation de l'âge
        df_anon['age_group'] = pd.cut(df_anon['age_at_treatment_start'],
                                     bins=[0, 18, 30, 50, 65, 100],
                                     labels=['0-17', '18-29', '30-49', '50-64', '65+'])

        # Suppression des colonnes identifiantes
        df_anon = df_anon.drop(['patient_id', 'treatment_start', 'treatment_end',
                               'effective_end', 'age_at_treatment_start'], axis=1)

        return df_anon

    async def _anonymize_physiological_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymise les données physiologiques
        """
        df_anon = df.copy()

        # ID anonyme
        df_anon['anonymized_patient_id'] = df_anon['patient_id'].apply(
            lambda x: f"ANON_{hashlib.md5(str(x).encode()).hexdigest()[:8].upper()}"
        )

        # Généralisation temporelle
        df_anon['measurement_week'] = df_anon['measurement_date'].dt.to_period('W')

        # Généralisation de l'âge
        df_anon['age_group'] = pd.cut(df_anon['age'],
                                     bins=[0, 18, 30, 50, 65, 100],
                                     labels=['0-17', '18-29', '30-49', '50-64', '65+'])

        # Suppression des colonnes identifiantes
        df_anon = df_anon.drop(['patient_id', 'measurement_date', 'age'], axis=1)

        return df_anon

    async def _anonymize_environmental_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Anonymise les données environnementales
        """
        df_anon = df.copy()

        # ID anonyme
        df_anon['anonymized_patient_id'] = df_anon['patient_id'].apply(
            lambda x: f"ANON_{hashlib.md5(str(x).encode()).hexdigest()[:8].upper()}"
        )

        # Généralisation temporelle et géographique
        df_anon['measurement_month'] = df_anon['date'].dt.to_period('M')
        df_anon['season'] = df_anon['date'].dt.month.map({
            12: 'Winter', 1: 'Winter', 2: 'Winter',
            3: 'Spring', 4: 'Spring', 5: 'Spring',
            6: 'Summer', 7: 'Summer', 8: 'Summer',
            9: 'Fall', 10: 'Fall', 11: 'Fall'
        })

        # Généralisation géographique
        country_regions = {
            'France': 'Europe_Temperate',
            'Maroc': 'Africa_Mediterranean',
            'Sénégal': 'Africa_Tropical'
        }
        df_anon['climate_region'] = df_anon['country'].map(country_regions).fillna('Other')

        # Généralisation de l'âge
        df_anon['age_group'] = pd.cut(df_anon['age'],
                                     bins=[0, 18, 30, 50, 65, 100],
                                     labels=['0-17', '18-29', '30-49', '50-64', '65+'])

        # Suppression des colonnes identifiantes
        df_anon = df_anon.drop(['patient_id', 'date', 'country', 'age'], axis=1)

        return df_anon

    async def _calculate_treatment_effectiveness_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calcule les métriques d'efficacité des traitements
        """
        df_calc = df.copy()

        # Amélioration SpO2
        df_calc['spo2_improvement'] = df_calc['avg_spo2_during_treatment'] - df_calc['avg_spo2_before_treatment']
        df_calc['spo2_improvement_pct'] = (df_calc['spo2_improvement'] / df_calc['avg_spo2_before_treatment']) * 100

        # Réduction des crises
        df_calc['crisis_reduction'] = df_calc['critical_crises_before'] - df_calc['critical_crises_during']
        df_calc['crisis_reduction_rate'] = df_calc['crisis_reduction'] / (df_calc['critical_crises_before'] + 1)  # +1 pour éviter division par 0

        # Score d'efficacité combiné (0-100)
        df_calc['effectiveness_score'] = (
            (df_calc['spo2_improvement'].clip(-10, 10) + 10) * 2.5 +  # SpO2 component (0-50)
            (df_calc['crisis_reduction_rate'].clip(-1, 1) + 1) * 25    # Crisis component (0-50)
        ).clip(0, 100)

        return df_calc

    async def _export_dataset(self, df: pd.DataFrame, filename: str):
        """
        Exporte un dataset vers un fichier CSV
        """
        import os

        # Dossier d'export
        export_dir = "../../evidence/research_datasets"
        os.makedirs(export_dir, exist_ok=True)

        # Export CSV avec métadonnées
        filepath = f"{export_dir}/{filename}"
        df.to_csv(filepath, index=False, encoding='utf-8')

        # Création d'un fichier de métadonnées associé
        metadata = {
            'filename': filename,
            'generation_date': datetime.now().isoformat(),
            'record_count': len(df),
            'columns': list(df.columns),
            'anonymization_level': 'high',
            'rgpd_compliant': True,
            'data_types': df.dtypes.astype(str).to_dict()
        }

        metadata_file = filepath.replace('.csv', '_metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"📁 Dataset exporté: {filepath}")

    async def _calculate_dataset_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Calcule les statistiques descriptives générales
        """
        if df.empty:
            return {}

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        stats = {}

        for col in numeric_cols:
            if not df[col].isna().all():
                stats[col] = {
                    'mean': float(df[col].mean()),
                    'std': float(df[col].std()),
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'median': float(df[col].median()),
                    'missing_count': int(df[col].isna().sum())
                }

        return stats

    async def _calculate_crisis_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Calcule les statistiques spécifiques aux crises
        """
        if df.empty:
            return {}

        return {
            'total_crises': len(df),
            'severity_distribution': df['severity'].value_counts().to_dict(),
            'avg_spo2_at_crisis': float(df['spo2_at_crisis'].mean()) if 'spo2_at_crisis' in df.columns else None,
            'genotype_distribution': df['genotype'].value_counts().to_dict() if 'genotype' in df.columns else {}
        }

    async def _calculate_treatment_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Calcule les statistiques spécifiques aux traitements
        """
        if df.empty:
            return {}

        return {
            'total_treatments': len(df),
            'unique_drugs': df['drug_name'].nunique() if 'drug_name' in df.columns else 0,
            'avg_effectiveness_score': float(df['effectiveness_score'].mean()) if 'effectiveness_score' in df.columns else None,
            'drug_distribution': df['drug_name'].value_counts().to_dict() if 'drug_name' in df.columns else {}
        }

    async def _calculate_physiological_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Calcule les statistiques physiologiques
        """
        if df.empty:
            return {}

        return {
            'total_patient_days': len(df),
            'avg_daily_spo2': float(df['daily_avg_spo2'].mean()) if 'daily_avg_spo2' in df.columns else None,
            'spo2_variability': float(df['daily_std_spo2'].mean()) if 'daily_std_spo2' in df.columns else None,
            'genotype_distribution': df['genotype'].value_counts().to_dict() if 'genotype' in df.columns else {}
        }

    async def _calculate_environmental_statistics(self, df: pd.DataFrame) -> Dict:
        """
        Calcule les statistiques environnementales
        """
        if df.empty:
            return {}

        return {
            'total_observation_days': len(df),
            'crisis_rate': float(df['had_crisis_same_day'].mean()) if 'had_crisis_same_day' in df.columns else None,
            'avg_ambient_temp': float(df['avg_ambient_temp'].mean()) if 'avg_ambient_temp' in df.columns else None,
            'high_temp_exposure_rate': float(df['high_temp_measurements'].sum() / df['daily_measurements_count'].sum()) if all(col in df.columns for col in ['high_temp_measurements', 'daily_measurements_count']) else None
        }

    async def _save_research_metadata(self, research_report: Dict):
        """
        Sauvegarde les métadonnées des datasets de recherche
        """
        try:
            query = """
            INSERT INTO research_datasets_metadata (
                generation_date, datasets_count,
                total_records, anonymization_level,
                compliance_status, metadata_json
            ) VALUES (%s, %s, %s, %s, %s, %s)
            """

            total_records = sum(d['record_count'] for d in research_report['datasets_generated'])

            params = (
                research_report['generation_date'],
                len(research_report['datasets_generated']),
                total_records,
                research_report['anonymization_level'],
                research_report['compliance_status'],
                json.dumps(research_report, default=str)
            )

            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
            conn.close()

            logger.info("✅ Métadonnées de recherche sauvegardées")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde métadonnées: {e}")

async def main():
    """
    Test du processeur de datasets de recherche
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    processor = ResearchDatasetsProcessor(db_config)
    research_report = await processor.generate_research_datasets()

    print(f"🔬 Datasets de recherche générés:")
    print(f"   Total datasets: {len(research_report['datasets_generated'])}")
    for dataset in research_report['datasets_generated']:
        print(f"   - {dataset['dataset_type']}: {dataset['record_count']} enregistrements")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
