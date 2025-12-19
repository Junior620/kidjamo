#!/usr/bin/env python3
"""
Test Simple Pipeline Kidjamo - Injection directe Kinesis
Teste le pipeline sans MQTT : injection directe dans Kinesis → PostgreSQL
"""

import boto3
import json
import time
from datetime import datetime, timezone
import logging
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimplePipelineTest:
    """Test simple du pipeline Kinesis → PostgreSQL"""

    def __init__(self):
        self.kinesis_client = boto3.client('kinesis', region_name='eu-west-1')
        self.stream_name = "kidjamo-dev-iot-measurements"

    def generate_realistic_bracelet_data(self, device_id="test-bracelet-001", patient_id="test-patient-001"):
        """Génère des données réalistes de bracelet IoT"""

        # Simulation de différents états de santé
        scenarios = ["normal", "stress", "exercise", "crisis"]
        scenario = random.choice(scenarios)

        if scenario == "normal":
            heart_rate = random.randint(60, 80)
            spo2 = random.uniform(95.0, 99.0)
            temperature = random.uniform(36.2, 37.0)
            activity = "repos"
        elif scenario == "stress":
            heart_rate = random.randint(85, 110)
            spo2 = random.uniform(92.0, 96.0)
            temperature = random.uniform(36.8, 37.5)
            activity = "mouvement_leger"
        elif scenario == "exercise":
            heart_rate = random.randint(120, 160)
            spo2 = random.uniform(94.0, 98.0)
            temperature = random.uniform(37.0, 38.0)
            activity = "activite_intense"
        else:  # crisis
            heart_rate = random.randint(100, 140)
            spo2 = random.uniform(85.0, 92.0)  # SpO2 critique !
            temperature = random.uniform(37.5, 39.0)
            activity = "risque_medical"

        return {
            "device_id": device_id,
            "patient_id": patient_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vitals": {
                "heart_rate": heart_rate,
                "spo2": round(spo2, 1),
                "temperature": round(temperature, 1)
            },
            "accelerometer": {
                "x": random.uniform(-2.0, 2.0),
                "y": random.uniform(8.0, 11.0),
                "z": random.uniform(-1.0, 1.0),
                "activity": activity
            },
            "metadata": {
                "battery_level": random.randint(75, 100),
                "signal_strength": random.randint(80, 100),
                "firmware_version": "v2.1.3"
            },
            "event_type": "bracelet_reading",
            "scenario": scenario,
            "source": "simple_test"
        }

    def inject_test_data(self, num_records=10):
        """Injecte des données de test dans Kinesis"""
        logger.info(f"🚀 Injection de {num_records} enregistrements de test...")

        devices = ["bracelet-001", "bracelet-002", "bracelet-003"]
        patients = ["patient-001", "patient-002", "patient-003"]

        success_count = 0

        for i in range(num_records):
            device_id = random.choice(devices)
            patient_id = random.choice(patients)

            # Générer données réalistes
            data = self.generate_realistic_bracelet_data(device_id, patient_id)

            try:
                response = self.kinesis_client.put_record(
                    StreamName=self.stream_name,
                    Data=json.dumps(data),
                    PartitionKey=device_id
                )

                success_count += 1

                # Log avec code couleur pour les alertes
                if data["vitals"]["spo2"] < 90:
                    logger.warning(f"🚨 ALERTE CRITIQUE: {device_id} - SpO2: {data['vitals']['spo2']}% → Shard: {response['ShardId']}")
                elif data["vitals"]["heart_rate"] > 150:
                    logger.warning(f"💓 ALERTE FC: {device_id} - HR: {data['vitals']['heart_rate']} bpm → Shard: {response['ShardId']}")
                else:
                    logger.info(f"✅ {device_id}: HR:{data['vitals']['heart_rate']} SpO2:{data['vitals']['spo2']}% → Shard: {response['ShardId']}")

                # Pause réaliste entre les mesures
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Erreur injection {device_id}: {e}")

        logger.info(f"📊 Injection terminée: {success_count}/{num_records} enregistrements envoyés")
        return success_count

    def run_continuous_test(self, duration_minutes=5):
        """Lance un test continu pendant X minutes"""
        logger.info(f"🔄 Démarrage test continu pendant {duration_minutes} minutes...")

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        total_records = 0

        while time.time() < end_time:
            # Injecter des données toutes les 30 secondes
            records_sent = self.inject_test_data(3)  # 3 bracelets
            total_records += records_sent

            remaining_time = (end_time - time.time()) / 60
            logger.info(f"⏱️ Temps restant: {remaining_time:.1f} minutes - Total envoyé: {total_records}")

            # Pause avant le prochain batch
            time.sleep(30)

        logger.info(f"🏁 Test terminé! Total: {total_records} enregistrements envoyés sur {duration_minutes} minutes")

def main():
    """Point d'entrée principal"""
    logger.info("🎯 TEST SIMPLE PIPELINE KIDJAMO - KINESIS → POSTGRESQL")
    logger.info("=" * 60)

    tester = SimplePipelineTest()

    try:
        # Option 1: Test rapide
        logger.info("📋 Options de test:")
        logger.info("1. Test rapide (10 enregistrements)")
        logger.info("2. Test continu (5 minutes)")

        choice = input("\nChoisissez (1 ou 2) [défaut: 1]: ").strip() or "1"

        if choice == "1":
            tester.inject_test_data(10)
        elif choice == "2":
            tester.run_continuous_test(5)
        else:
            logger.info("🔄 Lancement du test par défaut...")
            tester.inject_test_data(10)

        logger.info("\n✨ PROCHAINES ÉTAPES:")
        logger.info("1. Surveillez CloudWatch Logs pour les traitements")
        logger.info("2. Vérifiez votre base PostgreSQL pour les données")
        logger.info("3. Lancez vos jobs Glue pour traitement batch")

    except KeyboardInterrupt:
        logger.info("\n🔄 Test interrompu par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur test: {e}")

if __name__ == "__main__":
    main()
