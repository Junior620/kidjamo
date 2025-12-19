#!/usr/bin/env python3
"""
Processeur Complet MPU Christian
- Intercepte les données Kinesis en temps réel
- Déclenche les alertes critiques 
- Achemine vers S3 pour stockage raw
"""

import json
import boto3
import asyncio
import logging
from datetime import datetime, timezone
import time
import os
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MPUDataProcessor:
    """Processeur complet pour données MPU Christian"""

    def __init__(self):
        self.region = "eu-west-1"
        
        # Configuration Kinesis
        self.streams = [
            "kidjamo-alerts-stream",
            "kidjamo-vital-signs-stream", 
            "kidjamo-iot-stream"
        ]
        
        # Configuration S3
        self.s3_bucket = "kidjamo-dev-datalake-e75d5213"
        self.s3_raw_prefix = "raw/iot-measurements"

        # Configuration alertes
        self.alert_thresholds = {
            "acceleration_max": 20.0,
            "gyro_max": 500.0,
            "temperature_min": 10.0,
            "temperature_max": 50.0,
        }

        # NOUVEAU: Configuration pour flux haute fréquence
        self.batch_config = {
            "batch_size": 60,  # 60 échantillons = 1 minute de données
            "batch_timeout": 300,  # 5 minutes maximum avant forçage
            "pipeline_cooldown": 300,  # 5 minutes entre déclenchements pipeline (au lieu de 30 min)
            "alert_buffer_size": 10,  # Buffer pour éviter spam d'alertes
        }

        # Buffers pour batching intelligent
        self.data_buffer = []
        self.last_pipeline_trigger = 0
        self.last_batch_save = time.time()
        self.alert_buffer = []

        # Clients AWS
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.sns_client = boto3.client('sns', region_name=self.region)
        
        # Métriques
        self.processed_count = 0
        self.alerts_triggered = 0
        self.s3_uploads = 0
        self.batches_saved = 0
        self.shard_iterators = {}
        
        logger.info("🚀 Processeur MPU Christian initialisé (MODE HAUTE FRÉQUENCE)")
        logger.info(f"🌊 Streams surveillés: {self.streams}")
        logger.info(f"📦 Bucket S3: {self.s3_bucket}")
        logger.info(f"⚡ Batch size: {self.batch_config['batch_size']} échantillons")
        logger.info(f"⏱️ Pipeline cooldown: {self.batch_config['pipeline_cooldown']}s")

    async def start_processing(self):
        """Démarre le traitement complet des données"""
        
        logger.info("🎯 DÉMARRAGE PROCESSEUR COMPLET MPU CHRISTIAN")
        logger.info("📡 Interception → Alertes → S3")
        logger.info("=" * 70)
        
        # Initialiser les streams Kinesis
        await self._initialize_kinesis_streams()
        
        # Vérifier la connectivité S3
        await self._verify_s3_access()
        
        while True:
            try:
                # Traitement principal
                await self._process_kinesis_data()
                
                # Afficher les métriques toutes les 30 secondes
                if self.processed_count % 15 == 0 and self.processed_count > 0:
                    await self._display_metrics()
                
                await asyncio.sleep(2)  # Vérification toutes les 2 secondes
                
            except KeyboardInterrupt:
                logger.info("🔄 Arrêt processeur demandé")
                break
            except Exception as e:
                logger.error(f"❌ Erreur processeur: {e}")
                await asyncio.sleep(5)

    async def _initialize_kinesis_streams(self):
        """Initialise les streams Kinesis"""
        
        for stream_name in self.streams:
            try:
                response = self.kinesis_client.describe_stream(StreamName=stream_name)
                shards = response['StreamDescription']['Shards']
                
                self.shard_iterators[stream_name] = {}
                
                for shard in shards:
                    shard_id = shard['ShardId']
                    
                    # Itérateur pour nouvelles données uniquement
                    iterator_response = self.kinesis_client.get_shard_iterator(
                        StreamName=stream_name,
                        ShardId=shard_id,
                        ShardIteratorType='LATEST'
                    )
                    
                    self.shard_iterators[stream_name][shard_id] = iterator_response['ShardIterator']
                    
                logger.info(f"✅ {stream_name}: {len(shards)} shard(s) initialisés")
                
            except Exception as e:
                logger.warning(f"⚠️ Stream {stream_name}: {e}")

    async def _verify_s3_access(self):
        """Vérifie l'accès au bucket S3"""
        
        try:
            # Tester l'accès au bucket
            self.s3_client.head_bucket(Bucket=self.s3_bucket)
            logger.info(f"✅ Accès S3 vérifié: {self.s3_bucket}")
            
            # Créer le préfixe raw si nécessaire
            test_key = f"{self.s3_raw_prefix}/_test_access.json"
            test_data = {
                "test": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "processor": "MPUDataProcessor"
            }
            
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=test_key,
                Body=json.dumps(test_data),
                ContentType='application/json'
            )
            
            logger.info(f"✅ Écriture S3 testée: {self.s3_raw_prefix}/")
            
        except Exception as e:
            logger.error(f"❌ Erreur accès S3: {e}")
            raise

    async def _process_kinesis_data(self):
        """Traite les données Kinesis en temps réel avec surveillance améliorée"""

        for stream_name in self.streams:
            if stream_name not in self.shard_iterators:
                continue
                
            for shard_id, iterator in self.shard_iterators[stream_name].items():
                try:
                    # Lire plus de records pour capturer plus de données
                    response = self.kinesis_client.get_records(
                        ShardIterator=iterator,
                        Limit=100  # Augmenté de 50 à 100 pour capturer plus de données
                    )
                    
                    records = response.get('Records', [])
                    next_iterator = response.get('NextShardIterator')
                    
                    # Mettre à jour l'itérateur
                    if next_iterator:
                        self.shard_iterators[stream_name][shard_id] = next_iterator
                    
                    # Traiter chaque record
                    for record in records:
                        await self._process_single_record(stream_name, record)

                    # Log de surveillance pour debugging
                    if records:
                        logger.debug(f"📊 {stream_name}/{shard_id}: {len(records)} records traités")

                except Exception as e:
                    logger.debug(f"⚠️ Erreur lecture {stream_name}/{shard_id}: {e}")

    async def _process_single_record(self, stream_name: str, record: Dict):
        """Traite un record Kinesis individuel avec streaming direct vers S3"""

        try:
            # Décoder les données
            data_bytes = record['Data']
            if isinstance(data_bytes, bytes):
                data_str = data_bytes.decode('utf-8')
            else:
                data_str = str(data_bytes)
            
            data = json.loads(data_str)
            self.processed_count += 1
            
            # Identifier si c'est du MPU Christian
            is_mpu_christian = self._is_mpu_christian_data(data)
            
            if is_mpu_christian:
                # 1. Analyser et déclencher alertes (immédiat pour sécurité)
                alerts = await self._analyze_and_alert(data)
                
                # 2. NOUVEAU: Streaming direct vers S3 (pas de batching)
                s3_key = await self._stream_direct_to_s3(data, stream_name)

                # Log pour chaque échantillon en streaming
                logger.info(f"🎯 MPU Christian #{self.processed_count}: streaming direct → {s3_key}")
                if alerts:
                    logger.info(f"   🚨 {len(alerts)} alertes déclenchées")

            else:
                # Afficher les données non-MPU pour debugging
                logger.debug(f"📋 Données autres (#{self.processed_count}): {stream_name}")
                
        except json.JSONDecodeError:
            logger.debug(f"⚠️ Record non-JSON dans {stream_name}")
        except Exception as e:
            logger.error(f"❌ Erreur traitement record: {e}")

    async def _stream_direct_to_s3(self, data: Dict, stream_name: str) -> str:
        """Streaming direct vers S3 - chaque donnée bracelet devient immédiatement un fichier S3"""

        try:
            # Générer la clé S3 unique pour chaque échantillon
            now = datetime.now(timezone.utc)

            # Clé S3 avec timestamp précis (microseconde) pour éviter collisions
            s3_key = f"{self.s3_raw_prefix}/year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}/mpu_christian_stream_{now.strftime('%Y%m%d_%H%M%S_%f')}.json"

            # Enrichir les données avec métadonnées pour streaming
            enriched_data = {
                'original_data': data,
                'metadata': {
                    'ingestion_timestamp': now.isoformat(),
                    'stream_name': stream_name,
                    'processor': 'MPUDataProcessor_DirectStreaming',
                    'device_type': 'MPU_Christian_8266MOD',
                    'streaming_mode': 'direct_1hz',
                    'sample_id': f"sample_{now.strftime('%Y%m%d_%H%M%S_%f')}"
                }
            }

            # Upload immédiat vers S3
            self.s3_client.put_object(
                Bucket=self.s3_bucket,
                Key=s3_key,
                Body=json.dumps(enriched_data, indent=2),
                ContentType='application/json',
                Metadata={
                    'device_id': str(data.get('device_id', 'MPU_Christian_8266MOD')),
                    'ingestion_time': now.isoformat(),
                    'stream': stream_name,
                    'streaming_mode': 'direct'
                }
            )

            self.s3_uploads += 1

            # Déclencher la pipeline intelligemment (avec cooldown pour éviter surcharge)
            await self._trigger_smart_pipeline_streaming(s3_key, data)

            return s3_key

        except Exception as e:
            logger.error(f"❌ Erreur streaming S3: {e}")
            return f"ERROR: {e}"

    async def _trigger_smart_pipeline_streaming(self, s3_key: str, data: Dict):
        """Déclenche la pipeline intelligemment pour streaming haute fréquence"""

        current_time = time.time()

        # Cooldown plus intelligent pour streaming (5 minutes)
        if (current_time - self.last_pipeline_trigger) < self.batch_config['pipeline_cooldown']:
            logger.debug(f"🔄 Pipeline en cooldown, fichier sauvé sans déclenchement immédiat")
            return

        try:
            # Initialiser le client Lambda si pas déjà fait
            if not hasattr(self, 'lambda_client'):
                self.lambda_client = boto3.client('lambda', region_name=self.region)

            # Préparer l'événement pour la Lambda d'orchestration
            event_payload = {
                "trigger_type": "s3_streaming_ready",
                "s3_bucket": self.s3_bucket,
                "s3_key": s3_key,
                "device_id": data.get('device_id', 'MPU_Christian_8266MOD'),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "streaming_mode": True,
                "immediate_processing": False  # Pas immédiat pour éviter surcharge
            }

            # Déclencher la Lambda d'orchestration
            self.lambda_client.invoke(
                FunctionName='kidjamo-auto-pipeline-orchestrator',
                InvocationType='Event',
                Payload=json.dumps(event_payload)
            )

            self.last_pipeline_trigger = current_time
            logger.info(f"🚀 Pipeline déclenchée pour streaming (cooldown: {self.batch_config['pipeline_cooldown']}s)")

        except Exception as e:
            logger.warning(f"⚠️ Erreur déclenchement pipeline streaming: {e}")

    def _is_mpu_christian_data(self, data: Dict) -> bool:
        """Identifie si les données proviennent du MPU Christian - VERSION ÉLARGIE"""

        # Rechercher dans TOUS les champs possibles (version plus permissive)
        search_fields = [
            str(data.get('device_id', '')),
            str(data.get('topic', '')),
            str(data.get('clientId', '')),
            str(data.get('deviceId', '')),
            str(data.get('source', '')),
            str(data.get('client_id', '')),  # Variante snake_case
            str(data.get('device', '')),
            str(data.get('sender', '')),
        ]

        # Mots-clés élargis pour capturer plus de variantes
        keywords = [
            'mpu_christian', 'christian', '8266mod', 'mpu6050',
            'bracelet_christian', 'christian_bracelet', 'mpu_8266',
            'esp8266', 'bracelet', 'wearable'
        ]
        
        for field in search_fields:
            field_str = str(field).lower()
            if any(keyword in field_str for keyword in keywords):
                logger.info(f"🎯 MPU Christian identifié par champ '{field}' = '{field_str}'")
                return True
        
        # Vérifier aussi la structure des données (accéléromètre/gyroscope) - plus permissif
        sensor_keys = [
            'accelerometer', 'gyroscope', 'accel', 'gyro',
            'ax', 'ay', 'az', 'gx', 'gy', 'gz',
            'acc_x', 'acc_y', 'acc_z', 'gyro_x', 'gyro_y', 'gyro_z',
            'acceleration', 'rotation', 'motion'
        ]

        has_sensor_data = any(key in data for key in sensor_keys)

        if has_sensor_data:
            logger.info(f"🎯 MPU Christian identifié par données capteurs: {[k for k in sensor_keys if k in data]}")
            return True

        # Log pour debugging - voir toutes les données qui passent
        logger.debug(f"📋 Données non-MPU: device_id={data.get('device_id')}, clientId={data.get('clientId')}, keys={list(data.keys())}")

        return False

    async def _analyze_and_alert(self, data: Dict) -> List[Dict]:
        """Analyse les données et déclenche des alertes si nécessaire"""
        
        alerts = []
        
        # Analyser accéléromètre
        if 'accelerometer' in data:
            accel = data['accelerometer']
            ax, ay, az = accel.get('x', 0), accel.get('y', 0), accel.get('z', 0)
            
            # Calculer l'accélération totale
            total_accel = (ax**2 + ay**2 + az**2)**0.5
            
            if total_accel > self.alert_thresholds['acceleration_max']:
                alert = {
                    'type': 'ACCELERATION_CRITIQUE',
                    'value': total_accel,
                    'threshold': self.alert_thresholds['acceleration_max'],
                    'severity': 'HIGH',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'device': data.get('device_id', 'MPU_Christian_8266MOD')
                }
                alerts.append(alert)
                await self._trigger_alert(alert)
        
        # Analyser gyroscope
        if 'gyroscope' in data:
            gyro = data['gyroscope']
            gx, gy, gz = gyro.get('x', 0), gyro.get('y', 0), gyro.get('z', 0)
            
            # Calculer la rotation totale
            total_gyro = (gx**2 + gy**2 + gz**2)**0.5
            
            if total_gyro > self.alert_thresholds['gyro_max']:
                alert = {
                    'type': 'ROTATION_CRITIQUE',
                    'value': total_gyro,
                    'threshold': self.alert_thresholds['gyro_max'],
                    'severity': 'HIGH',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'device': data.get('device_id', 'MPU_Christian_8266MOD')
                }
                alerts.append(alert)
                await self._trigger_alert(alert)
        
        # Analyser température
        if 'temperature' in data:
            temp = data['temperature']
            
            if temp < self.alert_thresholds['temperature_min'] or temp > self.alert_thresholds['temperature_max']:
                alert = {
                    'type': 'TEMPERATURE_ANORMALE',
                    'value': temp,
                    'thresholds': [self.alert_thresholds['temperature_min'], self.alert_thresholds['temperature_max']],
                    'severity': 'MEDIUM',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'device': data.get('device_id', 'MPU_Christian_8266MOD')
                }
                alerts.append(alert)
                await self._trigger_alert(alert)
        
        return alerts

    async def _trigger_alert(self, alert: Dict):
        """Déclenche une alerte"""
        
        self.alerts_triggered += 1
        
        logger.warning(f"🚨 ALERTE #{self.alerts_triggered}: {alert['type']}")
        logger.warning(f"   📊 Valeur: {alert['value']}")
        logger.warning(f"   ⚠️ Seuil: {alert.get('threshold', alert.get('thresholds'))}")
        logger.warning(f"   📱 Device: {alert['device']}")
        
        # Envoyer vers SNS (si configuré)
        try:
            # Vous pouvez configurer un topic SNS pour les alertes
            pass
        except Exception as e:
            logger.debug(f"⚠️ Erreur SNS: {e}")

    async def _display_metrics(self):
        """Affiche les métriques du processeur"""
        
        logger.info("📊 MÉTRIQUES PROCESSEUR:")
        logger.info(f"   📨 Records traités: {self.processed_count}")
        logger.info(f"   🚨 Alertes déclenchées: {self.alerts_triggered}")
        logger.info(f"   📦 Uploads S3: {self.s3_uploads}")
        logger.info(f"   ⏱️ Uptime: {time.time() - self.start_time:.0f}s")
        logger.info("=" * 70)

async def main():
    """Point d'entrée principal"""
    
    logger.info("🚀 DÉMARRAGE PROCESSEUR COMPLET MPU CHRISTIAN")
    logger.info("🎯 Pipeline: Kinesis → Alertes → S3")
    logger.info("=" * 70)
    
    processor = MPUDataProcessor()
    processor.start_time = time.time()
    
    try:
        await processor.start_processing()
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt processeur demandé par l'utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
    finally:
        logger.info("🔄 Processeur arrêté")
        await processor._display_metrics()

if __name__ == "__main__":
    asyncio.run(main())
