"""
Service de Notifications AWS pour Alertes Médicales IoT
Gère l'envoi de SMS et emails via Amazon SNS et SES
"""

import boto3
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
from botocore.exceptions import ClientError, BotoCoreError

class NotificationType(Enum):
    SMS = "SMS"
    EMAIL = "EMAIL"
    BOTH = "BOTH"

class NotificationUrgency(Enum):
    IMMEDIATE = "IMMEDIATE"  # < 2 minutes
    URGENT = "URGENT"       # < 5 minutes
    HIGH = "HIGH"           # < 15 minutes
    NORMAL = "NORMAL"       # < 30 minutes

@dataclass
class NotificationRecipient:
    """Destinataire de notification"""
    name: str
    phone: str
    email: str
    role: str  # médecin, infirmière, famille, urgence
    notification_types: List[NotificationType]
    severity_threshold: str  # LOW, MEDIUM, HIGH, CRITICAL

@dataclass
class NotificationTemplate:
    """Template de notification"""
    template_id: str
    subject_template: str
    sms_template: str
    email_template: str
    urgency: NotificationUrgency

class AWSNotificationService:
    """Service principal de notifications AWS"""

    def __init__(self, aws_region: str = 'eu-west-1'):
        self.aws_region = aws_region
        self.logger = logging.getLogger(__name__)

        # Initialisation des clients AWS
        self.sns_client = None
        self.ses_client = None

        # Configuration des topics SNS
        self.sns_topics = {
            'critical_alerts': None,
            'high_alerts': None,
            'medium_alerts': None,
            'system_notifications': None
        }

        # Configuration SES
        self.ses_sender_email = "christianmomojunior@gmail.com"
        self.ses_configuration_set = "kidjamo-alerts"

        # Templates de notification
        self.notification_templates = self._initialize_templates()

        # Destinataires par défaut
        self.default_recipients = self._load_default_recipients()

        # Métriques
        self.metrics = {
            'sms_sent': 0,
            'emails_sent': 0,
            'failures': 0,
            'last_notification': None
        }

    def _initialize_templates(self) -> Dict[str, NotificationTemplate]:
        """Initialise les templates de notification"""
        return {
            'critical_emergency': NotificationTemplate(
                template_id='critical_emergency',
                subject_template='🚨 URGENCE MÉDICALE - Patient {patient_id}',
                sms_template='URGENCE: Patient {patient_id} - {alert_type} - {message}. Intervention IMMÉDIATE requise.',
                email_template='''
ALERTE CRITIQUE - INTERVENTION IMMÉDIATE REQUISE

Patient: {patient_id}
Appareil: {device_id}
Heure: {timestamp}
Type d'alerte: {alert_type}
Gravité: {severity}

DÉTAILS:
{message}

SIGNES VITAUX:
- Fréquence cardiaque: {freq_card} bpm
- SpO2: {spo2_pct}%
- Température corporelle: {temp_corp}°C
- Fréquence respiratoire: {freq_resp} /min

CONTEXTE MÉDICAL:
{medical_context}

ACTION RECOMMANDÉE:
{recommended_action}

Score de corrélation: {correlation_score}%

⚠️ Cette alerte nécessite une intervention médicale immédiate.
                ''',
                urgency=NotificationUrgency.IMMEDIATE
            ),

            'high_priority': NotificationTemplate(
                template_id='high_priority',
                subject_template='⚠️ Alerte Prioritaire - Patient {patient_id}',
                sms_template='ALERTE: Patient {patient_id} - {alert_type}. Évaluation requise dans les 15 min.',
                email_template='''
ALERTE PRIORITAIRE

Patient: {patient_id}
Appareil: {device_id}
Heure: {timestamp}
Type d'alerte: {alert_type}
Gravité: {severity}

DÉTAILS:
{message}

SIGNES VITAUX ACTUELS:
- Fréquence cardiaque: {freq_card} bpm
- SpO2: {spo2_pct}%
- Température corporelle: {temp_corp}°C
- Fréquence respiratoire: {freq_resp} /min

CONTEXTE MÉDICAL:
{medical_context}

ACTION RECOMMANDÉE:
{recommended_action}

Veuillez évaluer le patient dans les 15 minutes.
                ''',
                urgency=NotificationUrgency.HIGH
            ),

            'medium_alert': NotificationTemplate(
                template_id='medium_alert',
                subject_template='📊 Alerte Médicale - Patient {patient_id}',
                sms_template='Alert: Patient {patient_id} - {alert_type}. Surveillance renforcée recommandée.',
                email_template='''
ALERTE MÉDICALE

Patient: {patient_id}
Appareil: {device_id}
Heure: {timestamp}
Type d'alerte: {alert_type}
Gravité: {severity}

DÉTAILS:
{message}

SIGNES VITAUX:
- Fréquence cardiaque: {freq_card} bpm
- SpO2: {spo2_pct}%
- Température corporelle: {temp_corp}°C
- Fréquence respiratoire: {freq_resp} /min

CONTEXTE MÉDICAL:
{medical_context}

Surveillance renforcée recommandée.
                ''',
                urgency=NotificationUrgency.NORMAL
            )
        }

    def _load_default_recipients(self) -> List[NotificationRecipient]:
        """Charge les destinataires par défaut"""
        return [
            NotificationRecipient(
                name="Dr. Urgences",
                phone="+237695607089",
                email="christianmomojunior@gmail.com",
                role="urgence",
                notification_types=[NotificationType.BOTH],
                severity_threshold="CRITICAL"
            ),
            NotificationRecipient(
                name="Équipe Soignante",
                phone="+33123456790",
                email="christianmomojunior@gmail.com",
                role="infirmière",
                notification_types=[NotificationType.EMAIL],
                severity_threshold="HIGH"
            ),
            NotificationRecipient(
                name="Système de Monitoring",
                phone="",
                email="christianmomojunior@gmail.com",
                role="système",
                notification_types=[NotificationType.EMAIL],
                severity_threshold="MEDIUM"
            )
        ]

    async def initialize_aws_services(self):
        """Initialise les services AWS"""
        try:
            self.logger.info("Initialisation des services AWS...")

            # Initialiser les clients AWS
            self.sns_client = boto3.client('sns', region_name=self.aws_region)
            self.ses_client = boto3.client('ses', region_name=self.aws_region)

            # Vérifier les configurations
            await self.verify_ses_configuration()
            await self.create_sns_topics()

            self.logger.info("Services AWS initialisés avec succès")

        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation AWS: {e}")
            raise

    async def verify_ses_configuration(self):
        """Vérifie la configuration SES"""
        try:
            # Vérifier le statut de vérification de l'email
            response = self.ses_client.get_send_quota()
            self.logger.info(f"Quota SES: {response['Max24HourSend']} emails/24h")

            # Vérifier les adresses vérifiées
            verified_emails = self.ses_client.list_verified_email_addresses()
            if self.ses_sender_email not in verified_emails['VerifiedEmailAddresses']:
                self.logger.warning(f"Email {self.ses_sender_email} non vérifié dans SES")

        except ClientError as e:
            self.logger.error(f"Erreur de configuration SES: {e}")
            raise

    async def create_sns_topics(self):
        """Crée les topics SNS nécessaires"""
        try:
            for topic_name in self.sns_topics.keys():
                full_topic_name = f"kidjamo-{topic_name}"

                response = self.sns_client.create_topic(Name=full_topic_name)
                topic_arn = response['TopicArn']
                self.sns_topics[topic_name] = topic_arn

                self.logger.info(f"Topic SNS créé: {full_topic_name} -> {topic_arn}")

                # Configurer les attributs du topic
                self.sns_client.set_topic_attributes(
                    TopicArn=topic_arn,
                    AttributeName='DisplayName',
                    AttributeValue=f'KidJamo {topic_name.replace("_", " ").title()}'
                )

        except ClientError as e:
            self.logger.error(f"Erreur lors de la création des topics SNS: {e}")
            raise

    async def send_alert_notification(self, alert):
        """Envoie une notification d'alerte"""
        try:
            # Déterminer le template approprié
            template = self._select_template(alert.severity.value)

            # Déterminer les destinataires
            recipients = self._get_recipients_for_severity(alert.severity.value)

            if not recipients:
                self.logger.warning(f"Aucun destinataire trouvé pour l'alerte {alert.alert_id}")
                return

            # Préparer les données pour le template
            template_data = self._prepare_template_data(alert)

            # Envoyer les notifications
            notification_tasks = []

            for recipient in recipients:
                if NotificationType.SMS in recipient.notification_types or NotificationType.BOTH in recipient.notification_types:
                    if recipient.phone:
                        task = self._send_sms_notification(recipient, template, template_data)
                        notification_tasks.append(task)

                if NotificationType.EMAIL in recipient.notification_types or NotificationType.BOTH in recipient.notification_types:
                    if recipient.email:
                        task = self._send_email_notification(recipient, template, template_data)
                        notification_tasks.append(task)

            # Exécuter toutes les notifications en parallèle
            if notification_tasks:
                results = await asyncio.gather(*notification_tasks, return_exceptions=True)

                # Compter les succès et échecs
                success_count = sum(1 for r in results if r is True)
                error_count = len(results) - success_count

                self.logger.info(f"Alerte {alert.alert_id}: {success_count} notifications envoyées, {error_count} échecs")

                # Mettre à jour les métriques
                self.metrics['last_notification'] = datetime.now()

        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de notification: {e}")
            self.metrics['failures'] += 1

    def _select_template(self, severity: str) -> NotificationTemplate:
        """Sélectionne le template approprié selon la gravité"""
        if severity == "CRITICAL":
            return self.notification_templates['critical_emergency']
        elif severity == "HIGH":
            return self.notification_templates['high_priority']
        else:
            return self.notification_templates['medium_alert']

    def _get_recipients_for_severity(self, severity: str) -> List[NotificationRecipient]:
        """Retourne les destinataires appropriés selon la gravité"""
        severity_hierarchy = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
        alert_level = severity_hierarchy.get(severity, 1)

        recipients = []
        for recipient in self.default_recipients:
            threshold_level = severity_hierarchy.get(recipient.severity_threshold, 1)
            if alert_level >= threshold_level:
                recipients.append(recipient)

        return recipients

    def _prepare_template_data(self, alert) -> Dict:
        """Prépare les données pour le template"""
        vitals = alert.vitals_snapshot

        return {
            'patient_id': alert.patient_id,
            'device_id': alert.device_id,
            'timestamp': alert.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'alert_type': alert.alert_type.value if hasattr(alert.alert_type, 'value') else str(alert.alert_type),
            'severity': alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity),
            'message': getattr(alert, 'message', 'Alerte médicale détectée'),
            'freq_card': vitals.get('freq_card', 'N/A'),
            'spo2_pct': vitals.get('spo2_pct', 'N/A'),
            'temp_corp': vitals.get('temp_corp', 'N/A'),
            'freq_resp': vitals.get('freq_resp', 'N/A'),
            'medical_context': getattr(alert, 'medical_context', 'Contexte médical non disponible'),
            'recommended_action': getattr(alert, 'recommended_action', 'Évaluation médicale recommandée'),
            'correlation_score': getattr(alert, 'correlation_score', 0)
        }

    async def _send_sms_notification(self, recipient: NotificationRecipient,
                                   template: NotificationTemplate,
                                   data: Dict) -> bool:
        """Envoie une notification SMS"""
        try:
            message = template.sms_template.format(**data)

            # Limiter la taille du SMS (160 caractères standard)
            if len(message) > 160:
                message = message[:157] + "..."

            # Sélectionner le topic approprié
            topic_arn = self._get_topic_for_severity(data['severity'])

            response = self.sns_client.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject=f"Alerte {data['severity']}",
                MessageAttributes={
                    'recipient_role': {
                        'DataType': 'String',
                        'StringValue': recipient.role
                    },
                    'alert_severity': {
                        'DataType': 'String',
                        'StringValue': data['severity']
                    }
                }
            )

            self.logger.info(f"SMS envoyé à {recipient.name} ({recipient.phone})")
            self.metrics['sms_sent'] += 1
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi SMS à {recipient.name}: {e}")
            return False

    async def _send_email_notification(self, recipient: NotificationRecipient,
                                     template: NotificationTemplate,
                                     data: Dict) -> bool:
        """Envoie une notification email"""
        try:
            subject = template.subject_template.format(**data)
            body = template.email_template.format(**data)

            response = self.ses_client.send_email(
                Source=self.ses_sender_email,
                Destination={
                    'ToAddresses': [recipient.email]
                },
                Message={
                    'Subject': {
                        'Data': subject,
                        'Charset': 'UTF-8'
                    },
                    'Body': {
                        'Text': {
                            'Data': body,
                            'Charset': 'UTF-8'
                        }
                    }
                },
                ConfigurationSetName=self.ses_configuration_set,
                Tags=[
                    {
                        'Name': 'AlertType',
                        'Value': data['alert_type']
                    },
                    {
                        'Name': 'Severity',
                        'Value': data['severity']
                    },
                    {
                        'Name': 'PatientId',
                        'Value': data['patient_id']
                    }
                ]
            )

            self.logger.info(f"Email envoyé à {recipient.name} ({recipient.email})")
            self.metrics['emails_sent'] += 1
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi email à {recipient.name}: {e}")
            return False

    def _get_topic_for_severity(self, severity: str) -> str:
        """Retourne le topic SNS approprié selon la gravité"""
        severity_to_topic = {
            'CRITICAL': 'critical_alerts',
            'HIGH': 'high_alerts',
            'MEDIUM': 'medium_alerts',
            'LOW': 'medium_alerts'
        }

        topic_key = severity_to_topic.get(severity, 'medium_alerts')
        return self.sns_topics[topic_key]

    async def subscribe_phone_to_topic(self, phone_number: str, severity_level: str = 'HIGH'):
        """Abonne un numéro de téléphone à un topic SNS"""
        try:
            topic_key = f"{severity_level.lower()}_alerts"
            topic_arn = self.sns_topics.get(topic_key)

            if not topic_arn:
                self.logger.error(f"Topic non trouvé: {topic_key}")
                return False

            response = self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol='sms',
                Endpoint=phone_number
            )

            self.logger.info(f"Numéro {phone_number} abonné au topic {topic_key}")
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors de l'abonnement SMS: {e}")
            return False

    async def subscribe_email_to_topic(self, email: str, severity_level: str = 'MEDIUM'):
        """Abonne une adresse email à un topic SNS"""
        try:
            topic_key = f"{severity_level.lower()}_alerts"
            topic_arn = self.sns_topics.get(topic_key)

            if not topic_arn:
                self.logger.error(f"Topic non trouvé: {topic_key}")
                return False

            response = self.sns_client.subscribe(
                TopicArn=topic_arn,
                Protocol='email',
                Endpoint=email
            )

            self.logger.info(f"Email {email} abonné au topic {topic_key}")
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors de l'abonnement email: {e}")
            return False

    async def send_test_notification(self, recipient_type: str = "email"):
        """Envoie une notification de test"""
        try:
            test_alert = type('TestAlert', (), {
                'alert_id': 'TEST_001',
                'patient_id': 'PATIENT_TEST',
                'device_id': 'DEVICE_TEST',
                'severity': type('MockSeverity', (), {'value': 'HIGH'})(),
                'alert_type': type('MockType', (), {'value': 'TEST'})(),
                'vitals_snapshot': {
                    'freq_card': 75,
                    'spo2_pct': 98,
                    'temp_corp': 36.5,
                    'freq_resp': 16
                },
                'medical_context': 'Test du système de notifications',
                'recommended_action': 'Aucune action requise - Test système',
                'created_at': datetime.now(),
                'correlation_score': 95
            })()

            await self.send_alert_notification(test_alert)
            self.logger.info("Notification de test envoyée")

        except Exception as e:
            self.logger.error(f"Erreur lors du test de notification: {e}")

    def get_metrics(self) -> Dict:
        """Retourne les métriques du service de notifications"""
        return {
            'sms_sent': self.metrics['sms_sent'],
            'emails_sent': self.metrics['emails_sent'],
            'failures': self.metrics['failures'],
            'last_notification': self.metrics['last_notification'].isoformat() if self.metrics['last_notification'] else None,
            'topics_configured': len([t for t in self.sns_topics.values() if t is not None]),
            'recipients_count': len(self.default_recipients)
        }

    async def add_recipient(self, recipient: NotificationRecipient):
        """Ajoute un nouveau destinataire"""
        self.default_recipients.append(recipient)
        self.logger.info(f"Nouveau destinataire ajouté: {recipient.name} ({recipient.role})")

    async def remove_recipient(self, name: str):
        """Supprime un destinataire"""
        self.default_recipients = [r for r in self.default_recipients if r.name != name]
        self.logger.info(f"Destinataire supprimé: {name}")

    def __del__(self):
        """Nettoyage lors de la destruction de l'objet"""
        self.logger.info("Service de notifications AWS fermé")

