"""
Configuration AWS pour les Notifications
Paramètres pour SNS (SMS) et SES (Email)
"""

import os
from typing import Dict

class AWSConfig:
    """Configuration AWS pour les services de notification"""

    def __init__(self, test_mode: bool = False):
        # Mode test pour éviter les appels AWS réels
        self.test_mode = test_mode

        # Région AWS par défaut
        self.region = os.getenv('AWS_REGION', 'eu-west-1')

        # Configuration SNS pour SMS
        self.sns_config = {
            'region_name': self.region,
            'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'sender_id': 'KidJamo',
            'sms_type': 'Transactional'
        }

        # Configuration SES pour Email
        self.ses_config = {
            'region_name': self.region,
            'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
            'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
            'source_email': 'alerts@kidjamo-health.com',
            'reply_to_email': 'noreply@kidjamo-health.com'
        }

        # Topics SNS par niveau d'urgence
        self.sns_topics = {
            'CRITICAL': f'arn:aws:sns:{self.region}:account:kidjamo-critical-alerts',
            'HIGH': f'arn:aws:sns:{self.region}:account:kidjamo-high-alerts',
            'MEDIUM': f'arn:aws:sns:{self.region}:account:kidjamo-medium-alerts',
            'LOW': f'arn:aws:sns:{self.region}:account:kidjamo-low-alerts'
        }

        # Configuration des destinataires par défaut
        self.default_recipients = {
            'CRITICAL': [
                {
                    'name': 'Dr. Urgences',
                    'phone': '+33123456789',
                    'email': 'urgences@kidjamo-health.com',
                    'role': 'médecin_urgences'
                }
            ],
            'HIGH': [
                {
                    'name': 'Équipe Soignante',
                    'phone': '+33123456790',
                    'email': 'equipe@kidjamo-health.com',
                    'role': 'infirmière'
                }
            ],
            'MEDIUM': [
                {
                    'name': 'Surveillance',
                    'phone': '',
                    'email': 'monitoring@kidjamo-health.com',
                    'role': 'système'
                }
            ]
        }

    def validate_configuration(self) -> Dict:
        """Valide la configuration AWS"""
        errors = []
        warnings = []

        if self.test_mode:
            # En mode test, on simule une configuration valide
            return {
                'valid': True,
                'errors': [],
                'warnings': ['Mode test activé - configuration AWS simulée']
            }

        # Vérifier les clés AWS
        if not self.sns_config['aws_access_key_id']:
            errors.append('AWS_ACCESS_KEY_ID manquant')

        if not self.sns_config['aws_secret_access_key']:
            errors.append('AWS_SECRET_ACCESS_KEY manquant')

        # Vérifier la région
        if not self.region:
            warnings.append('Région AWS non définie, utilisation de eu-west-1 par défaut')

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }

    def get_notification_config(self, alert_severity: str) -> Dict:
        """Retourne la configuration de notification pour une gravité donnée"""
        return {
            'sns_topic': self.sns_topics.get(alert_severity, self.sns_topics['MEDIUM']),
            'recipients': self.default_recipients.get(alert_severity, []),
            'region': self.region
        }
