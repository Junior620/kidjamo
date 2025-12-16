#!/usr/bin/env python3
"""
🏥 KIDJAMO - Routines de Nettoyage Automatique
Nettoyage intelligent et maintenance préventive du système
"""

import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, List
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
import json

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemCleanupManager:
    """
    Gestionnaire de nettoyage automatique pour maintenir les performances système
    """

    def __init__(self, db_config: Dict, cleanup_config: Dict = None):
        self.db_config = db_config

        # Configuration par défaut
        self.cleanup_config = cleanup_config or {
            'temp_files_retention_hours': 24,
            'log_files_retention_days': 30,
            'cache_files_retention_hours': 6,
            'orphaned_data_retention_days': 7,
            'cleanup_paths': [
                '../../logs',
                '../../evidence/temp',
                '../../quarantine/temp',
                '/tmp/kidjamo'
            ]
        }

    async def run_complete_cleanup(self) -> Dict:
        """
        Exécute le nettoyage complet du système
        """
        logger.info("🧹 Démarrage nettoyage complet du système")

        cleanup_results = {
            'start_time': datetime.now(),
            'operations': [],
            'files_cleaned': 0,
            'space_freed_mb': 0,
            'errors': []
        }

        try:
            # 1. Nettoyage des fichiers temporaires
            temp_cleanup = await self._cleanup_temporary_files()
            cleanup_results['operations'].append(temp_cleanup)
            cleanup_results['files_cleaned'] += temp_cleanup.get('files_removed', 0)
            cleanup_results['space_freed_mb'] += temp_cleanup.get('space_freed_mb', 0)

            # 2. Nettoyage des logs anciens
            logs_cleanup = await self._cleanup_old_logs()
            cleanup_results['operations'].append(logs_cleanup)
            cleanup_results['files_cleaned'] += logs_cleanup.get('files_removed', 0)
            cleanup_results['space_freed_mb'] += logs_cleanup.get('space_freed_mb', 0)

            # 3. Nettoyage des caches expirés
            cache_cleanup = await self._cleanup_expired_caches()
            cleanup_results['operations'].append(cache_cleanup)
            cleanup_results['files_cleaned'] += cache_cleanup.get('files_removed', 0)

            # 4. Nettoyage des données orphelines en base
            orphaned_cleanup = await self._cleanup_orphaned_database_records()
            cleanup_results['operations'].append(orphaned_cleanup)

            # 5. Nettoyage des sessions expirées
            sessions_cleanup = await self._cleanup_expired_sessions()
            cleanup_results['operations'].append(sessions_cleanup)

            # 6. Optimisation de l'espace disque
            disk_optimization = await self._optimize_disk_space()
            cleanup_results['operations'].append(disk_optimization)
            cleanup_results['space_freed_mb'] += disk_optimization.get('space_freed_mb', 0)

            # 7. Nettoyage des processus zombie
            process_cleanup = await self._cleanup_zombie_processes()
            cleanup_results['operations'].append(process_cleanup)

            cleanup_results['end_time'] = datetime.now()
            cleanup_results['duration'] = (cleanup_results['end_time'] - cleanup_results['start_time']).total_seconds()
            cleanup_results['status'] = 'SUCCESS'

            logger.info(f"✅ Nettoyage terminé: {cleanup_results['files_cleaned']} fichiers, {cleanup_results['space_freed_mb']:.1f}MB libérés en {cleanup_results['duration']:.1f}s")

        except Exception as e:
            cleanup_results['errors'].append(str(e))
            cleanup_results['status'] = 'FAILED'
            logger.error(f"❌ Erreur nettoyage: {e}")

        # Sauvegarde du rapport de nettoyage
        await self._save_cleanup_report(cleanup_results)

        return cleanup_results

    async def _cleanup_temporary_files(self) -> Dict:
        """
        Nettoie les fichiers temporaires anciens
        """
        logger.info("🗂️ Nettoyage fichiers temporaires")

        cutoff_time = datetime.now() - timedelta(hours=self.cleanup_config['temp_files_retention_hours'])

        files_removed = 0
        space_freed = 0
        temp_patterns = [
            '*.tmp',
            '*.temp',
            '*.cache',
            '*_temp_*',
            'temp_*'
        ]

        for cleanup_path in self.cleanup_config['cleanup_paths']:
            if os.path.exists(cleanup_path):
                for root, dirs, files in os.walk(cleanup_path):
                    for file in files:
                        file_path = os.path.join(root, file)

                        try:
                            # Vérifier si c'est un fichier temporaire et ancien
                            file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                            is_temp_file = any(file.endswith(pattern[1:]) or pattern[:-1] in file
                                             for pattern in temp_patterns)

                            if is_temp_file and file_mtime < cutoff_time:
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                files_removed += 1
                                space_freed += file_size

                        except Exception as e:
                            logger.warning(f"Erreur suppression {file_path}: {e}")

        return {
            'operation': 'temporary_files_cleanup',
            'files_removed': files_removed,
            'space_freed_mb': space_freed / (1024*1024),
            'cutoff_time': cutoff_time,
            'status': 'success'
        }

    async def _cleanup_old_logs(self) -> Dict:
        """
        Nettoie les fichiers de logs anciens
        """
        logger.info("📄 Nettoyage logs anciens")

        cutoff_date = datetime.now() - timedelta(days=self.cleanup_config['log_files_retention_days'])

        files_removed = 0
        space_freed = 0
        log_extensions = ['.log', '.out', '.err', '.txt']

        logs_paths = [
            '../../logs',
            '../../evidence/security_logs',
            '../../data/logs'
        ]

        for logs_path in logs_paths:
            if os.path.exists(logs_path):
                for root, dirs, files in os.walk(logs_path):
                    for file in files:
                        if any(file.endswith(ext) for ext in log_extensions):
                            file_path = os.path.join(root, file)

                            try:
                                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                                if file_mtime < cutoff_date:
                                    file_size = os.path.getsize(file_path)

                                    # Compression avant suppression pour les gros logs
                                    if file_size > 10*1024*1024:  # > 10MB
                                        compressed_path = f"{file_path}.gz"
                                        if not os.path.exists(compressed_path):
                                            import gzip
                                            with open(file_path, 'rb') as f_in:
                                                with gzip.open(compressed_path, 'wb') as f_out:
                                                    shutil.copyfileobj(f_in, f_out)

                                    os.remove(file_path)
                                    files_removed += 1
                                    space_freed += file_size

                            except Exception as e:
                                logger.warning(f"Erreur traitement log {file_path}: {e}")

        return {
            'operation': 'old_logs_cleanup',
            'files_removed': files_removed,
            'space_freed_mb': space_freed / (1024*1024),
            'cutoff_date': cutoff_date,
            'status': 'success'
        }

    async def _cleanup_expired_caches(self) -> Dict:
        """
        Nettoie les caches expirés
        """
        logger.info("💾 Nettoyage caches expirés")

        cutoff_time = datetime.now() - timedelta(hours=self.cleanup_config['cache_files_retention_hours'])

        files_removed = 0
        cache_paths = [
            '../../evidence/quality_metrics',
            '../../evidence/test_reports',
            '/tmp/kidjamo_cache'
        ]

        cache_patterns = ['cache_', '.cache', '_cached_', 'temp_metrics_']

        for cache_path in cache_paths:
            if os.path.exists(cache_path):
                for root, dirs, files in os.walk(cache_path):
                    for file in files:
                        if any(pattern in file for pattern in cache_patterns):
                            file_path = os.path.join(root, file)

                            try:
                                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))

                                if file_mtime < cutoff_time:
                                    os.remove(file_path)
                                    files_removed += 1

                            except Exception as e:
                                logger.warning(f"Erreur suppression cache {file_path}: {e}")

        # Nettoyage cache Redis si disponible
        redis_cleaned = 0
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

            # Suppression des clés expirées manuellement
            expired_keys = []
            for key in r.scan_iter(match="dashboard:*"):
                ttl = r.ttl(key)
                if ttl == -1:  # Pas de TTL défini
                    expired_keys.append(key)

            if expired_keys:
                r.delete(*expired_keys)
                redis_cleaned = len(expired_keys)

        except Exception as e:
            logger.warning(f"Nettoyage Redis non disponible: {e}")

        return {
            'operation': 'expired_caches_cleanup',
            'files_removed': files_removed,
            'redis_keys_cleaned': redis_cleaned,
            'cutoff_time': cutoff_time,
            'status': 'success'
        }

    async def _cleanup_orphaned_database_records(self) -> Dict:
        """
        Nettoie les enregistrements orphelins en base de données
        """
        logger.info("🗄️ Nettoyage données orphelines en base")

        conn = psycopg2.connect(**self.db_config)
        cleaned_records = 0

        cleanup_queries = [
            # Sessions expirées
            {
                'name': 'expired_sessions',
                'query': "DELETE FROM user_sessions WHERE end_at < NOW() - INTERVAL '7 days'",
                'description': 'Sessions expirées depuis plus de 7 jours'
            },

            # Logs de statut d'alertes sans alerte parent
            {
                'name': 'orphaned_alert_logs',
                'query': """
                    DELETE FROM alert_statut_logs 
                    WHERE alert_id NOT IN (SELECT alert_id FROM alerts)
                """,
                'description': 'Logs de statut sans alerte parent'
            },

            # Mesures sans patient (cas d'erreur)
            {
                'name': 'orphaned_measurements',
                'query': """
                    DELETE FROM measurements 
                    WHERE patient_id NOT IN (SELECT patient_id FROM patients)
                """,
                'description': 'Mesures sans patient associé'
            },

            # Données de test anciennes
            {
                'name': 'old_test_data',
                'query': """
                    DELETE FROM measurements 
                    WHERE device_id LIKE 'TEST_%' 
                    AND tz_timestamp < NOW() - INTERVAL '30 days'
                """,
                'description': 'Données de test anciennes'
            }
        ]

        cleanup_details = []

        for cleanup in cleanup_queries:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(cleanup['query'])
                    affected_rows = cursor.rowcount
                    conn.commit()

                cleaned_records += affected_rows
                cleanup_details.append({
                    'operation': cleanup['name'],
                    'description': cleanup['description'],
                    'records_cleaned': affected_rows
                })

                logger.info(f"🧹 {cleanup['name']}: {affected_rows} enregistrements supprimés")

            except Exception as e:
                logger.error(f"Erreur nettoyage {cleanup['name']}: {e}")
                conn.rollback()

        conn.close()

        return {
            'operation': 'orphaned_database_cleanup',
            'total_records_cleaned': cleaned_records,
            'cleanup_details': cleanup_details,
            'status': 'success'
        }

    async def _cleanup_expired_sessions(self) -> Dict:
        """
        Nettoie les sessions utilisateur expirées
        """
        logger.info("👤 Nettoyage sessions expirées")

        conn = psycopg2.connect(**self.db_config)

        # Suppression sessions inactives depuis plus de 24h
        cleanup_query = """
            UPDATE user_sessions 
            SET end_at = NOW() 
            WHERE end_at IS NULL 
            AND start_at < NOW() - INTERVAL '24 hours'
        """

        with conn.cursor() as cursor:
            cursor.execute(cleanup_query)
            expired_sessions = cursor.rowcount
            conn.commit()

        # Suppression définitive des sessions anciennes (> 30 jours)
        delete_query = """
            DELETE FROM user_sessions 
            WHERE end_at < NOW() - INTERVAL '30 days'
        """

        with conn.cursor() as cursor:
            cursor.execute(delete_query)
            deleted_sessions = cursor.rowcount
            conn.commit()

        conn.close()

        return {
            'operation': 'expired_sessions_cleanup',
            'expired_sessions': expired_sessions,
            'deleted_sessions': deleted_sessions,
            'total_sessions_processed': expired_sessions + deleted_sessions,
            'status': 'success'
        }

    async def _optimize_disk_space(self) -> Dict:
        """
        Optimise l'utilisation de l'espace disque
        """
        logger.info("💽 Optimisation espace disque")

        space_freed = 0
        optimization_operations = []

        # 1. Compression des fichiers volumineux
        large_files_compressed = await self._compress_large_files()
        space_freed += large_files_compressed
        optimization_operations.append(f"Fichiers volumineux compressés")

        # 2. Déduplication des fichiers
        deduplicated_space = await self._deduplicate_files()
        space_freed += deduplicated_space
        optimization_operations.append(f"Déduplication effectuée")

        # 3. Nettoyage des dossiers vides
        empty_dirs_removed = await self._remove_empty_directories()
        optimization_operations.append(f"{empty_dirs_removed} dossiers vides supprimés")

        return {
            'operation': 'disk_space_optimization',
            'space_freed_mb': space_freed / (1024*1024),
            'optimization_operations': optimization_operations,
            'status': 'success'
        }

    async def _compress_large_files(self) -> int:
        """
        Compresse les fichiers volumineux non compressés
        """
        space_saved = 0

        for cleanup_path in self.cleanup_config['cleanup_paths']:
            if os.path.exists(cleanup_path):
                for root, dirs, files in os.walk(cleanup_path):
                    for file in files:
                        if not file.endswith('.gz') and not file.endswith('.zip'):
                            file_path = os.path.join(root, file)

                            try:
                                file_size = os.path.getsize(file_path)

                                # Compresser si > 50MB
                                if file_size > 50*1024*1024:
                                    import gzip
                                    compressed_path = f"{file_path}.gz"

                                    with open(file_path, 'rb') as f_in:
                                        with gzip.open(compressed_path, 'wb') as f_out:
                                            shutil.copyfileobj(f_in, f_out)

                                    compressed_size = os.path.getsize(compressed_path)
                                    space_saved += (file_size - compressed_size)

                                    os.remove(file_path)

                            except Exception as e:
                                logger.warning(f"Erreur compression {file_path}: {e}")

        return space_saved

    async def _deduplicate_files(self) -> int:
        """
        Supprime les fichiers dupliqués
        """
        import hashlib

        file_hashes = {}
        space_saved = 0

        for cleanup_path in self.cleanup_config['cleanup_paths']:
            if os.path.exists(cleanup_path):
                for root, dirs, files in os.walk(cleanup_path):
                    for file in files:
                        file_path = os.path.join(root, file)

                        try:
                            # Calcul hash MD5
                            with open(file_path, 'rb') as f:
                                file_hash = hashlib.md5(f.read()).hexdigest()

                            if file_hash in file_hashes:
                                # Fichier dupliqué trouvé
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                space_saved += file_size
                            else:
                                file_hashes[file_hash] = file_path

                        except Exception as e:
                            logger.warning(f"Erreur déduplication {file_path}: {e}")

        return space_saved

    async def _remove_empty_directories(self) -> int:
        """
        Supprime les dossiers vides
        """
        removed_dirs = 0

        for cleanup_path in self.cleanup_config['cleanup_paths']:
            if os.path.exists(cleanup_path):
                for root, dirs, files in os.walk(cleanup_path, topdown=False):
                    for dir_name in dirs:
                        dir_path = os.path.join(root, dir_name)

                        try:
                            if not os.listdir(dir_path):
                                os.rmdir(dir_path)
                                removed_dirs += 1
                        except Exception as e:
                            logger.warning(f"Erreur suppression dossier {dir_path}: {e}")

        return removed_dirs

    async def _cleanup_zombie_processes(self) -> Dict:
        """
        Nettoie les processus zombie liés au système
        """
        logger.info("⚰️ Nettoyage processus zombie")

        try:
            import psutil

            zombie_processes = []
            kidjamo_processes = []

            for proc in psutil.process_iter(['pid', 'name', 'status', 'cmdline']):
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombie_processes.append(proc.info['pid'])

                    # Processus Kidjamo orphelins
                    if proc.info['cmdline'] and any('kidjamo' in str(cmd).lower() for cmd in proc.info['cmdline']):
                        if proc.info['status'] in [psutil.STATUS_ZOMBIE, psutil.STATUS_STOPPED]:
                            kidjamo_processes.append(proc.info['pid'])

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                'operation': 'zombie_processes_cleanup',
                'zombie_processes_found': len(zombie_processes),
                'kidjamo_orphans_found': len(kidjamo_processes),
                'status': 'success'
            }

        except ImportError:
            return {
                'operation': 'zombie_processes_cleanup',
                'status': 'skipped',
                'reason': 'psutil not available'
            }

    async def _save_cleanup_report(self, results: Dict):
        """
        Sauvegarde le rapport de nettoyage
        """
        report_dir = "../../evidence/maintenance_reports"
        os.makedirs(report_dir, exist_ok=True)

        report_file = f"{report_dir}/cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"📋 Rapport de nettoyage sauvegardé: {report_file}")

    async def get_system_health_status(self) -> Dict:
        """
        Retourne l'état de santé général du système
        """
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': 'healthy',
            'disk_space': {},
            'database_status': {},
            'processes_status': {},
            'cleanup_needed': False
        }

        # Vérification espace disque
        try:
            import shutil
            for path in self.cleanup_config['cleanup_paths']:
                if os.path.exists(path):
                    total, used, free = shutil.disk_usage(path)
                    free_pct = (free / total) * 100

                    health_status['disk_space'][path] = {
                        'free_gb': free / (1024**3),
                        'free_percentage': free_pct,
                        'status': 'critical' if free_pct < 10 else 'warning' if free_pct < 20 else 'healthy'
                    }

                    if free_pct < 20:
                        health_status['cleanup_needed'] = True
                        health_status['overall_status'] = 'warning'

        except Exception as e:
            logger.error(f"Erreur vérification disque: {e}")

        # Vérification base de données
        try:
            conn = psycopg2.connect(**self.db_config)
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM measurements WHERE tz_timestamp >= NOW() - INTERVAL '1 hour'")
                recent_measurements = cursor.fetchone()[0]

            health_status['database_status'] = {
                'connection': 'healthy',
                'recent_measurements': recent_measurements,
                'status': 'healthy' if recent_measurements > 0 else 'warning'
            }

            conn.close()

        except Exception as e:
            health_status['database_status'] = {
                'connection': 'error',
                'error': str(e),
                'status': 'critical'
            }
            health_status['overall_status'] = 'critical'

        return health_status

async def main():
    """
    Test du gestionnaire de nettoyage
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    cleanup_manager = SystemCleanupManager(db_config)

    # Test nettoyage complet
    results = await cleanup_manager.run_complete_cleanup()
    print(f"🧹 Nettoyage terminé: {results['files_cleaned']} fichiers, {results['space_freed_mb']:.1f}MB libérés")

    # Vérification santé système
    health = await cleanup_manager.get_system_health_status()
    print(f"💚 État système: {health['overall_status']}")

if __name__ == "__main__":
    asyncio.run(main())
