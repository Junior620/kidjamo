#!/usr/bin/env python3
"""
Processeur Kinesis Temps Réel avec Alertes MPU Christian
Traite les données Kinesis et génère des alertes en temps réel
"""

import json
import boto3
import asyncio
import logging
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

class MPURealtimeAlertProcessor:
    """Processeur temps réel avec système d'alertes pour MPU Christian"""

    def __init__(self):
        self.region = "eu-west-1"
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.kinesis_client = boto3.client('kinesis', region_name=self.region)
        self.sns_client = boto3.client('sns', region_name=self.region)
        # NOUVEAU: Client SES pour emails professionnels avec domaine vérifié
        self.ses_client = boto3.client('ses', region_name=self.region)

        # Configuration
        self.bucket_name = "kidjamo-dev-datalake-e75d5213"
        self.stream_name = "kidjamo-iot-stream-dev"
        self.device_id = "MPU_Christian_8266MOD"
        
        # NOUVEAU: Configuration SES professionnelle
        self.ses_config = {
            'sender_email': 'support@kidjamo.app',
            'sender_name': 'Kidjamo Alert',
            'recipient_email': 'christianouragan@gmail.com',
            'reply_to': 'support@kidjamo.app'
        }

        # Seuils d'alertes MPU6050
        self.alert_thresholds = {
            'acceleration_magnitude': 15.0,  # m/s² - détection de chute
            'gyro_magnitude': 10.0,          # rad/s - rotation rapide
            'temperature': {'min': 15.0, 'max': 40.0},  # °C
            'inactivity_duration': 300,      # 5 minutes sans mouvement
            'high_activity_duration': 60     # 1 minute d'activité intense
        }
        
        # Historique pour détection de patterns
        self.data_history = []
        self.max_history = 100  # Garder 100 derniers échantillons
        
        # Compteurs et état
        self.processed_count = 0
        self.alerts_sent = 0
        self.is_running = False
        self.shard_iterators = {}
        
        logger.info("🚀 Processeur MPU Christian avec Alertes initialisé")
        logger.info(f"📡 Stream: {self.stream_name}")
        logger.info(f"🚨 Seuils d'alertes configurés")

    async def start_processing(self):
        """Démarre le traitement temps réel avec alertes"""
        
        logger.info("🔄 DÉMARRAGE TRAITEMENT TEMPS RÉEL AVEC ALERTES")
        
        try:
            # Découvrir les shards Kinesis
            await self._discover_shards()
            self.is_running = True

            # Créer les tâches de traitement
            tasks = []
            for shard_id in self.shard_iterators.keys():
                tasks.append(self._process_shard_with_alerts(shard_id))

            # Ajouter tâche de monitoring
            tasks.append(self._monitoring_task())

            # Démarrer le traitement
            await asyncio.gather(*tasks)

        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            raise

    async def _discover_shards(self):
        """Découvre les shards du stream Kinesis"""
        self.shard_iterators = {}
        
        try:
            response = self.kinesis_client.describe_stream(StreamName=self.stream_name)
            shards = response['StreamDescription']['Shards']

            for shard in shards:
                shard_id = shard['ShardId']
                
                # Commencer par les nouvelles données (LATEST)
                iterator_response = self.kinesis_client.get_shard_iterator(
                    StreamName=self.stream_name,
                    ShardId=shard_id,
                    ShardIteratorType='LATEST'
                )

                self.shard_iterators[shard_id] = iterator_response['ShardIterator']
                logger.info(f"📊 Shard configuré: {shard_id}")

        except Exception as e:
            logger.error(f"❌ Erreur découverte shards: {e}")
            raise

    async def _process_shard_with_alerts(self, shard_id: str):
        """Traite un shard avec détection d'alertes"""
        
        while self.is_running:
            try:
                iterator = self.shard_iterators.get(shard_id)
                if not iterator:
                    await asyncio.sleep(1)
                    continue

                # Lire les records Kinesis
                response = self.kinesis_client.get_records(
                    ShardIterator=iterator,
                    Limit=50
                )

                records = response.get('Records', [])
                next_iterator = response.get('NextShardIterator')

                if records:
                    await self._analyze_records_for_alerts(records, shard_id)

                # Mettre à jour l'itérateur
                self.shard_iterators[shard_id] = next_iterator

                # Pause courte pour éviter rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"❌ Erreur traitement shard {shard_id}: {e}")
                await asyncio.sleep(5)

    async def _analyze_records_for_alerts(self, records: list, shard_id: str):
        """Analyse les enregistrements et génère des alertes"""
        
        for record in records:
            try:
                # Décoder les données Kinesis
                data = json.loads(record['Data'])
                
                # Log détaillé pour chaque donnée reçue
                logger.info(f"🔍 ANALYSE DONNÉE: accel_mag={math.sqrt(data.get('accel_x',0)**2 + data.get('accel_y',0)**2 + data.get('accel_z',0)**2):.2f}, temp={data.get('temp',0):.1f}°C")

                # Vérifier que c'est bien des données MPU Christian
                if self._is_mpu_christian_data(data):
                    logger.info(f"✅ Données MPU Christian confirmées - Device: {data.get('device_id')}")

                    # Analyser pour alertes (CHAQUE DONNÉE)
                    alerts = await self._detect_alerts(data)
                    
                    # Log du nombre d'alertes détectées
                    if alerts:
                        logger.warning(f"🚨 {len(alerts)} ALERTE(S) DÉTECTÉE(S) !")
                        for alert in alerts:
                            logger.warning(f"   → {alert['type']}: {alert['message']}")
                    else:
                        logger.info("✅ Aucune alerte détectée pour cette donnée")

                    # Envoyer les alertes si nécessaire
                    if alerts:
                        await self._send_alerts(alerts, data)
                    
                    # Ajouter à l'historique
                    self._update_history(data)
                    
                    self.processed_count += 1
                else:
                    logger.warning(f"⚠️ Données non-MPU Christian ignorées: {data.get('device_id', 'UNKNOWN')}")

            except Exception as e:
                logger.warning(f"⚠️ Erreur analyse record: {e}")
                logger.warning(f"   Données brutes: {record.get('Data', 'N/A')}")

    def _is_mpu_christian_data(self, data: Dict) -> bool:
        """Vérifie si les données proviennent du MPU Christian"""
        
        required_fields = ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z', 'temp']
        has_device_id = data.get('device_id') == self.device_id
        has_all_fields = all(field in data for field in required_fields)
        
        return has_device_id and has_all_fields

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
            
            # 1. ALERTE DE CHUTE (accélération élevée) - SEUIL OPTIMAL
            if accel_magnitude > 15.0:  # Seuil remis à 15.0 pour détecter les chutes réelles
                alerts.append({
                    'type': 'FALL_DETECTION',
                    'severity': 'HIGH',
                    'message': f'Chute détectée - Accélération: {accel_magnitude:.2f} m/s²',
                    'value': accel_magnitude,
                    'threshold': 15.0,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'device_id': self.device_id
                })
            
            # 2. ALERTE HYPERACTIVITÉ - Analyse des patterns d'activité
            hyperactivity_alerts = self._analyze_hyperactivity_patterns(data, accel_magnitude, gyro_magnitude)
            if hyperactivity_alerts:
                alerts.extend(hyperactivity_alerts)

            # SUPPRIMÉ: ABNORMAL_MOVEMENT (mouvement anormal)
            # SUPPRIMÉ: TEMPERATURE_CRITICAL (température critique)

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

            # Maintenir un historique récent pour l'analyse
            if not hasattr(self, 'activity_history'):
                self.activity_history = []

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
                if avg_accel > 12.0 or avg_gyro > 3.0:  # Seuils pour activité intense soutenue

                    # Vérifier que c'est vraiment soutenu (pas juste un pic)
                    high_activity_count = sum(1 for d in recent_activity
                                            if d['accel_magnitude'] > 11.0 or d['gyro_magnitude'] > 2.5)

                    if high_activity_count >= 20:  # Au moins 20/30 échantillons avec activité élevée
                        alerts.append({
                            'type': 'HYPERACTIVITY_DETECTED',
                            'severity': 'MEDIUM',
                            'message': f'Hyperactivité détectée - Activité moyenne: {avg_accel:.2f} m/s²',
                            'value': avg_accel,
                            'threshold': 12.0,
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

    async def _send_alerts(self, alerts: List[Dict], data: Dict):
        """Envoie les alertes via SNS et stockage S3"""
        
        for alert in alerts:
            try:
                # Enrichir l'alerte avec les données complètes
                alert_payload = {
                    **alert,
                    'raw_data': data,
                    'processed_timestamp': datetime.now(timezone.utc).isoformat(),
                    'processor': 'mpu_christian_realtime'
                }
                
                # 1. Envoyer via SNS (si configuré)
                await self._send_sns_alert(alert_payload)
                
                # 2. Stocker dans S3 pour audit
                await self._store_alert_s3(alert_payload)
                
                # 3. Log de l'alerte
                logger.warning(f"🚨 ALERTE {alert['severity']}: {alert['message']}")
                
                self.alerts_sent += 1
                
            except Exception as e:
                logger.error(f"❌ Erreur envoi alerte: {e}")

    async def _send_sns_alert(self, alert: Dict):
        """Envoie une alerte via Amazon SES avec domaine professionnel kidjamo.app"""

        try:
            # NOUVEAU: Utiliser Amazon SES avec domaine vérifié
            severity = alert.get('severity', 'MEDIUM')
            message_details = alert.get('message', 'Alerte détectée')

            # Configuration de l'expéditeur professionnel
            sender_name = self.ses_config['sender_name']
            sender_email = self.ses_config['sender_email']
            recipient_email = self.ses_config['recipient_email']

            # Formats d'expéditeur professionnel : "Kidjamo Alert <support@kidjamo.app>"
            from_address = f"{sender_name} <{sender_email}>"

            # Template HTML professionnel selon la sévérité
            if severity == 'HIGH':
                subject = f"🚨 ALERTE CRITIQUE - MPU Christian - {alert['type']}"

                html_body = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Alerte Critique Kidjamo</title>
                </head>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #dc3545; color: white; padding: 20px; border-radius: 8px; text-align: center;">
                            <h1 style="margin: 0;">🚨 ALERTE CRITIQUE</h1>
                            <p style="margin: 10px 0 0 0; font-size: 18px;">Système de Surveillance IoT</p>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                            <h2 style="color: #dc3545; margin-top: 0;">Détails de l'Alerte</h2>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Device:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['device_id']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Type d'alerte:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['type']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Détails:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{message_details}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Valeur mesurée:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('value', 'N/A')}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Seuil dépassé:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('threshold', 'N/A')}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['timestamp']}</td></tr>
                            </table>
                        </div>
                        
                        <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="color: #856404; margin-top: 0;">🚑 ACTION IMMÉDIATE REQUISE!</h3>
                            <p>Cette alerte indique une situation critique nécessitant une attention immédiate. Vérifiez l'état du dispositif MPU Christian.</p>
                        </div>
                        
                        <div style="text-align: center; padding: 20px; color: #6c757d; font-size: 12px;">
                            <p>Système d'alertes Kidjamo - Surveillance IoT<br>
                            Pour toute question, répondez à cet email ou contactez: support@kidjamo.app</p>
                        </div>
                    </div>
                </body>
                </html>
                """

                text_body = f"""🚨 ALERTE CRITIQUE DÉTECTÉE!

