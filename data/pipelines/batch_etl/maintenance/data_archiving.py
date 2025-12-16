#!/usr/bin/env python3
"""
🏥 KIDJAMO - Archivage Automatique des Données
Système d'archivage intelligent pour optimiser les performances et la conformité
"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import asyncio
import os
import gzip
import json

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataArchivingManager:
    """
    Gestionnaire d'archivage automatique pour optimiser les performances
    """

    def __init__(self, db_config: Dict, archive_config: Dict = None):
        self.db_config = db_config

        # Configuration par défaut
        self.archive_config = archive_config or {
            'measurements_retention_days': 365,  # 1 an en base active
            'logs_retention_days': 90,          # 3 mois de logs
            'alerts_retention_days': 730,       # 2 ans d'alertes
            'archive_path': '../../evidence/archives',
            'compression': True
        }

        # Création dossier archives
        os.makedirs(self.archive_config['archive_path'], exist_ok=True)

    async def run_automated_archiving(self) -> Dict:
        """
        Exécute l'archivage automatique complet
        """
        logger.info("📦 Démarrage archivage automatique")

        archiving_results = {
            'start_time': datetime.now(),
            'operations': [],
            'archived_records': 0,
            'freed_space_mb': 0,
            'errors': []
        }

        try:
            # 1. Archivage des mesures anciennes
            measurements_result = await self._archive_old_measurements()
            archiving_results['operations'].append(measurements_result)
            archiving_results['archived_records'] += measurements_result.get('archived_count', 0)

            # 2. Archivage des logs système
            logs_result = await self._archive_old_logs()
            archiving_results['operations'].append(logs_result)
            archiving_results['archived_records'] += logs_result.get('archived_count', 0)

            # 3. Archivage des alertes résolues anciennes
            alerts_result = await self._archive_old_alerts()
            archiving_results['operations'].append(alerts_result)
            archiving_results['archived_records'] += alerts_result.get('archived_count', 0)

            # 4. Archivage des données de quarantaine
            quarantine_result = await self._archive_quarantine_data()
            archiving_results['operations'].append(quarantine_result)

            # 5. Nettoyage des fichiers temporaires
            temp_cleanup = await self._cleanup_temporary_files()
            archiving_results['operations'].append(temp_cleanup)

            # 6. Optimisation post-archivage
            optimization_result = await self._post_archive_optimization()
            archiving_results['operations'].append(optimization_result)

            archiving_results['end_time'] = datetime.now()
            archiving_results['duration'] = (archiving_results['end_time'] - archiving_results['start_time']).total_seconds()
            archiving_results['status'] = 'SUCCESS'

            logger.info(f"✅ Archivage terminé: {archiving_results['archived_records']} enregistrements en {archiving_results['duration']:.1f}s")

        except Exception as e:
            archiving_results['errors'].append(str(e))
            archiving_results['status'] = 'FAILED'
            logger.error(f"❌ Erreur archivage: {e}")

        # Sauvegarde du rapport d'archivage
        await self._save_archiving_report(archiving_results)

        return archiving_results

    async def _archive_old_measurements(self) -> Dict:
        """
        Archive les mesures anciennes (> 1 an)
        """
        logger.info("📊 Archivage mesures anciennes")

        cutoff_date = datetime.now() - timedelta(days=self.archive_config['measurements_retention_days'])
        archive_file = f"{self.archive_config['archive_path']}/measurements_archive_{datetime.now().strftime('%Y%m%d')}.csv"

        # Extraction des données à archiver
        query = """
        SELECT 
            measure_id, patient_id, tz_timestamp, device_id,
            spo2_pct, freq_card, temp_corp, temp_abiante,
            pct_hydratation, activity, heat_index, quality_flag
        FROM measurements 
        WHERE tz_timestamp < %s
        ORDER BY tz_timestamp
        """

        conn = psycopg2.connect(**self.db_config)

        # Export vers fichier
        old_measurements = pd.read_sql_query(query, conn, params=(cutoff_date,))

        if not old_measurements.empty:
            # Compression si demandée
            if self.archive_config['compression']:
                archive_file += '.gz'
                old_measurements.to_csv(archive_file, index=False, compression='gzip')
            else:
                old_measurements.to_csv(archive_file, index=False)

            # Suppression des données archivées
            delete_query = "DELETE FROM measurements WHERE tz_timestamp < %s"
            with conn.cursor() as cursor:
                cursor.execute(delete_query, (cutoff_date,))
                deleted_count = cursor.rowcount
                conn.commit()

            conn.close()

            logger.info(f"📦 {len(old_measurements)} mesures archivées vers {archive_file}")

            return {
                'operation': 'measurements_archiving',
                'archived_count': len(old_measurements),
                'deleted_count': deleted_count,
                'archive_file': archive_file,
                'cutoff_date': cutoff_date,
                'status': 'success'
            }
        else:
            conn.close()
            return {
                'operation': 'measurements_archiving',
                'archived_count': 0,
                'status': 'no_data_to_archive'
            }

    async def _archive_old_logs(self) -> Dict:
        """
        Archive les logs système anciens
        """
        logger.info("📝 Archivage logs système")

        cutoff_date = datetime.now() - timedelta(days=self.archive_config['logs_retention_days'])

        # Archivage logs IoT
        iot_logs_query = """
        SELECT * FROM logs_iot 
        WHERE timestamp < %s
        ORDER BY timestamp
        """

        conn = psycopg2.connect(**self.db_config)
        old_iot_logs = pd.read_sql_query(iot_logs_query, conn, params=(cutoff_date,))

        archived_count = 0

        if not old_iot_logs.empty:
            # Archive IoT logs
            iot_archive_file = f"{self.archive_config['archive_path']}/iot_logs_archive_{datetime.now().strftime('%Y%m%d')}.csv.gz"
            old_iot_logs.to_csv(iot_archive_file, index=False, compression='gzip')
            archived_count += len(old_iot_logs)

            # Suppression
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM logs_iot WHERE timestamp < %s", (cutoff_date,))
                conn.commit()

        # Archivage des logs d'audit (si table existe)
        try:
            audit_logs_query = """
            SELECT * FROM audit_logs 
            WHERE created_at < %s
            ORDER BY created_at
            """
            old_audit_logs = pd.read_sql_query(audit_logs_query, conn, params=(cutoff_date,))

            if not old_audit_logs.empty:
                audit_archive_file = f"{self.archive_config['archive_path']}/audit_logs_archive_{datetime.now().strftime('%Y%m%d')}.csv.gz"
                old_audit_logs.to_csv(audit_archive_file, index=False, compression='gzip')
                archived_count += len(old_audit_logs)

                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM audit_logs WHERE created_at < %s", (cutoff_date,))
                    conn.commit()

        except Exception as e:
            logger.warning(f"Pas de table audit_logs ou erreur: {e}")

        conn.close()

        return {
            'operation': 'logs_archiving',
            'archived_count': archived_count,
            'cutoff_date': cutoff_date,
            'status': 'success'
        }

    async def _archive_old_alerts(self) -> Dict:
        """
        Archive les alertes résolues anciennes
        """
        logger.info("🚨 Archivage alertes anciennes")

        cutoff_date = datetime.now() - timedelta(days=self.archive_config['alerts_retention_days'])

        # Sélection des alertes résolues anciennes
        query = """
        SELECT a.*, als.statut, als.changed_at as resolution_date
        FROM alerts a
        JOIN alert_statut_logs als ON a.alert_id = als.alert_id
        WHERE als.statut = 'resolved'
            AND als.changed_at < %s
        ORDER BY a.created_at
        """

        conn = psycopg2.connect(**self.db_config)
        old_alerts = pd.read_sql_query(query, conn, params=(cutoff_date,))

        if not old_alerts.empty:
            # Archive des alertes
            alerts_archive_file = f"{self.archive_config['archive_path']}/resolved_alerts_archive_{datetime.now().strftime('%Y%m%d')}.csv.gz"
            old_alerts.to_csv(alerts_archive_file, index=False, compression='gzip')

            # Suppression (avec gestion des contraintes)
            alert_ids = old_alerts['alert_id'].tolist()

            with conn.cursor() as cursor:
                # Suppression des logs de statut d'abord
                cursor.execute("DELETE FROM alert_statut_logs WHERE alert_id = ANY(%s)", (alert_ids,))
                # Puis suppression des alertes
                cursor.execute("DELETE FROM alerts WHERE alert_id = ANY(%s)", (alert_ids,))
                conn.commit()

            conn.close()

            logger.info(f"🗂️ {len(old_alerts)} alertes résolues archivées")

            return {
                'operation': 'alerts_archiving',
                'archived_count': len(old_alerts),
                'archive_file': alerts_archive_file,
                'status': 'success'
            }
        else:
            conn.close()
            return {
                'operation': 'alerts_archiving',
                'archived_count': 0,
                'status': 'no_data_to_archive'
            }

    async def _archive_quarantine_data(self) -> Dict:
        """
        Archive les données de quarantaine anciennes
        """
        logger.info("🗃️ Archivage données quarantaine")

        quarantine_path = "../../quarantine"
        cutoff_date = datetime.now() - timedelta(days=30)  # 30 jours en quarantaine max

        archived_files = []

        if os.path.exists(quarantine_path):
            for item in os.listdir(quarantine_path):
                item_path = os.path.join(quarantine_path, item)

                if os.path.isdir(item_path) and item.startswith('ingestion_date='):
                    # Extraction de la date du nom du dossier
                    try:
                        date_str = item.split('=')[1]
                        folder_date = datetime.strptime(date_str, '%Y-%m-%d')

                        if folder_date < cutoff_date:
                            # Compression du dossier entier
                            archive_name = f"{self.archive_config['archive_path']}/quarantine_{date_str}.tar.gz"

                            import tarfile
                            with tarfile.open(archive_name, 'w:gz') as tar:
                                tar.add(item_path, arcname=item)

                            # Suppression du dossier original
                            import shutil
                            shutil.rmtree(item_path)

                            archived_files.append(archive_name)

                    except ValueError:
                        logger.warning(f"Format de date invalide dans {item}")

        return {
            'operation': 'quarantine_archiving',
            'archived_count': len(archived_files),
            'archived_files': archived_files,
            'status': 'success'
        }

    async def _cleanup_temporary_files(self) -> Dict:
        """
        Nettoyage des fichiers temporaires
        """
        logger.info("🧹 Nettoyage fichiers temporaires")

        temp_paths = [
            "../../logs/temp",
            "../../evidence/temp",
            "/tmp/kidjamo"
        ]

        cleaned_files = 0
        freed_space = 0

        for temp_path in temp_paths:
            if os.path.exists(temp_path):
                for root, dirs, files in os.walk(temp_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            # Fichiers de plus de 7 jours
                            if os.path.getmtime(file_path) < (datetime.now() - timedelta(days=7)).timestamp():
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                cleaned_files += 1
                                freed_space += file_size
                        except Exception as e:
                            logger.warning(f"Erreur suppression {file_path}: {e}")

        return {
            'operation': 'temp_cleanup',
            'cleaned_files': cleaned_files,
            'freed_space_mb': freed_space / (1024*1024),
            'status': 'success'
        }

    async def _post_archive_optimization(self) -> Dict:
        """
        Optimisation post-archivage de la base de données
        """
        logger.info("⚡ Optimisation post-archivage")

        optimization_commands = [
            "VACUUM ANALYZE measurements;",
            "VACUUM ANALYZE alerts;",
            "VACUUM ANALYZE logs_iot;",
            "REINDEX TABLE measurements;",
            "UPDATE pg_stat_user_tables SET n_tup_upd = 0, n_tup_del = 0;",
        ]

        conn = psycopg2.connect(**self.db_config)
        executed_commands = []

        for command in optimization_commands:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(command)
                    conn.commit()
                executed_commands.append(command)
                logger.debug(f"✅ Exécuté: {command}")
            except Exception as e:
                logger.warning(f"⚠️ Erreur optimisation {command}: {e}")

        conn.close()

        return {
            'operation': 'post_archive_optimization',
            'executed_commands': len(executed_commands),
            'commands': executed_commands,
            'status': 'success'
        }

    async def _save_archiving_report(self, results: Dict):
        """
        Sauvegarde le rapport d'archivage
        """
        report_file = f"{self.archive_config['archive_path']}/archiving_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"📋 Rapport d'archivage sauvegardé: {report_file}")

    async def restore_from_archive(self, archive_date: str, data_type: str = 'measurements') -> Dict:
        """
        Restaure des données depuis les archives
        """
        logger.info(f"📥 Restauration depuis archive: {data_type} du {archive_date}")

        archive_pattern = f"{data_type}_archive_{archive_date}"
        archive_files = [f for f in os.listdir(self.archive_config['archive_path'])
                        if f.startswith(archive_pattern)]

        if not archive_files:
            return {'status': 'error', 'message': f'Aucune archive trouvée pour {archive_pattern}'}

        archive_file = os.path.join(self.archive_config['archive_path'], archive_files[0])

        try:
            # Lecture de l'archive
            if archive_file.endswith('.gz'):
                df = pd.read_csv(archive_file, compression='gzip')
            else:
                df = pd.read_csv(archive_file)

            # Restauration en base (en mode append)
            conn = psycopg2.connect(**self.db_config)

            if data_type == 'measurements':
                df.to_sql('measurements', conn, if_exists='append', index=False, method='multi')
            elif data_type == 'alerts':
                df.to_sql('alerts', conn, if_exists='append', index=False, method='multi')

            conn.close()

            logger.info(f"✅ {len(df)} enregistrements restaurés depuis {archive_file}")

            return {
                'status': 'success',
                'restored_records': len(df),
                'archive_file': archive_file
            }

        except Exception as e:
            logger.error(f"❌ Erreur restauration: {e}")
            return {'status': 'error', 'message': str(e)}

    async def get_archive_inventory(self) -> Dict:
        """
        Inventaire des archives disponibles
        """
        inventory = {
            'archive_path': self.archive_config['archive_path'],
            'total_archives': 0,
            'total_size_mb': 0,
            'archives_by_type': {},
            'oldest_archive': None,
            'newest_archive': None
        }

        if os.path.exists(self.archive_config['archive_path']):
            archive_files = os.listdir(self.archive_config['archive_path'])
            inventory['total_archives'] = len(archive_files)

            for file in archive_files:
                file_path = os.path.join(self.archive_config['archive_path'], file)
                file_size = os.path.getsize(file_path) / (1024*1024)  # MB
                file_date = datetime.fromtimestamp(os.path.getmtime(file_path))

                inventory['total_size_mb'] += file_size

                # Classification par type
                if 'measurements' in file:
                    archive_type = 'measurements'
                elif 'alerts' in file:
                    archive_type = 'alerts'
                elif 'logs' in file:
                    archive_type = 'logs'
                else:
                    archive_type = 'other'

                if archive_type not in inventory['archives_by_type']:
                    inventory['archives_by_type'][archive_type] = []

                inventory['archives_by_type'][archive_type].append({
                    'filename': file,
                    'size_mb': file_size,
                    'created_date': file_date.isoformat()
                })

                # Dates extrêmes
                if inventory['oldest_archive'] is None or file_date < datetime.fromisoformat(inventory['oldest_archive']):
                    inventory['oldest_archive'] = file_date.isoformat()
                if inventory['newest_archive'] is None or file_date > datetime.fromisoformat(inventory['newest_archive']):
                    inventory['newest_archive'] = file_date.isoformat()

        return inventory

async def main():
    """
    Test du gestionnaire d'archivage
    """
    db_config = {
        'host': 'localhost',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    archiving_manager = DataArchivingManager(db_config)

    # Test archivage complet
    results = await archiving_manager.run_automated_archiving()
    print(f"📦 Archivage terminé: {results['archived_records']} enregistrements")

    # Inventaire des archives
    inventory = await archiving_manager.get_archive_inventory()
    print(f"📁 Inventaire: {inventory['total_archives']} archives, {inventory['total_size_mb']:.1f} MB")

if __name__ == "__main__":
    asyncio.run(main())
