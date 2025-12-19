#!/usr/bin/env python3
"""
Connecteur Direct pour MPU_Christian_8266MOD
Surveillance spécialisée de l'appareil IoT actif de Christian
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MPUChristianConnector:
    """Connecteur spécialisé pour le MPU de Christian"""

    def __init__(self):
        self.region = "eu-west-1"
        self.kinesis_stream = "kidjamo-iot-stream"

        # Appareil cible spécifique
        self.device_name = "MPU_Christian_8266MOD"
        self.device_type = "ESP8266_MPU6050"  # Type de capteur

        # Clients AWS
        self.iot_data_client = boto3.client('iot-data', region_name=self.region)
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.iot_client = boto3.client('iot', region_name=self.region)

        # Topics potentiels pour ce device
        self.possible_topics = [
            f"mpu/{self.device_name}/data",
            f"sensor/{self.device_name}/readings",
            f"device/{self.device_name}/telemetry",
            f"{self.device_name}/data",
            f"christian/mpu/data",
            f"esp8266/mpu6050/data"
        ]

        self.processed_count = 0
        self.last_shadow_check = 0

        logger.info(f"🚀 Connecteur MPU Christian initialisé")
        logger.info(f"🎯 Device cible: {self.device_name}")
        logger.info(f"📡 Topics surveillés: {len(self.possible_topics)}")

    async def start_monitoring(self):
        """Démarre la surveillance du MPU de Christian"""

        logger.info("🎯 SURVEILLANCE MPU CHRISTIAN EN COURS")
        logger.info(f"📱 Appareil: {self.device_name}")
        logger.info("🔍 Recherche de données temps réel...")
        logger.info("")

        # Première vérification: État de l'appareil
        await self._check_device_status()

        # Boucle de surveillance
        while True:
            try:
                # 1. Vérifier Device Shadow
                shadow_data = await self._check_device_shadow()

                # 2. Si shadow vide, essayer les logs récents
                if not shadow_data:
                    await self._check_recent_logs()

                # 3. Vérifier les règles IoT Core actives
                await self._check_iot_rules()

                # Attendre avant le prochain cycle
                await asyncio.sleep(8)  # Check toutes les 8 secondes

            except KeyboardInterrupt:
                logger.info("🔄 Arrêt surveillance demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur surveillance: {e}")
                await asyncio.sleep(15)

    async def _check_device_status(self):
        """Vérifie le statut de l'appareil dans IoT Core"""
        try:
            response = self.iot_client.describe_thing(thingName=self.device_name)

            thing_name = response.get('thingName')
            thing_type = response.get('thingTypeName', 'N/A')
            creation_date = response.get('creationDate', 'N/A')

            logger.info(f"📱 APPAREIL DÉTECTÉ:")
            logger.info(f"   Nom: {thing_name}")
            logger.info(f"   Type: {thing_type}")
            logger.info(f"   Créé: {creation_date}")
            logger.info("")

        except Exception as e:
            logger.error(f"❌ Erreur statut appareil: {e}")

    async def _check_device_shadow(self):
        """Vérifie le Device Shadow pour nouvelles données"""
        try:
            response = self.iot_data_client.get_thing_shadow(thingName=self.device_name)
            shadow_payload = response['payload'].read().decode('utf-8')
            shadow_data = json.loads(shadow_payload)

            logger.info(f"👤 DEVICE SHADOW RÉCUPÉRÉ:")
            logger.info(f"   Taille: {len(shadow_payload)} bytes")

            # Analyser les données
            state = shadow_data.get('state', {})
            reported = state.get('reported', {})
            desired = state.get('desired', {})

            logger.info(f"   État rapporté: {len(reported)} champs")
            logger.info(f"   État désiré: {len(desired)} champs")

            # Vérifier si on a des données de capteurs
            if self._has_mpu_data(reported):
                logger.info("✅ Données MPU détectées dans le shadow!")
                await self._process_mpu_data(reported)
                return reported
            else:
                logger.info("⚠️ Pas de données MPU dans le shadow")
                logger.debug(f"Shadow content: {json.dumps(reported, indent=2)}")
                return None

        except self.iot_data_client.exceptions.ResourceNotFoundException:
            logger.info("⚠️ Pas de Device Shadow trouvé")
            return None
        except Exception as e:
            logger.error(f"❌ Erreur shadow: {e}")
            return None

    async def _check_recent_logs(self):
        """Vérifie les logs CloudWatch récents pour activité MPU"""
        try:
            # Chercher dans différents log groups
            log_groups = [
                '/aws/iot/rules',
                '/aws/iot/things',
                f'/aws/iot/thing/{self.device_name}',
                'kidjamo-iot-logs'
            ]

            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=2)  # 2 dernières minutes

            for log_group in log_groups:
                try:
                    response = self.logs_client.filter_log_events(
                        logGroupName=log_group,
                        startTime=int(start_time.timestamp() * 1000),
                        endTime=int(end_time.timestamp() * 1000),
                        filterPattern=f'[timestamp, requestId, clientId="{self.device_name}", ...]'
                    )

                    events = response.get('events', [])
                    if events:
                        logger.info(f"📋 {len(events)} événements récents dans {log_group}")

                        for event in events[:3]:  # Montrer les 3 plus récents
                            message = event.get('message', '')
                            if any(keyword in message.lower() for keyword in ['accel', 'gyro', 'mpu', 'sensor']):
                                logger.info(f"   🔍 Event: {message[:100]}...")

                except Exception:
                    pass  # Log group n'existe pas ou pas d'accès

        except Exception as e:
            logger.debug(f"⚠️ Logs: {e}")

    async def _check_iot_rules(self):
        """Vérifie les règles IoT Core actives pour ce device"""
        try:
            response = self.iot_client.list_topic_rules()
            rules = response.get('rules', [])

            active_rules = []
            for rule in rules:
                rule_name = rule.get('ruleName')

                # Récupérer les détails de la règle
                try:
                    rule_detail = self.iot_client.get_topic_rule(ruleName=rule_name)
                    sql = rule_detail.get('rule', {}).get('sql', '')

                    # Vérifier si la règle concerne notre device
                    if any(topic in sql.lower() for topic in [
                        self.device_name.lower(),
                        'mpu', 'sensor', 'christian'
                    ]):
                        active_rules.append({
                            'name': rule_name,
                            'sql': sql,
                            'status': rule.get('ruleDisabled', False)
                        })
                except Exception:
                    pass

            if active_rules:
                logger.info(f"📋 RÈGLES IoT ACTIVES ({len(active_rules)}):")
                for rule in active_rules[:2]:  # Montrer les 2 premières
                    status = "🔴 Désactivée" if rule['status'] else "🟢 Active"
                    logger.info(f"   • {rule['name']} - {status}")
                    logger.info(f"     SQL: {rule['sql'][:80]}...")
            else:
                logger.info("⚠️ Aucune règle IoT active détectée pour ce device")

        except Exception as e:
            logger.debug(f"⚠️ Règles IoT: {e}")

    def _has_mpu_data(self, data: Dict) -> bool:
        """Vérifie si les données contiennent des informations MPU6050"""
        # Champs typiques d'un MPU6050
        mpu_fields = ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z']
        temp_fields = ['temp', 'temperature']

        # Au minimum accéléromètre requis
        has_accel = all(field in data for field in ['accel_x', 'accel_y', 'accel_z'])
        has_temp = any(field in data for field in temp_fields)

        return has_accel or len([f for f in mpu_fields if f in data]) >= 3

    async def _process_mpu_data(self, data: Dict):
        """Traite les données MPU6050 de Christian"""
        try:
            # Extraire données MPU6050
            accel_x = float(data.get('accel_x', 0))
            accel_y = float(data.get('accel_y', 0))
            accel_z = float(data.get('accel_z', 0))

            gyro_x = float(data.get('gyro_x', 0))
            gyro_y = float(data.get('gyro_y', 0))
            gyro_z = float(data.get('gyro_z', 0))

            temp = float(data.get('temp', data.get('temperature', 25.0)))

            # Calculer magnitude et activité
            accel_magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
            gyro_magnitude = (gyro_x**2 + gyro_y**2 + gyro_z**2)**0.5

            activity = self._classify_activity(accel_magnitude)

            # Créer le record Kinesis
            kinesis_record = {
                'device_id': self.device_name,
                'patient_id': 'patient_christian_mpu',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'sensors': {
                    'accelerometer': {
                        'x': accel_x,
                        'y': accel_y,
                        'z': accel_z,
                        'magnitude': accel_magnitude
                    },
                    'gyroscope': {
                        'x': gyro_x,
                        'y': gyro_y,
                        'z': gyro_z,
                        'magnitude': gyro_magnitude
                    },
                    'temperature': temp
                },
                'activity_classification': activity,
                'data_source': 'mpu_christian_real',
                'event_type': 'mpu_reading',
                'device_type': self.device_type,
                'ingestion_timestamp': datetime.now(timezone.utc).isoformat()
            }

            # Envoyer vers Kinesis
            response = self.kinesis_client.put_record(
                StreamName=self.kinesis_stream,
                Data=json.dumps(kinesis_record),
                PartitionKey=self.device_name
            )

            self.processed_count += 1

            logger.info(f"✅ MPU CHRISTIAN - DONNÉES TRAITÉES:")
            logger.info(f"   📊 Accél: X={accel_x:.3f}, Y={accel_y:.3f}, Z={accel_z:.3f} (Mag: {accel_magnitude:.3f})")
            logger.info(f"   🌀 Gyro: X={gyro_x:.3f}, Y={gyro_y:.3f}, Z={gyro_z:.3f} (Mag: {gyro_magnitude:.3f})")
            logger.info(f"   🌡️  Temp: {temp:.1f}°C")
            logger.info(f"   🏃 Activité: {activity}")
            logger.info(f"   📈 Shard: {response['ShardId']} | Total: {self.processed_count}")
            logger.info("")

            return True

        except Exception as e:
            logger.error(f"❌ Erreur traitement MPU: {e}")
            return False

    def _classify_activity(self, magnitude: float) -> str:
        """Classification d'activité selon magnitude accéléromètre"""
        if magnitude > 15.0:
            return "🚨 CHUTE_DETECTEE"
        elif magnitude > 12.0:
            return "🏃 MOUVEMENT_INTENSE"
        elif magnitude > 10.5:
            return "🚶 ACTIVITE_MODEREE"
        elif magnitude > 9.0:
            return "🚶 MOUVEMENT_LEGER"
        else:
            return "😴 STATIONNAIRE"

# Point d'entrée
async def main():
    """Démarre la surveillance du MPU de Christian"""

    connector = MPUChristianConnector()

    try:
        logger.info("🎯 SURVEILLANCE MPU CHRISTIAN DÉMARRÉE")
        logger.info("📋 Recherche de données IoT temps réel...")
        logger.info("")

        await connector.start_monitoring()

    except KeyboardInterrupt:
        logger.info("🔄 Arrêt surveillance MPU Christian")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")

if __name__ == "__main__":
    asyncio.run(main())