👤 Device: {alert['device_id']}
⚠️ Type d'alerte: {alert['type']}
📊 Détails: {message_details}
📈 Valeur mesurée: {alert.get('value', 'N/A')}
🎯 Seuil dépassé: {alert.get('threshold', 'N/A')}
🕐 Timestamp: {alert['timestamp']}

🚑 ACTION IMMÉDIATE REQUISE!

Cette alerte indique une situation critique nécessitant une attention immédiate.
Vérifiez l'état du dispositif MPU Christian.

Système d'alertes Kidjamo - Surveillance IoT
Support: support@kidjamo.app"""

            elif severity == 'MEDIUM':
                subject = f"⚠️ ALERTE - MPU Christian - {alert['type']}"

                html_body = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Alerte Kidjamo</title>
                </head>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #fd7e14; color: white; padding: 20px; border-radius: 8px; text-align: center;">
                            <h1 style="margin: 0;">⚠️ ALERTE MOYENNE</h1>
                            <p style="margin: 10px 0 0 0; font-size: 18px;">Système de Surveillance IoT</p>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                            <h2 style="color: #fd7e14; margin-top: 0;">Détails de l'Alerte</h2>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Device:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['device_id']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Type d'alerte:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['type']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Détails:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{message_details}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Valeur mesurée:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('value', 'N/A')}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Seuil:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('threshold', 'N/A')}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['timestamp']}</td></tr>
                            </table>
                        </div>
                        
                        <div style="background: #d1ecf1; border: 1px solid #bee5eb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h3 style="color: #0c5460; margin-top: 0;">📱 Vérification Recommandée</h3>
                            <p>Vérification recommandée dans les prochaines minutes.</p>
                        </div>
                        
                        <div style="text-align: center; padding: 20px; color: #6c757d; font-size: 12px;">
                            <p>Système d'alertes Kidjamo - Surveillance IoT<br>
                            Pour toute question, répondez à cet email ou contactez: support@kidjamo.app</p>
                        </div>
                    </div>
                </body>
                </html>
                """

                text_body = f"""⚠️ ALERTE MOYENNE DÉTECTÉE

👤 Device: {alert['device_id']}
📋 Type d'alerte: {alert['type']}
📊 Détails: {message_details}
📈 Valeur mesurée: {alert.get('value', 'N/A')}
🎯 Seuil: {alert.get('threshold', 'N/A')}
🕐 Timestamp: {alert['timestamp']}

📱 Vérification recommandée dans les prochaines minutes.

Système d'alertes Kidjamo - Surveillance IoT
Support: support@kidjamo.app"""

            else:  # LOW
                subject = f"ℹ️ Notification - MPU Christian - {alert['type']}"

                html_body = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <title>Notification Kidjamo</title>
                </head>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                        <div style="background: #17a2b8; color: white; padding: 20px; border-radius: 8px; text-align: center;">
                            <h1 style="margin: 0;">ℹ️ NOTIFICATION</h1>
                            <p style="margin: 10px 0 0 0; font-size: 18px;">Système de Surveillance IoT</p>
                        </div>
                        
                        <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                            <h2 style="color: #17a2b8; margin-top: 0;">Détails de la Notification</h2>
                            <table style="width: 100%; border-collapse: collapse;">
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Device:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['device_id']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['type']}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Détails:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{message_details}</td></tr>
                                <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['timestamp']}</td></tr>
                            </table>
                        </div>
                        
                        <div style="background: #d4edda; border: 1px solid #c3e6cb; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <p style="margin: 0; color: #155724;">Notification d'information - Aucune action urgente requise.</p>
                        </div>
                        
                        <div style="text-align: center; padding: 20px; color: #6c757d; font-size: 12px;">
                            <p>Système d'alertes Kidjamo - Surveillance IoT<br>
                            Pour toute question, répondez à cet email ou contactez: support@kidjamo.app</p>
                        </div>
                    </div>
                </body>
                </html>
                """

                text_body = f"""ℹ️ NOTIFICATION SYSTÈME

