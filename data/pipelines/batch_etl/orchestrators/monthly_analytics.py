#!/usr/bin/env python3
"""
🏥 KIDJAMO - Analyses Mensuelles Batch ETL
Analyses approfondies mensuelles pour insights médicaux et recherche
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonthlyAnalyticsProcessor:
    """
    Processeur pour analyses mensuelles approfondies et insights médicaux
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.month_end = datetime.now().date().replace(day=1) - timedelta(days=1)  # Dernier jour mois précédent
        self.month_start = self.month_end.replace(day=1)  # Premier jour mois précédent

    async def run_monthly_analytics(self) -> Dict:
        """
        Exécute toutes les analyses mensuelles
        """
        logger.info(f"🔬 Démarrage analyses mensuelles {self.month_start} → {self.month_end}")

        results = {
            'month_start': self.month_start,
            'month_end': self.month_end,
            'start_time': datetime.now(),
            'analytics_completed': [],
            'insights_generated': [],
            'errors': []
        }

        try:
            # 1. Analyses épidémiologiques de cohorte
            await self._run_epidemiological_analysis()
            results['analytics_completed'].append('epidemiological')

            # 2. Analyses prédictives et tendances
            insights = await self._run_predictive_analysis()
            results['insights_generated'].extend(insights)
            results['analytics_completed'].append('predictive')

            # 3. Efficacité des traitements
            await self._analyze_treatment_effectiveness()
            results['analytics_completed'].append('treatment_effectiveness')

            # 4. Corrélations environnementales
            await self._analyze_environmental_correlations()
            results['analytics_completed'].append('environmental_correlations')

            # 5. Analyses de compliance et engagement
            await self._analyze_patient_compliance()
            results['analytics_completed'].append('compliance_analysis')

            # 6. Détection d'anomalies et patterns
            anomalies = await self._detect_monthly_anomalies()
            results['insights_generated'].extend(anomalies)
            results['analytics_completed'].append('anomaly_detection')

            # 7. Recommandations d'amélioration système
            recommendations = await self._generate_system_recommendations()
            results['insights_generated'].extend(recommendations)
            results['analytics_completed'].append('system_recommendations')

            results['end_time'] = datetime.now()
            results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
            results['status'] = 'SUCCESS'

            logger.info(f"✅ Analyses mensuelles terminées en {results['duration']:.1f}s")

        except Exception as e:
            results['errors'].append(str(e))
            results['status'] = 'FAILED'
            logger.error(f"❌ Erreur analyses mensuelles: {e}")

        return results

    async def _run_epidemiological_analysis(self):
        """
        Analyses épidémiologiques sur la cohorte de patients
        """
        logger.info("🔬 Analyse épidémiologique de cohorte...")

        # Analyse par génotype
        genotype_analysis = await self._analyze_by_genotype()

        # Analyse par tranche d'âge
        age_analysis = await self._analyze_by_age_groups()

        # Saisonnalité des crises
        seasonal_analysis = await self._analyze_seasonal_patterns()

        # Sauvegarde des résultats
        query = """
        INSERT INTO monthly_epidemiological_analysis (
            month_start, month_end,
            genotype_ss_avg_spo2, genotype_sc_avg_spo2, genotype_as_avg_spo2,
            pediatric_crisis_rate, adult_crisis_rate,
            seasonal_pattern_detected, peak_crisis_month,
            total_patients_analyzed, generated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (month_start) DO UPDATE SET
            genotype_ss_avg_spo2 = EXCLUDED.genotype_ss_avg_spo2,
            genotype_sc_avg_spo2 = EXCLUDED.genotype_sc_avg_spo2,
            genotype_as_avg_spo2 = EXCLUDED.genotype_as_avg_spo2,
            pediatric_crisis_rate = EXCLUDED.pediatric_crisis_rate,
            adult_crisis_rate = EXCLUDED.adult_crisis_rate,
            seasonal_pattern_detected = EXCLUDED.seasonal_pattern_detected,
            peak_crisis_month = EXCLUDED.peak_crisis_month,
            total_patients_analyzed = EXCLUDED.total_patients_analyzed
        """

        await self._execute_query(query, (
            self.month_start, self.month_end,
            genotype_analysis.get('SS', {}).get('avg_spo2'),
            genotype_analysis.get('SC', {}).get('avg_spo2'),
            genotype_analysis.get('AS', {}).get('avg_spo2'),
            age_analysis.get('pediatric_crisis_rate'),
            age_analysis.get('adult_crisis_rate'),
            seasonal_analysis.get('pattern_detected'),
            seasonal_analysis.get('peak_month'),
            len(await self._get_analyzed_patients())
        ))

    async def _analyze_by_genotype(self) -> Dict:
        """
        Analyse comparative par génotype de drépanocytose
        """
        query = """
        SELECT 
            p.genotype,
            COUNT(DISTINCT p.patient_id) as patient_count,
            AVG(m.spo2_pct) as avg_spo2,
            STDDEV(m.spo2_pct) as std_spo2,
            COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
            COUNT(DISTINCT DATE(a.created_at)) as crisis_days,
            AVG(m.temp_corp) as avg_temperature,
            MAX(m.temp_corp) as max_temperature
        FROM patients p
        LEFT JOIN measurements m ON p.patient_id = m.patient_id 
            AND DATE(m.tz_timestamp) BETWEEN %s AND %s
        LEFT JOIN alerts a ON p.patient_id = a.patient_id 
            AND DATE(a.created_at) BETWEEN %s AND %s
        WHERE p.genotype IN ('SS', 'SC', 'AS')
        GROUP BY p.genotype
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (self.month_start, self.month_end,
                                 self.month_start, self.month_end))
            results = {row['genotype']: dict(row) for row in cursor.fetchall()}
        conn.close()

        return results

    async def _analyze_by_age_groups(self) -> Dict:
        """
        Analyse comparative par tranches d'âge
        """
        query = """
        SELECT 
            CASE 
                WHEN EXTRACT(YEAR FROM AGE(birth_date)) < 18 THEN 'pediatric'
                ELSE 'adult'
            END as age_group,
            COUNT(DISTINCT p.patient_id) as patient_count,
            COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
            (COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') * 1.0 / COUNT(DISTINCT p.patient_id)) as crisis_rate
        FROM patients p
        LEFT JOIN alerts a ON p.patient_id = a.patient_id 
            AND DATE(a.created_at) BETWEEN %s AND %s
        GROUP BY age_group
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (self.month_start, self.month_end))
            results = {row['age_group'] + '_crisis_rate': row['crisis_rate']
                      for row in cursor.fetchall()}
        conn.close()

        return results

    async def _run_predictive_analysis(self) -> List[str]:
        """
        Analyses prédictives et détection de tendances
        """
        logger.info("🔮 Analyses prédictives et tendances...")

        insights = []

        # Prédiction des risques de crise
        risk_predictions = await self._predict_crisis_risk()
        if risk_predictions['high_risk_patients']:
            insights.append(f"🚨 {len(risk_predictions['high_risk_patients'])} patients à haut risque identifiés")

        # Tendances d'évolution SpO2
        spo2_trends = await self._analyze_spo2_trends()
        if spo2_trends['declining_patients']:
            insights.append(f"📉 {len(spo2_trends['declining_patients'])} patients montrent une tendance dégradante")

        # Efficacité du monitoring
        monitoring_insights = await self._analyze_monitoring_effectiveness()
        insights.extend(monitoring_insights)

        return insights

    async def _predict_crisis_risk(self) -> Dict:
        """
        Prédiction du risque de crise basée sur les patterns historiques
        """
        query = """
        WITH patient_risk_factors AS (
            SELECT 
                p.patient_id,
                AVG(m.spo2_pct) as avg_spo2,
                STDDEV(m.spo2_pct) as spo2_variability,
                COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as recent_crises,
                AVG(m.temp_corp) as avg_temperature,
                CASE 
                    WHEN p.genotype = 'SS' THEN 3
                    WHEN p.genotype = 'SC' THEN 2
                    ELSE 1
                END as genotype_risk_score
            FROM patients p
            LEFT JOIN measurements m ON p.patient_id = m.patient_id 
                AND m.tz_timestamp >= NOW() - INTERVAL '30 days'
            LEFT JOIN alerts a ON p.patient_id = a.patient_id 
                AND a.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY p.patient_id, p.genotype
        )
        SELECT 
            patient_id,
            (
                CASE WHEN avg_spo2 < 92 THEN 3 WHEN avg_spo2 < 95 THEN 2 ELSE 1 END +
                CASE WHEN spo2_variability > 5 THEN 2 ELSE 1 END +
                CASE WHEN recent_crises > 2 THEN 3 WHEN recent_crises > 0 THEN 2 ELSE 1 END +
                genotype_risk_score
            ) as risk_score
        FROM patient_risk_factors
        WHERE avg_spo2 IS NOT NULL
        ORDER BY risk_score DESC
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
        conn.close()

        high_risk_patients = [r['patient_id'] for r in results if r['risk_score'] >= 8]

        return {
            'high_risk_patients': high_risk_patients,
            'risk_distribution': results
        }

    async def _analyze_spo2_trends(self) -> Dict:
        """
        Analyse des tendances SpO2 sur les 3 derniers mois
        """
        query = """
        WITH monthly_spo2 AS (
            SELECT 
                patient_id,
                DATE_TRUNC('month', tz_timestamp) as month,
                AVG(spo2_pct) as avg_spo2
            FROM measurements 
            WHERE tz_timestamp >= NOW() - INTERVAL '3 months'
                AND spo2_pct IS NOT NULL
            GROUP BY patient_id, DATE_TRUNC('month', tz_timestamp)
        ),
        trends AS (
            SELECT 
                patient_id,
                REGR_SLOPE(avg_spo2, EXTRACT(EPOCH FROM month)) as trend_slope
            FROM monthly_spo2
            GROUP BY patient_id
            HAVING COUNT(*) >= 2
        )
        SELECT patient_id, trend_slope
        FROM trends
        WHERE trend_slope < -0.5  -- Déclin significatif
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            declining_patients = [row['patient_id'] for row in cursor.fetchall()]
        conn.close()

        return {'declining_patients': declining_patients}

    async def _analyze_treatment_effectiveness(self):
        """
        Analyse de l'efficacité des traitements
        """
        logger.info("💊 Analyse efficacité des traitements...")

        query = """
        WITH treatment_outcomes AS (
            SELECT 
                t.drug_name,
                COUNT(DISTINCT t.patient_id) as patients_count,
                AVG(m.spo2_pct) as avg_spo2_during_treatment,
                COUNT(a.alert_id) FILTER (WHERE a.severity = 'critical') as crises_during_treatment,
                AVG(EXTRACT(EPOCH FROM (t.treatment_end - t.treatment_start))/86400) as avg_treatment_duration_days
            FROM treatments t
            LEFT JOIN measurements m ON t.patient_id = m.patient_id 
                AND m.tz_timestamp BETWEEN t.treatment_start AND COALESCE(t.treatment_end, NOW())
            LEFT JOIN alerts a ON t.patient_id = a.patient_id 
                AND a.created_at BETWEEN t.treatment_start AND COALESCE(t.treatment_end, NOW())
            WHERE t.treatment_start BETWEEN %s AND %s
            GROUP BY t.drug_name
            HAVING COUNT(DISTINCT t.patient_id) >= 3
        )
        INSERT INTO monthly_treatment_analysis (
            month_start, month_end, drug_name, patients_count,
            avg_spo2_during_treatment, crises_during_treatment,
            avg_treatment_duration_days, generated_at
        )
        SELECT %s, %s, drug_name, patients_count, avg_spo2_during_treatment,
               crises_during_treatment, avg_treatment_duration_days, NOW()
        FROM treatment_outcomes
        ON CONFLICT (month_start, drug_name) DO UPDATE SET
            patients_count = EXCLUDED.patients_count,
            avg_spo2_during_treatment = EXCLUDED.avg_spo2_during_treatment,
            crises_during_treatment = EXCLUDED.crises_during_treatment,
            avg_treatment_duration_days = EXCLUDED.avg_treatment_duration_days
        """

        await self._execute_query(query, (self.month_start, self.month_end,
                                        self.month_start, self.month_end))

    async def _analyze_environmental_correlations(self):
        """
        Analyse des corrélations avec facteurs environnementaux
        """
        logger.info("🌡️ Analyse corrélations environnementales...")

        # Corrélation température ambiante vs crises
        query = """
        WITH daily_env_data AS (
            SELECT 
                DATE(tz_timestamp) as date,
                AVG(temp_abiante) as avg_ambient_temp,
                AVG(heat_index) as avg_heat_index,
                COUNT(DISTINCT patient_id) as patients_monitored
            FROM measurements 
            WHERE DATE(tz_timestamp) BETWEEN %s AND %s
                AND temp_abiante IS NOT NULL
            GROUP BY DATE(tz_timestamp)
        ),
        daily_crises AS (
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as crisis_count
            FROM alerts 
            WHERE DATE(created_at) BETWEEN %s AND %s
                AND severity = 'critical'
            GROUP BY DATE(created_at)
        )
        INSERT INTO monthly_environmental_analysis (
            month_start, month_end,
            avg_ambient_temperature, avg_heat_index,
            high_temp_crisis_correlation, generated_at
        )
        SELECT 
            %s, %s,
            AVG(e.avg_ambient_temp),
            AVG(e.avg_heat_index),
            CORR(e.avg_ambient_temp, COALESCE(c.crisis_count, 0)),
            NOW()
        FROM daily_env_data e
        LEFT JOIN daily_crises c ON e.date = c.date
        ON CONFLICT (month_start) DO UPDATE SET
            avg_ambient_temperature = EXCLUDED.avg_ambient_temperature,
            avg_heat_index = EXCLUDED.avg_heat_index,
            high_temp_crisis_correlation = EXCLUDED.high_temp_crisis_correlation
        """

        await self._execute_query(query, (
            self.month_start, self.month_end, self.month_start, self.month_end,
            self.month_start, self.month_end
        ))

    async def _analyze_patient_compliance(self):
        """
        Analyse de la compliance et engagement des patients
        """
        logger.info("📊 Analyse compliance patients...")

        query = """
        WITH patient_compliance AS (
            SELECT 
                p.patient_id,
                COUNT(DISTINCT DATE(m.tz_timestamp)) as days_with_data,
                %s - %s + 1 as total_days_in_month,
                (COUNT(DISTINCT DATE(m.tz_timestamp)) * 100.0 / (%s - %s + 1)) as compliance_rate,
                COUNT(m.measure_id) as total_measurements,
                COUNT(m.measure_id) FILTER (WHERE m.quality_flag = 'ok') as valid_measurements
            FROM patients p
            LEFT JOIN measurements m ON p.patient_id = m.patient_id 
                AND DATE(m.tz_timestamp) BETWEEN %s AND %s
            GROUP BY p.patient_id
        )
        INSERT INTO monthly_compliance_analysis (
            month_start, month_end,
            avg_compliance_rate, high_compliance_patients,
            low_compliance_patients, avg_data_quality,
            generated_at
        )
        SELECT 
            %s, %s,
            AVG(compliance_rate),
            COUNT(*) FILTER (WHERE compliance_rate >= 80),
            COUNT(*) FILTER (WHERE compliance_rate < 50),
            AVG(valid_measurements * 100.0 / NULLIF(total_measurements, 0)),
            NOW()
        FROM patient_compliance
        ON CONFLICT (month_start) DO UPDATE SET
            avg_compliance_rate = EXCLUDED.avg_compliance_rate,
            high_compliance_patients = EXCLUDED.high_compliance_patients,
            low_compliance_patients = EXCLUDED.low_compliance_patients,
            avg_data_quality = EXCLUDED.avg_data_quality
        """

        month_days = (self.month_end - self.month_start).days + 1
        await self._execute_query(query, (
            month_days, 0, month_days, 0,  # Calculs de jours
            self.month_start, self.month_end,  # Filtre dates
            self.month_start, self.month_end   # INSERT
        ))

    async def _detect_monthly_anomalies(self) -> List[str]:
        """
        Détection d'anomalies et patterns inhabituels
        """
        logger.info("🔍 Détection anomalies mensuelles...")

        anomalies = []

        # Détection pics d'alertes inhabituels
        query = """
        SELECT DATE(created_at) as date, COUNT(*) as alert_count
        FROM alerts 
        WHERE DATE(created_at) BETWEEN %s AND %s
        GROUP BY DATE(created_at)
        HAVING COUNT(*) > (
            SELECT AVG(daily_count) + 2 * STDDEV(daily_count)
            FROM (
                SELECT COUNT(*) as daily_count
                FROM alerts 
                WHERE created_at >= NOW() - INTERVAL '3 months'
                GROUP BY DATE(created_at)
            ) daily_stats
        )
        ORDER BY alert_count DESC
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (self.month_start, self.month_end))
            spike_days = cursor.fetchall()
        conn.close()

        if spike_days:
            anomalies.append(f"⚠️ {len(spike_days)} jours avec pics d'alertes anormaux détectés")

        return anomalies

    async def _generate_system_recommendations(self) -> List[str]:
        """
        Génère des recommandations d'amélioration du système
        """
        logger.info("💡 Génération recommandations système...")

        recommendations = []

        # Analyse performance globale
        performance_data = await self._get_system_performance_metrics()

        if performance_data.get('avg_quality_score', 100) < 95:
            recommendations.append("📡 Améliorer la qualité des capteurs IoT")

        if performance_data.get('avg_compliance_rate', 100) < 70:
            recommendations.append("📱 Campagne sensibilisation port capteurs")

        if performance_data.get('unresolved_alerts_rate', 0) > 10:
            recommendations.append("🚨 Optimiser workflows résolution alertes")

        return recommendations

    async def _get_system_performance_metrics(self) -> Dict:
        """
        Récupère les métriques de performance système
        """
        query = """
        SELECT 
            AVG(CASE WHEN quality_flag = 'ok' THEN 100 ELSE 0 END) as avg_quality_score,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_percentage
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (self.month_start, self.month_end))
            metrics = dict(cursor.fetchone() or {})
        conn.close()

        return metrics

    async def _get_analyzed_patients(self) -> List[str]:
        """
        Récupère la liste des patients analysés ce mois
        """
        query = """
        SELECT DISTINCT patient_id 
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor() as cursor:
            cursor.execute(query, (self.month_start, self.month_end))
            patients = [row[0] for row in cursor.fetchall()]
        conn.close()

        return patients

    async def _analyze_seasonal_patterns(self) -> Dict:
        """
        Analyse des patterns saisonniers (nécessite données historiques)
        """
        # Placeholder pour analyse saisonnière
        return {
            'pattern_detected': False,
            'peak_month': None
        }

    async def _analyze_monitoring_effectiveness(self) -> List[str]:
        """
        Analyse l'efficacité du monitoring
        """
        insights = []

        # Temps de détection moyen des crises
        query = """
        SELECT AVG(EXTRACT(EPOCH FROM (a.created_at - m.tz_timestamp))/60) as avg_detection_time_minutes
        FROM alerts a
        JOIN measurements m ON a.patient_id = m.patient_id
        WHERE a.severity = 'critical'
            AND DATE(a.created_at) BETWEEN %s AND %s
            AND m.tz_timestamp <= a.created_at
            AND m.tz_timestamp >= a.created_at - INTERVAL '1 hour'
        ORDER BY m.tz_timestamp DESC
        LIMIT 1
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor() as cursor:
            cursor.execute(query, (self.month_start, self.month_end))
            result = cursor.fetchone()
        conn.close()

        if result and result[0]:
            avg_detection = result[0]
            if avg_detection < 5:
                insights.append("⚡ Excellent temps de détection des crises (< 5min)")
            elif avg_detection > 15:
                insights.append("⏰ Temps de détection à optimiser (> 15min)")

        return insights

    async def _execute_query(self, query: str, params: tuple = None):
        """
        Exécute une requête SQL de manière sécurisée
        """
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Erreur SQL: {e}")
            raise

async def main():
    """
    Point d'entrée principal pour les analyses mensuelles
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    processor = MonthlyAnalyticsProcessor(db_config)
    results = await processor.run_monthly_analytics()

    print(f"📋 Résultats analyses mensuelles:")
    print(f"   Période: {results['month_start']} → {results['month_end']}")
    print(f"   Statut: {results['status']}")
    print(f"   Durée: {results.get('duration', 'N/A'):.1f}s")
    print(f"   Analyses réalisées: {len(results['analytics_completed'])}")
    print(f"   Insights générés: {len(results['insights_generated'])}")

if __name__ == "__main__":
    asyncio.run(main())
