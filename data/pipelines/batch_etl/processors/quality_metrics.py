#!/usr/bin/env python3
"""
🏥 KIDJAMO - Processeur Métriques Qualité
Calcul et analyse des métriques de qualité des données sur de larges fenêtres temporelles
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QualityMetricsProcessor:
    """
    Processeur pour analyser la qualité des données médicales IoT
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config

    async def calculate_comprehensive_quality_metrics(self, timeframe_days: int = 30) -> Dict:
        """
        Calcule des métriques de qualité complètes sur une période donnée
        """
        logger.info(f"🔍 Calcul métriques qualité sur {timeframe_days} jours")

        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=timeframe_days)

        quality_report = {
            'analysis_period': {'start': start_date, 'end': end_date},
            'analysis_date': datetime.now(),
            'timeframe_days': timeframe_days,
            'status': 'SUCCESS'
        }

        # 1. Métriques globales de qualité
        quality_report['global_metrics'] = await self._calculate_global_quality_metrics(start_date, end_date)

        # 2. Qualité par patient
        quality_report['patient_quality'] = await self._calculate_per_patient_quality(start_date, end_date)

        # 3. Qualité par capteur/device
        quality_report['device_quality'] = await self._calculate_per_device_quality(start_date, end_date)

        # 4. Patterns temporels de qualité
        quality_report['temporal_patterns'] = await self._analyze_temporal_quality_patterns(start_date, end_date)

        # 5. Détection d'anomalies qualité
        quality_report['quality_anomalies'] = await self._detect_quality_anomalies(start_date, end_date)

        # 6. Recommandations d'amélioration
        quality_report['recommendations'] = await self._generate_quality_recommendations(quality_report)

        # 7. Comparaison avec période précédente
        quality_report['trend_comparison'] = await self._compare_with_previous_period(start_date, end_date, timeframe_days)

        # Sauvegarde du rapport
        await self._save_quality_report(quality_report)

        return quality_report

    async def _calculate_global_quality_metrics(self, start_date: datetime, end_date: datetime) -> Dict:
        """
        Calcule les métriques de qualité globales
        """
        query = """
        SELECT 
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'motion') as motion_artifacts,
            COUNT(*) FILTER (WHERE quality_flag = 'low_signal') as low_signal_issues,
            COUNT(*) FILTER (WHERE quality_flag = 'sensor_drop') as sensor_drops,
            COUNT(*) FILTER (WHERE quality_flag = 'signal_loss') as signal_losses,
            COUNT(*) FILTER (WHERE quality_flag = 'out_of_range') as out_of_range_values,
            COUNT(*) FILTER (WHERE quality_flag = 'device_error') as device_errors,
            COUNT(*) FILTER (WHERE quality_flag = 'noise') as noise_issues,
            COUNT(*) FILTER (WHERE quality_flag = 'low_perfusion') as low_perfusion_issues,
            
            -- Métriques par paramètre vital
            COUNT(*) FILTER (WHERE spo2_pct IS NOT NULL AND spo2_pct BETWEEN 70 AND 100) as valid_spo2_count,
            COUNT(*) FILTER (WHERE spo2_pct IS NOT NULL) as total_spo2_count,
            COUNT(*) FILTER (WHERE freq_card IS NOT NULL AND freq_card BETWEEN 40 AND 200) as valid_hr_count,
            COUNT(*) FILTER (WHERE freq_card IS NOT NULL) as total_hr_count,
            COUNT(*) FILTER (WHERE temp_corp IS NOT NULL AND temp_corp BETWEEN 35 AND 42) as valid_temp_count,
            COUNT(*) FILTER (WHERE temp_corp IS NOT NULL) as total_temp_count,
            
            -- Métriques temporelles
            MIN(tz_timestamp) as first_measurement,
            MAX(tz_timestamp) as last_measurement,
            COUNT(DISTINCT patient_id) as patients_monitored,
            COUNT(DISTINCT device_id) as devices_active
            
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (start_date, end_date))
            result = dict(cursor.fetchone())
        conn.close()

        # Calculs des pourcentages et scores
        total = result['total_measurements']
        if total > 0:
            result['overall_quality_score'] = (result['valid_measurements'] / total) * 100
            result['motion_artifact_rate'] = (result['motion_artifacts'] / total) * 100
            result['signal_loss_rate'] = (result['signal_losses'] / total) * 100
            result['device_error_rate'] = (result['device_errors'] / total) * 100

            # Scores par paramètre
            if result['total_spo2_count'] > 0:
                result['spo2_quality_score'] = (result['valid_spo2_count'] / result['total_spo2_count']) * 100
            if result['total_hr_count'] > 0:
                result['hr_quality_score'] = (result['valid_hr_count'] / result['total_hr_count']) * 100
            if result['total_temp_count'] > 0:
                result['temp_quality_score'] = (result['valid_temp_count'] / result['total_temp_count']) * 100

        return result

    async def _calculate_per_patient_quality(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Calcule la qualité des données par patient
        """
        query = """
        SELECT 
            m.patient_id,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_score,
            COUNT(DISTINCT DATE(tz_timestamp)) as days_with_data,
            %s - %s + 1 as total_days_in_period,
            (COUNT(DISTINCT DATE(tz_timestamp)) * 100.0 / (%s - %s + 1)) as coverage_percentage,
            
            -- Problèmes spécifiques
            COUNT(*) FILTER (WHERE quality_flag = 'motion') as motion_issues,
            COUNT(*) FILTER (WHERE quality_flag = 'sensor_drop') as sensor_drops,
            COUNT(*) FILTER (WHERE quality_flag = 'low_signal') as low_signal_issues,
            
            -- Compliance approximative (mesures par jour)
            (COUNT(*) / NULLIF(COUNT(DISTINCT DATE(tz_timestamp)), 0)) as avg_measurements_per_day,
            
            -- Génotype pour contextualisation
            p.genotype
            
        FROM measurements m
        JOIN patients pat ON m.patient_id = pat.patient_id
        WHERE DATE(m.tz_timestamp) BETWEEN %s AND %s
        GROUP BY m.patient_id, p.genotype
        ORDER BY quality_score DESC
        """

        days_in_period = (end_date - start_date).days + 1

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (days_in_period, 0, days_in_period, 0, start_date, end_date))
            patient_quality = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Classification des patients par qualité
        for patient in patient_quality:
            score = patient['quality_score']
            if score >= 95:
                patient['quality_category'] = 'excellent'
            elif score >= 90:
                patient['quality_category'] = 'good'
            elif score >= 80:
                patient['quality_category'] = 'acceptable'
            else:
                patient['quality_category'] = 'poor'

        return patient_quality

    async def _calculate_per_device_quality(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Calcule la qualité des données par device/capteur
        """
        query = """
        SELECT 
            device_id,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_score,
            COUNT(DISTINCT patient_id) as patients_count,
            
            -- Problèmes techniques spécifiques
            COUNT(*) FILTER (WHERE quality_flag = 'device_error') as device_errors,
            COUNT(*) FILTER (WHERE quality_flag = 'low_signal') as low_signal_count,
            COUNT(*) FILTER (WHERE quality_flag = 'sensor_drop') as sensor_drops,
            COUNT(*) FILTER (WHERE quality_flag = 'checksum_fail') as checksum_failures,
            
            -- Métriques temporelles
            MIN(tz_timestamp) as first_seen,
            MAX(tz_timestamp) as last_seen,
            
            -- Utilisation
            COUNT(DISTINCT DATE(tz_timestamp)) as active_days
            
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        GROUP BY device_id
        ORDER BY quality_score DESC
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (start_date, end_date))
            device_quality = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Identification des devices problématiques
        for device in device_quality:
            issues = []
            if device['quality_score'] < 85:
                issues.append('low_quality')
            if device['device_errors'] > device['total_measurements'] * 0.05:
                issues.append('frequent_errors')
            if device['sensor_drops'] > device['total_measurements'] * 0.02:
                issues.append('connection_issues')

            device['identified_issues'] = issues

        return device_quality

    async def _analyze_temporal_quality_patterns(self, start_date: datetime, end_date: datetime) -> Dict:
        """
        Analyse les patterns temporels de qualité
        """
        # Qualité par heure de la journée
        hourly_query = """
        SELECT 
            EXTRACT(HOUR FROM tz_timestamp) as hour,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_score
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        GROUP BY EXTRACT(HOUR FROM tz_timestamp)
        ORDER BY hour
        """

        # Qualité par jour de la semaine
        weekly_query = """
        SELECT 
            EXTRACT(DOW FROM tz_timestamp) as day_of_week,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_score
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        GROUP BY EXTRACT(DOW FROM tz_timestamp)
        ORDER BY day_of_week
        """

        conn = psycopg2.connect(**self.db_config)

        # Données horaires
        hourly_df = pd.read_sql_query(hourly_query, conn, params=(start_date, end_date))

        # Données hebdomadaires
        weekly_df = pd.read_sql_query(weekly_query, conn, params=(start_date, end_date))

        conn.close()

        patterns = {
            'hourly_quality': hourly_df.to_dict('records') if not hourly_df.empty else [],
            'weekly_quality': weekly_df.to_dict('records') if not weekly_df.empty else []
        }

        # Identification des heures/jours problématiques
        if not hourly_df.empty:
            worst_hours = hourly_df.nsmallest(3, 'quality_score')['hour'].tolist()
            best_hours = hourly_df.nlargest(3, 'quality_score')['hour'].tolist()
            patterns['worst_hours'] = [int(h) for h in worst_hours]
            patterns['best_hours'] = [int(h) for h in best_hours]

        if not weekly_df.empty:
            # 0=Dimanche, 1=Lundi, etc.
            day_names = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
            worst_day = weekly_df.loc[weekly_df['quality_score'].idxmin(), 'day_of_week']
            best_day = weekly_df.loc[weekly_df['quality_score'].idxmax(), 'day_of_week']
            patterns['worst_day'] = day_names[int(worst_day)]
            patterns['best_day'] = day_names[int(best_day)]

        return patterns

    async def _detect_quality_anomalies(self, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Détecte les anomalies de qualité (pics d'erreurs, chutes soudaines)
        """
        # Qualité par jour pour détecter les anomalies
        daily_query = """
        SELECT 
            DATE(tz_timestamp) as date,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_score,
            COUNT(*) FILTER (WHERE quality_flag = 'device_error') as device_errors,
            COUNT(*) FILTER (WHERE quality_flag = 'signal_loss') as signal_losses
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        GROUP BY DATE(tz_timestamp)
        ORDER BY date
        """

        conn = psycopg2.connect(**self.db_config)
        daily_df = pd.read_sql_query(daily_query, conn, params=(start_date, end_date))
        conn.close()

        anomalies = []

        if not daily_df.empty and len(daily_df) >= 5:
            # Calcul des seuils statistiques
            mean_quality = daily_df['quality_score'].mean()
            std_quality = daily_df['quality_score'].std()

            # Seuil pour anomalie : moyenne - 2 * écart-type
            anomaly_threshold = mean_quality - 2 * std_quality

            # Détection des jours avec qualité anormalement basse
            anomaly_days = daily_df[daily_df['quality_score'] < anomaly_threshold]

            for _, day in anomaly_days.iterrows():
                anomalies.append({
                    'type': 'low_quality_day',
                    'date': day['date'].strftime('%Y-%m-%d'),
                    'quality_score': float(day['quality_score']),
                    'expected_range': f"{mean_quality:.1f} ± {std_quality:.1f}",
                    'severity': 'high' if day['quality_score'] < anomaly_threshold - std_quality else 'medium'
                })

            # Détection de pics d'erreurs
            mean_errors = daily_df['device_errors'].mean()
            std_errors = daily_df['device_errors'].std()
            error_threshold = mean_errors + 2 * std_errors

            error_spike_days = daily_df[daily_df['device_errors'] > error_threshold]

            for _, day in error_spike_days.iterrows():
                anomalies.append({
                    'type': 'device_error_spike',
                    'date': day['date'].strftime('%Y-%m-%d'),
                    'error_count': int(day['device_errors']),
                    'expected_range': f"< {error_threshold:.0f}",
                    'severity': 'high' if day['device_errors'] > error_threshold + std_errors else 'medium'
                })

        return anomalies

    async def _generate_quality_recommendations(self, quality_report: Dict) -> List[Dict]:
        """
        Génère des recommandations basées sur l'analyse qualité
        """
        recommendations = []
        global_metrics = quality_report.get('global_metrics', {})

        # Recommandations basées sur le score global
        overall_score = global_metrics.get('overall_quality_score', 0)
        if overall_score < 90:
            recommendations.append({
                'category': 'global_quality',
                'priority': 'high',
                'issue': f'Score qualité global faible ({overall_score:.1f}%)',
                'recommendation': 'Audit complet des capteurs et processus de validation',
                'expected_impact': 'Amélioration +5-10% qualité globale'
            })

        # Recommandations basées sur les artefacts de mouvement
        motion_rate = global_metrics.get('motion_artifact_rate', 0)
        if motion_rate > 10:
            recommendations.append({
                'category': 'motion_artifacts',
                'priority': 'medium',
                'issue': f'Taux élevé d\'artefacts de mouvement ({motion_rate:.1f}%)',
                'recommendation': 'Formation patients sur positionnement capteurs + algorithmes filtrage',
                'expected_impact': 'Réduction -50% artefacts mouvement'
            })

        # Recommandations basées sur les erreurs devices
        device_error_rate = global_metrics.get('device_error_rate', 0)
        if device_error_rate > 5:
            recommendations.append({
                'category': 'device_reliability',
                'priority': 'high',
                'issue': f'Taux élevé d\'erreurs matérielles ({device_error_rate:.1f}%)',
                'recommendation': 'Maintenance préventive + remplacement capteurs défaillants',
                'expected_impact': 'Réduction -80% erreurs techniques'
            })

        # Recommandations basées sur la qualité par patient
        patient_quality = quality_report.get('patient_quality', [])
        poor_quality_patients = [p for p in patient_quality if p.get('quality_category') == 'poor']

        if len(poor_quality_patients) > 0:
            recommendations.append({
                'category': 'patient_compliance',
                'priority': 'medium',
                'issue': f'{len(poor_quality_patients)} patients avec qualité données insuffisante',
                'recommendation': 'Programme d\'accompagnement personnalisé + vérification matériel',
                'expected_impact': 'Amélioration compliance +30%'
            })

        return recommendations

    async def _compare_with_previous_period(self, start_date: datetime, end_date: datetime, timeframe_days: int) -> Dict:
        """
        Compare avec la période précédente pour identifier les tendances
        """
        # Période précédente
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=timeframe_days-1)

        # Métriques période actuelle vs précédente
        current_query = """
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as score
        FROM measurements 
        WHERE DATE(tz_timestamp) BETWEEN %s AND %s
        """

        conn = psycopg2.connect(**self.db_config)

        # Période actuelle
        with conn.cursor() as cursor:
            cursor.execute(current_query, (start_date, end_date))
            current = cursor.fetchone()

        # Période précédente
        with conn.cursor() as cursor:
            cursor.execute(current_query, (prev_start, prev_end))
            previous = cursor.fetchone()

        conn.close()

        comparison = {
            'current_period': {
                'total_measurements': current[0] if current else 0,
                'quality_score': current[2] if current else 0
            },
            'previous_period': {
                'total_measurements': previous[0] if previous else 0,
                'quality_score': previous[2] if previous else 0
            }
        }

        # Calcul des variations
        if previous and previous[2] > 0:
            score_change = current[2] - previous[2] if current else -previous[2]
            volume_change = (current[0] - previous[0]) / previous[0] * 100 if current else -100

            comparison['changes'] = {
                'quality_score_change': score_change,
                'volume_change_percentage': volume_change,
                'trend': 'improving' if score_change > 1 else 'declining' if score_change < -1 else 'stable'
            }

        return comparison

    async def _save_quality_report(self, quality_report: Dict):
        """
        Sauvegarde le rapport de qualité en base de données
        """
        try:
            query = """
            INSERT INTO quality_analysis_reports (
                analysis_date, timeframe_days,
                overall_quality_score, total_measurements,
                patients_analyzed, devices_analyzed,
                anomalies_detected, recommendations_count,
                report_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            global_metrics = quality_report.get('global_metrics', {})

            params = (
                quality_report['analysis_date'],
                quality_report['timeframe_days'],
                global_metrics.get('overall_quality_score'),
                global_metrics.get('total_measurements'),
                global_metrics.get('patients_monitored'),
                global_metrics.get('devices_active'),
                len(quality_report.get('quality_anomalies', [])),
                len(quality_report.get('recommendations', [])),
                json.dumps(quality_report, default=str)
            )

            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                conn.commit()
            conn.close()

            logger.info("✅ Rapport qualité sauvegardé avec succès")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde rapport qualité: {e}")

async def main():
    """
    Test du processeur de métriques qualité
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    processor = QualityMetricsProcessor(db_config)
    quality_report = await processor.calculate_comprehensive_quality_metrics(timeframe_days=7)

    print(f"📊 Rapport qualité généré:")
    print(f"   Score global: {quality_report['global_metrics']['overall_quality_score']:.1f}%")
    print(f"   Patients analysés: {quality_report['global_metrics']['patients_monitored']}")
    print(f"   Anomalies détectées: {len(quality_report['quality_anomalies'])}")
    print(f"   Recommandations: {len(quality_report['recommendations'])}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
