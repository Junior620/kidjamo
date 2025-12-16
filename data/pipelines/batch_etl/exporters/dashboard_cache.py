#!/usr/bin/env python3
"""
🏥 KIDJAMO - Cache Dashboard
Optimisation des performances dashboards avec mise en cache intelligente
"""

import logging
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import asyncio

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DashboardCacheManager:
    """
    Gestionnaire de cache pour optimiser les performances des dashboards médicaux
    """

    def __init__(self, db_config: Dict, redis_config: Dict = None):
        self.db_config = db_config

        # Configuration Redis par défaut
        if redis_config is None:
            redis_config = {'host': 'localhost', 'port': 6379, 'db': 0}

        try:
            self.redis_client = redis.Redis(**redis_config, decode_responses=True)
            self.redis_available = True
            logger.info("✅ Connexion Redis établie")
        except Exception as e:
            logger.warning(f"⚠️ Redis non disponible: {e}. Cache en mémoire utilisé.")
            self.redis_available = False
            self.memory_cache = {}

    async def refresh_all_dashboard_caches(self) -> Dict:
        """
        Rafraîchit tous les caches dashboard
        """
        logger.info("🔄 Rafraîchissement caches dashboard")

        refresh_results = {
            'start_time': datetime.now(),
            'caches_refreshed': [],
            'errors': []
        }

        try:
            # 1. Cache métriques temps réel
            await self._refresh_realtime_metrics_cache()
            refresh_results['caches_refreshed'].append('realtime_metrics')

            # 2. Cache statistiques patients
            await self._refresh_patient_stats_cache()
            refresh_results['caches_refreshed'].append('patient_stats')

            # 3. Cache tendances historiques
            await self._refresh_trends_cache()
            refresh_results['caches_refreshed'].append('trends')

            # 4. Cache alertes actives
            await self._refresh_alerts_cache()
            refresh_results['caches_refreshed'].append('alerts')

            # 5. Cache qualité données
            await self._refresh_quality_cache()
            refresh_results['caches_refreshed'].append('quality')

            # 6. Cache performance système
            await self._refresh_system_performance_cache()
            refresh_results['caches_refreshed'].append('system_performance')

            refresh_results['end_time'] = datetime.now()
            refresh_results['duration'] = (refresh_results['end_time'] - refresh_results['start_time']).total_seconds()
            refresh_results['status'] = 'SUCCESS'

            logger.info(f"✅ Caches rafraîchis en {refresh_results['duration']:.1f}s")

        except Exception as e:
            refresh_results['errors'].append(str(e))
            refresh_results['status'] = 'FAILED'
            logger.error(f"❌ Erreur rafraîchissement caches: {e}")

        return refresh_results

    async def _refresh_realtime_metrics_cache(self):
        """
        Cache des métriques temps réel pour dashboard principal
        """
        logger.info("📊 Cache métriques temps réel")

        query = """
        SELECT 
            COUNT(DISTINCT m.patient_id) as active_patients,
            COUNT(*) as measurements_last_hour,
            AVG(m.spo2_pct) as avg_spo2_global,
            COUNT(*) FILTER (WHERE m.spo2_pct < 90) as hypoxemia_events,
            COUNT(DISTINCT a.alert_id) as active_alerts,
            COUNT(DISTINCT a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts,
            
            -- Métriques par génotype
            AVG(m.spo2_pct) FILTER (WHERE p.genotype = 'SS') as avg_spo2_ss,
            AVG(m.spo2_pct) FILTER (WHERE p.genotype = 'SC') as avg_spo2_sc,
            AVG(m.spo2_pct) FILTER (WHERE p.genotype = 'AS') as avg_spo2_as,
            
            -- Qualité système
            COUNT(*) FILTER (WHERE m.quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE m.quality_flag = 'ok') * 100.0 / COUNT(*)) as system_quality_pct
            
        FROM measurements m
        JOIN patients p ON m.patient_id = p.patient_id
        LEFT JOIN alerts a ON m.patient_id = a.patient_id 
            AND a.created_at >= NOW() - INTERVAL '1 hour'
            AND a.created_at IN (
                SELECT MAX(created_at) FROM alerts 
                WHERE patient_id = a.patient_id AND severity = a.severity
            )
        WHERE m.tz_timestamp >= NOW() - INTERVAL '1 hour'
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            metrics = dict(cursor.fetchone())
        conn.close()

        # Ajout métadonnées
        metrics['last_updated'] = datetime.now().isoformat()
        metrics['cache_ttl'] = 300  # 5 minutes

        await self._set_cache('dashboard:realtime_metrics', metrics, ttl=300)

    async def _refresh_patient_stats_cache(self):
        """
        Cache statistiques détaillées par patient
        """
        logger.info("👥 Cache statistiques patients")

        query = """
        WITH patient_last_24h AS (
            SELECT 
                m.patient_id,
                u.first_name,
                u.last_name,
                p.genotype,
                EXTRACT(YEAR FROM AGE(p.birth_date)) as age,
                
                -- Données dernières 24h
                COUNT(*) as measurements_24h,
                AVG(m.spo2_pct) as avg_spo2_24h,
                MIN(m.spo2_pct) as min_spo2_24h,
                AVG(m.freq_card) as avg_hr_24h,
                AVG(m.temp_corp) as avg_temp_24h,
                MAX(m.temp_corp) as max_temp_24h,
                
                -- Dernière mesure
                FIRST_VALUE(m.spo2_pct) OVER (PARTITION BY m.patient_id ORDER BY m.tz_timestamp DESC) as last_spo2,
                FIRST_VALUE(m.tz_timestamp) OVER (PARTITION BY m.patient_id ORDER BY m.tz_timestamp DESC) as last_measurement,
                
                -- Alertes actives
                COUNT(DISTINCT a.alert_id) FILTER (WHERE a.severity = 'critical') as critical_alerts_24h,
                
                -- Compliance
                COUNT(DISTINCT DATE(m.tz_timestamp)) as monitoring_days,
                (COUNT(*) * 100.0 / 288) as compliance_pct  -- 288 = mesures théoriques par jour
                
            FROM measurements m
            JOIN patients p ON m.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            LEFT JOIN alerts a ON m.patient_id = a.patient_id 
                AND a.created_at >= NOW() - INTERVAL '24 hours'
            WHERE m.tz_timestamp >= NOW() - INTERVAL '24 hours'
                AND m.quality_flag = 'ok'
            GROUP BY m.patient_id, u.first_name, u.last_name, p.genotype, p.birth_date
        )
        SELECT 
            patient_id,
            first_name,
            last_name,
            genotype,
            age,
            measurements_24h,
            avg_spo2_24h,
            min_spo2_24h,
            last_spo2,
            last_measurement,
            critical_alerts_24h,
            compliance_pct,
            
            -- Classification du statut
            CASE 
                WHEN critical_alerts_24h > 0 THEN 'critical'
                WHEN min_spo2_24h < 90 THEN 'warning'
                WHEN avg_spo2_24h < 95 THEN 'monitoring'
                ELSE 'stable'
            END as status_category
            
        FROM patient_last_24h
        ORDER BY 
            CASE status_category 
                WHEN 'critical' THEN 1
                WHEN 'warning' THEN 2  
                WHEN 'monitoring' THEN 3
                ELSE 4
            END,
            avg_spo2_24h ASC
        """

        conn = psycopg2.connect(**self.db_config)
        patients_df = pd.read_sql_query(query, conn)
        conn.close()

        # Conversion en format JSON
        patients_data = {
            'patients': patients_df.to_dict('records'),
            'summary': {
                'total_patients': len(patients_df),
                'critical_patients': len(patients_df[patients_df['status_category'] == 'critical']),
                'warning_patients': len(patients_df[patients_df['status_category'] == 'warning']),
                'stable_patients': len(patients_df[patients_df['status_category'] == 'stable']),
                'avg_compliance': float(patients_df['compliance_pct'].mean())
            },
            'last_updated': datetime.now().isoformat()
        }

        await self._set_cache('dashboard:patient_stats', patients_data, ttl=600)  # 10 minutes

    async def _refresh_trends_cache(self):
        """
        Cache des tendances historiques pour graphiques
        """
        logger.info("📈 Cache tendances historiques")

        # Tendances 7 derniers jours
        query_7d = """
        SELECT 
            DATE(tz_timestamp) as date,
            AVG(spo2_pct) as avg_spo2,
            COUNT(DISTINCT patient_id) as active_patients,
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements
        FROM measurements 
        WHERE tz_timestamp >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(tz_timestamp)
        ORDER BY date
        """

        # Tendances par heure (dernières 24h)
        query_24h = """
        SELECT 
            DATE_TRUNC('hour', tz_timestamp) as hour,
            AVG(spo2_pct) as avg_spo2,
            COUNT(*) as measurements_count,
            COUNT(DISTINCT patient_id) as active_patients
        FROM measurements 
        WHERE tz_timestamp >= NOW() - INTERVAL '24 hours'
            AND quality_flag = 'ok'
        GROUP BY DATE_TRUNC('hour', tz_timestamp)
        ORDER BY hour
        """

        conn = psycopg2.connect(**self.db_config)

        trends_7d = pd.read_sql_query(query_7d, conn)
        trends_24h = pd.read_sql_query(query_24h, conn)

        conn.close()

        trends_data = {
            'weekly_trends': trends_7d.to_dict('records'),
            'hourly_trends': trends_24h.to_dict('records'),
            'last_updated': datetime.now().isoformat()
        }

        await self._set_cache('dashboard:trends', trends_data, ttl=900)  # 15 minutes

    async def _refresh_alerts_cache(self):
        """
        Cache des alertes actives et récentes
        """
        logger.info("🚨 Cache alertes actives")

        query = """
        WITH recent_alerts AS (
            SELECT 
                a.alert_id,
                a.patient_id,
                u.first_name,
                u.last_name,
                a.alert_type,
                a.severity,
                a.message,
                a.created_at,
                
                -- Statut de résolution
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM alert_statut_logs 
                        WHERE alert_id = a.alert_id AND statut = 'resolved'
                    ) THEN 'resolved'
                    WHEN EXISTS (
                        SELECT 1 FROM alert_statut_logs 
                        WHERE alert_id = a.alert_id AND statut = 'seen'
                    ) THEN 'acknowledged'
                    ELSE 'new'
                END as status,
                
                -- Temps écoulé
                EXTRACT(EPOCH FROM (NOW() - a.created_at))/60 as minutes_ago
                
            FROM alerts a
            JOIN patients p ON a.patient_id = p.patient_id
            JOIN users u ON p.user_id = u.user_id
            WHERE a.created_at >= NOW() - INTERVAL '24 hours'
            ORDER BY a.created_at DESC
        )
        SELECT 
            alert_id,
            patient_id,
            first_name,
            last_name,
            alert_type,
            severity,
            message,
            created_at,
            status,
            minutes_ago
        FROM recent_alerts
        LIMIT 50
        """

        conn = psycopg2.connect(**self.db_config)
        alerts_df = pd.read_sql_query(query, conn)
        conn.close()

        # Statistiques des alertes
        alerts_summary = {
            'total_alerts_24h': len(alerts_df),
            'critical_alerts': len(alerts_df[alerts_df['severity'] == 'critical']),
            'unresolved_alerts': len(alerts_df[alerts_df['status'] != 'resolved']),
            'avg_resolution_time': None  # À calculer si nécessaire
        }

        alerts_data = {
            'recent_alerts': alerts_df.to_dict('records'),
            'summary': alerts_summary,
            'last_updated': datetime.now().isoformat()
        }

        await self._set_cache('dashboard:alerts', alerts_data, ttl=180)  # 3 minutes

    async def _refresh_quality_cache(self):
        """
        Cache métriques qualité des données
        """
        logger.info("🔍 Cache qualité données")

        query = """
        SELECT 
            -- Qualité globale
            COUNT(*) as total_measurements,
            COUNT(*) FILTER (WHERE quality_flag = 'ok') as valid_measurements,
            (COUNT(*) FILTER (WHERE quality_flag = 'ok') * 100.0 / COUNT(*)) as overall_quality_pct,
            
            -- Problèmes par type
            COUNT(*) FILTER (WHERE quality_flag = 'motion') as motion_artifacts,
            COUNT(*) FILTER (WHERE quality_flag = 'low_signal') as low_signal_issues,
            COUNT(*) FILTER (WHERE quality_flag = 'sensor_drop') as sensor_drops,
            COUNT(*) FILTER (WHERE quality_flag = 'device_error') as device_errors,
            
            -- Qualité par device
            COUNT(DISTINCT device_id) as total_devices,
            COUNT(DISTINCT device_id) FILTER (WHERE quality_flag = 'ok') as working_devices,
            
            -- Couverture temporelle
            COUNT(DISTINCT patient_id) as monitored_patients,
            COUNT(DISTINCT DATE(tz_timestamp)) as monitoring_days
            
        FROM measurements 
        WHERE tz_timestamp >= NOW() - INTERVAL '24 hours'
        """

        conn = psycopg2.connect(**self.db_config)
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query)
            quality_metrics = dict(cursor.fetchone())
        conn.close()

        # Calculs dérivés
        if quality_metrics['total_measurements'] > 0:
            quality_metrics['motion_artifact_rate'] = (quality_metrics['motion_artifacts'] / quality_metrics['total_measurements']) * 100
            quality_metrics['device_error_rate'] = (quality_metrics['device_errors'] / quality_metrics['total_measurements']) * 100

        quality_metrics['last_updated'] = datetime.now().isoformat()

        await self._set_cache('dashboard:quality', quality_metrics, ttl=600)

    async def _refresh_system_performance_cache(self):
        """
        Cache métriques performance système
        """
        logger.info("⚙️ Cache performance système")

        # Métriques de base
        performance_metrics = {
            'cache_refresh_time': datetime.now().isoformat(),
            'database_status': 'connected',
            'redis_status': 'connected' if self.redis_available else 'unavailable',
            'cache_hit_rate': 85.5,  # À calculer dynamiquement si besoin
            'avg_query_time_ms': 45.2,  # À mesurer dynamiquement
            'system_load': 'normal'
        }

        # Vérification santé base de données
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM measurements WHERE tz_timestamp >= NOW() - INTERVAL '1 hour'")
                recent_measurements = cursor.fetchone()[0]
            conn.close()

            performance_metrics['recent_measurements_count'] = recent_measurements
            performance_metrics['data_ingestion_rate'] = f"{recent_measurements}/hour"

        except Exception as e:
            performance_metrics['database_status'] = 'error'
            performance_metrics['database_error'] = str(e)

        await self._set_cache('dashboard:system_performance', performance_metrics, ttl=300)

    async def get_cached_data(self, cache_key: str) -> Optional[Dict]:
        """
        Récupère des données du cache
        """
        try:
            if self.redis_available:
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    return json.loads(cached_data)
            else:
                return self.memory_cache.get(cache_key)
        except Exception as e:
            logger.error(f"Erreur lecture cache {cache_key}: {e}")

        return None

    async def _set_cache(self, cache_key: str, data: Dict, ttl: int = 3600):
        """
        Stocke des données dans le cache
        """
        try:
            if self.redis_available:
                self.redis_client.setex(cache_key, ttl, json.dumps(data, default=str))
            else:
                # Cache mémoire simple avec TTL
                self.memory_cache[cache_key] = {
                    'data': data,
                    'expires_at': datetime.now() + timedelta(seconds=ttl)
                }

            logger.debug(f"✅ Cache mis à jour: {cache_key}")

        except Exception as e:
            logger.error(f"Erreur écriture cache {cache_key}: {e}")

    async def get_dashboard_data(self, dashboard_type: str = 'main') -> Dict:
        """
        Récupère toutes les données nécessaires pour un dashboard
        """
        if dashboard_type == 'main':
            return {
                'realtime_metrics': await self.get_cached_data('dashboard:realtime_metrics'),
                'patient_stats': await self.get_cached_data('dashboard:patient_stats'),
                'trends': await self.get_cached_data('dashboard:trends'),
                'alerts': await self.get_cached_data('dashboard:alerts'),
                'quality': await self.get_cached_data('dashboard:quality'),
                'system_performance': await self.get_cached_data('dashboard:system_performance')
            }

        return {}

    async def invalidate_cache(self, pattern: str = None):
        """
        Invalide le cache selon un pattern
        """
        if self.redis_available and pattern:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
                logger.info(f"🗑️ Cache invalidé: {len(keys)} clés supprimées")
        elif not self.redis_available:
            # Nettoyage cache mémoire
            keys_to_remove = [k for k in self.memory_cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self.memory_cache[key]

async def main():
    """
    Test du gestionnaire de cache dashboard
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    cache_manager = DashboardCacheManager(db_config)

    # Test rafraîchissement complet
    results = await cache_manager.refresh_all_dashboard_caches()
    print(f"📊 Caches rafraîchis: {len(results['caches_refreshed'])} en {results.get('duration', 0):.1f}s")

    # Test récupération données dashboard
    dashboard_data = await cache_manager.get_dashboard_data('main')
    print(f"🖥️ Données dashboard récupérées: {len([k for k, v in dashboard_data.items() if v is not None])} sections")

if __name__ == "__main__":
    asyncio.run(main())
