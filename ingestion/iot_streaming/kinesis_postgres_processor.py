#!/usr/bin/env python3
"""
Pipeline Kinesis → PostgreSQL pour Bracelet IoT Kidjamo
Traite les données temps réel depuis Kinesis et les insère dans PostgreSQL
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import uuid
import os
import sys
from dataclasses import dataclass

# Ajouter le chemin vers le module PostgreSQL
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'pipelines', 'pipeline_glue', 'glue_jobs'))

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "kinesis_processor", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedBraceletReading:
    """Lecture de bracelet traitée pour PostgreSQL"""
    device_id: str
    patient_id: str
    timestamp: datetime

    # Vitales
    heart_rate: Optional[int] = None
    spo2: Optional[float] = None
    temperature: Optional[float] = None

    # Accéléromètre
    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None
    accel_magnitude: Optional[float] = None
    activity_classification: Optional[str] = None

    # Métadonnées
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None
    data_source: str = "kinesis_stream"

    def to_postgres_record(self) -> Dict[str, Any]:
        """Convertit en format pour insertion PostgreSQL"""
        return {
            'patient_id': self.patient_id,
            'device_id': self.device_id,
            'recorded_at': self.timestamp,
            'heart_rate_bpm': self.heart_rate,
            'spo2_percent': self.spo2,
            'temperature_celsius': self.temperature,
            'accel_x': self.accel_x,
            'accel_y': self.accel_y,
            'accel_z': self.accel_z,
            'accel_magnitude': self.accel_magnitude,
            'activity_classification': self.activity_classification,
            'battery_percent': self.battery_level,
            'signal_quality': self.signal_strength,
            'data_source': self.data_source,
            'quality_flag': 'ok'
        }

class KinesisBraceletProcessor:
    """Processeur principal Kinesis → PostgreSQL pour bracelets IoT"""

    def __init__(self,
                 stream_name: str,
                 postgres_secret_id: str = "kidjamo-rds-credentials",
                 region: str = "eu-west-1"):

        self.stream_name = stream_name
        self.postgres_secret_id = postgres_secret_id
        self.region = region

        self.kinesis_client = boto3.client('kinesis', region_name=region)

        # Importer le connecteur PostgreSQL simplifié (sans AWS Glue)
        from simple_postgres_connector import SimplePostgreSQLConnector
        self.pg_connector = SimplePostgreSQLConnector(postgres_secret_id, region)

        self.is_running = False
        self.shard_iterators = {}

        logger.info(f"✅ Processeur Kinesis initialisé: {stream_name}")

    async def start_processing(self):
        """Démarre le traitement Kinesis → PostgreSQL"""
        logger.info("🚀 Démarrage traitement Kinesis → PostgreSQL")

        try:
            # Connexion PostgreSQL
            self.pg_connector.connect()

            # Découvrir les shards du stream
            await self._discover_shards()

            self.is_running = True

            # Créer les tâches de traitement par shard
            tasks = []
            for shard_id in self.shard_iterators.keys():
                tasks.append(self._process_shard(shard_id))

            # Démarrer le traitement
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"❌ Erreur démarrage traitement: {e}")
            raise

    async def _discover_shards(self):
        """Découvre les shards du stream Kinesis"""
        try:
            response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
            shards = response['StreamDescription']['Shards']

            for shard in shards:
                shard_id = shard['ShardId']

                # Obtenir l'itérateur pour ce shard (commence par LATEST)
                iterator_response = self.kinesis_client.get_shard_iterator(
                    StreamName=self.stream_name,
                    ShardId=shard_id,
                    ShardIteratorType='LATEST'  # Commence par les nouvelles données
                )

                self.shard_iterators[shard_id] = iterator_response['ShardIterator']
                logger.info(f"📊 Shard découvert: {shard_id}")

        except Exception as e:
            logger.error(f"❌ Erreur découverte shards: {e}")
            raise

    async def _process_shard(self, shard_id: str):
        """Traite un shard Kinesis spécifique"""
        logger.info(f"🔄 Début traitement shard: {shard_id}")

        while self.is_running:
            try:
                iterator = self.shard_iterators.get(shard_id)
                if not iterator:
                    await asyncio.sleep(1)
                    continue

                # Lire les records du shard
                response = self.kinesis_client.get_records(
                    ShardIterator=iterator,
                    Limit=100  # Traiter max 100 records par batch
                )

                records = response.get('Records', [])
                next_iterator = response.get('NextShardIterator')

                if records:
                    # Traiter les records
                    await self._process_records(records, shard_id)

                # Mettre à jour l'itérateur
                self.shard_iterators[shard_id] = next_iterator

                # Pause pour éviter de surcharger l'API
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Erreur traitement shard {shard_id}: {e}")
                await asyncio.sleep(5)  # Pause plus longue en cas d'erreur

    async def _process_records(self, records: List[Dict], shard_id: str):
        """Traite un batch de records Kinesis"""
        processed_readings = []

        for record in records:
            try:
                # Décoder les données
                data = json.loads(record['Data'])

                # Convertir en lecture structurée
                reading = self._parse_bracelet_data(data)
                if reading:
                    processed_readings.append(reading)

            except Exception as e:
                logger.warning(f"⚠️ Erreur parsing record: {e}")
                continue

        if processed_readings:
            # Insertion batch dans PostgreSQL
            await self._insert_batch_to_postgres(processed_readings)
            logger.info(f"✅ {len(processed_readings)} lectures traitées depuis shard {shard_id}")

    def _parse_bracelet_data(self, data: Dict[str, Any]) -> Optional[ProcessedBraceletReading]:
        """Parse les données JSON du bracelet en structure typée"""
        try:
            # Extraction des données selon le format de votre bracelet
            device_id = data.get('device_id')
            patient_id = data.get('patient_id', device_id)  # Fallback

            # Parse timestamp
            timestamp_str = data.get('timestamp', data.get('ingestion_timestamp'))
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            else:
                timestamp = datetime.now(timezone.utc)

            # Créer la lecture
            reading = ProcessedBraceletReading(
                device_id=device_id,
                patient_id=patient_id,
                timestamp=timestamp
            )

            # Remplir selon le type de données disponibles
            vitals = data.get('vitals', {})
            if vitals:
                reading.heart_rate = vitals.get('heart_rate')
                reading.spo2 = vitals.get('spo2')
                reading.temperature = vitals.get('temperature')

            # Données directes (format alternatif)
            reading.heart_rate = reading.heart_rate or data.get('heart_rate')
            reading.spo2 = reading.spo2 or data.get('spo2')
            reading.temperature = reading.temperature or data.get('temperature')

            # Accéléromètre
            accelerometer = data.get('accelerometer', {})
            if accelerometer:
                reading.accel_x = accelerometer.get('x')
                reading.accel_y = accelerometer.get('y')
                reading.accel_z = accelerometer.get('z')

                # Calculer magnitude si pas fournie
                if reading.accel_x and reading.accel_y and reading.accel_z:
                    reading.accel_magnitude = (
                        reading.accel_x**2 + reading.accel_y**2 + reading.accel_z**2
                    )**0.5

                reading.activity_classification = accelerometer.get('activity')

            # Données directes accéléromètre
            reading.accel_x = reading.accel_x or data.get('x')
            reading.accel_y = reading.accel_y or data.get('y')
            reading.accel_z = reading.accel_z or data.get('z')
            reading.activity_classification = reading.activity_classification or data.get('activity')

            # Métadonnées
            metadata = data.get('metadata', {})
            reading.battery_level = metadata.get('battery_level') or data.get('battery')
            reading.signal_strength = metadata.get('signal_strength') or data.get('signal')

            return reading

        except Exception as e:
            logger.warning(f"⚠️ Erreur parsing données bracelet: {e}")
            return None

    async def _insert_batch_to_postgres(self, readings: List[ProcessedBraceletReading]):
        """Insère un batch de lectures dans PostgreSQL"""
        try:
            # Convertir en format PostgreSQL
            postgres_records = [reading.to_postgres_record() for reading in readings]

            # S'assurer que les patients existent
            await self._ensure_patients_exist(readings)

            # Préparer la requête d'insertion
            insert_query = """
            INSERT INTO measurements (
                patient_id, device_id, recorded_at,
                heart_rate_bpm, spo2_percent, temperature_celsius,
                accel_x, accel_y, accel_z, accel_magnitude, activity_classification,
                battery_percent, signal_quality, data_source, quality_flag
            ) VALUES %s
            ON CONFLICT (patient_id, device_id, recorded_at) 
            DO UPDATE SET
                heart_rate_bpm = EXCLUDED.heart_rate_bpm,
                spo2_percent = EXCLUDED.spo2_percent,
                temperature_celsius = EXCLUDED.temperature_celsius,
                accel_x = EXCLUDED.accel_x,
                accel_y = EXCLUDED.accel_y,
                accel_z = EXCLUDED.accel_z,
                accel_magnitude = EXCLUDED.accel_magnitude,
                activity_classification = EXCLUDED.activity_classification,
                updated_at = CURRENT_TIMESTAMP
            """

            # Préparer les valeurs
            values = []
            for record in postgres_records:
                values.append((
                    record['patient_id'],
                    record['device_id'],
                    record['recorded_at'],
                    record['heart_rate_bpm'],
                    record['spo2_percent'],
                    record['temperature_celsius'],
                    record['accel_x'],
                    record['accel_y'],
                    record['accel_z'],
                    record['accel_magnitude'],
                    record['activity_classification'],
                    record['battery_percent'],
                    record['signal_quality'],
                    record['data_source'],
                    record['quality_flag']
                ))

            # Exécution avec gestion de transaction
            with self.pg_connector.connection.cursor() as cursor:
                from psycopg2.extras import execute_values
                execute_values(cursor, insert_query, values)
                self.pg_connector.connection.commit()

            logger.info(f"✅ {len(values)} measurements insérés dans PostgreSQL")

            # Vérifier les alertes critiques
            await self._check_critical_alerts(readings)

        except Exception as e:
            self.pg_connector.connection.rollback()
            logger.error(f"❌ Erreur insertion PostgreSQL: {e}")
            raise

    async def _ensure_patients_exist(self, readings: List[ProcessedBraceletReading]):
        """S'assure que tous les patients existent dans la DB"""
        patient_ids = list(set([r.patient_id for r in readings if r.patient_id]))

        if not patient_ids:
            return

        try:
            # Vérifier quels patients existent
            placeholders = ','.join(['%s'] * len(patient_ids))
            check_query = f"SELECT patient_id FROM patients WHERE patient_id IN ({placeholders})"

            with self.pg_connector.connection.cursor() as cursor:
                cursor.execute(check_query, patient_ids)
                existing_patients = {row[0] for row in cursor.fetchall()}

            # Créer les patients manquants
            missing_patients = set(patient_ids) - existing_patients

            if missing_patients:
                for patient_id in missing_patients:
                    # Créer user d'abord
                    user_id = str(uuid.uuid4())

                    user_insert = """
                    INSERT INTO users (user_id, role, first_name, last_name, email)
                    VALUES (%s, 'patient', 'Patient', %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    """

                    patient_insert = """
                    INSERT INTO patients (patient_id, user_id, genotype, birth_date)
                    VALUES (%s, %s, 'SS', '2000-01-01')
                    ON CONFLICT (patient_id) DO NOTHING
                    """

                    with self.pg_connector.connection.cursor() as cursor:
                        cursor.execute(user_insert, (
                            user_id,
                            f"IoT-{patient_id[:8]}",
                            f"iot.{patient_id[:8]}@kidjamo.auto"
                        ))
                        cursor.execute(patient_insert, (patient_id, user_id))

                self.pg_connector.connection.commit()
                logger.info(f"✅ {len(missing_patients)} nouveaux patients créés automatiquement")

        except Exception as e:
            logger.warning(f"⚠️ Erreur création patients: {e}")

    async def _check_critical_alerts(self, readings: List[ProcessedBraceletReading]):
        """Vérifie et génère des alertes critiques temps réel"""
        for reading in readings:
            alerts = []

            # SpO2 critique
            if reading.spo2 and reading.spo2 < 88:
                alerts.append({
                    'patient_id': reading.patient_id,
                    'alert_type': 'spo2_critical_realtime',
                    'severity': 'critical',
                    'title': '🚨 SpO2 Critique Temps Réel',
                    'message': f'SpO2 critique détectée: {reading.spo2:.1f}% (device: {reading.device_id})'
                })

            # Fréquence cardiaque anormale
            if reading.heart_rate:
                if reading.heart_rate > 150 or reading.heart_rate < 45:
                    alerts.append({
                        'patient_id': reading.patient_id,
                        'alert_type': 'heart_rate_abnormal_realtime',
                        'severity': 'alert',
                        'title': '💓 Fréquence Cardiaque Anormale',
                        'message': f'FC anormale: {reading.heart_rate} bpm (device: {reading.device_id})'
                    })

            # Détection de chute
            if (reading.activity_classification and
                reading.activity_classification in ['chute_detectee', 'risque_chute']):
                alerts.append({
                    'patient_id': reading.patient_id,
                    'alert_type': 'fall_detection_realtime',
                    'severity': 'critical',
                    'title': '🚨 Chute Détectée',
                    'message': f'Possible chute détectée (magnitude: {reading.accel_magnitude:.2f})'
                })

            # Insérer les alertes
            if alerts:
                await self._insert_alerts(alerts)

    async def _insert_alerts(self, alerts: List[Dict]):
        """Insère des alertes dans la table alerts"""
        try:
            insert_query = """
            INSERT INTO alerts (
                patient_id, alert_type, severity, title, message, 
                created_at, vitals_snapshot
            ) VALUES %s
            ON CONFLICT (patient_id, alert_type, created_at) DO NOTHING
            """

            values = []
            current_time = datetime.now(timezone.utc)

            for alert in alerts:
                values.append((
                    alert['patient_id'],
                    alert['alert_type'],
                    alert['severity'],
                    alert['title'],
                    alert['message'],
                    current_time,
                    json.dumps({'realtime_alert': True, 'timestamp': current_time.isoformat()})
                ))

            with self.pg_connector.connection.cursor() as cursor:
                from psycopg2.extras import execute_values
                execute_values(cursor, insert_query, values)
                self.pg_connector.connection.commit()

            logger.warning(f"🚨 {len(alerts)} alertes critiques générées")

        except Exception as e:
            logger.error(f"❌ Erreur insertion alertes: {e}")

    async def stop_processing(self):
        """Arrête le traitement proprement"""
        logger.info("🛑 Arrêt du traitement Kinesis")
        self.is_running = False

        if self.pg_connector:
            self.pg_connector.close()

        logger.info("✅ Traitement Kinesis arrêté")

# Point d'entrée principal
async def main():
    """Démarre le processeur Kinesis → PostgreSQL"""

    # Configuration depuis variables d'environnement
    stream_name = os.environ.get('KINESIS_STREAM_NAME', 'kidjamo-iot-stream')
    postgres_secret = os.environ.get('PG_SECRET_ID', 'kidjamo-rds-credentials')
    region = os.environ.get('AWS_REGION', 'eu-west-1')

    processor = KinesisBraceletProcessor(
        stream_name=stream_name,
        postgres_secret_id=postgres_secret,
        region=region
    )

    try:
        logger.info("🚀 Démarrage pipeline Kinesis → PostgreSQL Kidjamo")
        await processor.start_processing()
    except KeyboardInterrupt:
        logger.info("🔄 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
    finally:
        await processor.stop_processing()

if __name__ == "__main__":
    asyncio.run(main())
