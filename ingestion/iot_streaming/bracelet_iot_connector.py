#!/usr/bin/env python3
"""
Connecteur MQTT → Kinesis pour Bracelet IoT Kidjamo
Gère la connexion directe avec vos bracelets IoT via MQTT et AWS IoT Core
"""

import json
import boto3
import logging
import asyncio
import ssl
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import uuid
import time
import os

# AWS IoT Device SDK
try:
    from awsiot import mqtt_connection_builder
    from awscrt import io, mqtt, auth, http
    from awsiot.mqtt_connection_builder import MqttConnectionBuilder
except ImportError:
    print("⚠️ AWS IoT Device SDK non installé. Utilisez: pip install awsiotsdk")

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "bracelet_iot", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

@dataclass
class BraceletIoTMessage:
    """Structure des données du bracelet IoT"""
    device_id: str
    patient_id: str
    timestamp: datetime

    # Données vitales
    heart_rate: Optional[int] = None
    spo2: Optional[float] = None
    temperature: Optional[float] = None

    # Données d'accéléromètre
    accel_x: Optional[float] = None
    accel_y: Optional[float] = None
    accel_z: Optional[float] = None

    # Température du capteur
    temp: Optional[float] = None

    # Métadonnées
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None
    firmware_version: Optional[str] = None

    def to_kinesis_record(self) -> Dict[str, Any]:
        """Convertit en format Kinesis"""
        return {
            'device_id': self.device_id,
            'patient_id': self.patient_id,
            'timestamp': self.timestamp.isoformat(),
            'sensors': {
                'accelerometer': {
                    'x': self.accel_x,
                    'y': self.accel_y,
                    'z': self.accel_z
                },
                'temperature': self.temp
            },
            'vitals': {
                'heart_rate': self.heart_rate,
                'spo2': self.spo2,
                'temperature': self.temperature
            },
            'metadata': {
                'battery_level': self.battery_level,
                'signal_strength': self.signal_strength,
                'firmware_version': self.firmware_version
            },
            'event_type': 'bracelet_reading',
            'ingestion_timestamp': datetime.now(timezone.utc).isoformat()
        }

class KinesisPublisher:
    """Publie les données vers Kinesis Data Streams"""

    def __init__(self, stream_name: str, region: str = "eu-west-1"):
        self.stream_name = stream_name
        self.kinesis_client = boto3.client('kinesis', region_name=region)
        self.logger = logging.getLogger(f"{__name__}.KinesisPublisher")

    async def publish_message(self, message: BraceletIoTMessage) -> bool:
        """Publie un message vers Kinesis"""
        try:
            record = message.to_kinesis_record()

            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(record),
                PartitionKey=message.device_id  # Partition par device_id
            )

            self.logger.info(f"✅ Message publié vers Kinesis: {message.device_id} → {response['ShardId']}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur publication Kinesis: {e}")
            return False

