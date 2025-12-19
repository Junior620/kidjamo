#!/usr/bin/env python3
"""
Processeur Kinesis Simplifié pour Bracelet IoT Kidjamo
Version simplifiée qui traite les données et les affiche pour validation
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Configuration logging simple
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleBraceletProcessor:
    """Processeur simplifié pour validation du pipeline"""

    def __init__(self, stream_name: str = "kidjamo-iot-stream", region: str = "eu-west-1"):
        self.stream_name = stream_name
        self.region = region
        self.kinesis_client = boto3.client('kinesis', region_name=region)
        self.is_running = False
        self.shard_iterators = {}
        self.processed_count = 0

    async def start_processing(self):
        """Démarre le traitement Kinesis (mode validation)"""
        logger.info(f"🚀 DEMARRAGE PROCESSEUR BRACELET IOT")
        logger.info(f"📡 Stream: {self.stream_name}")
        
        try:
            # Découvrir les shards
            await self._discover_shards()
            self.is_running = True

            # Créer les tâches de traitement
            tasks = []
            for shard_id in self.shard_iterators.keys():
                tasks.append(self._process_shard(shard_id))

            # Démarrer le traitement
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            raise

    async def _discover_shards(self):
        """Découvre les shards du stream Kinesis"""
        try:
            response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
            shards = response['StreamDescription']['Shards']

            for shard in shards:
                shard_id = shard['ShardId']
                
                # Obtenir l'itérateur (commence par LATEST pour nouvelles données)
                iterator_response = self.kinesis_client.get_shard_iterator(
                    StreamName=self.stream_name,
                    ShardId=shard_id,
                    ShardIteratorType='LATEST'
                )

                self.shard_iterators[shard_id] = iterator_response['ShardIterator']
                logger.info(f"📊 Shard découvert: {shard_id}")

        except Exception as e:
            logger.error(f"❌ Erreur découverte shards: {e}")
            raise

    async def _process_shard(self, shard_id: str):
        """Traite un shard spécifique"""
        logger.info(f"🔄 Traitement shard: {shard_id}")

        while self.is_running:
            try:
                iterator = self.shard_iterators.get(shard_id)
                if not iterator:
                    await asyncio.sleep(1)
                    continue

                # Lire les records
                response = self.kinesis_client.get_records(
                    ShardIterator=iterator,
                    Limit=50
                )

                records = response.get('Records', [])
                next_iterator = response.get('NextShardIterator')

                if records:
                    await self._process_records(records, shard_id)

                # Mettre à jour l'itérateur
                self.shard_iterators[shard_id] = next_iterator
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Erreur shard {shard_id}: {e}")
                await asyncio.sleep(2)

    async def _process_records(self, records: List[Dict], shard_id: str):
        """Traite les records reçus"""
        for record in records:
            try:
                # Décoder les données JSON
                data = json.loads(record['Data'])
                
                # Traiter les données du bracelet
                self._process_bracelet_data(data)
                self.processed_count += 1

            except Exception as e:
                logger.warning(f"⚠️ Erreur record: {e}")

        logger.info(f"✅ {len(records)} records traités depuis {shard_id} (Total: {self.processed_count})")

    def _process_bracelet_data(self, data: Dict[str, Any]):
        """Traite et affiche les données du bracelet"""
        try:
            # Extraire les informations principales
            device_id = data.get('device_id', 'N/A')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            # Données capteurs (format de votre bracelet)
            sensors = data.get('sensors', {})
            
            # Accéléromètre
            accel = sensors.get('accelerometer', {})
            accel_x = accel.get('x', 0)
            accel_y = accel.get('y', 0) 
            accel_z = accel.get('z', 0)
            
            # Calculer magnitude
            magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
            
            # Température
            temperature = sensors.get('temperature', 0)
            
            # Classification d'activité basique
            activity = self._classify_activity(magnitude)
            
            # Affichage formaté
            logger.info(f"")
            logger.info(f"📱 DONNEES BRACELET IOT RECUES:")
            logger.info(f"   Device: {device_id}")
            logger.info(f"   Timestamp: {timestamp}")
            logger.info(f"   📊 Accelerometre: X={accel_x:.3f}, Y={accel_y:.3f}, Z={accel_z:.3f}")
            logger.info(f"   🔢 Magnitude: {magnitude:.3f}")
            logger.info(f"   🌡️  Temperature: {temperature:.1f}°C")
            logger.info(f"   🏃 Activite: {activity}")
            logger.info(f"   ✅ Donnees traitees avec succes!")
            logger.info(f"")

        except Exception as e:
            logger.warning(f"⚠️ Erreur traitement bracelet: {e}")

    def _classify_activity(self, magnitude: float) -> str:
        """Classification basique d'activité selon la magnitude"""
        if magnitude > 15.0:
            return "🚨 CHUTE_DETECTEE"
        elif magnitude > 12.0:
            return "🏃 COURSE"
        elif magnitude > 10.5:
            return "🚶 MARCHE_ACTIVE"
        elif magnitude > 9.0:
            return "🚶 MARCHE"
        else:
            return "😴 REPOS"

    async def stop_processing(self):
        """Arrête le processeur"""
        logger.info("🛑 Arrêt du processeur bracelet IoT")
        self.is_running = False

# Point d'entrée
async def main():
    """Démarre le processeur simplifié"""
    processor = SimpleBraceletProcessor()
    
    try:
        logger.info("🎯 PROCESSEUR BRACELET IOT KIDJAMO - MODE VALIDATION")
        logger.info("📋 Ce processeur affiche les données reçues de votre bracelet")
        logger.info("📋 Utilisez Ctrl+C pour arrêter")
        logger.info("")
        await processor.start_processing()
    except KeyboardInterrupt:
        logger.info("🔄 Arrêt demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
    finally:
        await processor.stop_processing()

if __name__ == "__main__":
    asyncio.run(main())
