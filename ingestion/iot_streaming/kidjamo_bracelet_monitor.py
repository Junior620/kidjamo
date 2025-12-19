#!/usr/bin/env python3
"""
Connecteur Simplifié pour Bracelets Kidjamo Réels
Surveille les données via AWS IoT Data API et CloudWatch Logs
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class KidjamoRealBraceletMonitor:
    """Monitor simplifié pour bracelets Kidjamo réels"""

    def __init__(self):
        self.region = "eu-west-1"
        self.kinesis_stream = "kidjamo-iot-stream"
        
        # Clients AWS
        self.iot_data_client = boto3.client('iot-data', region_name=self.region)
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.logs_client = boto3.client('logs', region_name=self.region)
        
        # Appareil actuellement connecté et actif
        self.active_device = "MPU_Christian_8266MOD"

        # Tous les bracelets pour surveillance étendue (si besoin)
        self.all_bracelets = [
            "MPU_Christian_8266MOD",  # Appareil actif principal
            "bracelet-P0001", "bracelet-P0002", "bracelet-P0003",
            "bracelet-P0004", "bracelet-P0005",
            "bracelet-patient-P0001", "bracelet-patient-P0002", 
            "bracelet-patient-P0003"
        ]
        
        self.processed_count = 0
        self.last_data_seen = {}
        
        logger.info("🚀 Monitor Bracelet Kidjamo Réel initialisé")
        logger.info(f"🎯 APPAREIL ACTIF: {self.active_device}")
        logger.info(f"👁️ Surveillance étendue: {len(self.all_bracelets)} appareils")

    async def start_monitoring(self):
        """Démarre la surveillance des bracelets"""
        
        logger.info("🎯 DEMARRAGE SURVEILLANCE BRACELETS REELS")
        logger.info("📡 Méthodes de surveillance:")
        logger.info("   1. Device Shadows IoT Core")
        logger.info("   2. CloudWatch Logs IoT Core")
        logger.info("   3. Simulation pour test")
        logger.info("")
        
        while True:
            try:
                # 1. Vérifier les Device Shadows
                await self._check_device_shadows()
                
                # 2. Vérifier CloudWatch Logs
                await self._check_cloudwatch_logs()
                
                # 3. Statistiques
                if self.processed_count > 0 and self.processed_count % 10 == 0:
                    logger.info(f"📊 Statistiques: {self.processed_count} messages traités")
                
                # Attendre avant le prochain cycle
                await asyncio.sleep(10)  # Check toutes les 10 secondes
                
            except KeyboardInterrupt:
                logger.info("🔄 Arrêt surveillance demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                await asyncio.sleep(30)  # Attendre plus longtemps en cas d'erreur

    async def _check_device_shadows(self):
        """Vérifie les Device Shadows pour nouvelles données"""
        
        for bracelet_name in self.all_bracelets:
            try:
                response = self.iot_data_client.get_thing_shadow(thingName=bracelet_name)
                shadow_payload = response['payload'].read().decode('utf-8')
                shadow_data = json.loads(shadow_payload)
                
                # Vérifier si on a de nouvelles données
                state = shadow_data.get('state', {})
                reported = state.get('reported', {})
                
                # Vérifier timestamp pour éviter les doublons
                shadow_timestamp = reported.get('timestamp', reported.get('last_update', 0))
                last_seen = self.last_data_seen.get(bracelet_name, 0)
                
                if shadow_timestamp > last_seen and self._has_sensor_data(reported):
                    await self._process_bracelet_data(bracelet_name, reported)
                    self.last_data_seen[bracelet_name] = shadow_timestamp
                
            except self.iot_data_client.exceptions.ResourceNotFoundException:
                # Pas de shadow, normal
                pass
            except Exception as e:
                logger.debug(f"⚠️ Shadow {bracelet_name}: {e}")

    async def _check_cloudwatch_logs(self):
        """Vérifie CloudWatch Logs pour données IoT Core"""
        try:
            # Chercher dans les logs IoT Core des dernières minutes
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)
            
            # Nom du log group IoT Core (ajustez selon votre config)
            log_groups = [
                '/aws/iot/rules',
                '/aws/iot/things', 
                '/aws/iot/kidjamo',
                'kidjamo-iot-logs'
            ]
            
            for log_group in log_groups:
                try:
                    response = self.logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=int(start_time.timestamp() * 1000),
                        endTime=int(end_time.timestamp() * 1000),
                        filterPattern='{ $.accel_x = * }'  # Filtrer sur données accéléromètre
                    )
                    
                    for event in response.get('events', []):
                        message = event.get('message', '')
                        if 'accel_x' in message:
                            try:
                                log_data = json.loads(message)
                                device_id = log_data.get('device_id', 'unknown')
                                if device_id in self.all_bracelets:
                                    await self._process_bracelet_data(device_id, log_data)
                            except json.JSONDecodeError:
                                pass
                                
                except self.logs_client.exceptions.ResourceNotFoundException:
                    # Log group n'existe pas
                    pass
                    
        except Exception as e:
            logger.debug(f"⚠️ CloudWatch Logs: {e}")

    def _has_sensor_data(self, data: Dict) -> bool:
        """Vérifie si les données contiennent des capteurs"""
        required_fields = ['accel_x', 'accel_y', 'accel_z']
        return all(field in data for field in required_fields)

    async def _process_bracelet_data(self, bracelet_name: str, data: Dict):
        """Traite les données d'un bracelet"""
        try:
            # Extraire les données capteurs
            accel_x = float(data.get('accel_x', 0))
            accel_y = float(data.get('accel_y', 0))
            accel_z = float(data.get('accel_z', 0))
            temp = float(data.get('temp', data.get('temperature', 20)))
            
            # Calculer magnitude et activité
            magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
            activity = self._classify_activity(magnitude)
            
            # Créer le record Kinesis
            kinesis_record = {
                'device_id': bracelet_name,
                'patient_id': f'patient_{bracelet_name.replace("bracelet-", "").replace("bracelet-patient-", "")}',
                'timestamp': datetime.now(timezone.utc).isoformat(),
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
                'data_source': 'real_bracelet_kidjamo',
                'event_type': 'bracelet_reading',
                'ingestion_timestamp': datetime.now(timezone.utc).isoformat(),
                'raw_data': data  # Données brutes pour debug
            }
            
            # Envoyer vers Kinesis
            response = self.kinesis_client.put_record(
                StreamName=self.kinesis_stream,
                Data=json.dumps(kinesis_record),
                PartitionKey=bracelet_name
            )
            
            self.processed_count += 1
            
            logger.info(f"✅ BRACELET RÉEL KIDJAMO - {bracelet_name}:")
            logger.info(f"   📊 Accéléromètre: X={accel_x:.3f}, Y={accel_y:.3f}, Z={accel_z:.3f}")
            logger.info(f"   🔢 Magnitude: {magnitude:.3f}")
            logger.info(f"   🌡️  Température: {temp:.1f}°C")
            logger.info(f"   🏃 Activité: {activity}")
            logger.info(f"   📈 Shard: {response['ShardId']} | Total: {self.processed_count}")
            logger.info("")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement {bracelet_name}: {e}")
            return False

    def _classify_activity(self, magnitude: float) -> str:
        """Classification d'activité selon magnitude"""
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

    async def simulate_test_data(self):
        """Simule des données pour test du pipeline"""
        import random
        
        logger.info("🧪 Mode simulation pour test du pipeline")
        
        while True:
            # Choisir un bracelet aléatoire
            bracelet = random.choice(self.all_bracelets)

            # Générer des données réalistes
            test_data = {
                'accel_x': random.uniform(-2.0, 2.0),
                'accel_y': random.uniform(8.0, 11.0),  # Gravité + mouvement
                'accel_z': random.uniform(-2.0, 2.0),
                'temp': random.uniform(25.0, 35.0),
                'timestamp': int(time.time()),
                'test_mode': True
            }
            
            await self._process_bracelet_data(bracelet, test_data)
            await asyncio.sleep(5)  # Une donnée toutes les 5 secondes

# Point d'entrée
async def main():
    """Démarre le monitoring des bracelets Kidjamo réels"""
    
    monitor = KidjamoRealBraceletMonitor()
    
    try:
        logger.info("🎯 SURVEILLANCE BRACELETS KIDJAMO RÉELS")
        logger.info("📋 Recherche de données temps réel dans AWS IoT Core...")
        logger.info("")
        
        print("Modes disponibles:")
        print("1 = Surveillance réelle (Device Shadows + CloudWatch)")
        print("2 = Simulation pour test du pipeline")
        print("3 = Les deux modes combinés")
        
        choice = input("Votre choix (1/2/3): ").strip()
        
        if choice == "2":
            await monitor.simulate_test_data()
        elif choice == "3":
            # Lancer les deux en parallèle
            await asyncio.gather(
                monitor.start_monitoring(),
                monitor.simulate_test_data()
            )
        else:
            await monitor.start_monitoring()
            
    except KeyboardInterrupt:
        logger.info("🔄 Arrêt du monitoring")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")

if __name__ == "__main__":
    asyncio.run(main())