class BraceletIoTMQTTConnector:
    """Connecteur MQTT pour recevoir les données des bracelets IoT"""

    def __init__(self,
                 endpoint: str,
                 cert_path: str,
                 key_path: str,
                 ca_path: str,
                 client_id: str = None,
                 kinesis_stream: str = "kidjamo-iot-stream"):

        self.endpoint = endpoint
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path
        self.client_id = client_id or f"kidjamo-connector-{uuid.uuid4()}"

        self.kinesis_publisher = KinesisPublisher(kinesis_stream)
        self.mqtt_connection = None
        self.is_connected = False

        self.logger = logging.getLogger(f"{__name__}.BraceletIoTMQTTConnector")

        # Topics MQTT pour vos bracelets
        self.topics = {
            'vitals': 'kidjamo/bracelet/+/vitals',  # kidjamo/bracelet/DEVICE_ID/vitals
            'accelerometer': 'kidjamo/bracelet/+/accelerometer',
            'status': 'kidjamo/bracelet/+/status',
            'alerts': 'kidjamo/bracelet/+/alerts'
        }

    def _create_mqtt_connection(self):
        """Crée la connexion MQTT avec AWS IoT Core"""
        try:
            # Configuration du client MQTT
            event_loop_group = io.EventLoopGroup(1)
            host_resolver = io.DefaultHostResolver(event_loop_group)
            client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.endpoint,
                cert_filepath=self.cert_path,
                pri_key_filepath=self.key_path,
                client_bootstrap=client_bootstrap,
                ca_filepath=self.ca_path,
                client_id=self.client_id,
                clean_session=False,
                keep_alive_secs=30
            )

            self.logger.info(f"✅ Connexion MQTT créée pour {self.client_id}")

        except Exception as e:
            self.logger.error(f"❌ Erreur création connexion MQTT: {e}")
            raise

    async def connect(self) -> bool:
        """Établit la connexion MQTT"""
        try:
            if not self.mqtt_connection:
                self._create_mqtt_connection()

            # Connexion asynchrone
            connect_future = self.mqtt_connection.connect()
            connect_result = connect_future.result()

            self.is_connected = True
            self.logger.info(f"✅ Connecté à AWS IoT Core: {self.endpoint}")

            # S'abonner aux topics
            await self._subscribe_to_topics()

            return True

        except Exception as e:
            self.logger.error(f"❌ Erreur connexion MQTT: {e}")
            return False

    async def _subscribe_to_topics(self):
        """S'abonne aux topics MQTT des bracelets"""
        for topic_name, topic_pattern in self.topics.items():
            try:
                subscribe_future, packet_id = self.mqtt_connection.subscribe(
                    topic=topic_pattern,
                    qos=mqtt.QoS.AT_LEAST_ONCE,
                    callback=self._create_message_handler(topic_name)
                )

                subscribe_result = subscribe_future.result()
                self.logger.info(f"✅ Abonné au topic {topic_name}: {topic_pattern}")

            except Exception as e:
                self.logger.error(f"❌ Erreur abonnement topic {topic_name}: {e}")

    def _create_message_handler(self, topic_type: str) -> Callable:
        """Crée un handler pour chaque type de message"""

        def on_message_received(topic: str, payload: bytes, **kwargs):
            try:
                # Décoder le payload JSON
                message_data = json.loads(payload.decode('utf-8'))

                # Extraire device_id du topic (kidjamo/bracelet/DEVICE_ID/vitals)
                topic_parts = topic.split('/')
                device_id = topic_parts[2] if len(topic_parts) >= 3 else "unknown"

                # Traiter selon le type de message
                asyncio.create_task(
                    self._process_bracelet_message(topic_type, device_id, message_data)
                )

            except Exception as e:
                self.logger.error(f"❌ Erreur traitement message {topic}: {e}")

        return on_message_received

    async def _process_bracelet_message(self, topic_type: str, device_id: str, data: Dict[str, Any]):
        """Traite un message reçu d'un bracelet"""
        try:
            # Créer le message structuré
            message = BraceletIoTMessage(
                device_id=device_id,
                patient_id=data.get('patient_id', device_id),
                timestamp=datetime.now(timezone.utc)
            )

            # Traitement direct des données du format bracelet IoT
            # Format reçu: {"accel_x": 1.041478, "accel_y": 9.442732, "accel_z": 2.521094, "gyro_x": -0.00453, "gyro_y": 0.003198, "gyro_z": -0.014655, "temp": 28.50353}

            # Données d'accéléromètre (celles qu'on veut traiter)
            message.accel_x = data.get('accel_x')
            message.accel_y = data.get('accel_y')
            message.accel_z = data.get('accel_z')

            # Température du capteur
            message.temp = data.get('temp')

            # Métadonnées si disponibles
            message.battery_level = data.get('battery')
            message.signal_strength = data.get('signal')
            message.firmware_version = data.get('firmware')

            # Publier vers Kinesis
            success = await self.kinesis_publisher.publish_message(message)

            if success:
                self.logger.info(f"✅ Message bracelet traité: {device_id} - accel({message.accel_x:.3f},{message.accel_y:.3f},{message.accel_z:.3f}) temp:{message.temp}°C")
            else:
                self.logger.error(f"❌ Échec publication: {device_id}")

        except Exception as e:
            self.logger.error(f"❌ Erreur traitement message bracelet: {e}")

    async def disconnect(self):
        """Ferme la connexion MQTT proprement"""
        if self.mqtt_connection and self.is_connected:
            try:
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result()
                self.is_connected = False
                self.logger.info("✅ Connexion MQTT fermée")
            except Exception as e:
                self.logger.error(f"❌ Erreur fermeture MQTT: {e}")

class BraceletIoTStreamProcessor:
    """Processeur principal pour le streaming des bracelets IoT"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.connector = None
        self.is_running = False

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Charge la configuration"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)

        # Configuration par défaut depuis variables d'environnement
        return {
            'aws_iot': {
                'endpoint': os.environ.get('AWS_IOT_ENDPOINT'),
                'cert_path': os.environ.get('AWS_IOT_CERT_PATH'),
                'key_path': os.environ.get('AWS_IOT_KEY_PATH'),
                'ca_path': os.environ.get('AWS_IOT_CA_PATH'),
                'client_id': os.environ.get('AWS_IOT_CLIENT_ID', f'kidjamo-{uuid.uuid4()}')
            },
            'kinesis': {
                'stream_name': os.environ.get('KINESIS_STREAM_NAME', 'kidjamo-iot-stream'),
                'region': os.environ.get('AWS_REGION', 'eu-west-1')
            }
        }

    async def start(self):
        """Démarre le processeur de streaming"""
        try:
            logger.info("🚀 Démarrage du processeur bracelet IoT")

            # Créer le connecteur MQTT
            self.connector = BraceletIoTMQTTConnector(
                endpoint=self.config['aws_iot']['endpoint'],
                cert_path=self.config['aws_iot']['cert_path'],
                key_path=self.config['aws_iot']['key_path'],
                ca_path=self.config['aws_iot']['ca_path'],
                client_id=self.config['aws_iot']['client_id'],
                kinesis_stream=self.config['kinesis']['stream_name']
            )

            # Établir la connexion
            if await self.connector.connect():
                self.is_running = True
                logger.info("✅ Processeur bracelet IoT démarré et en écoute")

                # Boucle principale (garde la connexion active)
                while self.is_running:
                    await asyncio.sleep(1)

            else:
                raise Exception("Impossible de se connecter au broker MQTT")

        except Exception as e:
            logger.error(f"❌ Erreur démarrage processeur: {e}")
            raise

    async def stop(self):
        """Arrête le processeur proprement"""
        logger.info("🛑 Arrêt du processeur bracelet IoT")
        self.is_running = False

        if self.connector:
            await self.connector.disconnect()

        logger.info("✅ Processeur bracelet IoT arrêté")

# Point d'entrée pour tests et débogage
async def main():
    """Test du connecteur bracelet IoT"""
    processor = BraceletIoTStreamProcessor()

    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("🔄 Arrêt demandé par l'utilisateur")
    finally:
        await processor.stop()

if __name__ == "__main__":
    asyncio.run(main())
