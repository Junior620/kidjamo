"""
Test de Notifications Twilio RÉELLES
⚠️ ATTENTION: Ce script envoie de vraies notifications SMS/Email
"""

import asyncio
import logging
from datetime import datetime
from alert_orchestrator import AlertOrchestrator

# Configuration des logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_real_notifications():
    """Test avec vraies notifications Twilio (FRAIS APPLICABLES)"""

    print("""
    🚨 ATTENTION: TEST EN MODE PRODUCTION
    =====================================
    
    Ce test va envoyer de VRAIES notifications:
    📱 SMS via Twilio (+18317403115)
    📧 Email via SendGrid (support@kidjamo.app)
    
    Les destinataires configurés recevront:
    - Dr. Urgences: +237695607089 / christianouragan@gmail.com
    - Équipe de Garde: +237695607089 / christianouragan@gmail.com
    
    💰 FRAIS TWILIO/SENDGRID APPLICABLES
    
    """)

    # Demander confirmation
    response = input("Êtes-vous sûr de vouloir continuer ? (tapez 'OUI' pour confirmer): ")

    if response.upper() != 'OUI':
        print("❌ Test annulé par l'utilisateur")
        return False

    print("\n🚀 Démarrage du test en mode PRODUCTION...")

    # Configuration base de données
    db_config = {
        'host': 'localhost',
        'port': 5432,
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

    try:
        # Créer orchestrateur avec Twilio en MODE PRODUCTION
        orchestrator = AlertOrchestrator(db_config, use_twilio=True)
        orchestrator.set_test_mode(False)  # 🔴 MODE PRODUCTION - Vraies notifications

        # Initialiser
        print("📡 Initialisation du système Twilio...")
        await orchestrator.initialize()

        # Envoyer notification de test CRITIQUE
        print("📤 Envoi notification CRITIQUE en cours...")
        result = await orchestrator.send_test_notification("CRITICAL")

        if result:
            print("✅ Notification RÉELLE envoyée avec succès!")
            print("📱 Vérifiez votre téléphone pour le SMS")
            print("📧 Vérifiez votre email pour le message")

            # Afficher métriques
            metrics = orchestrator.get_notification_metrics()
            print(f"\n📊 Métriques:")
            print(f"   SMS envoyés: {metrics.get('sms_sent', 0)}")
            print(f"   Emails envoyés: {metrics.get('emails_sent', 0)}")
            print(f"   Échecs: {metrics.get('total_failures', 0)}")
            print(f"   Taux succès: {metrics.get('success_rate', 0):.1f}%")

        else:
            print("❌ Échec envoi notification")

    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

    return True

async def test_custom_notification():
    """Test avec destinataire personnalisé"""

    print("\n📱 Test avec votre propre numéro/email")
    phone = input("Entrez votre numéro (format: +33612345678): ").strip()
    email = input("Entrez votre email: ").strip()

    if not phone or not email:
        print("❌ Numéro ou email manquant")
        return False

    print(f"\n🎯 Notification sera envoyée à:")
    print(f"   📱 SMS: {phone}")
    print(f"   📧 Email: {email}")

    response = input("Confirmer l'envoi ? (tapez 'OUI'): ")
    if response.upper() != 'OUI':
        print("❌ Test annulé")
        return False

    try:
        from notifications.twilio_notification_service import TwilioNotificationService
        from twilio_config import TwilioRecipient

        # Créer service de notification
        service = TwilioNotificationService(test_mode=False)  # MODE PRODUCTION
        await service.initialize_services()

        # Ajouter votre destinataire
        custom_recipient = TwilioRecipient(
            name="Test Personnel",
            phone=phone,
            email=email,
            role="test",
            severity_threshold="CRITICAL"
        )

        service.add_recipient("CRITICAL", custom_recipient)

        # Créer alerte de test
        class TestAlert:
            def __init__(self):
                self.alert_id = "CUSTOM_TEST_001"
                self.patient_id = "PATIENT_CUSTOM"
                self.device_id = "DEVICE_TEST"
                self.severity = type('MockSeverity', (), {'value': 'CRITICAL'})()
                self.alert_type = type('MockType', (), {'value': 'TEST'})()
                self.vitals_snapshot = {
                    'freq_card': 180,
                    'spo2_pct': 82,
                    'temp_corp': 40.5,
                    'temp_ambiante': 35.0
                }
                self.medical_context = 'Test personnalisé du système Twilio KidJamo'
                self.recommended_action = 'Test seulement - Aucune action médicale requise'
                self.created_at = datetime.now()
                self.correlation_score = 95
                self.message = 'Alerte de test personnalisée - Système KidJamo opérationnel'

        test_alert = TestAlert()
        await service.send_alert_notification(test_alert)

        print("✅ Notification personnalisée envoyée!")
        print("📱 Vérifiez votre SMS")
        print("📧 Vérifiez votre email")

        return True

    except Exception as e:
        print(f"❌ Erreur lors de l'envoi personnalisé: {e}")
        return False

async def main():
    """Menu principal"""

    print("""
    🧪 TEST NOTIFICATIONS TWILIO RÉELLES
    ====================================
    
    Choisissez une option:
    1. Test avec destinataires par défaut (Dr. Urgences)
    2. Test avec votre propre numéro/email
    3. Annuler
    """)

    choice = input("Votre choix (1, 2 ou 3): ").strip()

    if choice == "1":
        await test_real_notifications()
    elif choice == "2":
        await test_custom_notification()
    elif choice == "3":
        print("✅ Test annulé")
    else:
        print("❌ Choix invalide")

if __name__ == "__main__":
    asyncio.run(main())
