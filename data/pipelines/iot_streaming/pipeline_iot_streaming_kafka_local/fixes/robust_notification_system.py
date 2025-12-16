"""
Fix for Twilio SMS Rate Limiting and Email Configuration Issues

This creates a robust notification system with fallback mechanisms when external services fail.
"""

import logging
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

class RobustNotificationService:
    """Notification service with fallback mechanisms and rate limiting"""

    def __init__(self):
        self.sms_enabled = True
        self.email_enabled = True
        self.sms_quota_exceeded = False
        self.email_connection_failed = False

        # Rate limiting
        self.notification_history = {}
        self.max_notifications_per_hour = 50

        # Fallback storage for failed notifications
        self.failed_notifications = []

    def send_alert_notification(self, alert: Dict[str, Any], patient_info: Dict[str, Any]) -> bool:
        """Send notification with intelligent fallback system"""

        # Check rate limiting
        if not self._check_rate_limit(alert['patient_id'], alert['alert_type']):
            logger.warning(f"⚠️ Rate limit exceeded for {alert['alert_type']} - {patient_info.get('name', 'Unknown')}")
            return False

        notification_success = False

        # Try SMS first for critical alerts
        if alert['severity'] == 'critical' and self.sms_enabled and not self.sms_quota_exceeded:
            try:
                success = self._send_sms_safe(alert, patient_info)
                if success:
                    notification_success = True
                    logger.info(f"📱 SMS envoyé avec succès - {alert['title']}")
                else:
                    self.sms_quota_exceeded = True
                    logger.warning("📱 Quota SMS épuisé - Basculement vers alternatives")
            except Exception as e:
                logger.error(f"❌ Erreur SMS: {e}")
                self.sms_enabled = False

        # Try email as backup or primary method
        if self.email_enabled and not self.email_connection_failed:
            try:
                success = self._send_email_safe(alert, patient_info)
                if success:
                    notification_success = True
                    logger.info(f"📧 Email envoyé avec succès - {alert['title']}")
                else:
                    self.email_connection_failed = True
                    logger.warning("📧 Connexion email échouée - Basculement vers alternatives")
            except Exception as e:
                logger.error(f"❌ Erreur Email: {e}")
                self.email_enabled = False

        # Fallback: Log to file and console for critical alerts
        if not notification_success:
            self._log_notification_fallback(alert, patient_info)
            notification_success = True

        # Record notification attempt
        self._record_notification(alert['patient_id'], alert['alert_type'])

        return notification_success

    def _send_sms_safe(self, alert: Dict[str, Any], patient_info: Dict[str, Any]) -> bool:
        """Safe SMS sending with quota detection"""
        try:
            if not TWILIO_AVAILABLE:
                return False

            from twilio.rest import Client
            client = Client(TWILIO_CONFIG['account_sid'], TWILIO_CONFIG['auth_token'])

            message_body = self._format_sms_message(alert, patient_info)

            message = client.messages.create(
                body=message_body,
                from_=TWILIO_CONFIG['from_number'],
                to=TWILIO_CONFIG['to_number']
            )

            return True

        except Exception as e:
            error_str = str(e)
            # Detect quota exceeded
            if "exceeded" in error_str.lower() or "limit" in error_str.lower():
                self.sms_quota_exceeded = True
                logger.warning("📱 Quota SMS Twilio épuisé")
            return False

    def _send_email_safe(self, alert: Dict[str, Any], patient_info: Dict[str, Any]) -> bool:
        """Safe email sending with connection retry"""
        try:
            # Use simple SMTP with Gmail or fallback
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🚨 ALERTE KIDJAMO - {alert['title']}"
            msg['From'] = "kidjamo-system@localhost"  # Fallback sender
            msg['To'] = "admin@localhost"  # Fallback recipient

            # Create message body
            html_body = self._format_email_message(alert, patient_info)
            msg.attach(MIMEText(html_body, 'html'))

            # Try local SMTP first (if available), then external
            try:
                # Local SMTP server
                with smtplib.SMTP('localhost', 25) as server:
                    server.send_message(msg)
                    return True
            except:
                # Try external SMTP with fallback configuration
                try:
                    with smtplib.SMTP('smtp.gmail.com', 587) as server:
                        server.starttls()
                        # Use app-specific password if available
                        if EMAIL_CONFIG.get('password'):
                            server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
                        server.send_message(msg)
                        return True
                except:
                    return False

        except Exception as e:
            logger.error(f"❌ Erreur email: {e}")
            return False

    def _log_notification_fallback(self, alert: Dict[str, Any], patient_info: Dict[str, Any]):
        """Fallback logging when all notification methods fail"""

        # Log to console with visual emphasis
        print("\n" + "="*80)
        print("🚨 ALERTE CRITIQUE - NOTIFICATION MANUELLE REQUISE 🚨")
        print("="*80)
        print(f"⏰ Heure: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"👤 Patient: {patient_info.get('name', 'Inconnu')}")
        print(f"🆔 ID Patient: {alert['patient_id']}")
        print(f"🔴 Type: {alert['alert_type']}")
        print(f"⚠️ Sévérité: {alert['severity'].upper()}")
        print(f"📋 Titre: {alert['title']}")
        print(f"💬 Message: {alert['message']}")

        if alert.get('vitals_snapshot'):
            print("\n📊 Signes vitaux:")
            for vital, value in alert['vitals_snapshot'].items():
                if value is not None:
                    print(f"   • {vital}: {value}")

        if alert.get('suggested_actions'):
            print("\n🎯 Actions suggérées:")
            for action in alert['suggested_actions']:
                print(f"   • {action}")

        print("="*80)
        print("⚠️ Vérifiez configuration SMS/Email pour notifications automatiques")
        print("="*80 + "\n")

        # Log to file
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'alert': alert,
            'patient_info': patient_info,
            'notification_methods_failed': {
                'sms_quota_exceeded': self.sms_quota_exceeded,
                'email_connection_failed': self.email_connection_failed
            }
        }

        # Create alerts log directory
        os.makedirs('logs/alerts', exist_ok=True)

        # Write to daily log file
        log_file = f"logs/alerts/critical_alerts_{datetime.now().strftime('%Y%m%d')}.json"

        try:
            # Read existing logs
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except FileNotFoundError:
                logs = []

            # Add new log
            logs.append(log_entry)

            # Write back
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)

            logger.warning(f"📝 Alerte critique sauvegardée: {log_file}")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde log: {e}")

    def _format_sms_message(self, alert: Dict[str, Any], patient_info: Dict[str, Any]) -> str:
        """Format SMS message (160 char limit)"""
        patient_name = patient_info.get('name', 'Patient')[:15]
        severity_emoji = "🚨" if alert['severity'] == 'critical' else "⚠️"

        message = f"{severity_emoji} KIDJAMO: {patient_name} - {alert['title'][:50]}"

        # Add key vital if available
        vitals = alert.get('vitals_snapshot', {})
        if vitals.get('spo2'):
            message += f" SpO2:{vitals['spo2']}%"
        elif vitals.get('heart_rate'):
            message += f" FC:{vitals['heart_rate']}"

        return message[:160]  # SMS limit

    def _format_email_message(self, alert: Dict[str, Any], patient_info: Dict[str, Any]) -> str:
        """Format HTML email message"""
        severity_color = "#dc3545" if alert['severity'] == 'critical' else "#fd7e14"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .alert-header {{ background-color: {severity_color}; color: white; padding: 15px; border-radius: 5px; }}
                .patient-info {{ background-color: #f8f9fa; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                .vitals {{ background-color: #e9ecef; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                .actions {{ background-color: #d1ecf1; padding: 10px; margin: 10px 0; border-radius: 5px; }}
                ul {{ margin: 0; padding-left: 20px; }}
            </style>
        </head>
        <body>
            <div class="alert-header">
                <h2>🚨 ALERTE KIDJAMO - {alert['title']}</h2>
                <p><strong>Sévérité:</strong> {alert['severity'].upper()}</p>
                <p><strong>Heure:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="patient-info">
                <h3>👤 Informations Patient</h3>
                <p><strong>Nom:</strong> {patient_info.get('name', 'Inconnu')}</p>
                <p><strong>ID:</strong> {alert['patient_id']}</p>
                <p><strong>Génotype:</strong> {patient_info.get('genotype', 'N/A')}</p>
            </div>
            
            <div>
                <h3>📋 Description</h3>
                <p>{alert['message']}</p>
            </div>
        """

        # Add vitals if available
        if alert.get('vitals_snapshot'):
            html += """
            <div class="vitals">
                <h3>📊 Signes Vitaux</h3>
                <ul>
            """
            for vital, value in alert['vitals_snapshot'].items():
                if value is not None:
                    html += f"<li><strong>{vital}:</strong> {value}</li>"
            html += "</ul></div>"

        # Add suggested actions
        if alert.get('suggested_actions'):
            html += """
            <div class="actions">
                <h3>🎯 Actions Suggérées</h3>
                <ul>
            """
            for action in alert['suggested_actions']:
                html += f"<li>{action}</li>"
            html += "</ul></div>"

        html += """
            <div style="margin-top: 20px; padding: 10px; background-color: #fff3cd; border-radius: 5px;">
                <p><small>⚠️ Cette alerte a été générée automatiquement par le système de surveillance IoT Kidjamo. 
                En cas de problème technique, contactez l'équipe support.</small></p>
            </div>
        </body>
        </html>
        """

        return html

    def _check_rate_limit(self, patient_id: str, alert_type: str) -> bool:
        """Check if notification rate limit is exceeded"""
        key = f"{patient_id}_{alert_type}"
        current_time = datetime.now()

        # Clean old entries (older than 1 hour)
        cutoff_time = current_time - timedelta(hours=1)
        self.notification_history = {
            k: v for k, v in self.notification_history.items()
            if v > cutoff_time
        }

        # Count recent notifications for this patient/alert type
        recent_count = sum(1 for k, v in self.notification_history.items()
                          if k.startswith(f"{patient_id}_") and v > cutoff_time)

        return recent_count < self.max_notifications_per_hour

    def _record_notification(self, patient_id: str, alert_type: str):
        """Record notification for rate limiting"""
        key = f"{patient_id}_{alert_type}_{datetime.now().timestamp()}"
        self.notification_history[key] = datetime.now()

    def get_notification_status(self) -> Dict[str, Any]:
        """Get current notification system status"""
        return {
            'sms_enabled': self.sms_enabled and not self.sms_quota_exceeded,
            'email_enabled': self.email_enabled and not self.email_connection_failed,
            'sms_quota_exceeded': self.sms_quota_exceeded,
            'email_connection_failed': self.email_connection_failed,
            'fallback_logging_active': True,
            'recent_notifications_count': len(self.notification_history)
        }

# Global instance
robust_notification_service = RobustNotificationService()
