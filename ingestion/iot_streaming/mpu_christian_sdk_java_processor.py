#!/usr/bin/env python3
"""
Processeur Temps Réel MPU Christian - Topic sdk/test/java
Stream directement les données vers S3 avec structure year/month/day/hour
Adapté pour votre Arduino qui publie sur sdk/test/java toutes les secondes
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
import uuid

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MPUChristianRealtimeProcessor:
    """Processeur temps réel pour MPU Christian depuis topic sdk/test/java"""

    def __init__(self):
        self.region = "eu-west-1"
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.lambda_client = boto3.client('lambda', region_name=self.region)

        # Configuration
        self.bucket_name = "kidjamo-dev-datalake-e75d5213"
        self.stream_name = "kidjamo-iot-stream"
        self.device_id = "MPU_Christian_8266MOD"
        self.topic = "sdk/test/java"

        # Compteurs
        self.processed_count = 0
        self.s3_uploads = 0
        self.is_running = False

        logger.info(f"🚀 Processeur MPU Christian initialisé")
        logger.info(f"📡 Topic IoT: {self.topic}")
        logger.info(f"🏗️ Device: {self.device_id}")

    async def start_processing(self):
        """Démarre le traitement en temps réel depuis Kinesis"""

        logger.info("🔄 DÉMARRAGE TRAITEMENT TEMPS RÉEL MPU CHRISTIAN")
        logger.info(f"📊 Stream Kinesis: {self.stream_name}")

        try:
            # Découvrir les shards Kinesis
            await self._discover_shards()
            self.is_running = True

            # Créer les tâches de traitement
            tasks = []
            for shard_id in self.shard_iterators.keys():
                tasks.append(self._process_shard(shard_id))

            # Ajouter tâche de monitoring
            tasks.append(self._monitoring_task())

            # Démarrer le traitement
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            raise

    async def _discover_shards(self):
        """Découvre les shards du stream Kinesis"""
        self.shard_iterators = {}

        try:
            response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
            shards = response['StreamDescription']['Shards']

            for shard in shards:
                shard_id = shard['ShardId']

                # Commencer par les nouvelles données (LATEST)
                iterator_response = self.kinesis_client.get_shard_iterator(
                    StreamName=self.stream_name,
                    ShardId=shard_id,
                    ShardIteratorType='LATEST'
                )

                self.shard_iterators[shard_id] = iterator_response['ShardIterator']
                logger.info(f"📊 Shard configuré: {shard_id}")

        except Exception as e:
            logger.error(f"❌ Erreur découverte shards: {e}")
            raise

    async def _process_shard(self, shard_id: str):
        """Traite un shard spécifique"""

        while self.is_running:
            try:
                iterator = self.shard_iterators.get(shard_id)
                if not iterator:
                    await asyncio.sleep(1)
                    continue

                # Lire les records Kinesis
                response = self.kinesis_client.get_records(
                    ShardIterator=iterator,
                    Limit=100  # Traiter par batch pour efficacité
                )

                records = response.get('Records', [])
                next_iterator = response.get('NextShardIterator')

                if records:
                    await self._process_mpu_records(records, shard_id)

                # Mettre à jour l'itérateur
                self.shard_iterators[shard_id] = next_iterator

                # Pause courte pour éviter rate limiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"❌ Erreur traitement shard {shard_id}: {e}")
                await asyncio.sleep(5)

    async def _process_mpu_records(self, records: list, shard_id: str):
        """Traite les enregistrements MPU Christian"""

        batch_data = []

        for record in records:
            try:
                # Décoder les données
                data = json.loads(record['Data'])

                # Vérifier que c'est bien des données MPU
                if self._is_mpu_christian_data(data):
                    # Enrichir avec métadonnées
                    enriched_data = await self._enrich_mpu_data(data, record)
                    batch_data.append(enriched_data)

                    self.processed_count += 1

            except Exception as e:
                logger.warning(f"⚠️ Erreur traitement record: {e}")

        # Traiter le batch si on a des données
        if batch_data:
            await self._stream_to_s3(batch_data)
            await self._trigger_pipeline_if_needed(len(batch_data))

    def _is_mpu_christian_data(self, data: Dict) -> bool:
        """Vérifie si les données proviennent du MPU Christian"""

        # Vérifier la structure attendue du MPU6050
        required_fields = ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z', 'temp']

        return all(field in data for field in required_fields)

    async def _enrich_mpu_data(self, data: Dict, kinesis_record: Dict) -> Dict:
        """Enrichit les données MPU avec métadonnées"""

        now = datetime.now(timezone.utc)

        enriched = {
            # Données originales MPU
            'accel_x': data.get('accel_x', 0.0),
            'accel_y': data.get('accel_y', 0.0),
            'accel_z': data.get('accel_z', 0.0),
            'gyro_x': data.get('gyro_x', 0.0),
            'gyro_y': data.get('gyro_y', 0.0),
            'gyro_z': data.get('gyro_z', 0.0),
            'temp': data.get('temp', 0.0),

            # Métadonnées
            'device_id': self.device_id,
            'topic': self.topic,
            'timestamp': now.isoformat(),
            'kinesis_sequence': kinesis_record.get('SequenceNumber'),
            'partition_key': kinesis_record.get('PartitionKey'),

            # Structure partitionnée pour S3
            'year': now.year,
            'month': f"{now.month:02d}",
            'day': f"{now.day:02d}",
            'hour': f"{now.hour:02d}",

            # ID unique
            'record_id': str(uuid.uuid4()),

            # Calculs dérivés
            'accel_magnitude': (data.get('accel_x', 0)**2 + data.get('accel_y', 0)**2 + data.get('accel_z', 0)**2)**0.5,
            'gyro_magnitude': (data.get('gyro_x', 0)**2 + data.get('gyro_y', 0)**2 + data.get('gyro_z', 0)**2)**0.5,
        }

        return enriched

    async def _stream_to_s3(self, batch_data: list):
        """Stream directement vers S3 avec structure partitionnée"""

        try:
            # Grouper par partition (year/month/day/hour)
            partitions = {}

            for data in batch_data:
                partition_key = f"{data['year']}/{data['month']}/{data['day']}/{data['hour']}"

                if partition_key not in partitions:
                    partitions[partition_key] = []

                partitions[partition_key].append(data)

            # Uploader chaque partition
            for partition, records in partitions.items():
                await self._upload_partition_to_s3(partition, records)

        except Exception as e:
            logger.error(f"❌ Erreur streaming S3: {e}")

    async def _upload_partition_to_s3(self, partition: str, records: list):
        """Upload une partition vers S3"""

        try:
            # Générer le nom de fichier avec timestamp
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:-3]
            s3_key = f"raw/iot-measurements/mpu_christian/year={partition.split('/')[0]}/month={partition.split('/')[1]}/day={partition.split('/')[2]}/hour={partition.split('/')[3]}/mpu_christian_{timestamp}_{len(records)}_records.json"

            # Préparer le contenu
            content = {
                'device_id': self.device_id,
                'topic': self.topic,
                'upload_timestamp': datetime.now(timezone.utc).isoformat(),
                'records_count': len(records),
                'partition': partition,
                'records': records
            }

            # Upload vers S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(content, indent=2),
                ContentType='application/json',
                Metadata={
                    'device_id': self.device_id,
                    'topic': self.topic,
                    'records_count': str(len(records)),
                    'partition': partition
                }
            )

            self.s3_uploads += 1
            logger.info(f"📦 S3 Upload: {s3_key} ({len(records)} records)")

        except Exception as e:
            logger.error(f"❌ Erreur upload S3: {e}")

    async def _trigger_pipeline_if_needed(self, batch_size: int):
        """Déclenche la pipeline si nécessaire"""

        # Déclencher toutes les 100 données ou toutes les 5 minutes via EventBridge
        if self.processed_count % 100 == 0:
            try:
                # Notifier Lambda orchestrateur
                event = {
                    'trigger_type': 's3_streaming_ready',
                    'device_id': self.device_id,
                    'topic': self.topic,
                    'batch_size': batch_size,
                    'total_processed': self.processed_count,
                    'streaming_mode': True
                }

                # Invoke asynchrone pour ne pas bloquer
                self.lambda_client.invoke(
                    FunctionName='kidjamo-auto-pipeline-orchestrator',
                    InvocationType='Event',  # Asynchrone
                    Payload=json.dumps(event)
                )

                logger.info(f"🚀 Pipeline trigger envoyé ({self.processed_count} records traités)")

            except Exception as e:
                logger.warning(f"⚠️ Erreur trigger pipeline: {e}")

    async def _monitoring_task(self):
        """Tâche de monitoring périodique"""

        while self.is_running:
            await asyncio.sleep(60)  # Toutes les minutes

            logger.info(f"📊 STATUS - Traités: {self.processed_count}, S3 Uploads: {self.s3_uploads}")

    def stop_processing(self):
        """Arrête le traitement"""
        logger.info("🛑 Arrêt du traitement demandé")
        self.is_running = False

async def main():
    """Point d'entrée principal"""

    processor = MPUChristianRealtimeProcessor()

    try:
        logger.info("🚀 DÉMARRAGE PROCESSEUR TEMPS RÉEL MPU CHRISTIAN")
        logger.info("📡 Topic: sdk/test/java")
        logger.info("🏗️ Device: MPU_Christian_8266MOD")
        logger.info("⚡ Mode: Streaming direct vers S3")

        await processor.start_processing()

    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par utilisateur")
        processor.stop_processing()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
