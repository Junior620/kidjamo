"""
Configuration Twilio pour les Notifications SMS/Email
Alternative à AWS SNS/SES pour les alertes médicales
"""

import os
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class TwilioRecipient:
    """Destinataire de notification Twilio"""
    name: str
    phone: str
    email: str
    role: str
    severity_threshold: str

class TwilioConfig:
    """Configuration Twilio pour les services de notification"""

    def __init__(self, test_mode: bool = False):
        # Mode test pour éviter les appels Twilio réels
        self.test_mode = test_mode

        # Configuration Twilio SMS - UTILISER VARIABLES D'ENVIRONNEMENT
        self.twilio_config = {
            'account_sid': os.getenv('TWILIO_ACCOUNT_SID', ''),
            'auth_token': os.getenv('TWILIO_AUTH_TOKEN', ''),
            'phone_number': os.getenv('TWILIO_PHONE_NUMBER', ''),
            'messaging_service_sid': os.getenv('TWILIO_MESSAGING_SERVICE_SID', '')
        }

        # Configuration SendGrid pour les emails - UTILISER VARIABLES D'ENVIRONNEMENT
        self.sendgrid_config = {
            'api_key': os.getenv('SENDGRID_API_KEY', ''),
            'from_email': os.getenv('SENDGRID_FROM_EMAIL', 'support@kidjamo.app'),
            'from_name': 'KidJamo-team'
        }

        # Configuration des destinataires par défaut
        self.default_recipients = self._load_default_recipients()

        # Templates de messages
        self.message_templates = self._initialize_message_templates()

    def _load_default_recipients(self) -> Dict[str, List[TwilioRecipient]]:
        """Charge les destinataires par défaut"""
        return {
            'CRITICAL': [
                TwilioRecipient(
                    name='Dr. Urgences',
                    phone='+237695607089',
                    email='christianouragan@gmail.com',
                    role='médecin_urgences',
                    severity_threshold='CRITICAL'
                ),
                TwilioRecipient(
                    name='Équipe de Garde',
                    phone='+237695607089',
                    email='christianouragan@gmail.com',
                    role='infirmière_garde',
                    severity_threshold='CRITICAL'
                )
            ],
            'HIGH': [
                TwilioRecipient(
                    name='Équipe Soignante',
                    phone='+23795607089',
                    email='christianouragan@gmail.com',
                    role='infirmière',
                    severity_threshold='HIGH'
                ),
                TwilioRecipient(
                    name='Médecin Référent',
                    phone='+237695607089',
                    email='christianouragan@gmail.com',
                    role='médecin',
                    severity_threshold='HIGH'
                )
            ],
            'MEDIUM': [
                TwilioRecipient(
                    name='Supervision',
                    phone='',
                    email='support@kidjamo.app',
                    role='superviseur',
                    severity_threshold='MEDIUM'
                )
            ],
            'LOW': [
                TwilioRecipient(
                    name='Monitoring',
                    phone='',
                    email='support@kidjamo.app',
                    role='système',
                    severity_threshold='LOW'
                )
            ]
        }

    def _initialize_message_templates(self) -> Dict:
        """Initialise les templates de messages"""
        return {
            'sms_templates': {
                'CRITICAL': "🚨 URGENCE MÉDICALE - Patient {patient_id}: {message}. Intervention IMMÉDIATE requise. #{alert_id}",
                'HIGH': "⚠️ ALERTE PRIORITAIRE - Patient {patient_id}: {message}. Évaluation dans 15min. #{alert_id}",
                'MEDIUM': "📊 Alerte Médicale - Patient {patient_id}: {message}. Surveillance renforcée. #{alert_id}",
                'LOW': "ℹ️ Info Patient {patient_id}: {message}. #{alert_id}"
            },
            'email_templates': {
                'subject': {
                    'CRITICAL': '🚨 URGENCE MÉDICALE - Patient {patient_id}',
                    'HIGH': '⚠️ Alerte Prioritaire - Patient {patient_id}',
                    'MEDIUM': '📊 Alerte Médicale - Patient {patient_id}',
                    'LOW': 'ℹ️ Information Patient {patient_id}'
                },
                'body': {
                    'CRITICAL': '''
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
- Température ambiante: {temp_ambiante}°C
- Fréquence respiratoire: {freq_resp} /min

CONTEXTE MÉDICAL:
{medical_context}

ACTION RECOMMANDÉE:
{recommended_action}

Score de corrélation: {correlation_score}%

⚠️ Cette alerte nécessite une intervention médicale immédiate.

ID Alerte: {alert_id}
                    ''',
                    'HIGH': '''
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
- Température ambiante: {temp_ambiante}°C
- Fréquence respiratoire: {freq_resp} /min

CONTEXTE MÉDICAL:
{medical_context}

ACTION RECOMMANDÉE:
{recommended_action}

Veuillez évaluer le patient dans les 15 minutes.

ID Alerte: {alert_id}
                    ''',
                    'MEDIUM': '''
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
- Température ambiante: {temp_ambiante}°C
- Fréquence respiratoire: {freq_resp} /min

CONTEXTE MÉDICAL:
{medical_context}

Surveillance renforcée recommandée.

ID Alerte: {alert_id}
                    '''
                }
            }
        }

    def validate_configuration(self) -> Dict:
        """Valide la configuration Twilio"""
        errors = []
        warnings = []

        if self.test_mode:
            return {
                'valid': True,
                'errors': [],
                'warnings': ['Mode test activé - configuration Twilio simulée']
            }

        # Vérifier les paramètres Twilio SMS
        if not self.twilio_config['account_sid']:
            errors.append('TWILIO_ACCOUNT_SID manquant')

        if not self.twilio_config['auth_token']:
            errors.append('TWILIO_AUTH_TOKEN manquant')

        if not self.twilio_config['phone_number']:
            errors.append('TWILIO_PHONE_NUMBER manquant')

        # Vérifier SendGrid pour les emails
        if not self.sendgrid_config['api_key']:
            warnings.append('SENDGRID_API_KEY manquant - emails désactivés')

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def get_recipients_for_severity(self, severity: str) -> List[TwilioRecipient]:
        """Retourne les destinataires pour un niveau de gravité donné"""
        return self.default_recipients.get(severity, [])

    def get_sms_template(self, severity: str) -> str:
        """Retourne le template SMS pour une gravité donnée"""
        return self.message_templates['sms_templates'].get(
            severity,
            self.message_templates['sms_templates']['MEDIUM']
        )

    def get_email_templates(self, severity: str) -> Dict[str, str]:
        """Retourne les templates email (subject et body) pour une gravité donnée"""
        return {
            'subject': self.message_templates['email_templates']['subject'].get(
                severity,
                self.message_templates['email_templates']['subject']['MEDIUM']
            ),
            'body': self.message_templates['email_templates']['body'].get(
                severity,
                self.message_templates['email_templates']['body']['MEDIUM']
            )
        }

    def add_recipient(self, severity: str, recipient: TwilioRecipient):
        """Ajoute un destinataire pour un niveau de gravité"""
        if severity not in self.default_recipients:
            self.default_recipients[severity] = []
        self.default_recipients[severity].append(recipient)

    def remove_recipient(self, severity: str, recipient_name: str):
        """Supprime un destinataire"""
        if severity in self.default_recipients:
            self.default_recipients[severity] = [
                r for r in self.default_recipients[severity]
                if r.name != recipient_name
            ]

    def get_notification_summary(self) -> Dict:
        """Retourne un résumé de la configuration des notifications"""
        summary = {
            'twilio_configured': bool(self.twilio_config['account_sid'] and self.twilio_config['auth_token']),
            'sendgrid_configured': bool(self.sendgrid_config['api_key']),
            'total_recipients': sum(len(recipients) for recipients in self.default_recipients.values()),
            'recipients_by_severity': {
                severity: len(recipients)
                for severity, recipients in self.default_recipients.items()
            },
            'test_mode': self.test_mode
        }
        return summary
