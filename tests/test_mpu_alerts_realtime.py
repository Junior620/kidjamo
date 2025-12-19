#!/usr/bin/env python3
"""
Test du système d'alertes temps réel MPU Christian
Simule des données d'alerte et teste le processeur
"""

import asyncio
import json
import boto3
import logging
from datetime import datetime, timezone
import random
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MPUAlertTester:
    """Testeur pour le système d'alertes MPU Christian"""

    def __init__(self):
        self.region = "eu-west-1"
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.stream_name = "kidjamo-iot-stream-dev"
        self.device_id = "MPU_Christian_8266MOD"

    async def test_alert_scenarios(self):
        """Teste différents scénarios d'alertes"""

        logger.info("🧪 DÉMARRAGE TEST SYSTÈME D'ALERTES MPU CHRISTIAN")

        scenarios = [
            self._test_normal_data,
            self._test_fall_detection,
            self._test_temperature_alert,
            self._test_abnormal_movement,
            self._test_inactivity
        ]

        for i, scenario in enumerate(scenarios, 1):
            logger.info(f"🔬 Test {i}/{len(scenarios)}: {scenario.__name__}")
            await scenario()
            await asyncio.sleep(2)  # Pause entre tests

        logger.info("✅ TOUS LES TESTS TERMINÉS")

    async def _test_normal_data(self):
        """Test avec données normales (pas d'alerte)"""

        data = {
            "accel_x": 0.5,
            "accel_y": -0.2,
            "accel_z": -9.8,  # Gravité normale
            "gyro_x": 0.01,
            "gyro_y": -0.005,
            "gyro_z": 0.02,
            "temp": 22.5,
            "aws_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "device_id": self.device_id
        }

        await self._send_to_kinesis(data, "Données normales - aucune alerte attendue")

    async def _test_fall_detection(self):
        """Test de détection de chute (alerte HIGH)"""

        data = {
            "accel_x": 18.2,   # Accélération élevée
            "accel_y": -15.8,
            "accel_z": -12.4,
            "gyro_x": 0.5,
            "gyro_y": -0.3,
            "gyro_z": 0.8,
            "temp": 23.1,
            "aws_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "device_id": self.device_id
        }

        await self._send_to_kinesis(data, "🚨 CHUTE DÉTECTÉE - Alerte HIGH attendue")

    async def _test_temperature_alert(self):
        """Test d'alerte de température (alerte MEDIUM/HIGH)"""

        data = {
            "accel_x": 0.3,
            "accel_y": -0.1,
            "accel_z": -9.7,
            "gyro_x": 0.02,
            "gyro_y": -0.01,
            "gyro_z": 0.015,
            "temp": 47.8,  # Température critique
            "aws_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "device_id": self.device_id
        }

        await self._send_to_kinesis(data, "🌡️ TEMPÉRATURE CRITIQUE - Alerte HIGH attendue")

    async def _test_abnormal_movement(self):
        """Test de mouvement anormal (alerte MEDIUM)"""

        data = {
            "accel_x": 2.1,
            "accel_y": -1.8,
            "accel_z": -8.9,
            "gyro_x": 12.5,   # Rotation rapide
            "gyro_y": -8.3,
            "gyro_z": 15.7,
            "temp": 24.2,
            "aws_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "device_id": self.device_id
        }

        await self._send_to_kinesis(data, "🔄 MOUVEMENT ANORMAL - Alerte MEDIUM attendue")

    async def _test_inactivity(self):
        """Test de détection d'inactivité (alerte LOW après accumulation)"""

        logger.info("📊 Test d'inactivité - envoi de 5 échantillons très peu actifs")

        for i in range(5):
            data = {
                "accel_x": random.uniform(-0.05, 0.05),
                "accel_y": random.uniform(-0.05, 0.05),
                "accel_z": random.uniform(-9.85, -9.75),
                "gyro_x": random.uniform(-0.001, 0.001),
                "gyro_y": random.uniform(-0.001, 0.001),
                "gyro_z": random.uniform(-0.001, 0.001),
                "temp": 23.0,
                "aws_timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "device_id": self.device_id
            }

            await self._send_to_kinesis(data, f"😴 Inactivité #{i+1}/5")
            await asyncio.sleep(0.5)

    async def _send_to_kinesis(self, data: dict, description: str):
        """Envoie des données de test vers Kinesis"""

        try:
            # Convertir en JSON
            record_data = json.dumps(data)

            # Envoyer vers Kinesis
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=record_data,
                PartitionKey=f"mpu_test_{random.randint(1000, 9999)}"
            )

            logger.info(f"📤 {description}")
            logger.info(f"   Sequence: {response['SequenceNumber']}")
            logger.info(f"   Shard: {response['ShardId']}")

        except Exception as e:
            logger.error(f"❌ Erreur envoi test: {e}")

async def main():
    """Point d'entrée principal du test"""

    tester = MPUAlertTester()

    try:
        logger.info("🧪 DÉMARRAGE TESTS SYSTÈME D'ALERTES MPU CHRISTIAN")
        logger.info("📡 Les données de test vont être envoyées vers Kinesis")
        logger.info("🔍 Surveillez les logs du processeur d'alertes pour voir les détections")

        await tester.test_alert_scenarios()

        logger.info("\n✅ TESTS TERMINÉS!")
        logger.info("📊 Vérifiez:")
        logger.info("   1. Les logs du processeur d'alertes")
        logger.info("   2. Les notifications SNS reçues")
        logger.info("   3. Les fichiers d'alertes dans S3")

    except Exception as e:
        logger.error(f"❌ Erreur tests: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
