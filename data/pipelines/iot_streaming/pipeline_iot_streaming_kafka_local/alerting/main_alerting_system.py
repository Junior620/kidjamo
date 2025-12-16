"""
Script Principal - Système d'Alertes Composées IoT Médical
Lance le monitoring continu avec notifications SMS/Email via Twilio
"""

import asyncio
import logging
import sys
import signal
import json
import os
from datetime import datetime
from pathlib import Path

# Ajouter le chemin du projet
sys.path.append(str(Path(__file__).parent))

from alert_orchestrator import AlertOrchestrator
from aws_config import AWSConfig

# Configuration du logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/alerting_system.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class AlertingSystemMain:
    """Classe principale du système d'alertes"""

    def __init__(self):
        self.orchestrator = None
        self.is_running = False

        # Configuration de la base de données (mise à jour avec vos paramètres)
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'kidjamo-db',  # Corrigé avec votre vraie DB
            'user': 'postgres',
            'password': 'kidjamo@'     # Corrigé avec votre vraie password
        }

    async def initialize(self):
        """Initialise le système d'alertes"""
        try:
            logger.info("🚀 Initialisation du système d'alertes KidJamo")

            # Créer l'orchestrateur avec Twilio par défaut
            self.orchestrator = AlertOrchestrator(
                self.db_config,
                use_twilio=True  # Utiliser Twilio au lieu d'AWS
            )

            # Mode production (vraies notifications)
            # self.orchestrator.set_test_mode(False)  # Décommenter pour production
            self.orchestrator.set_test_mode(True)     # Mode test par défaut

            # Initialiser l'orchestrateur
            await self.orchestrator.initialize()

            logger.info("✅ Système d'alertes initialisé avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation: {e}")
            return False

    async def start_monitoring(self):
        """Démarre le monitoring continu"""
        if not self.orchestrator:
            logger.error("❌ Orchestrateur non initialisé")
            return False

        try:
            logger.info("📡 Démarrage du monitoring temps réel...")
            logger.info("🔴 Mode Twilio activé - Notifications opérationnelles")
            logger.info("⏹️  Appuyez sur Ctrl+C pour arrêter proprement")

            self.is_running = True

            # Afficher le statut initial
            status = await self.orchestrator.get_system_status()
            logger.info(f"📊 Statut initial: {status['active_patients']} patients actifs")

            # Démarrer le monitoring (boucle infinie)
            await self.orchestrator.start_monitoring()

        except KeyboardInterrupt:
            logger.info("\n🛑 Arrêt demandé par l'utilisateur")
            await self.stop_monitoring()
        except Exception as e:
            logger.error(f"❌ Erreur dans le monitoring: {e}")
            await self.stop_monitoring()

    async def stop_monitoring(self):
        """Arrête le monitoring proprement"""
        if self.orchestrator and self.is_running:
            logger.info("🛑 Arrêt du monitoring en cours...")
            await self.orchestrator.stop_monitoring()
            self.is_running = False

            # Afficher les métriques finales
            metrics = self.orchestrator.get_notification_metrics()
            logger.info("📊 Métriques finales:")
            logger.info(f"   SMS envoyés: {metrics.get('sms_sent', 0)}")
            logger.info(f"   Emails envoyés: {metrics.get('emails_sent', 0)}")
            logger.info(f"   Taux succès: {metrics.get('success_rate', 0):.1f}%")

            logger.info("✅ Système arrêté proprement")

    async def send_test_alert(self):
        """Envoie une alerte de test"""
        if not self.orchestrator:
            logger.error("❌ Orchestrateur non initialisé")
            return False

        try:
            logger.info("📤 Envoi d'une alerte de test...")
            result = await self.orchestrator.send_test_notification("HIGH")

            if result:
                logger.info("✅ Alerte de test envoyée avec succès")
            else:
                logger.error("❌ Échec envoi alerte de test")

            return result

        except Exception as e:
            logger.error(f"❌ Erreur lors du test: {e}")
            return False

    async def get_system_status(self):
        """Affiche le statut système"""
        if not self.orchestrator:
            logger.error("❌ Orchestrateur non initialisé")
            return

        try:
            status = await self.orchestrator.get_system_status()

            logger.info("📊 STATUT SYSTÈME:")
            logger.info(f"   Status: {status['status']}")
            logger.info(f"   Patients actifs: {status['active_patients']}")
            logger.info(f"   Alertes actives: {status['active_alerts']}")
            logger.info(f"   Service notifications: {status['metrics']['notification_service']}")
            logger.info(f"   Dernière exécution: {status['last_update']}")

            # Métriques notifications
            notif_metrics = self.orchestrator.get_notification_metrics()
            logger.info("📱 MÉTRIQUES NOTIFICATIONS:")
            logger.info(f"   SMS envoyés: {notif_metrics.get('sms_sent', 0)}")
            logger.info(f"   Emails envoyés: {notif_metrics.get('emails_sent', 0)}")
            logger.info(f"   Échecs: {notif_metrics.get('total_failures', 0)}")
            logger.info(f"   Taux succès: {notif_metrics.get('success_rate', 0):.1f}%")

            return status

        except Exception as e:
            logger.error(f"❌ Erreur lors de la récupération du statut: {e}")

def setup_signal_handlers(main_system):
    """Configure les gestionnaires de signaux pour arrêt propre"""
    def signal_handler(sig, frame):
        logger.info(f"\n🛑 Signal {sig} reçu - Arrêt en cours...")
        asyncio.create_task(main_system.stop_monitoring())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Point d'entrée principal"""

    print("""
🏥 KIDJAMO - SYSTÈME D'ALERTES MÉDICALES IoT
===========================================

🔧 Configuration: Twilio SMS + SendGrid Email
📡 Base de données: PostgreSQL Local (kidjamo-db)
🚨 Monitoring: Temps réel (30s)
    """)

    # Créer le système principal
    alerting_system = AlertingSystemMain()

    # Configurer les gestionnaires de signaux
    setup_signal_handlers(alerting_system)

    # Menu interactif
    while True:
        print("""
Choisissez une action:
1. 🚀 Démarrer monitoring temps réel
2. 📤 Envoyer alerte de test
3. 📊 Afficher statut système  
4. 🛑 Quitter

""")

        choice = input("Votre choix (1-4): ").strip()

        if choice == "1":
            # Initialiser et démarrer
            if await alerting_system.initialize():
                await alerting_system.start_monitoring()
            break

        elif choice == "2":
            # Test d'alerte
            if not alerting_system.orchestrator:
                if not await alerting_system.initialize():
                    continue
            await alerting_system.send_test_alert()

        elif choice == "3":
            # Statut système
            if not alerting_system.orchestrator:
                if not await alerting_system.initialize():
                    continue
            await alerting_system.get_system_status()

        elif choice == "4":
            print("👋 Au revoir!")
            break

        else:
            print("❌ Choix invalide")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Arrêt du programme")
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)