👤 Device: {alert['device_id']}
📝 Type: {alert['type']}
📊 Détails: {message_details}
🕐 Timestamp: {alert['timestamp']}

Notification d'information - Aucune action urgente requise.

Système d'alertes Kidjamo - Surveillance IoT
Support: support@kidjamo.app"""

            # Envoi via Amazon SES
            try:
                response = self.ses_client.send_email(
                    Source=from_address,
                    Destination={
                        'ToAddresses': [recipient_email]
                    },
                    Message={
                        'Subject': {
                            'Data': subject,
                            'Charset': 'UTF-8'
                        },
                        'Body': {
                            'Html': {
                                'Data': html_body,
                                'Charset': 'UTF-8'
                            },
                            'Text': {
                                'Data': text_body,
                                'Charset': 'UTF-8'
                            }
                        }
                    },
                    ReplyToAddresses=[self.ses_config['reply_to']],
                    Tags=[
                        {
                            'Name': 'AlertType',
                            'Value': alert['type']
                        },
                        {
                            'Name': 'Severity',
                            'Value': severity
                        },
                        {
                            'Name': 'System',
                            'Value': 'KidjamoIoT'
                        }
                    ]
                )

                logger.info(f"📧 Alerte {severity} envoyée via SES: {alert['type']}")
                logger.info(f"   📤 Expéditeur: {from_address}")
                logger.info(f"   📬 Destinataire: {recipient_email}")
                logger.info(f"   📋 MessageId: {response['MessageId']}")

                return response

            except Exception as ses_error:
                logger.error(f"❌ Erreur envoi SES: {ses_error}")
                logger.warning(f"💡 SOLUTION: Vérifiez que le domaine {sender_email} est vérifié dans SES!")
                logger.warning(f"   🔗 Console SES: https://console.aws.amazon.com/ses/")
                raise ses_error

        except Exception as e:
            logger.error(f"❌ Erreur système SES: {e}")
            logger.info(f"💾 Alerte sauvegardée dans S3 en backup")
            # Ne pas bloquer le traitement - l'alerte sera dans S3

    async def _send_sms_cameroun_alternative(self, alert: Dict, message_text: str):
        """Tentatives multiples SMS pour le Cameroun (+237)"""
        
        phone_number = "+237695607089"
        
        # Message SMS raccourci (limite 160 caractères)
        sms_message = f"🚨 MPU Christian: {alert['type']} - {alert['message'][:80]}... Tel: {phone_number}"
        
        # Tentatives avec différents formats et configurations
        sms_attempts = [
            # Tentative 1: SMS direct simple
            {"phone": phone_number, "message": sms_message},
            
            # Tentative 2: Format international alternatif
            {"phone": "237695607089", "message": sms_message},
            
            # Tentative 3: Message encore plus court
            {"phone": phone_number, "message": f"ALERTE MPU: {alert['type']}"},
            
            # Tentative 4: Format avec espaces
            {"phone": "+237 695 607 089", "message": f"MPU Alert: {alert['type']}"}
        ]
        
        for i, attempt in enumerate(sms_attempts, 1):
            try:
                # Configuration SMS optimale pour le Cameroun
                response = self.sns_client.publish(
                    PhoneNumber=attempt["phone"],
                    Message=attempt["message"],
                    MessageAttributes={
                        'AWS.SNS.SMS.SMSType': {
                            'DataType': 'String',
                            'StringValue': 'Transactional'
                        },
                        'AWS.SNS.SMS.MaxPrice': {
                            'DataType': 'String', 
                            'StringValue': '1.00'  # Prix max par SMS
                        }
                    }
                )
                
                logger.info(f"📱 SMS Cameroun envoyé (tentative {i}): {response['MessageId']}")
                logger.info(f"   Format: {attempt['phone']}")
                return True  # Succès, arrêter les tentatives
                
            except Exception as e:
                logger.warning(f"⚠️ SMS tentative {i} échouée ({attempt['phone']}): {e}")
                
                # Si c'est la dernière tentative, essayer via service tiers
                if i == len(sms_attempts):
                    await self._send_sms_alternative_service(alert, phone_number)
        
        return False

    async def _send_sms_alternative_service(self, alert: Dict, phone_number: str):
        """Service SMS alternatif si AWS SNS échoue pour le Cameroun"""
        
        try:
            # Log de l'échec pour dépannage
            logger.error(f"❌ Tous les tentatives SMS AWS ont échoué pour {phone_number}")
            logger.info(f"💡 Solutions alternatives:")
            logger.info(f"   1. Email: Fonctionne sur christianouragan@gmail.com")
            logger.info(f"   2. S3: Toutes les alertes sauvegardées")
            logger.info(f"   3. Console: Alertes visibles en temps réel")
            
            # Créer un fichier spécial pour les SMS ratés
            failed_sms_alert = {
                **alert,
                'sms_failure': True,
                'phone_number': phone_number,
                'failure_reason': 'AWS SNS limitations for Cameroon (+237)',
                'alternatives_active': ['email', 's3_storage', 'console_logs'],
                'recommendation': 'Check email or S3 for all alerts'
            }
            
            # Sauvegarder l'alerte SMS ratée
            now = datetime.now(timezone.utc)
            s3_key = f"alerts/failed_sms/year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}/failed_sms_{int(now.timestamp() * 1000)}.json"
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(failed_sms_alert, indent=2),
                ContentType='application/json',
                Metadata={
                    'alert_type': 'FAILED_SMS',
                    'phone_number': phone_number,
                    'original_severity': alert['severity']
                }
            )
            
            logger.info(f"📁 SMS raté archivé: s3://{self.bucket_name}/{s3_key}")
            
        except Exception as e:
            logger.error(f"❌ Erreur service SMS alternatif: {e}")

    async def _store_alert_s3(self, alert: Dict):
        """Stocke l'alerte dans S3 pour audit"""
        
        try:
            # CORRECTION: Utiliser timezone.utc explicitement pour éviter les problèmes de fuseau horaire
            now = datetime.now(timezone.utc)
            s3_key = f"alerts/mpu_christian/year={now.year}/month={now.month:02d}/day={now.day:02d}/hour={now.hour:02d}/alert_{int(now.timestamp() * 1000)}.json"
            
            # Log pour vérification du timestamp correct
            logger.info(f"📅 Alert timestamp UTC: {now} → day={now.day}")

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=json.dumps(alert, indent=2),
                ContentType='application/json',
                Metadata={
                    'alert_type': alert['type'],
                    'severity': alert['severity'],
                    'device_id': self.device_id
                }
            )
            
            logger.info(f"💾 Alerte stockée: s3://{self.bucket_name}/{s3_key}")
            
        except Exception as e:
            logger.error(f"❌ Erreur stockage S3 alerte: {e}")

    def _update_history(self, data: Dict):
        """Met à jour l'historique des données"""
        
        # Ajouter les nouvelles données
        self.data_history.append(data)
        
        # Garder seulement les N derniers échantillons
        if len(self.data_history) > self.max_history:
            self.data_history.pop(0)

    async def _monitoring_task(self):
        """Tâche de monitoring périodique"""
        
        while self.is_running:
            await asyncio.sleep(60)  # Toutes les minutes
            
            logger.info(f"📊 STATUS - Traités: {self.processed_count}, Alertes: {self.alerts_sent}")

    def stop_processing(self):
        """Arrête le traitement"""
        logger.info("🛑 Arrêt du traitement demandé")
        self.is_running = False

async def main():
    """Point d'entrée principal"""
    
    processor = MPURealtimeAlertProcessor()
    
    try:
        logger.info("🚀 DÉMARRAGE PROCESSEUR TEMPS RÉEL AVEC ALERTES MPU CHRISTIAN")
        logger.info("📡 Surveillance du stream Kinesis pour alertes temps réel")
        
        await processor.start_processing()
        
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par utilisateur")
        processor.stop_processing()
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
