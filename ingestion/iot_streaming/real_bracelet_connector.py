#!/usr/bin/env python3
"""
Connecteur AWS IoT Core → Kinesis pour Bracelet Réel Kidjamo
Intercepte les données du vrai bracelet depuis AWS IoT Core
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import time

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RealBraceletConnector:
    """Connecteur pour bracelet IoT réel via AWS IoT Core"""

    def __init__(self,
                 thing_name: str,
                 topic_pattern: str = "device/+/data",
                 kinesis_stream: str = "kidjamo-iot-stream",
                 region: str = "eu-west-1"):

        self.thing_name = thing_name
        self.topic_pattern = topic_pattern
        self.kinesis_stream = kinesis_stream
        self.region = region

        # Clients AWS
        self.iot_client = boto3.client('iot-data', region_name=region)
        self.kinesis_client = boto3.client('kinesis', region_name=region)

        self.is_running = False
        self.processed_count = 0

        logger.info(f"🚀 Connecteur bracelet réel initialisé")
        logger.info(f"📱 Thing Name: {thing_name}")
        logger.info(f"📡 Topic Pattern: {topic_pattern}")
        logger.info(f"🌊 Kinesis Stream: {kinesis_stream}")

    async def start_monitoring(self):
        """Démarre la surveillance du bracelet réel"""
        logger.info("🎯 DEMARRAGE SURVEILLANCE BRACELET REEL")
        logger.info("📋 Polling AWS IoT Core pour données bracelet...")

        self.is_running = True

        try:
            # Méthode de polling IoT Core (alternative au MQTT direct)
            while self.is_running:
                await self._check_iot_core_data()
                await asyncio.sleep(2)  # Check toutes les 2 secondes

        except KeyboardInterrupt:
            logger.info("🔄 Arrêt demandé par l'utilisateur")
        finally:
            await self.stop_monitoring()

    async def _check_iot_core_data(self):
        """Vérifie s'il y a de nouvelles données du bracelet"""
        try:
            # Pour l'instant, on va utiliser IoT Device Shadow ou logs CloudWatch
            # Mais commençons par vérifier les topics disponibles

            # Alternative: Utiliser AWS IoT Analytics ou Device Defender
            # pour récupérer les dernières données

            logger.debug(f"🔍 Vérification données bracelet {self.thing_name}...")

            # Simulation temporaire - en attendant la vraie implémentation
            # Vous pourrez remplacer par la vraie source de données
            pass

        except Exception as e:
            logger.error(f"❌ Erreur vérification IoT Core: {e}")

    def process_real_bracelet_data(self, raw_data: str) -> bool:
        """Traite les données réelles du bracelet"""
        try:
            # Parser les données JSON reçues du bracelet
            data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data

            logger.info("📱 DONNEES BRACELET REEL RECUES:")
            logger.info(f"   📊 Données brutes: {data}")

            # Extraire les champs selon le format de votre bracelet
            accel_x = data.get('accel_x', 0)
            accel_y = data.get('accel_y', 0)
            accel_z = data.get('accel_z', 0)
            gyro_x = data.get('gyro_x', 0)
            gyro_y = data.get('gyro_y', 0)
            gyro_z = data.get('gyro_z', 0)
            temp = data.get('temp', 0)

            # Calculer magnitude pour classification
            magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
            activity = self._classify_activity(magnitude)

            # Créer le message formaté pour Kinesis
            kinesis_record = {
                'device_id': data.get('device_id', self.thing_name),
                'patient_id': data.get('patient_id', f'patient_{self.thing_name}'),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'sensors': {
                    'accelerometer': {
                        'x': accel_x,
                        'y': accel_y,
                        'z': accel_z,
                        'magnitude': magnitude
                    },
                    'gyroscope': {
                        'x': gyro_x,
                        'y': gyro_y,
                        'z': gyro_z
                    },
                    'temperature': temp
                },
                'activity_classification': activity,
                'data_source': 'real_bracelet',
                'event_type': 'bracelet_reading',
                'ingestion_timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Envoyer vers Kinesis
            success = self._send_to_kinesis(kinesis_record)

            if success:
                self.processed_count += 1
                logger.info(f"✅ BRACELET REEL - Données traitées:")
                logger.info(f"   📊 Accel: X={accel_x:.3f}, Y={accel_y:.3f}, Z={accel_z:.3f}")
                logger.info(f"   🌡️  Temp: {temp:.1f}°C")
                logger.info(f"   🏃 Activité: {activity}")
                logger.info(f"   📈 Total traité: {self.processed_count}")
                logger.info("")

            return success

        except Exception as e:
            logger.error(f"❌ Erreur traitement données bracelet réel: {e}")
            return False

    def _send_to_kinesis(self, record: Dict[str, Any]) -> bool:
        """Envoie les données vers Kinesis"""
        try:
            response = self.kinesis_client.put_record(
                StreamName=self.kinesis_stream,
                Data=json.dumps(record),
                PartitionKey=record['device_id']
            )

            logger.debug(f"✅ Envoyé vers Kinesis: {response['ShardId']}")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur envoi Kinesis: {e}")
            return False

    def _classify_activity(self, magnitude: float) -> str:
        """Classification d'activité basée sur la magnitude"""
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

    async def stop_monitoring(self):
        """Arrête la surveillance"""
        logger.info("🛑 Arrêt surveillance bracelet réel")
        self.is_running = False
        logger.info(f"📊 Total messages traités: {self.processed_count}")

# Fonction utilitaire pour tester avec des données simulées
def test_with_real_data():
    """Test avec format de données réelles du bracelet"""

    # Format exact de votre bracelet
    sample_data = {
        "device_id": "bracelet_real_001",
        "patient_id": "patient_123",
        "accel_x": 1.041478,
        "accel_y": 9.442732,
        "accel_z": 2.521094,
        "gyro_x": -0.00453,
        "gyro_y": 0.003198,
        "gyro_z": -0.014655,
        "temp": 28.50353,
        "timestamp": datetime.now().isoformat()
    }

    connector = RealBraceletConnector(
        thing_name="bracelet_real_001",
        topic_pattern="device/bracelet_real_001/data"
    )

    # Traiter les données
    success = connector.process_real_bracelet_data(sample_data)

    if success:
        print("✅ Test réussi - Données du bracelet réel traitées")
    else:
        print("❌ Test échoué")

# Point d'entrée principal
async def main():
    """Démarre la surveillance du bracelet réel"""

    # Configuration pour votre bracelet - À ADAPTER
    THING_NAME = "your_bracelet_thing_name"  # Remplacer par le nom de votre Thing IoT
    TOPIC_PATTERN = "device/+/data"          # Remplacer par votre pattern de topic

    connector = RealBraceletConnector(
        thing_name=THING_NAME,
        topic_pattern=TOPIC_PATTERN
    )

    try:
        logger.info("🎯 CONNECTEUR BRACELET IOT REEL - KIDJAMO")
        logger.info("📋 Surveillance des données AWS IoT Core en cours...")
        logger.info("📋 Utilisez Ctrl+C pour arrêter")
        logger.info("")

        await connector.start_monitoring()

    except KeyboardInterrupt:
        logger.info("🔄 Arrêt demandé")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")

if __name__ == "__main__":
    # Test rapide avec données simulées
    print("🧪 Test avec données réelles du bracelet:")
    test_with_real_data()

    print("\n" + "="*50)
    print("🚀 Démarrage surveillance bracelet réel:")

    # Démarrage réel
    asyncio.run(main())
