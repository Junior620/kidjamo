"""
Service de Notifications Twilio pour Alertes Médicales IoT
Gère l'envoi de SMS via Twilio et emails via SendGrid
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio_config import TwilioConfig, TwilioRecipient

class TwilioNotificationService:
    """Service principal de notifications Twilio"""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.logger = logging.getLogger(__name__)

        # Configuration Twilio
        self.config = TwilioConfig(test_mode=test_mode)

        # Clients Twilio et SendGrid
        self.twilio_client = None
        self.sendgrid_client = None

        # Métriques
        self.metrics = {
            'sms_sent': 0,
            'emails_sent': 0,
            'sms_failures': 0,
            'email_failures': 0,
            'last_notification': None
        }

    async def initialize_services(self):
        """Initialise les services Twilio et SendGrid"""
        try:
            self.logger.info("Initialisation des services Twilio...")

            if not self.test_mode:
                # Initialiser le client Twilio pour SMS
                if self.config.twilio_config['account_sid'] and self.config.twilio_config['auth_token']:
                    self.twilio_client = Client(
                        self.config.twilio_config['account_sid'],
                        self.config.twilio_config['auth_token']
                    )
                    self.logger.info("Client Twilio initialisé")

                # Initialiser le client SendGrid pour emails
                if self.config.sendgrid_config['api_key']:
                    self.sendgrid_client = SendGridAPIClient(
                        api_key=self.config.sendgrid_config['api_key']
                    )
                    self.logger.info("Client SendGrid initialisé")
            else:
                self.logger.info("Mode test activé - clients Twilio/SendGrid simulés")

        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation Twilio: {e}")
            if not self.test_mode:
                raise

    async def send_alert_notification(self, alert):
        """Envoie une notification d'alerte via Twilio/SendGrid"""
        try:
            severity = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)

            # Obtenir les destinataires pour cette gravité
            recipients = self.config.get_recipients_for_severity(severity)

            if not recipients:
                self.logger.warning(f"Aucun destinataire trouvé pour la gravité {severity}")
                return

            # Préparer les données pour les templates
            template_data = self._prepare_template_data(alert)

            # Envoyer les notifications
            notification_tasks = []

            for recipient in recipients:
                # Envoyer SMS si numéro de téléphone disponible
                if recipient.phone and recipient.phone.strip():
                    task = self._send_sms_notification(recipient, severity, template_data)
                    notification_tasks.append(task)

                # Envoyer email si adresse email disponible
                if recipient.email and recipient.email.strip():
                    task = self._send_email_notification(recipient, severity, template_data)
                    notification_tasks.append(task)

            # Exécuter toutes les notifications en parallèle
            if notification_tasks:
                results = await asyncio.gather(*notification_tasks, return_exceptions=True)

                # Compter les succès et échecs
                success_count = sum(1 for r in results if r is True)
                error_count = len(results) - success_count

                self.logger.info(f"Alerte {template_data['alert_id']}: {success_count} notifications envoyées, {error_count} échecs")

                # Mettre à jour les métriques
                self.metrics['last_notification'] = datetime.now()

        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de notification Twilio: {e}")

    async def _send_sms_notification(self, recipient: TwilioRecipient, severity: str, data: Dict) -> bool:
        """Envoie une notification SMS via Twilio"""
        try:
            # Obtenir le template SMS
            sms_template = self.config.get_sms_template(severity)
            message_body = sms_template.format(**data)

            # Limiter la taille du SMS (160 caractères pour compatibilité)
            if len(message_body) > 160:
                message_body = message_body[:157] + "..."

            if self.test_mode:
                self.logger.info(f"[TEST] SMS à {recipient.name} ({recipient.phone}): {message_body}")
                self.metrics['sms_sent'] += 1
                return True

            if not self.twilio_client:
                self.logger.error("Client Twilio non initialisé")
                self.metrics['sms_failures'] += 1
                return False

            # Envoyer le SMS via Twilio
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=self.config.twilio_config['phone_number'],
                to=recipient.phone
            )

            self.logger.info(f"SMS envoyé à {recipient.name} ({recipient.phone}) - SID: {message.sid}")
            self.metrics['sms_sent'] += 1
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi SMS à {recipient.name}: {e}")
            self.metrics['sms_failures'] += 1
            return False

    async def _send_email_notification(self, recipient: TwilioRecipient, severity: str, data: Dict) -> bool:
        """Envoie une notification email via SendGrid"""
        try:
            # Obtenir les templates email
            email_templates = self.config.get_email_templates(severity)
            subject = email_templates['subject'].format(**data)
            body = email_templates['body'].format(**data)

            if self.test_mode:
                self.logger.info(f"[TEST] Email à {recipient.name} ({recipient.email}): {subject}")
                self.metrics['emails_sent'] += 1
                return True

            if not self.sendgrid_client:
                self.logger.error("Client SendGrid non initialisé")
                self.metrics['email_failures'] += 1
                return False

            # Créer l'email avec SendGrid (correction des custom_args)
            message = Mail(
                from_email=(
                    self.config.sendgrid_config['from_email'],
                    self.config.sendgrid_config['from_name']
                ),
                to_emails=recipient.email,
                subject=subject,
                plain_text_content=body
            )

            # Correction : Ajouter des métadonnées avec la méthode correcte
            try:
                message.add_custom_arg("alert_id", data['alert_id'])
                message.add_custom_arg("patient_id", data['patient_id'])
                message.add_custom_arg("severity", severity)
                message.add_custom_arg("recipient_role", recipient.role)
            except:
                # Si custom_args ne fonctionne pas, on continue sans
                pass

            # Envoyer l'email
            response = self.sendgrid_client.send(message)

            if response.status_code in [200, 202]:
                self.logger.info(f"Email envoyé à {recipient.name} ({recipient.email})")
                self.metrics['emails_sent'] += 1
                return True
            else:
                self.logger.error(f"Échec envoi email à {recipient.name}: {response.status_code}")
                self.metrics['email_failures'] += 1
                return False

        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi email à {recipient.name}: {e}")
            self.metrics['email_failures'] += 1
            return False

    def _prepare_template_data(self, alert) -> Dict:
        """Prépare les données pour les templates"""
        vitals = alert.vitals_snapshot if hasattr(alert, 'vitals_snapshot') else {}

        return {
            'alert_id': getattr(alert, 'alert_id', 'N/A'),
            'patient_id': getattr(alert, 'patient_id', 'N/A'),
            'device_id': getattr(alert, 'device_id', 'N/A'),
            'timestamp': getattr(alert, 'created_at', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'alert_type': alert.alert_type.value if hasattr(alert.alert_type, 'value') else str(getattr(alert, 'alert_type', 'N/A')),
            'severity': alert.severity.value if hasattr(alert.severity, 'value') else str(getattr(alert, 'severity', 'N/A')),
            'message': getattr(alert, 'message', 'Alerte médicale détectée'),
            'freq_card': vitals.get('freq_card', 'N/A'),
            'spo2_pct': vitals.get('spo2_pct', 'N/A'),
            'temp_corp': vitals.get('temp_corp', 'N/A'),
            'temp_ambiante': vitals.get('temp_ambiante', 'N/A'),
            'freq_resp': vitals.get('freq_resp', 'N/A'),
            'medical_context': getattr(alert, 'medical_context', 'Contexte médical non disponible'),
            'recommended_action': getattr(alert, 'recommended_action', 'Évaluation médicale recommandée'),
            'correlation_score': getattr(alert, 'correlation_score', 0)
        }

    async def send_test_notification(self, severity: str = "HIGH") -> bool:
        """Envoie une notification de test"""
        try:
            # Créer une alerte de test
            class TestAlert:
                def __init__(self):
                    self.alert_id = "TEST_TWILIO_001"
                    self.patient_id = "PATIENT_TEST"
                    self.device_id = "DEVICE_TEST"
                    self.severity = type('MockSeverity', (), {'value': severity})()
                    self.alert_type = type('MockType', (), {'value': 'TEST'})()
                    self.vitals_snapshot = {
                        'freq_card': 75,
                        'spo2_pct': 98,
                        'temp_corp': 36.5,
                        'temp_ambiante': 22.0,
                        'freq_resp': 16
                    }
                    self.medical_context = 'Test du système de notifications Twilio'
                    self.recommended_action = 'Aucune action requise - Test système'
                    self.created_at = datetime.now()
                    self.correlation_score = 95
                    self.message = 'Test de notification Twilio'

            test_alert = TestAlert()
            await self.send_alert_notification(test_alert)

            self.logger.info("Notification de test Twilio envoyée")
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors du test de notification Twilio: {e}")
            return False

    async def verify_configuration(self) -> Dict:
        """Vérifie la configuration Twilio/SendGrid"""
        validation = self.config.validate_configuration()

        # Test de connectivité en mode non-test
        if not self.test_mode and validation['valid']:
            try:
                if self.twilio_client:
                    # Vérifier la validité du compte Twilio
                    account = self.twilio_client.api.accounts(
                        self.config.twilio_config['account_sid']
                    ).fetch()
                    validation['twilio_account_status'] = account.status

                if self.sendgrid_client:
                    # Test simple SendGrid (pas d'API directe pour vérifier)
                    validation['sendgrid_configured'] = True

            except Exception as e:
                validation['connectivity_error'] = str(e)

        return validation

    def get_metrics(self) -> Dict:
        """Retourne les métriques du service de notifications"""
        return {
            'sms_sent': self.metrics['sms_sent'],
            'emails_sent': self.metrics['emails_sent'],
            'sms_failures': self.metrics['sms_failures'],
            'email_failures': self.metrics['email_failures'],
            'last_notification': self.metrics['last_notification'].isoformat() if self.metrics['last_notification'] else None,
            'total_notifications': self.metrics['sms_sent'] + self.metrics['emails_sent'],
            'total_failures': self.metrics['sms_failures'] + self.metrics['email_failures'],
            'success_rate': (
                (self.metrics['sms_sent'] + self.metrics['emails_sent']) /
                max(1, self.metrics['sms_sent'] + self.metrics['emails_sent'] +
                    self.metrics['sms_failures'] + self.metrics['email_failures'])
            ) * 100,
            'test_mode': self.test_mode
        }

    def add_recipient(self, severity: str, recipient: TwilioRecipient):
        """Ajoute un nouveau destinataire"""
        self.config.add_recipient(severity, recipient)
        self.logger.info(f"Nouveau destinataire ajouté: {recipient.name} ({recipient.role}) pour {severity}")

    def remove_recipient(self, severity: str, recipient_name: str):
        """Supprime un destinataire"""
        self.config.remove_recipient(severity, recipient_name)
        self.logger.info(f"Destinataire supprimé: {recipient_name} pour {severity}")

    def get_configuration_summary(self) -> Dict:
        """Retourne un résumé de la configuration"""
        return self.config.get_notification_summary()

    def __del__(self):
        """Nettoyage lors de la destruction de l'objet"""
        self.logger.info("Service de notifications Twilio fermé")
