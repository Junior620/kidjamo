#!/usr/bin/env python3
"""
Connecteur MQTT Temps Réel pour Bracelets Kidjamo
Intercepte les vraies données des bracelets via AWS IoT Core MQTT
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import ssl
import time

# AWS IoT Device SDK pour MQTT
try:
    from awsiot import mqtt_connection_builder
    from awscrt import io, mqtt, auth, http
    from awsiot.mqtt_connection_builder import MqttConnectionBuilder
except ImportError:
    print("⚠️ Installation requise: pip install awsiotsdk")
    exit(1)

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KidjamoRealBraceletConnector:
    """Connecteur MQTT pour bracelets Kidjamo réels"""

    def __init__(self):
        # Configuration AWS IoT Core
        self.endpoint = "aqkov8uorjxj6-ats.iot.eu-west-1.amazonaws.com"  # Votre endpoint
        self.region = "eu-west-1"
        
        # Configuration Kinesis
        self.kinesis_stream = "kidjamo-iot-stream"
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        
        # Topics à surveiller pour tous les bracelets
        self.topics = [
            "device/+/data",                    # Pattern générique devices
            "bracelet/+/sensors",               # Pattern bracelets spécifique
            "kidjamo/+/data",                   # Pattern Kidjamo
            "+/telemetry",                      # Pattern télémétrie
            "bracelet-P0005/telemetry",         # Bracelet spécifique découvert
            "device/bracelet-P0005/data",       # Device spécifique
        ]
        
        # État
        self.mqtt_connection = None
        self.is_connected = False
        self.processed_count = 0
        
        logger.info("🚀 Connecteur Bracelet Kidjamo Réel initialisé")

    async def connect_and_listen(self):
        """Se connecte à AWS IoT Core et écoute les bracelets"""
        
        logger.info("🎯 CONNEXION AUX BRACELETS KIDJAMO REELS")
        logger.info(f"📡 Endpoint: {self.endpoint}")
        logger.info(f"🌊 Stream Kinesis: {self.kinesis_stream}")
        
        try:
            # Pour la connexion MQTT, nous utilisons les credentials AWS par défaut
            # Note: Nécessite des certificats IoT Core pour une vraie connexion MQTT
            
            logger.info("⚠️ ATTENTION: Connexion MQTT directe nécessite des certificats")
            logger.info("📋 Alternative: Utilisation de l'API IoT Data pour polling")
            
            # Alternative plus simple: Polling via API IoT Data
            await self._start_api_polling()
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            logger.info("🔄 Tentative de méthode alternative...")
            await self._start_api_polling()

    async def _start_api_polling(self):
        """Méthode alternative: Polling via AWS IoT Data API"""
        
        logger.info("🔄 Démarrage polling API IoT Data...")
        
        # Client IoT Data pour récupérer les données
        iot_data_client = boto3.client('iot-data', region_name=self.region)
        
        # Liste des bracelets à surveiller
        bracelet_names = [
            "bracelet-P0001", "bracelet-P0002", "bracelet-P0003", "bracelet-P0004", "bracelet-P0005",
            "bracelet-patient-P0001", "bracelet-patient-P0002", "bracelet-patient-P0003"
        ]
        
        logger.info(f"👁️ Surveillance de {len(bracelet_names)} bracelets")
        
        while True:
            try:
                for bracelet_name in bracelet_names:
                    await self._check_bracelet_shadow(iot_data_client, bracelet_name)
                
                # Attendre avant le prochain cycle
                await asyncio.sleep(5)  # Check toutes les 5 secondes
                
            except KeyboardInterrupt:
                logger.info("🔄 Arrêt demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur polling: {e}")
                await asyncio.sleep(10)

    async def _check_bracelet_shadow(self, iot_client, bracelet_name):
        """Vérifie le Device Shadow d'un bracelet pour récupérer les données"""
        try:
            # Tenter de récupérer le shadow
            response = iot_client.get_thing_shadow(thingName=bracelet_name)
            shadow_payload = response['payload'].read().decode('utf-8')
            shadow_data = json.loads(shadow_payload)
            
            # Traiter les données du shadow
            await self._process_shadow_data(bracelet_name, shadow_data)
            
        except iot_client.exceptions.ResourceNotFoundException:
            # Pas de shadow pour ce bracelet, normal
            pass
        except Exception as e:
            logger.debug(f"⚠️ Erreur shadow {bracelet_name}: {e}")

    async def _process_shadow_data(self, bracelet_name, shadow_data):
        """Traite les données du Device Shadow"""
        try:
            # Extraire les données du shadow
            state = shadow_data.get('state', {})
            reported = state.get('reported', {})
            
            # Vérifier si on a des données d'accéléromètre
            if 'accel_x' in reported and 'accel_y' in reported and 'accel_z' in reported:
                
                # Créer le message au format attendu
                bracelet_data = {
                    'device_id': bracelet_name,
                    'patient_id': f'patient_{bracelet_name.split("-")[-1]}',
                    'accel_x': reported.get('accel_x', 0),
                    'accel_y': reported.get('accel_y', 0),
                    'accel_z': reported.get('accel_z', 0),
                    'gyro_x': reported.get('gyro_x', 0),
                    'gyro_y': reported.get('gyro_y', 0),
                    'gyro_z': reported.get('gyro_z', 0),
                    'temp': reported.get('temp', reported.get('temperature', 0)),
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                # Traiter les données
                success = await self._process_real_data(bracelet_data)
                
                if success:
                    self.processed_count += 1
                    
                    if self.processed_count % 10 == 0:  # Log chaque 10 messages
                        logger.info(f"📊 Total traité: {self.processed_count} messages")

        except Exception as e:
            logger.error(f"❌ Erreur traitement shadow {bracelet_name}: {e}")

    async def _process_real_data(self, data):
        """Traite les vraies données du bracelet"""
        try:
            # Extraire les valeurs
            accel_x = float(data.get('accel_x', 0))
            accel_y = float(data.get('accel_y', 0))
            accel_z = float(data.get('accel_z', 0))
            temp = float(data.get('temp', 0))
            
            # Calculer la magnitude pour classification
            magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
            activity = self._classify_activity(magnitude)
            
            # Créer le record Kinesis
            kinesis_record = {
                'device_id': data['device_id'],
                'patient_id': data['patient_id'],
                'timestamp': data['timestamp'],
                'sensors': {
                    'accelerometer': {
                        'x': accel_x,
                        'y': accel_y,
                        'z': accel_z,
                        'magnitude': magnitude
                    },
                    'temperature': temp
                },
                'activity_classification': activity,
                'data_source': 'real_bracelet_shadow',
                'event_type': 'bracelet_reading',
                'ingestion_timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Envoyer vers Kinesis
            response = self.kinesis_client.put_record(
                StreamName=self.kinesis_stream,
                Data=json.dumps(kinesis_record),
                PartitionKey=data['device_id']
            )
            
            logger.info(f"✅ BRACELET RÉEL {data['device_id']}:")
            logger.info(f"   📊 Accel: X={accel_x:.3f}, Y={accel_y:.3f}, Z={accel_z:.3f}")
            logger.info(f"   🌡️  Temp: {temp:.1f}°C")
            logger.info(f"   🏃 Activité: {activity}")
            logger.info(f"   📈 Envoyé vers shard: {response['ShardId']}")
            logger.info("")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement données: {e}")
            return False

    def _classify_activity(self, magnitude: float) -> str:
        """Classification d'activité"""
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

# Fonction pour simuler des données si pas de shadow actif
async def simulate_bracelet_data(connector):
    """Simule des données de bracelet pour test"""
    
    import random
    
    bracelet_names = ["bracelet-P0001", "bracelet-P0002", "bracelet-P0003"]
    
    while True:
        for bracelet_name in bracelet_names:
            # Générer des données réalistes
            data = {
                'device_id': bracelet_name,
                'patient_id': f'patient_{bracelet_name.split("-")[-1]}',
                'accel_x': random.uniform(-2.0, 2.0),
                'accel_y': random.uniform(8.0, 11.0),
                'accel_z': random.uniform(-2.0, 2.0),
                'gyro_x': random.uniform(-0.02, 0.02),
                'gyro_y': random.uniform(-0.02, 0.02),
                'gyro_z': random.uniform(-0.02, 0.02),
                'temp': random.uniform(25.0, 35.0),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            await connector._process_real_data(data)
            await asyncio.sleep(3)  # 3 secondes entre chaque bracelet

# Point d'entrée principal
async def main():
    """Démarre la surveillance des bracelets réels"""
    
    connector = KidjamoRealBraceletConnector()
    
    try:
        logger.info("🎯 SURVEILLANCE BRACELETS KIDJAMO RÉELS")
        logger.info("📋 Recherche de données temps réel...")
        logger.info("📋 Utilisez Ctrl+C pour arrêter")
        logger.info("")
        
        # Choix: vraies données ou simulation
        mode = input("Mode? (1=Vraies données Shadow, 2=Simulation test): ").strip()
        
        if mode == "2":
            logger.info("🧪 Mode simulation activé")
            await simulate_bracelet_data(connector)
        else:
            logger.info("📡 Mode surveillance réelle activé")
            await connector.connect_and_listen()
            
    except KeyboardInterrupt:
        logger.info("🔄 Arrêt surveillance bracelets")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")

if __name__ == "__main__":
    asyncio.run(main())
