#!/usr/bin/env python3
"""
🏥 KIDJAMO - Agrégations Journalières Batch ETL
Traitement quotidien des données médicales IoT pour analyses et métriques
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DailyAggregationsProcessor:
    """
    Processeur pour les agrégations journalières des données médicales
    """

    def __init__(self, db_config: Dict):
        self.db_config = db_config
        self.target_date = datetime.now().date() - timedelta(days=1)  # Hier

    async def run_daily_aggregations(self) -> Dict:
        """
        Exécute toutes les agrégations journalières
        """
        logger.info(f"🚀 Démarrage agrégations journalières pour {self.target_date}")

        results = {
            'date': self.target_date,
            'start_time': datetime.now(),
            'tasks_completed': [],
            'errors': []
        }

        try:
            # 1. Agrégations par patient
            await self._aggregate_patient_metrics()
            results['tasks_completed'].append('patient_metrics')

            # 2. Métriques qualité globales
            await self._calculate_quality_metrics()
            results['tasks_completed'].append('quality_metrics')

            # 3. Alertes statistiques
            await self._generate_alert_statistics()
            results['tasks_completed'].append('alert_statistics')

            # 4. Performance capteurs IoT
            await self._analyze_device_performance()
            results['tasks_completed'].append('device_performance')

            # 5. Nettoyage données temporaires
            await self._cleanup_temporary_data()
            results['tasks_completed'].append('cleanup')

            results['end_time'] = datetime.now()
            results['duration'] = (results['end_time'] - results['start_time']).total_seconds()
            results['status'] = 'SUCCESS'

            logger.info(f"✅ Agrégations journalières terminées en {results['duration']:.1f}s")

        except Exception as e:
            results['errors'].append(str(e))
            results['status'] = 'FAILED'
            logger.error(f"❌ Erreur dans agrégations journalières: {e}")

        return results

    async def _aggregate_patient_metrics(self):
        """
        Calcule les métriques agrégées par patient pour la journée
        """
        logger.info("📊 Calcul métriques patients journalières...")

        query = """
        INSERT INTO daily_patient_aggregates (
            patient_id, 
            date,
            avg_spo2,
            min_spo2,
            max_spo2,
            avg_heart_rate,
            avg_temperature,
            max_temperature,
            total_measurements,
            alert_count,
            device_uptime_pct
        )
        SELECT 
            m.patient_id,
            %s as date,
            AVG(m.spo2_pct) as avg_spo2,
            MIN(m.spo2_pct) as min_spo2,
            MAX(m.spo2_pct) as max_spo2,
            AVG(m.freq_card) as avg_heart_rate,
            AVG(m.temp_corp) as avg_temperature,
            MAX(m.temp_corp) as max_temperature,
            COUNT(*) as total_measurements,
            COUNT(DISTINCT a.alert_id) as alert_count,
            (COUNT(*) * 100.0 / 288) as device_uptime_pct  -- 288 = mesures/jour si 5min
        FROM measurements m
        LEFT JOIN alerts a ON a.patient_id = m.patient_id 
            AND DATE(a.created_at) = %s
        WHERE DATE(m.tz_timestamp) = %s
        GROUP BY m.patient_id
        ON CONFLICT (patient_id, date) DO UPDATE SET
            avg_spo2 = EXCLUDED.avg_spo2,
            min_spo2 = EXCLUDED.min_spo2,
            max_spo2 = EXCLUDED.max_spo2,
            avg_heart_rate = EXCLUDED.avg_heart_rate,
            avg_temperature = EXCLUDED.avg_temperature,
            max_temperature = EXCLUDED.max_temperature,
            total_measurements = EXCLUDED.total_measurements,
            alert_count = EXCLUDED.alert_count,
            device_uptime_pct = EXCLUDED.device_uptime_pct
        """

        await self._execute_query(query, (self.target_date, self.target_date, self.target_date))

    async def _calculate_quality_metrics(self):
        """
        Calcule les métriques de qualité des données pour la journée
        """
        logger.info("🔍 Calcul métriques qualité journalières...")

        query = """
        INSERT INTO daily_quality_metrics (
            date,
            total_measurements,
            valid_measurements,
            invalid_measurements,
            quality_score,
            most_common_error,
            device_issues_count
        )
        SELECT 
            %s as date,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            COUNT(*) FILTER (WHERE quality_flag != 'ok') as invalid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as quality_score,
            MODE() WITHIN GROUP (ORDER BY quality_flag) FILTER (WHERE quality_flag != 'ok') as most_common_error,
            COUNT(DISTINCT device_id) FILTER (WHERE quality_flag LIKE '%device%') as device_issues_count
        FROM measurements 
        WHERE DATE(tz_timestamp) = %s
        ON CONFLICT (date) DO UPDATE SET
            total_measurements = EXCLUDED.total_measurements,
            valid_measurements = EXCLUDED.valid_measurements,
            invalid_measurements = EXCLUDED.invalid_measurements,
            quality_score = EXCLUDED.quality_score,
            most_common_error = EXCLUDED.most_common_error,
            device_issues_count = EXCLUDED.device_issues_count
        """

        await self._execute_query(query, (self.target_date, self.target_date))

    async def _generate_alert_statistics(self):
        """
        Génère les statistiques d'alertes pour la journée
        """
        logger.info("🚨 Calcul statistiques alertes journalières...")

        query = """
        INSERT INTO daily_alert_statistics (
            date,
            total_alerts,
            critical_alerts,
            medium_alerts,
            low_alerts,
            avg_resolution_time_minutes,
            unresolved_alerts
        )
        SELECT 
            %s as date,
            COUNT(*) as total_alerts,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_alerts,
            COUNT(*) FILTER (WHERE severity = 'medium') as medium_alerts,
            COUNT(*) FILTER (WHERE severity = 'low') as low_alerts,
            AVG(EXTRACT(EPOCH FROM (als.changed_at - a.created_at))/60) 
                FILTER (WHERE als.statut = 'resolved') as avg_resolution_time_minutes,
            COUNT(*) FILTER (WHERE a.alert_id NOT IN (
                SELECT alert_id FROM alert_statut_logs WHERE statut = 'resolved'
            )) as unresolved_alerts
        FROM alerts a
        LEFT JOIN alert_statut_logs als ON a.alert_id = als.alert_id
        WHERE DATE(a.created_at) = %s
        ON CONFLICT (date) DO UPDATE SET
            total_alerts = EXCLUDED.total_alerts,
            critical_alerts = EXCLUDED.critical_alerts,
            medium_alerts = EXCLUDED.medium_alerts,
            low_alerts = EXCLUDED.low_alerts,
            avg_resolution_time_minutes = EXCLUDED.avg_resolution_time_minutes,
            unresolved_alerts = EXCLUDED.unresolved_alerts
        """

        await self._execute_query(query, (self.target_date, self.target_date))

    async def _analyze_device_performance(self):
        """
        Analyse la performance des capteurs IoT pour la journée
        """
        logger.info("📱 Analyse performance capteurs IoT...")

        query = """
        INSERT INTO daily_device_performance (
            date,
            total_devices,
            active_devices,
            devices_with_issues,
            avg_battery_level,
            connectivity_score
        )
        SELECT 
            %s as date,
            COUNT(DISTINCT device_id) as total_devices,
            COUNT(DISTINCT device_id) FILTER (WHERE last_seen >= %s) as active_devices,
            COUNT(DISTINCT device_id) FILTER (WHERE status IN ('low_battery', 'offline')) as devices_with_issues,
            AVG(battery_level) FILTER (WHERE battery_level IS NOT NULL) as avg_battery_level,
            (COUNT(*) FILTER (WHERE status = 'connected') * 100.0 / COUNT(*)) as connectivity_score
        FROM logs_iot 
        WHERE DATE(timestamp) = %s
        ON CONFLICT (date) DO UPDATE SET
            total_devices = EXCLUDED.total_devices,
            active_devices = EXCLUDED.active_devices,
            devices_with_issues = EXCLUDED.devices_with_issues,
            avg_battery_level = EXCLUDED.avg_battery_level,
            connectivity_score = EXCLUDED.connectivity_score
        """

        yesterday = self.target_date
        await self._execute_query(query, (yesterday, yesterday, yesterday))

    async def _cleanup_temporary_data(self):
        """
        Nettoie les données temporaires de plus de 7 jours
        """
        logger.info("🧹 Nettoyage données temporaires...")

        cutoff_date = self.target_date - timedelta(days=7)

        queries = [
            "DELETE FROM temporary_processing WHERE created_at < %s",
            "DELETE FROM cache_tables WHERE last_updated < %s",
            "VACUUM ANALYZE temporary_processing, cache_tables"
        ]

        for query in queries[:-1]:  # Exécute les DELETE avec paramètres
            await self._execute_query(query, (cutoff_date,))

        # VACUUM sans paramètres
        await self._execute_query(queries[-1])

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
    Point d'entrée principal pour les agrégations journalières
    """
    # Configuration base de données (à adapter selon votre .env)
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    processor = DailyAggregationsProcessor(db_config)
    results = await processor.run_daily_aggregations()

    print(f"📋 Résultats agrégations journalières:")
    print(f"   Date: {results['date']}")
    print(f"   Statut: {results['status']}")
    print(f"   Durée: {results.get('duration', 'N/A'):.1f}s")
    print(f"   Tâches réussies: {len(results['tasks_completed'])}")

    if results['errors']:
        print(f"   ❌ Erreurs: {results['errors']}")

if __name__ == "__main__":
    asyncio.run(main())
