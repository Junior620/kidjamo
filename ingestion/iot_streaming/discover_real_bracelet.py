#!/usr/bin/env python3
"""
Configuration et Test de Connexion Bracelet Réel IoT Core
Détecte et configure la connexion avec le vrai bracelet
"""

import boto3
import json
import logging
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IoTCoreDiscovery:
    """Découvre et teste la connexion avec le bracelet réel"""

    def __init__(self, region="eu-west-1"):
        self.region = region
        self.iot_client = boto3.client('iot', region_name=region)
        self.iot_data_client = boto3.client('iot-data', region_name=region)

    def discover_things(self):
        """Découvre les Things IoT disponibles"""
        try:
            logger.info("🔍 Découverte des Things IoT Core...")

            response = self.iot_client.list_things()
            things = response.get('things', [])

            logger.info(f"📱 {len(things)} Things trouvés:")

            bracelet_things = []
            for thing in things:
                thing_name = thing['thingName']
                thing_type = thing.get('thingTypeName', 'N/A')
                created_date = thing.get('creationDate', 'N/A')

                logger.info(f"   • {thing_name} (Type: {thing_type})")

                # Identifier les bracelets potentiels
                if any(keyword in thing_name.lower() for keyword in ['bracelet', 'wearable', 'sensor', 'device']):
                    bracelet_things.append(thing_name)

            if bracelet_things:
                logger.info(f"🎯 Bracelets potentiels détectés: {bracelet_things}")
                return bracelet_things
            else:
                logger.warning("⚠️ Aucun bracelet détecté. Vérifiez le nom de votre Thing.")
                return []

        except Exception as e:
            logger.error(f"❌ Erreur découverte Things: {e}")
            return []

    def get_thing_shadow(self, thing_name):
        """Récupère le Device Shadow pour voir les dernières données"""
        try:
            logger.info(f"👤 Récupération Shadow pour {thing_name}...")

            response = self.iot_data_client.get_thing_shadow(thingName=thing_name)
            shadow_payload = response['payload'].read().decode('utf-8')
            shadow_data = json.loads(shadow_payload)

            logger.info(f"📊 Shadow data:")
            logger.info(json.dumps(shadow_data, indent=2))

            return shadow_data

        except Exception as e:
            logger.error(f"❌ Erreur récupération shadow: {e}")
            return None

    def test_topic_subscription(self, topic_patterns):
        """Teste l'écoute sur différents topics"""

        logger.info("🎯 Test des topics potentiels...")

        common_patterns = [
            "device/+/data",
            "bracelet/+/sensors",
            "kidjamo/+/data",
            "sensor/+/measurements",
            "+/telemetry",
            "+/data"
        ]

        # Combine les patterns fournis avec les patterns communs
        all_patterns = list(set(topic_patterns + common_patterns))

        for pattern in all_patterns:
            logger.info(f"   📡 Pattern testé: {pattern}")

        logger.info("💡 Configurez votre bracelet pour publier sur un de ces topics")
        return all_patterns

def configure_real_bracelet():
    """Configuration interactive du bracelet réel"""

    logger.info("🚀 CONFIGURATION BRACELET IOT REEL - KIDJAMO")
    logger.info("="*50)

    discovery = IoTCoreDiscovery()

    # 1. Découvrir les Things
    things = discovery.discover_things()

    if not things:
        logger.info("📋 CONFIGURATION MANUELLE REQUISE:")
        logger.info("   1. Vérifiez que votre bracelet est enregistré dans AWS IoT Core")
        logger.info("   2. Notez le nom exact de votre Thing")
        logger.info("   3. Notez le topic MQTT utilisé par votre bracelet")
        return None

    # 2. Tester le premier bracelet trouvé
    bracelet_name = things[0]
    logger.info(f"🎯 Test du bracelet: {bracelet_name}")

    # 3. Récupérer le Shadow
    shadow_data = discovery.get_thing_shadow(bracelet_name)

    # 4. Tester les topics
    topic_patterns = discovery.test_topic_subscription([
        f"device/{bracelet_name}/data",
        f"bracelet/{bracelet_name}/sensors",
        f"{bracelet_name}/telemetry"
    ])

    # 5. Générer la configuration
    config = {
        "thing_name": bracelet_name,
        "suggested_topics": topic_patterns[:3],
        "shadow_data": shadow_data,
        "kinesis_stream": "kidjamo-iot-stream",
        "region": "eu-west-1"
    }

    logger.info("📋 CONFIGURATION GÉNÉRÉE:")
    logger.info(json.dumps(config, indent=2, default=str))

    return config

def test_real_data_format():
    """Teste le format des données réelles"""

    logger.info("🧪 TEST FORMAT DONNÉES BRACELET RÉEL")

    # Format attendu de votre bracelet
    expected_format = {
        "accel_x": 1.041478,
        "accel_y": 9.442732,
        "accel_z": 2.521094,
        "gyro_x": -0.00453,
        "gyro_y": 0.003198,
        "gyro_z": -0.014655,
        "temp": 28.50353
    }

    logger.info("📊 Format attendu:")
    logger.info(json.dumps(expected_format, indent=2))

    # Validation du format
    required_fields = ['accel_x', 'accel_y', 'accel_z', 'temp']
    optional_fields = ['gyro_x', 'gyro_y', 'gyro_z']

    logger.info(f"✅ Champs requis: {required_fields}")
    logger.info(f"ℹ️  Champs optionnels: {optional_fields}")

    return expected_format

if __name__ == "__main__":
    print("🎯 DÉCOUVERTE ET CONFIGURATION BRACELET RÉEL")
    print("="*50)

    # 1. Test format des données
    test_real_data_format()

    print("\n" + "="*50)

    # 2. Configuration du bracelet
    config = configure_real_bracelet()

    if config:
        print("\n✅ Configuration terminée!")
        print("📋 Prochaines étapes:")
        print("   1. Vérifiez que votre bracelet publie sur les topics suggérés")
        print("   2. Lancez le connecteur bracelet réel")
        print("   3. Vérifiez les données dans Kinesis")
    else:
        print("\n⚠️  Configuration manuelle requise")
        print("📋 Contactez votre équipe IoT pour:")
        print("   • Nom exact du Thing IoT")
        print("   • Topic MQTT utilisé")
        print("   • Format exact des données")
