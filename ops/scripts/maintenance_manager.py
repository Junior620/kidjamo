#!/usr/bin/env python3
"""
KIDJAMO - Outils de Maintenance et Monitoring
Automatisation des tâches critiques post-migration
Date: 2025-08-18
"""

import psycopg2
import json
import logging
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import os
from dataclasses import dataclass
import pandas as pd

@dataclass
class MaintenanceResult:
    task_name: str
    success: bool
    rows_affected: int
    execution_time: float
    message: str
    timestamp: datetime

class KidjamoMaintenanceManager:

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.logger = self._setup_logging()
        self.connection = None

    def _setup_logging(self):
        """Configure le logging pour la maintenance."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/maintenance.log'),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger('kidjamo_maintenance')

    def get_connection(self):
        """Obtient une connexion à la base de données."""
        if not self.connection or self.connection.closed:
            self.connection = psycopg2.connect(**self.db_config)
        return self.connection

    def execute_maintenance_task(self, task_name: str, sql_query: str) -> MaintenanceResult:
        """Exécute une tâche de maintenance et retourne le résultat."""
        start_time = time.time()

        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                rows_affected = cursor.rowcount
                conn.commit()

            execution_time = time.time() - start_time
            result = MaintenanceResult(
                task_name=task_name,
                success=True,
                rows_affected=rows_affected,
                execution_time=execution_time,
                message="Completed successfully",
                timestamp=datetime.now()
            )

            self.logger.info(f"✅ {task_name}: {rows_affected} rows affected in {execution_time:.2f}s")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            result = MaintenanceResult(
                task_name=task_name,
                success=False,
                rows_affected=0,
                execution_time=execution_time,
                message=str(e),
                timestamp=datetime.now()
            )

            self.logger.error(f"❌ {task_name} failed: {str(e)}")
            return result

    def refresh_materialized_views(self) -> List[MaintenanceResult]:
        """Rafraîchit toutes les vues matérialisées."""
        results = []

        views = [
            'mv_patient_realtime_metrics',
            'mv_patient_weekly_trends'
        ]

        for view in views:
            sql = f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view};"
            result = self.execute_maintenance_task(f"refresh_view_{view}", sql)
            results.append(result)

        return results

    def create_weekly_partitions(self) -> MaintenanceResult:
        """Crée les partitions de la semaine suivante pour measurements."""
        sql = """
        DO $$
        DECLARE
            week_start DATE;
            week_end DATE;
            partition_name TEXT;
        BEGIN
            -- Créer partition pour la semaine prochaine
            week_start := DATE_TRUNC('week', CURRENT_DATE + INTERVAL '1 week');
            week_end := week_start + INTERVAL '1 week';
            partition_name := 'measurements_' || TO_CHAR(week_start, 'IYYY') || 'w' || TO_CHAR(week_start, 'IW');
            
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF measurements 
                 FOR VALUES FROM (%L) TO (%L)',
                partition_name, week_start, week_end
            );
            
            -- Index spécifique
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS %I ON %I(patient_id, recorded_at DESC)',
                partition_name || '_patient_time', partition_name
            );
            
            -- Partition pour audit_logs aussi
            partition_name := 'audit_logs_' || TO_CHAR(week_start, 'YYYY') || 'm' || TO_CHAR(week_start, 'MM');
            week_start := DATE_TRUNC('month', week_start);
            week_end := week_start + INTERVAL '1 month';
            
            EXECUTE format(
                'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs 
                 FOR VALUES FROM (%L) TO (%L)',
                partition_name, week_start, week_end
            );
        END $$;
        """

        return self.execute_maintenance_task("create_weekly_partitions", sql)

    def cleanup_expired_data(self) -> List[MaintenanceResult]:
        """Nettoie les données expirées selon les politiques de rétention."""
        results = []

        # Nettoyage des exports expirés
        sql_exports = "SELECT cleanup_expired_exports();"
        results.append(self.execute_maintenance_task("cleanup_expired_exports", sql_exports))

        # Nettoyage des sessions anciennes (>30 jours)
        sql_sessions = """
        DELETE FROM user_sessions 
        WHERE ended_at < now() - INTERVAL '30 days' 
           OR (started_at < now() - INTERVAL '30 days' AND ended_at IS NULL);
        """
        results.append(self.execute_maintenance_task("cleanup_old_sessions", sql_sessions))

        # Archivage des logs device anciens (>90 jours)
        sql_device_logs = """
        DELETE FROM device_logs 
        WHERE recorded_at < now() - INTERVAL '90 days';
        """
        results.append(self.execute_maintenance_task("cleanup_device_logs", sql_device_logs))

        # Nettoyage des alertes résolues anciennes (>1 an)
        sql_old_alerts = """
        DELETE FROM alerts 
        WHERE resolved_at IS NOT NULL 
          AND resolved_at < now() - INTERVAL '1 year';
        """
        results.append(self.execute_maintenance_task("cleanup_old_resolved_alerts", sql_old_alerts))

        return results

    def optimize_database(self) -> List[MaintenanceResult]:
        """Optimise les performances de la base de données."""
        results = []

        # VACUUM ANALYZE sur les tables principales
        tables = ['measurements', 'alerts', 'audit_logs', 'users', 'patients']

        for table in tables:
            sql = f"VACUUM ANALYZE {table};"
            results.append(self.execute_maintenance_task(f"vacuum_analyze_{table}", sql))

        # Réindexation des index fragmentés
        sql_reindex = """
        SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
        FROM pg_stat_user_indexes 
        WHERE idx_tup_read > 0 AND idx_tup_fetch/idx_tup_read < 0.99
        ORDER BY idx_tup_read DESC;
        """

        # En production, ceci identifierait les index à réindexer
        results.append(self.execute_maintenance_task("analyze_fragmented_indexes", sql_reindex))

        return results

    def generate_health_report(self) -> Dict:
        """Génère un rapport de santé de la base de données."""
        try:
            conn = self.get_connection()
            with conn.cursor() as cursor:

                # Statistiques générales
                cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM users WHERE is_active = true) as active_users,
                    (SELECT COUNT(*) FROM patients) as total_patients,
                    (SELECT COUNT(*) FROM measurements WHERE recorded_at >= now() - INTERVAL '24 hours') as measurements_24h,
                    (SELECT COUNT(*) FROM alerts WHERE resolved_at IS NULL) as active_alerts,
                    (SELECT COUNT(*) FROM alerts WHERE severity = 'critical' AND resolved_at IS NULL) as critical_alerts
                """)

                stats = cursor.fetchone()

                # Taille des tables principales
                cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public' 
                  AND tablename IN ('measurements', 'alerts', 'audit_logs', 'users', 'patients')
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
                """)

                table_sizes = cursor.fetchall()

                # Performance des requêtes lentes
                cursor.execute("""
                SELECT query, calls, total_time, mean_time
                FROM pg_stat_statements 
                WHERE mean_time > 100
                ORDER BY mean_time DESC 
                LIMIT 10;
                """)

                slow_queries = cursor.fetchall()

                # Alertes récentes par gravité
                cursor.execute("""
                SELECT severity, COUNT(*) as count
                FROM alerts 
                WHERE created_at >= now() - INTERVAL '24 hours'
                GROUP BY severity
                ORDER BY severity;
                """)

                recent_alerts = cursor.fetchall()

                # Construction du rapport
                report = {
                    "timestamp": datetime.now().isoformat(),
                    "database_health": "healthy",  # À calculer selon les métriques
                    "statistics": {
                        "active_users": stats[0],
                        "total_patients": stats[1],
                        "measurements_24h": stats[2],
                        "active_alerts": stats[3],
                        "critical_alerts": stats[4]
                    },
                    "table_sizes": [
                        {
                            "table": row[1],
                            "size_pretty": row[2],
                            "size_bytes": row[3]
                        }
                        for row in table_sizes
                    ],
                    "slow_queries": [
                        {
                            "query": row[0][:100] + "..." if len(row[0]) > 100 else row[0],
                            "calls": row[1],
                            "total_time": row[2],
                            "mean_time": row[3]
                        }
                        for row in slow_queries
                    ],
                    "recent_alerts_by_severity": {
                        row[0]: row[1] for row in recent_alerts
                    }
                }

                # Déterminer l'état de santé
                if stats[4] > 5:  # Plus de 5 alertes critiques
                    report["database_health"] = "critical"
                elif stats[3] > 20:  # Plus de 20 alertes actives
                    report["database_health"] = "warning"
                elif stats[2] == 0:  # Pas de mesures dans les 24h
                    report["database_health"] = "warning"

                return report

        except Exception as e:
            self.logger.error(f"Failed to generate health report: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "database_health": "error",
                "error": str(e)
            }

    def run_daily_maintenance(self):
        """Exécute la maintenance quotidienne."""
        self.logger.info("🔧 Starting daily maintenance...")

        # Rafraîchir les vues matérialisées
        view_results = self.refresh_materialized_views()

        # Créer les partitions de la semaine suivante
        partition_result = self.create_weekly_partitions()

        # Nettoyer les données expirées
        cleanup_results = self.cleanup_expired_data()

        # Générer le rapport de santé
        health_report = self.generate_health_report()

        # Sauvegarder le rapport
        with open(f'reports/health_report_{datetime.now().strftime("%Y%m%d")}.json', 'w') as f:
            json.dump(health_report, f, indent=2)

        self.logger.info("✅ Daily maintenance completed")

    def run_weekly_maintenance(self):
        """Exécute la maintenance hebdomadaire."""
        self.logger.info("🔧 Starting weekly maintenance...")

        # Optimiser la base de données
        optimization_results = self.optimize_database()

        # Générer un rapport détaillé
        detailed_report = self.generate_detailed_weekly_report()

        self.logger.info("✅ Weekly maintenance completed")

    def generate_detailed_weekly_report(self) -> Dict:
        """Génère un rapport détaillé hebdomadaire."""
        try:
            conn = self.get_connection()

            # Utiliser pandas pour des analyses plus complexes
            patients_df = pd.read_sql("""
                SELECT 
                    p.patient_id,
                    p.genotype,
                    get_age_group(p.birth_date) as age_group,
                    COUNT(m.measurement_id) as measurements_count,
                    AVG(m.spo2_percent) as avg_spo2,
                    COUNT(a.alert_id) as alerts_count
                FROM patients p
                LEFT JOIN measurements m ON m.patient_id = p.patient_id 
                    AND m.recorded_at >= now() - INTERVAL '7 days'
                LEFT JOIN alerts a ON a.patient_id = p.patient_id 
                    AND a.created_at >= now() - INTERVAL '7 days'
                GROUP BY p.patient_id, p.genotype, p.birth_date
            """, conn)

            # Analyses statistiques
            weekly_stats = {
                "total_patients": len(patients_df),
                "patients_with_measurements": len(patients_df[patients_df['measurements_count'] > 0]),
                "patients_with_alerts": len(patients_df[patients_df['alerts_count'] > 0]),
                "avg_measurements_per_patient": patients_df['measurements_count'].mean(),
                "genotype_distribution": patients_df['genotype'].value_counts().to_dict(),
                "age_group_distribution": patients_df['age_group'].value_counts().to_dict(),
                "spo2_statistics": {
                    "mean": patients_df['avg_spo2'].mean(),
                    "std": patients_df['avg_spo2'].std(),
                    "min": patients_df['avg_spo2'].min(),
                    "max": patients_df['avg_spo2'].max()
                }
            }

            # Patients à risque (peu de mesures ou SpO2 bas)
            at_risk_patients = patients_df[
                (patients_df['measurements_count'] < 50) |  # Moins de 50 mesures/semaine
                (patients_df['avg_spo2'] < 92)  # SpO2 moyenne basse
            ]['patient_id'].tolist()

            report = {
                "timestamp": datetime.now().isoformat(),
                "period": "weekly",
                "statistics": weekly_stats,
                "at_risk_patients": at_risk_patients,
                "recommendations": self._generate_recommendations(weekly_stats, at_risk_patients)
            }

            # Sauvegarder le rapport
            with open(f'reports/weekly_report_{datetime.now().strftime("%Y_w%U")}.json', 'w') as f:
                json.dump(report, f, indent=2)

            return report

        except Exception as e:
            self.logger.error(f"Failed to generate weekly report: {str(e)}")
            return {"error": str(e)}

    def _generate_recommendations(self, stats: Dict, at_risk_patients: List) -> List[str]:
        """Génère des recommandations basées sur les statistiques."""
        recommendations = []

        if stats['avg_measurements_per_patient'] < 100:
            recommendations.append("⚠️ Moyenne de mesures par patient faible (<100/semaine). Vérifier la connectivité des devices.")

        if len(at_risk_patients) > stats['total_patients'] * 0.1:
            recommendations.append(f"🚨 {len(at_risk_patients)} patients à risque détectés (>10%). Révision médicale recommandée.")

        if stats['spo2_statistics']['mean'] < 94:
            recommendations.append("📊 SpO2 moyenne générale basse (<94%). Analyser les facteurs environnementaux.")

        return recommendations

def setup_scheduled_tasks(maintenance_manager: KidjamoMaintenanceManager):
    """Configure les tâches automatisées."""

    # Tâches quotidiennes à 2h du matin
    schedule.every().day.at("02:00").do(maintenance_manager.run_daily_maintenance)

    # Tâches hebdomadaires le dimanche à 3h
    schedule.every().sunday.at("03:00").do(maintenance_manager.run_weekly_maintenance)

    # Rafraîchissement des vues matérialisées toutes les 5 minutes
    schedule.every(5).minutes.do(maintenance_manager.refresh_materialized_views)

    print("📅 Scheduled tasks configured:")
    print("  - Daily maintenance: Every day at 02:00")
    print("  - Weekly maintenance: Every Sunday at 03:00")
    print("  - Materialized views refresh: Every 5 minutes")

def main():
    """Point d'entrée principal pour le système de maintenance."""

    # Configuration base de données (à adapter selon environnement)
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': os.getenv('DB_PORT', '5432'),
        'database': os.getenv('DB_NAME', 'kidjamo'),
        'user': os.getenv('DB_USER', 'kidjamo_admin'),
        'password': os.getenv('DB_PASSWORD', '')
    }

    # Créer le gestionnaire de maintenance
    maintenance_manager = KidjamoMaintenanceManager(db_config)

    # Configurer les tâches automatisées
    setup_scheduled_tasks(maintenance_manager)

    print("🚀 Kidjamo Maintenance Manager started")
    print("   Press Ctrl+C to stop")

    try:
        # Boucle principale
        while True:
            schedule.run_pending()
            time.sleep(60)  # Vérifier toutes les minutes

    except KeyboardInterrupt:
        print("\n⏹️ Maintenance Manager stopped")
        if maintenance_manager.connection:
            maintenance_manager.connection.close()

if __name__ == "__main__":
    main()
