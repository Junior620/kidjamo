#!/usr/bin/env python3
"""
Simulateur Simple pour Bracelet IoT Kidjamo
Génère le format exact que votre bracelet envoie vers AWS IoT Core
"""

import json
import time
import random
import asyncio
import boto3
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleBraceletSimulator:
    """Simulateur qui génère le format exact du bracelet IoT réel"""

    def __init__(self, stream_name="kidjamo-iot-stream"):
        self.kinesis_client = boto3.client('kinesis', region_name='eu-west-1')
        self.stream_name = stream_name

    def generate_bracelet_data(self):
        """Génère exactement le format que votre bracelet envoie"""
        # Base de données similaire à votre exemple
        return {
            "accel_x": random.uniform(-2.0, 2.0),
            "accel_y": random.uniform(8.0, 11.0),  # Gravité + mouvement
            "accel_z": random.uniform(-2.0, 2.0),
            "gyro_x": random.uniform(-0.01, 0.01),
            "gyro_y": random.uniform(-0.01, 0.01),
            "gyro_z": random.uniform(-0.02, 0.02),
            "temp": random.uniform(25.0, 35.0)
        }

    def send_to_kinesis(self, data):
        """Envoie directement vers Kinesis (simule le passage par IoT Core)"""
        try:
            # Ajouter métadonnées pour Kinesis
            kinesis_record = {
                "device_id": "bracelet_test_01",
                "patient_id": "patient_123",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sensors": {
                    "accelerometer": {
                        "x": data["accel_x"],
                        "y": data["accel_y"],
                        "z": data["accel_z"]
                    },
                    "temperature": data["temp"]
                },
                "raw_data": data,  # Données brutes pour debug
                "event_type": "bracelet_reading",
                "ingestion_timestamp": datetime.now(timezone.utc).isoformat()
            }

            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(kinesis_record),
                PartitionKey="bracelet_test_01"
            )

            logger.info(f"✅ Données envoyées vers Kinesis: accel({data['accel_x']:.3f},{data['accel_y']:.3f},{data['accel_z']:.3f}) temp:{data['temp']:.1f}°C")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur envoi Kinesis: {e}")
            return False

    async def start_simulation(self, interval=5):
        """Démarre la simulation avec envoi périodique"""
        logger.info("🚀 Démarrage simulation bracelet IoT")
        logger.info(f"📡 Envoi vers Kinesis stream: {self.stream_name}")

        try:
            while True:
                # Générer et envoyer les données
                data = self.generate_bracelet_data()
                self.send_to_kinesis(data)

                # Attendre avant le prochain envoi
                await asyncio.sleep(interval)

        except KeyboardInterrupt:
            logger.info("🛑 Arrêt de la simulation demandé")
        except Exception as e:
            logger.error(f"❌ Erreur simulation: {e}")

async def main():
    """Point d'entrée pour tester"""
    simulator = SimpleBraceletSimulator()
    await simulator.start_simulation(interval=3)  # Envoi toutes les 3 secondes

if __name__ == "__main__":
    asyncio.run(main())
