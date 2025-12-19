#!/usr/bin/env python3
"""
Processeur Kinesis Temps Réel avec Alertes MPU Christian + PostgreSQL Automatique
Traite les données Kinesis, génère des alertes ET les insère automatiquement dans PostgreSQL
"""

import json
import boto3
import asyncio
import logging
import psycopg2
from datetime import datetime, timezone
from typing import Dict, Any, List
import uuid
import math

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MPURealtimeAlertProcessorAutoDB:
    """Processeur temps réel avec système d'alertes pour MPU Christian + PostgreSQL automatique"""

    def __init__(self):
        self.region = "eu-west-1"
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.sns_client = boto3.client('sns', region_name=self.region)
        self.ses_client = boto3.client('ses', region_name=self.region)

        # Configuration
        self.bucket_name = "kidjamo-dev-datalake-e75d5213"
        self.stream_name = "kidjamo-iot-stream-dev"
        self.device_id = "MPU_Christian_8266MOD"
        
        # Configuration SES professionnelle
        self.ses_config = {
            'sender_email': 'support@kidjamo.app',
            'sender_name': 'Kidjamo Alert',
            'recipient_email': 'christianouragan@gmail.com',
            'reply_to': 'support@kidjamo.app'
        }

        # NOUVEAU: Configuration PostgreSQL pour insertion automatique
        self.pg_config = {
            'host': 'kidjamo-dev-postgres-fixed.crgg26e8owiz.eu-west-1.rds.amazonaws.com',
            'port': 5432,
            'database': 'kidjamo',
            'user': 'kidjamo_admin',
            'password': 'JBRPp5t!uLqDKJRY'
        }

        # Seuils d'alertes MPU6050 - SEULEMENT CHUTE ET HYPERACTIVITÉ
        self.alert_thresholds = {
            'acceleration_magnitude': 15.0,  # m/s² - détection de chute
            'hyperactivity_threshold': 12.0,  # m/s² - activité soutenue élevée
            'hyperactivity_gyro': 3.0,       # rad/s - rotation soutenue
        }

        # Configuration SNS pour notifications - CORRIGÉ avec les vrais topics
        self.alert_topics = {
            'HIGH': 'arn:aws:sns:eu-west-1:930900578484:kidjamo-critical-alerts',
            'MEDIUM': 'arn:aws:sns:eu-west-1:930900578484:kidjamo-system-alerts',
            'LOW': 'arn:aws:sns:eu-west-1:930900578484:kidjamo-email-alerts-test'
        }

        # Variables d'état
        self.processed_count = 0
        self.alert_count = 0
        self.activity_history = []
        
        # NOUVEAU: Connexion PostgreSQL persistante
        self.pg_connection = None
        self.device_uuid = None
        self.patient_uuid = None
        
        # Initialiser la connexion PostgreSQL
        self._init_postgresql_connection()

        logger.info("🚀 Processeur MPU Christian avec Alertes + PostgreSQL automatique initialisé")
        logger.info(f"📡 Stream: {self.stream_name}")
        logger.info(f"🗄️ PostgreSQL: {self.pg_config['host']}")
        logger.info(f"🚨 Seuils d'alertes configurés")

    def _init_postgresql_connection(self):
        """Initialise la connexion PostgreSQL et récupère les UUIDs nécessaires"""
        try:
            self.pg_connection = psycopg2.connect(**self.pg_config)
            cursor = self.pg_connection.cursor()
            
            # Récupérer l'UUID du device
            cursor.execute("SELECT device_id FROM devices WHERE serial_number = %s", (self.device_id,))
            device_result = cursor.fetchone()
            self.device_uuid = device_result[0] if device_result else str(uuid.uuid4())
            
            # Récupérer l'UUID du patient
            cursor.execute("SELECT patient_id FROM patients LIMIT 1")
            patient_result = cursor.fetchone()
            self.patient_uuid = patient_result[0] if patient_result else str(uuid.uuid4())
            
            cursor.close()
            
            logger.info(f"✅ Connexion PostgreSQL établie")
            logger.info(f"🔧 Device UUID: {self.device_uuid}")
            logger.info(f"👤 Patient UUID: {self.patient_uuid}")
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            self.pg_connection = None

    def _severity_mapping(self, aws_severity):
        """Mapper les severités AWS vers PostgreSQL"""
        mapping = {
            'HIGH': 'critical',
            'MEDIUM': 'warn', 
            'LOW': 'info',
            'CRITICAL': 'critical',
            'WARNING': 'warn',
            'INFO': 'info'
        }
        return mapping.get(aws_severity.upper(), 'info')

    async def _insert_alert_to_postgresql(self, alert_data: Dict):
        """Insertion automatique de l'alerte dans PostgreSQL"""
        if not self.pg_connection:
            logger.warning("⚠️ Pas de connexion PostgreSQL - alerte non insérée en DB")
            return False

        try:
            cursor = self.pg_connection.cursor()
            
            # Mapper les données de l'alerte
            alert_type = alert_data.get('type', 'general_alert').lower()
            aws_severity = alert_data.get('severity', 'MEDIUM')
            pg_severity = self._severity_mapping(aws_severity)
            
            message = alert_data.get('message', 'Alerte détectée')[:500]
            timestamp_str = alert_data.get('timestamp', '')
            
            # Convertir timestamp
            try:
                if timestamp_str:
                    alert_timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                else:
                    alert_timestamp = datetime.now(timezone.utc)
            except:
                alert_timestamp = datetime.now(timezone.utc)
            
            # Créer vitals_snapshot avec toutes les données de l'alerte
            vitals_snapshot = {
                'raw_data': alert_data,
                'source': 'mpu_christian_realtime',
                'inserted_at': datetime.now().isoformat(),
                'device_id': self.device_id
            }
            
            # Insertion dans la table alerts
            cursor.execute("""
                INSERT INTO alerts (
                    patient_id, alert_type, severity, 
                    title, message, vitals_snapshot, 
                    created_at, escalation_level
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                self.patient_uuid,
                alert_type,
                pg_severity,
                f"Alerte {alert_type}",
                message,
                json.dumps(vitals_snapshot),
                alert_timestamp,
                1 if pg_severity in ['critical', 'alert'] else 0
            ))
            
            self.pg_connection.commit()
            cursor.close()
            
            logger.info(f"✅ Alerte insérée automatiquement dans PostgreSQL: {alert_type} | {pg_severity}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur insertion PostgreSQL: {e}")
            if self.pg_connection:
                self.pg_connection.rollback()
            return False

    async def _detect_alerts(self, data: Dict) -> List[Dict]:
        """Détecte les alertes basées sur les données MPU - SEULEMENT CHUTE ET HYPERACTIVITÉ"""

        alerts = []
        
        try:
            # Calculer les magnitudes
            accel_magnitude = math.sqrt(
                data['accel_x']**2 + data['accel_y']**2 + data['accel_z']**2
            )
            gyro_magnitude = math.sqrt(
                data['gyro_x']**2 + data['gyro_y']**2 + data['gyro_z']**2
            )
            temperature = data['temp']
            
            # 1. ALERTE DE CHUTE (accélération élevée)
            if accel_magnitude > self.alert_thresholds['acceleration_magnitude']:
                alerts.append({
                    'type': 'FALL_DETECTION',
                    'severity': 'HIGH',
                    'message': f'Chute détectée - Accélération: {accel_magnitude:.2f} m/s²',
                    'value': accel_magnitude,
                    'threshold': self.alert_thresholds['acceleration_magnitude'],
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'device_id': self.device_id
                })
            
            # 2. ALERTE HYPERACTIVITÉ - Analyse des patterns d'activité
            hyperactivity_alerts = self._analyze_hyperactivity_patterns(data, accel_magnitude, gyro_magnitude)
            if hyperactivity_alerts:
                alerts.extend(hyperactivity_alerts)

        except Exception as e:
            logger.error(f"❌ Erreur détection alertes: {e}")

        return alerts

    def _analyze_hyperactivity_patterns(self, data: Dict, accel_magnitude: float, gyro_magnitude: float) -> List[Dict]:
        """Analyse les patterns d'hyperactivité basés sur l'historique"""

        alerts = []

        try:
            # Ajouter les données actuelles à l'historique pour analyse
            current_data = {
                **data,
                'accel_magnitude': accel_magnitude,
                'gyro_magnitude': gyro_magnitude,
                'timestamp': datetime.now(timezone.utc)
            }

            self.activity_history.append(current_data)

            # Garder seulement les 60 derniers échantillons (environ 1 minute d'activité)
            if len(self.activity_history) > 60:
                self.activity_history.pop(0)

            # Analyser l'hyperactivité si on a suffisamment de données
            if len(self.activity_history) >= 30:  # Au moins 30 échantillons

                # Calculer l'activité moyenne sur la période récente
                recent_activity = self.activity_history[-30:]  # 30 derniers échantillons
                avg_accel = sum(d['accel_magnitude'] for d in recent_activity) / len(recent_activity)
                avg_gyro = sum(d['gyro_magnitude'] for d in recent_activity) / len(recent_activity)

                # Détection hyperactivité : activité soutenue élevée
                if avg_accel > self.alert_thresholds['hyperactivity_threshold'] or avg_gyro > self.alert_thresholds['hyperactivity_gyro']:

                    # Vérifier que c'est vraiment soutenu (pas juste un pic)
                    high_activity_count = sum(1 for d in recent_activity
                                            if d['accel_magnitude'] > 11.0 or d['gyro_magnitude'] > 2.5)

                    if high_activity_count >= 20:  # Au moins 20/30 échantillons avec activité élevée
                        alerts.append({
                            'type': 'HYPERACTIVITY_DETECTED',
                            'severity': 'MEDIUM',
                            'message': f'Hyperactivité détectée - Activité moyenne: {avg_accel:.2f}',
                            'value': avg_accel,
                            'threshold': self.alert_thresholds['hyperactivity_threshold'],
                            'timestamp': datetime.now(timezone.utc).isoformat(),
                            'device_id': self.device_id,
                            'pattern_details': {
                                'avg_acceleration': avg_accel,
                                'avg_rotation': avg_gyro,
                                'high_activity_samples': high_activity_count,
                                'total_samples': len(recent_activity)
                            }
                        })

        except Exception as e:
            logger.error(f"❌ Erreur analyse hyperactivité: {e}")

        return alerts

    async def _send_alert_notification(self, alert: Dict):
        """Envoie des notifications d'alerte via SNS et Email"""
        
        severity = alert.get('severity', 'MEDIUM')
        
        try:
            # Envoi SNS si configuré
            if severity in self.alert_topics:
                topic_arn = self.alert_topics[severity]
                
                message = {
                    'alert_type': alert['type'],
                    'severity': severity,
                    'message': alert['message'],
                    'device_id': alert['device_id'],
                    'timestamp': alert['timestamp'],
                    'value': alert.get('value', 0)
                }
                
                try:
                    self.sns_client.publish(
                        TopicArn=topic_arn,
                        Message=json.dumps(message),
                        Subject=f"Alerte {severity} - {alert['type']}"
                    )
                    logger.info(f"📧 Alerte {severity} envoyée via SNS: {alert['type']}")
                except Exception as e:
                    logger.error(f"❌ Erreur envoi SNS: {e}")

        except Exception as e:
            logger.error(f"❌ Erreur notification: {e}")

    async def _store_alert_s3(self, alert: Dict):
        """Stocke l'alerte dans S3 pour backup"""
        
        try:
            now = datetime.now(timezone.utc)
            timestamp_ms = int(now.timestamp() * 1000)
            
            s3_key = (f"alerts/mpu_christian/"
                     f"year={now.year}/month={now.month:02d}/"
                     f"day={now.day:02d}/hour={now.hour:02d}/"
                     f"alert_{timestamp_ms}.json")
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(alert, indent=2),
                ContentType='application/json'
            )
            
            logger.info(f"💾 Alerte stockée: s3://{self.bucket_name}/{s3_key}")
            
        except Exception as e:
            logger.error(f"❌ Erreur stockage S3: {e}")

    async def _process_alert(self, alert: Dict):
        """Traite une alerte complètement : S3 + PostgreSQL + Notifications"""
        
        logger.warning(f"🚨 {len([alert])} ALERTE(S) DÉTECTÉE(S) !")
        logger.warning(f"   → {alert['type']}: {alert['message']}")
        
        # 1. Insérer automatiquement dans PostgreSQL
        db_success = await self._insert_alert_to_postgresql(alert)
        
        # 2. Stocker dans S3 pour backup
        await self._store_alert_s3(alert)
        
        # 3. Envoyer notifications
        await self._send_alert_notification(alert)
        
        # 4. Log du résultat
        if db_success:
            logger.warning(f"🚨 ALERTE {alert['severity']} COMPLÈTE: {alert['message']}")
        else:
            logger.warning(f"🚨 ALERTE {alert['severity']} (S3 SEULEMENT): {alert['message']}")

    async def _process_record(self, record: Dict):
        """Traite un enregistrement Kinesis"""
        
        try:
            # Décoder les données
            data = json.loads(record['data'])
            
            # Vérifier que c'est notre device MPU Christian
            if data.get('device_id') != self.device_id:
                return
            
            # Calculer magnitude pour le log
            accel_magnitude = math.sqrt(
                data['accel_x']**2 + data['accel_y']**2 + data['accel_z']**2
            )
            
            logger.info(f"🔍 ANALYSE DONNÉE: accel_mag={accel_magnitude:.2f}, temp={data['temp']:.1f}°C")
            logger.info(f"✅ Données MPU Christian confirmées - Device: {data['device_id']}")
            
            # Détecter les alertes
            alerts = await self._detect_alerts(data)
            
            if alerts:
                # Traiter chaque alerte détectée
                for alert in alerts:
                    await self._process_alert(alert)
                    self.alert_count += 1
            else:
                logger.info("✅ Aucune alerte détectée pour cette donnée")
            
            self.processed_count += 1
            
        except Exception as e:
            logger.error(f"❌ Erreur traitement record: {e}")

    async def start_processing(self):
        """Démarre le traitement temps réel des données Kinesis"""
        
        logger.info("🚀 DÉMARRAGE PROCESSEUR TEMPS RÉEL AVEC ALERTES + POSTGRESQL")
        logger.info("📡 Surveillance du stream Kinesis pour alertes temps réel")
        logger.info("🔄 DÉMARRAGE TRAITEMENT TEMPS RÉEL AVEC ALERTES + AUTO DB")
        
        try:
            # Obtenir les shards du stream
            response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
            shards = response['StreamDescription']['Shards']
            
            # Traiter chaque shard
            tasks = []
            for shard in shards:
                shard_id = shard['ShardId']
                task = asyncio.create_task(self._process_shard(shard_id))
                tasks.append(task)
                logger.info(f"📊 Shard configuré: {shard_id}")
            
            # Démarrer la tâche de monitoring
            monitor_task = asyncio.create_task(self._monitor_status())
            tasks.append(monitor_task)
            
            # Attendre toutes les tâches
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"❌ Erreur démarrage processeur: {e}")
        finally:
            if self.pg_connection:
                self.pg_connection.close()
                logger.info("🔌 Connexion PostgreSQL fermée")

    async def _process_shard(self, shard_id: str):
        """Traite un shard Kinesis spécifique"""
        
        try:
            # Obtenir l'iterator du shard
            response = self.kinesis_client.get_shard_iterator(
                StreamName=self.stream_name,
                ShardId=shard_id,
                ShardIteratorType='LATEST'
            )
            
            shard_iterator = response['ShardIterator']
            
            while True:
                # Lire les records
                response = self.kinesis_client.get_records(
                    ShardIterator=shard_iterator,
                    Limit=100
                )
                
                records = response['Records']
                next_shard_iterator = response.get('NextShardIterator')
                
                # Traiter les records
                for record in records:
                    decoded_data = record['Data'].decode('utf-8')
                    await self._process_record({'data': decoded_data})
                
                # Passer au prochain iterator
                if next_shard_iterator:
                    shard_iterator = next_shard_iterator
                else:
                    logger.warning(f"🔚 Shard {shard_id} fermé")
                    break
                
                # Pause pour éviter de surcharger
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"❌ Erreur processing shard {shard_id}: {e}")

    async def _monitor_status(self):
        """Monitore le statut du processeur"""
        
        while True:
            await asyncio.sleep(120)  # Toutes les 2 minutes
            logger.info(f"📊 STATUS - Traités: {self.processed_count}, Alertes: {self.alert_count}")

async def main():
    """Fonction principale"""
    processor = MPURealtimeAlertProcessorAutoDB()
    await processor.start_processing()

if __name__ == "__main__":
    asyncio.run(main())
