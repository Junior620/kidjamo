#!/usr/bin/env python3
"""
Intercepteur Règles IoT pour MPU Christian
Surveille les données traitées par les règles IoT Core actives
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IoTRulesInterceptor:
    """Intercepteur pour données MPU via règles IoT Core"""

    def __init__(self):
        self.region = "eu-west-1"
        self.kinesis_stream = "kidjamo-iot-stream"
        
        # Clients AWS
        self.iot_client = boto3.client('iot', region_name=self.region)
        self.logs_client = boto3.client('logs', region_name=self.region)
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        
        # Règles IoT actives détectées
        self.active_rules = [
            "kidjamo_fall_risk_detection",
            "kidjamo_accelerometer_rule"
        ]
        
        # Topics surveillés (déduits des règles)
        self.monitored_topics = [
            "kidjamo/device/+/sensors",
            "kidjamo/device/MPU_Christian_8266MOD/sensors", 
            "sensor/MPU_Christian_8266MOD/data",
            "mpu/christian/data"
        ]
        
        self.processed_count = 0
        
        logger.info("🚀 Intercepteur Règles IoT initialisé")
        logger.info(f"📋 Règles surveillées: {self.active_rules}")

    async def start_monitoring(self):
        """Démarre l'interception des données IoT"""
        
        logger.info("🎯 INTERCEPTION DONNÉES RÈGLES IOT")
        logger.info("📡 Surveillance des logs CloudWatch des règles...")
        logger.info("")
        
        while True:
            try:
                # 1. Surveiller les logs des règles IoT
                await self._monitor_iot_rules_logs()
                
                # 2. Vérifier les destinations des règles
                await self._check_rule_destinations()
                
                # 3. Surveiller Kinesis directement (si règle redirige)
                await self._monitor_kinesis_destination()
                
                await asyncio.sleep(5)  # Check toutes les 5 secondes
                
            except KeyboardInterrupt:
                logger.info("🔄 Arrêt interception demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur interception: {e}")
                await asyncio.sleep(10)

    async def _monitor_iot_rules_logs(self):
        """Surveille les logs CloudWatch des règles IoT"""
        
        # Log groups potentiels pour les règles IoT
        rule_log_groups = [
            '/aws/iot/rules',
            '/aws/iot/rule/kidjamo_accelerometer_rule',
            '/aws/iot/rule/kidjamo_fall_risk_detection',
            'AWSIotLogsV2'
        ]
        
        end_time = datetime.now()
        start_time = end_time - timedelta(minutes=1)  # 1 minute
        
        for log_group in rule_log_groups:
            try:
                response = self.logs_client.filter_log_events(
                    logGroupName=log_group,
                    startTime=int(start_time.timestamp() * 1000),
                    endTime=int(end_time.timestamp() * 1000),
                    filterPattern='MPU_Christian_8266MOD'
                )
                
                events = response.get('events', [])
                for event in events:
                    message = event.get('message', '')
                    
                    # Analyser les messages pour données capteurs
                    if any(keyword in message.lower() for keyword in ['accel', 'gyro', 'mpu', 'sensor']):
                        logger.info(f"🔍 RÈGLE IoT - Message détecté:")
                        logger.info(f"   📋 Log Group: {log_group}")
                        logger.info(f"   📄 Message: {message[:200]}...")
                        
                        # Essayer de parser les données JSON
                        await self._parse_rule_message(message)
                        
            except self.logs_client.exceptions.ResourceNotFoundException:
                pass  # Log group n'existe pas
            except Exception as e:
                logger.debug(f"⚠️ Log group {log_group}: {e}")

    async def _parse_rule_message(self, message: str):
        """Parse un message de règle IoT pour extraire les données"""
        try:
            # Essayer de trouver du JSON dans le message
            json_start = message.find('{')
            json_end = message.rfind('}')
            
            if json_start != -1 and json_end != -1:
                json_str = message[json_start:json_end+1]
                data = json.loads(json_str)
                
                # Vérifier si on a des données de capteurs
                if self._has_sensor_data(data):
                    logger.info("✅ Données capteur détectées dans règle IoT!")
                    await self._process_iot_rule_data(data)
                    
        except json.JSONDecodeError:
            pass  # Pas de JSON valide
        except Exception as e:
            logger.debug(f"⚠️ Parse message: {e}")

    async def _check_rule_destinations(self):
        """Vérifie où les règles IoT redirigent les données"""
        
        for rule_name in self.active_rules:
            try:
                response = self.iot_client.get_topic_rule(ruleName=rule_name)
                rule = response.get('rule', {})
                
                sql = rule.get('sql', '')
                actions = rule.get('actions', [])
                
                logger.debug(f"📋 Règle {rule_name}:")
                logger.debug(f"   SQL: {sql[:100]}...")
                logger.debug(f"   Actions: {len(actions)}")
                
                # Analyser les actions pour trouver les destinations
                for action in actions:
                    if 'kinesis' in action:
                        kinesis_action = action['kinesis']
                        stream_name = kinesis_action.get('streamName', '')
                        logger.info(f"🌊 Règle {rule_name} → Kinesis: {stream_name}")
                        
                    elif 'cloudwatchLogs' in action:
                        logs_action = action['cloudwatchLogs'] 
                        log_group = logs_action.get('logGroupName', '')
                        logger.info(f"📋 Règle {rule_name} → CloudWatch: {log_group}")
                        
                    elif 's3' in action:
                        s3_action = action['s3']
                        bucket = s3_action.get('bucketName', '')
                        logger.info(f"📦 Règle {rule_name} → S3: {bucket}")
                        
            except Exception as e:
                logger.debug(f"⚠️ Règle {rule_name}: {e}")

    async def _monitor_kinesis_destination(self):
        """Surveille si des données arrivent dans Kinesis via les règles"""
        try:
            # Récupérer les derniers records du stream Kinesis
            response = self.kinesis_client.describe_stream(StreamName=self.kinesis_stream)
            shards = response['StreamDescription']['Shards']
            
            for shard in shards:
                shard_id = shard['ShardId']
                
                # Obtenir un itérateur pour les données récentes
                iterator_response = self.kinesis_client.get_shard_iterator(
                    StreamName=self.kinesis_stream,
                    ShardId=shard_id,
                    ShardIteratorType='TRIM_HORIZON'  # Depuis le début
                )
                
                iterator = iterator_response['ShardIterator']
                
                # Lire les records récents
                records_response = self.kinesis_client.get_records(
                    ShardIterator=iterator,
                    Limit=10  # Derniers 10 records
                )
                
                records = records_response.get('Records', [])
                
                for record in records:
                    data = json.loads(record['Data'])
                    device_id = data.get('device_id', '')
                    
                    # Vérifier si c'est du MPU Christian
                    if 'MPU_Christian' in device_id or 'christian' in device_id.lower():
                        logger.info(f"✅ DONNÉES MPU CHRISTIAN DÉTECTÉES dans Kinesis:")
                        logger.info(f"   📱 Device: {device_id}")
                        logger.info(f"   📊 Données: {json.dumps(data, indent=2)}")
                        logger.info("")
                        
                        self.processed_count += 1
                        
        except Exception as e:
            logger.debug(f"⚠️ Kinesis monitoring: {e}")

    def _has_sensor_data(self, data: dict) -> bool:
        """Vérifie si les données contiennent des informations de capteurs MPU"""

        # Vérifier la présence de données d'accéléromètre/gyroscope
        sensor_keys = [
            'accelerometer', 'accel', 'ax', 'ay', 'az',
            'gyroscope', 'gyro', 'gx', 'gy', 'gz',
            'temperature', 'temp',
            'sensors', 'sensor_data'
        ]

        # Recherche récursive dans les données
        def search_keys(obj, keys):
            if isinstance(obj, dict):
                for key in obj.keys():
                    if any(sensor_key in key.lower() for sensor_key in keys):
                        return True
                    if search_keys(obj[key], keys):
                        return True
            elif isinstance(obj, list):
                for item in obj:
                    if search_keys(item, keys):
                        return True
            return False

        return search_keys(data, sensor_keys)

    async def _process_iot_rule_data(self, data: dict):
        """Traite les données interceptées des règles IoT"""

        self.processed_count += 1

        logger.info(f"🔄 TRAITEMENT DONNÉES RÈGLE IoT (#{self.processed_count}):")
        logger.info(f"   📱 Device: {data.get('device_id', 'Unknown')}")
        logger.info(f"   📊 Type: {data.get('message_type', 'sensor_data')}")
        logger.info(f"   🕐 Timestamp: {data.get('timestamp', 'N/A')}")

        # Extraire les données capteurs si présentes
        if 'accelerometer' in data:
            accel = data['accelerometer']
            logger.info(f"   📈 Accéléromètre: X={accel.get('x')}, Y={accel.get('y')}, Z={accel.get('z')}")

        if 'gyroscope' in data:
            gyro = data['gyroscope']
            logger.info(f"   🌀 Gyroscope: X={gyro.get('x')}, Y={gyro.get('y')}, Z={gyro.get('z')}")

        if 'temperature' in data:
            logger.info(f"   🌡️ Température: {data['temperature']}°C")

        logger.info("")

async def main():
    """Point d'entrée principal"""

    logger.info("🚀 DÉMARRAGE INTERCEPTEUR RÈGLES IoT")
    logger.info("📡 Surveillance spécialisée pour MPU_Christian_8266MOD")
    logger.info("=" * 60)

    interceptor = IoTRulesInterceptor()
    
    try:
        await interceptor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt de l'intercepteur demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
    finally:
        logger.info("🔄 Arrêt de l'intercepteur")

if __name__ == "__main__":
    asyncio.run(main())
