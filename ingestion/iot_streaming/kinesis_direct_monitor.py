#!/usr/bin/env python3
"""
Moniteur Direct Kinesis pour MPU Christian
Surveille directement les streams Kinesis identifiés par l'intercepteur de règles
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KinesisDirectMonitor:
    """Moniteur direct des streams Kinesis pour MPU Christian"""

    def __init__(self):
        self.region = "eu-west-1"

        # Streams identifiés par l'intercepteur de règles
        self.streams = [
            "kidjamo-alerts-stream",      # Alertes de chute
            "kidjamo-vital-signs-stream", # Données accéléromètre
            "kidjamo-iot-stream"          # Stream général
        ]

        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.processed_count = 0
        self.shard_iterators = {}

        logger.info("🚀 Moniteur Direct Kinesis initialisé")
        logger.info(f"🌊 Streams surveillés: {self.streams}")

    async def start_monitoring(self):
        """Démarre la surveillance directe des streams Kinesis"""

        logger.info("🎯 SURVEILLANCE DIRECTE STREAMS KINESIS")
        logger.info("📡 Recherche de données MPU_Christian_8266MOD...")
        logger.info("=" * 60)

        # Initialiser les itérateurs pour chaque stream
        await self._initialize_stream_iterators()

        while True:
            try:
                # Surveiller chaque stream en parallèle
                tasks = []
                for stream_name in self.streams:
                    tasks.append(self._monitor_stream(stream_name))

                await asyncio.gather(*tasks, return_exceptions=True)

                await asyncio.sleep(2)  # Check toutes les 2 secondes

            except KeyboardInterrupt:
                logger.info("🔄 Arrêt surveillance demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                await asyncio.sleep(5)

    async def _initialize_stream_iterators(self):
        """Initialise les itérateurs pour chaque stream"""

        for stream_name in self.streams:
            try:
                # Vérifier si le stream existe
                response = self.kinesis_client.describe_stream(StreamName=stream_name)
                shards = response['StreamDescription']['Shards']

                self.shard_iterators[stream_name] = {}

                for shard in shards:
                    shard_id = shard['ShardId']

                    # Obtenir un itérateur pour les données les plus récentes
                    iterator_response = self.kinesis_client.get_shard_iterator(
                        StreamName=stream_name,
                        ShardId=shard_id,
                        ShardIteratorType='LATEST'  # Nouvelles données uniquement
                    )

                    self.shard_iterators[stream_name][shard_id] = iterator_response['ShardIterator']

                logger.info(f"✅ Stream {stream_name}: {len(shards)} shard(s) initialisés")

            except Exception as e:
                logger.warning(f"⚠️ Stream {stream_name} non accessible: {e}")

    async def _monitor_stream(self, stream_name: str):
        """Surveille un stream Kinesis spécifique"""

        if stream_name not in self.shard_iterators:
            return

        for shard_id, iterator in self.shard_iterators[stream_name].items():
            try:
                # Lire les nouveaux records
                response = self.kinesis_client.get_records(
                    ShardIterator=iterator,
                    Limit=100  # Jusqu'à 100 records par lecture
                )

                records = response.get('Records', [])
                next_iterator = response.get('NextShardIterator')

                # Mettre à jour l'itérateur pour la prochaine lecture
                if next_iterator:
                    self.shard_iterators[stream_name][shard_id] = next_iterator

                # Traiter chaque record
                for record in records:
                    await self._process_record(stream_name, shard_id, record)

            except Exception as e:
                logger.debug(f"⚠️ Erreur lecture {stream_name}/{shard_id}: {e}")

    async def _process_record(self, stream_name: str, shard_id: str, record: dict):
        """Traite un record Kinesis"""

        try:
            # Décoder les données
            data_bytes = record['Data']
            if isinstance(data_bytes, bytes):
                data_str = data_bytes.decode('utf-8')
            else:
                data_str = str(data_bytes)

            # Parser le JSON
            data = json.loads(data_str)

            # AFFICHER TOUTES LES DONNÉES POUR DEBUGGING
            self.processed_count += 1

            logger.info(f"🎯 DONNÉES KINESIS DÉTECTÉES (#{self.processed_count}):")
            logger.info(f"   🌊 Stream: {stream_name}")
            logger.info(f"   🔧 Shard: {shard_id}")
            logger.info(f"   🕐 Kinesis Timestamp: {record.get('ApproximateArrivalTimestamp')}")
            logger.info(f"   📊 DONNÉES COMPLÈTES:")

            # Afficher toutes les clés disponibles
            logger.info(f"   🗝️ Clés disponibles: {list(data.keys())}")

            # Afficher les data complètes avec indentation
            logger.info(json.dumps(data, indent=4, ensure_ascii=False, default=str))

            # Vérifier si c'est des données de MPU Christian
            device_id = data.get('device_id', '')
            topic = data.get('topic', '')
            clientId = data.get('clientId', '')

            is_mpu_christian = (
                'MPU_Christian' in str(device_id) or
                'christian' in str(device_id).lower() or
                'MPU_Christian' in str(topic) or
                'christian' in str(topic).lower() or
                'MPU_Christian' in str(clientId) or
                'christian' in str(clientId).lower()
            )

            if is_mpu_christian:
                logger.info("✅ *** DONNÉES MPU CHRISTIAN CONFIRMÉES ***")

            logger.info("=" * 80)

            # Analyser les données capteurs
            await self._analyze_sensor_data(data)

        except json.JSONDecodeError as e:
            logger.info(f"⚠️ Record non-JSON dans {stream_name}: {data_str[:200]}...")
        except Exception as e:
            logger.error(f"❌ Erreur traitement record: {e}")
            logger.info(f"   Raw data: {str(record)[:200]}...")

    async def _analyze_sensor_data(self, data: dict):
        """Analyse les données de capteurs détectées"""

        # Rechercher les données d'accéléromètre
        if 'accelerometer' in data:
            accel = data['accelerometer']
            logger.info(f"   📈 ACCÉLÉROMÈTRE:")
            logger.info(f"      X: {accel.get('x', 'N/A')}")
            logger.info(f"      Y: {accel.get('y', 'N/A')}")
            logger.info(f"      Z: {accel.get('z', 'N/A')}")

        # Rechercher les données de gyroscope
        if 'gyroscope' in data:
            gyro = data['gyroscope']
            logger.info(f"   🌀 GYROSCOPE:")
            logger.info(f"      X: {gyro.get('x', 'N/A')}")
            logger.info(f"      Y: {gyro.get('y', 'N/A')}")
            logger.info(f"      Z: {gyro.get('z', 'N/A')}")

        # Rechercher la température
        if 'temperature' in data:
            logger.info(f"   🌡️ TEMPÉRATURE: {data['temperature']}°C")

        # Rechercher d'autres formats de données
        for key, value in data.items():
            if key.lower() in ['ax', 'ay', 'az', 'gx', 'gy', 'gz']:
                logger.info(f"   📊 {key.upper()}: {value}")

async def main():
    """Point d'entrée principal"""

    logger.info("🚀 DÉMARRAGE MONITEUR DIRECT KINESIS")
    logger.info("📡 Surveillance directe pour MPU_Christian_8266MOD")
    logger.info("🎯 Streams: alerts, vital-signs, iot-stream")
    logger.info("=" * 60)

    monitor = KinesisDirectMonitor()

    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du moniteur demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
    finally:
        logger.info("🔄 Arrêt du moniteur")

if __name__ == "__main__":
    asyncio.run(main())
