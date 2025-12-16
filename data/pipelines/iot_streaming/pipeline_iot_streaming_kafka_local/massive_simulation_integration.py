                        'api_key': self.config.get('sendgrid_api_key', os.getenv('SENDGRID_API_KEY', '')),
"""
Script d'Intégration Complète - Simulateur Massif IoT Patients
                        'to_email': os.getenv('ALERT_EMAIL', '')
Rôle :
    Script principal pour assembler et exécuter l'ensemble du système :
    - Simulateur massif 50+ patients
    - Dashboard temps réel Streamlit
    - Notifications SMS/Email automatiques
    - Surveillance continue 24h avec gestion d'erreurs

Usage :
    python massive_simulation_integration.py --patients 50 --duration 24

Fonctionnalités :
    - Démarrage orchestré de tous les composants
    - Monitoring santé système en temps réel
    - Gestion gracieuse des arrêts et redémarrages
    - Logs centralisés et rapports de performance
    - Interface CLI pour contrôle à distance
"""

import os
import sys
import time
import subprocess
import threading
import signal
import logging
from datetime import datetime, timedelta
from pathlib import Path
import argparse
import json

# Ajouter le chemin du projet au PYTHONPATH
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import des modules créés (en supposant qu'ils sont combinés)
try:
    # Import correct depuis le module simulator
    from simulator.massive_patient_simulator_combined import MassivePatientSimulationController
    from simulator import PatientGenerator, PhysiologicalSimulator
except ImportError as e:
    print(f"⚠️  Modules simulateur non trouvés: {e}")
    print("   Assurez-vous que les fichiers sont présents et que le module simulator est correctement configuré.")
    sys.exit(1)

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('massive_simulation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MassiveSimulationOrchestrator:
    """Orchestrateur principal pour la simulation massive complète"""

    def __init__(self, config: dict):
        self.config = config
        self.simulation_controller = None
        self.dashboard_process = None
        self.monitoring_thread = None
        self.running = False
        self.start_time = None

        # Statistiques de fonctionnement
        self.stats = {
            'patients_simulated': 0,
            'total_measurements': 0,
            'total_alerts': 0,
            'critical_alerts': 0,
            'sms_sent': 0,
            'emails_sent': 0,
            'uptime_hours': 0,
            'performance_score': 100
        }

    def initialize_environment(self):
        """Initialise l'environnement et vérifie les prérequis"""
        logger.info("🔧 Initialisation environnement...")

        # Vérification Python et dépendances
        required_packages = [
            'streamlit', 'plotly', 'pandas', 'psycopg2',
            'twilio',  'requests'
        ]

        missing_packages = []
        for package in required_packages:
            try:
                __import__(package.replace('-', '_'))
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            logger.error(f"❌ Packages manquants: {missing_packages}")
            logger.info("Installation: pip install " + " ".join(missing_packages))
            return False

        # Vérification base de données avec gestion d'erreur d'encodage
        db_connected = self._test_database_connection()
        if not db_connected:
            logger.warning("⚠️  PostgreSQL non accessible - Mode simulation sans persistance")
            logger.info("   Le système fonctionnera en mode mémoire uniquement")
            # Continue l'initialisation même sans DB
        else:
            logger.info("✅ Connexion PostgreSQL OK")

        # Vérification configuration Twilio/Email
        if not self.config.get('twilio_account_sid'):
            logger.warning("⚠️  Configuration Twilio manquante - SMS désactivés")

        if not self.config.get('smtp_username'):
            logger.warning("⚠️  Configuration SMTP manquante - Emails désactivés")

        # Création dossiers nécessaires
        os.makedirs('logs', exist_ok=True)
        os.makedirs('reports', exist_ok=True)
        os.makedirs('exports', exist_ok=True)

        logger.info("✅ Environnement initialisé avec succès")
        return True

    def _test_database_connection(self):
        """Test la connexion PostgreSQL avec différentes méthodes d'encodage"""
        connection_configs = [
            {
                'name': 'UTF8 avec options serveur',
                'params': {
                    'host': self.config.get('db_host', 'localhost'),
                    'port': self.config.get('db_port', '5432'),
                    'database': self.config.get('db_name', 'kidjamo-db'),
                    'user': self.config.get('db_user', 'postgres'),
                    'password': self.config.get('db_password', 'kidjamo@'),
                    'options': '-c client_encoding=UTF8'
                }
            },
            {
                'name': 'LATIN1 fallback',
                'params': {
                    'host': self.config.get('db_host', 'localhost'),
                    'port': self.config.get('db_port', '5432'),
                    'database': self.config.get('db_name', 'kidjamo-db'),
                    'user': self.config.get('db_user', 'postgres'),
                    'password': self.config.get('db_password', 'kidjamo@'),
                    'client_encoding': 'LATIN1'
                }
            },
            {
                'name': 'Sans encodage explicite',
                'params': {
                    'host': self.config.get('db_host', 'localhost'),
                    'port': self.config.get('db_port', '5432'),
                    'database': self.config.get('db_name', 'kidjamo-db'),
                    'user': self.config.get('db_user', 'postgres'),
                    'password': self.config.get('db_password', 'kidjamo@')
                }
            }
        ]

        for config in connection_configs:
            try:
                import psycopg2
                # Configuration encodage pour Windows
                os.environ['PGCLIENTENCODING'] = 'UTF8'

                logger.info(f"🔗 Test connexion: {config['name']}")
                conn = psycopg2.connect(**config['params'])

                # Test simple
                cursor = conn.cursor()
                cursor.execute("SELECT 1;")
                result = cursor.fetchone()
                conn.close()

                logger.info(f"✅ Connexion réussie avec: {config['name']}")

                # Stocker la config qui fonctionne
                self.config['working_db_params'] = config['params']
                return True

            except Exception as e:
                logger.debug(f"❌ Échec {config['name']}: {str(e)[:100]}...")
                continue

        # Si toutes les méthodes échouent
        logger.warning("⚠️  Impossible de se connecter à PostgreSQL avec toutes les méthodes testées")
        return False

    def start_simulation_controller(self):
        """Démarre le contrôleur de simulation massif"""
        logger.info(f"🚀 Démarrage simulation {self.config['patient_count']} patients...")

        try:
            # Initialisation contrôleur avec configuration
            self.simulation_controller = MassivePatientSimulationController(
                patient_count=self.config['patient_count']
            )

            # Configuration base de données seulement si accessible
            if hasattr(self.simulation_controller, 'db_manager') and self.config.get('working_db_params'):
                logger.info("🔧 Configuration base de données...")
                # Utiliser les paramètres de connexion qui fonctionnent
                if hasattr(self.simulation_controller.db_manager, 'DB_CONFIG'):
                    self.simulation_controller.db_manager.DB_CONFIG.update(self.config['working_db_params'])
                else:
                    logger.warning("⚠️ DB_CONFIG non trouvé - Configuration ignorée")
            else:
                logger.info("💾 Mode simulation sans base de données")

            # Initialisation patients
            self.simulation_controller.initialize_patients()

            # Configuration notifications
            if hasattr(self.simulation_controller, 'notification_service'):
                # Configuration Twilio avec vos credentials - Utiliser les variables globales
                if self.config.get('twilio_account_sid'):
                    # Mise à jour des variables globales du module simulateur
                    import simulator.massive_patient_simulator as sim_module
                    sim_module.TWILIO_CONFIG.update({
                        'account_sid': self.config.get('twilio_account_sid', os.getenv('TWILIO_ACCOUNT_SID', '')),
                        'auth_token': self.config.get('twilio_auth_token', os.getenv('TWILIO_AUTH_TOKEN', '')),
                        'from_number': self.config.get('twilio_from_number', os.getenv('TWILIO_FROM_NUMBER', '')),
                        'to_number': os.getenv('TWILIO_TO_NUMBER', '')
                    })
                    logger.info("✅ Configuration Twilio mise à jour")

                # Configuration SendGrid Email - Utiliser les variables globales
                if self.config.get('sendgrid_api_key'):
                    # Mise à jour des variables globales du module simulateur
                    sim_module.EMAIL_CONFIG.update({
                        'provider': 'sendgrid',
                        'from_email': self.config.get('sendgrid_from_email', 'support@kidjamo.app'),
                        'from_name': self.config.get('sendgrid_from_name', 'KidJamo-team'),
                        'to_email': 'christianouragan@gmail.com'
                    })
                    logger.info("✅ Configuration SendGrid mise à jour")

            # Démarrage simulation
            self.simulation_controller.start_simulation()

            # Mise à jour statistiques
            self.stats['patients_simulated'] = self.config['patient_count']

            logger.info("✅ Contrôleur simulation démarré avec succès")
            return True

        except Exception as e:
            logger.error(f"❌ Erreur démarrage simulation: {e}")
            logger.info("💡 Tentative de démarrage en mode simplifié...")

            # Mode de fallback - utiliser le simulateur simple
            try:
                from simulator import PatientGenerator, PhysiologicalSimulator
                logger.info("🔄 Démarrage en mode simulateur simple...")

                # Créer un simulateur simple
                self.simple_generator = PatientGenerator()
                self.simple_simulator = PhysiologicalSimulator()

                # Générer des patients
                self.patients = self.simple_generator.generate_patient_batch(self.config['patient_count'])
                logger.info(f"✅ {len(self.patients)} patients générés en mode simple")

                # Marquer comme mode simple
                self.config['simple_mode'] = True
                self.stats['patients_simulated'] = len(self.patients)

                return True

            except Exception as e2:
                logger.error(f"❌ Échec mode simple: {e2}")
                return False

    def start_dashboard(self):
        """Démarre le dashboard Streamlit temps réel en arrière-plan"""
        logger.info("📊 Démarrage dashboard Streamlit temps réel...")

        try:
            # Utiliser le nouveau dashboard temps réel avec architecture Kafka
            dashboard_script = project_root / "monitoring" / "realtime_dashboard_advanced.py"

            # Fallback vers l'ancien dashboard si le nouveau n'existe pas
            if not dashboard_script.exists():
                logger.warning("⚠️  Dashboard v2 non trouvé, utilisation de l'ancien...")
                dashboard_script = project_root / "monitoring" / "realtime_dashboard_advanced.py"

                if not dashboard_script.exists():
                    logger.error(f"❌ Aucun script dashboard trouvé")
                    return False

            logger.info(f"🔧 Utilisation du dashboard: {dashboard_script.name}")

            # Configuration variables d'environnement pour Streamlit
            env = os.environ.copy()
            env.update({
                'POSTGRES_HOST': self.config.get('db_host', 'localhost'),
                'POSTGRES_PORT': str(self.config.get('db_port', '5432')),
                'POSTGRES_DB': self.config.get('db_name', 'kidjamo-db'),
                'POSTGRES_USER': self.config.get('db_user', 'postgres'),
                'POSTGRES_PASSWORD': self.config.get('db_password', 'kidjamo@'),
                # Configuration Kafka pour le dashboard temps réel
                'KAFKA_SERVERS': 'localhost:9092',
                'KAFKA_TOPICS_MEASUREMENTS': 'kidjamo-iot-measurements',
                'KAFKA_TOPICS_ALERTS': 'kidjamo-iot-alerts'
            })

            # Commande Streamlit avec port différent pour éviter les conflits
            dashboard_port = "8503" if "v2" in dashboard_script.name else "8501"

            cmd = [
                sys.executable, "-m", "streamlit", "run",
                str(dashboard_script),
                "--server.port", dashboard_port,
                "--server.address", "0.0.0.0",
                "--browser.gatherUsageStats", "false",
                "--server.headless", "true"  # Mode headless pour intégration
            ]

            # Démarrage processus
            self.dashboard_process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(project_root)
            )

            # Attendre démarrage
            time.sleep(8)  # Plus de temps pour le nouveau dashboard

            if self.dashboard_process.poll() is None:
                logger.info(f"✅ Dashboard temps réel démarré sur http://localhost:{dashboard_port}")
                logger.info(f"   🔄 Architecture: {'Kafka temps réel' if 'v2' in dashboard_script.name else 'SQL classique'}")

                # Stocker le port pour les logs
                self.config['dashboard_port'] = dashboard_port
                return True
            else:
                stdout, stderr = self.dashboard_process.communicate()
                logger.error(f"❌ Échec démarrage dashboard")
                logger.error(f"   STDOUT: {stdout.decode('utf-8', errors='ignore')[:200]}...")
                logger.error(f"   STDERR: {stderr.decode('utf-8', errors='ignore')[:200]}...")
                return False

        except Exception as e:
            logger.error(f"❌ Erreur démarrage dashboard: {e}")
            return False

    def start_monitoring(self):
        """Démarre le monitoring système"""
        logger.info("📡 Démarrage monitoring système...")

        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self.monitoring_thread.start()

        logger.info("✅ Monitoring système actif")

    def _monitoring_loop(self):
        """Boucle de monitoring continue"""
        while self.running:
            try:
                time.sleep(60)  # Monitoring toutes les minutes
                self._collect_system_metrics()
                self._check_system_health()
                self._generate_periodic_report()

            except Exception as e:
                logger.error(f"❌ Erreur monitoring: {e}")

    def _collect_system_metrics(self):
        """Collecte métriques système"""
        if not self.simulation_controller:
            return

        try:
            # Métriques simulation
            sim_metrics = self.simulation_controller.get_system_metrics()

            # Mise à jour statistiques
            self.stats.update({
                'total_measurements': sim_metrics.get('total_measurements', 0),
                'total_alerts': sim_metrics.get('total_alerts', 0),
                'uptime_hours': (datetime.now() - self.start_time).total_seconds() / 3600
            })

            # Calcul score performance
            expected_measurements = (
                self.stats['patients_simulated'] *
                self.stats['uptime_hours'] * 720  # 720 mesures/patient/heure
            )

            if expected_measurements > 0:
                efficiency = (self.stats['total_measurements'] / expected_measurements) * 100
                self.stats['performance_score'] = min(100, max(0, efficiency))

        except Exception as e:
            logger.error(f"❌ Erreur collecte métriques: {e}")

    def _check_system_health(self):
        # Utiliser variables d'environnement par défaut si non spécifiés
        issues = []
            'twilio_account_sid': os.getenv('TWILIO_ACCOUNT_SID', ''),
            'twilio_auth_token': os.getenv('TWILIO_AUTH_TOKEN', ''),
            'twilio_from_number': os.getenv('TWILIO_FROM_NUMBER', ''),
            'twilio_messaging_service_sid': os.getenv('TWILIO_MESSAGING_SERVICE_SID', '')

        # Vérification dashboard
        if self.dashboard_process and self.dashboard_process.poll() is not None:
            issues.append("Dashboard Streamlit arrêté")

        # Vérification performance
        if self.stats['performance_score'] < 80:
            issues.append(f"Performance dégradée: {self.stats['performance_score']:.1f}%")

        # Vérification base de données
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.config.get('db_host', 'localhost'),
                port=self.config.get('db_port', '5432'),
                database=self.config.get('db_name', 'kidjamo'),
                user=self.config.get('db_user', 'postgres'),
                password=self.config.get('db_password', 'password')
            )
            conn.close()
        except Exception:
            issues.append("Connexion base de données perdue")

        # Logs des problèmes
        if issues:
            logger.warning(f"⚠️  Problèmes détectés: {', '.join(issues)}")
        else:
            logger.debug("✅ Santé syst��me OK")

    def _generate_periodic_report(self):
        """Génère rapport périodique (toutes les heures)"""
        if self.stats['uptime_hours'] > 0 and int(self.stats['uptime_hours']) % 1 == 0:
            # Rapport horaire
            report = {
                'timestamp': datetime.now().isoformat(),
                'uptime_hours': round(self.stats['uptime_hours'], 2),
                'patients_active': self.stats['patients_simulated'],
                'measurements_generated': self.stats['total_measurements'],
                'alerts_triggered': self.stats['total_alerts'],
                'performance_score': round(self.stats['performance_score'], 1),
                'measurement_rate_per_hour': self.stats['total_measurements'] / max(1, self.stats['uptime_hours'])
            }

            # Sauvegarde rapport
            report_file = f"reports/hourly_report_{datetime.now().strftime('%Y%m%d_%H')}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)

            logger.info(f"📊 Rapport horaire généré: {report['measurement_rate_per_hour']:.0f} mesures/h")

    def start_complete_system(self):
        """Démarre le système complet orchestré"""
        logger.info("🚀 DÉMARRAGE SYSTÈME COMPLET KIDJAMO IoT")
        logger.info("=" * 60)

        self.running = True
        self.start_time = datetime.now()

        # Étape 1: Environnement
        if not self.initialize_environment():
            logger.error("❌ Échec initialisation environnement")
            return False

        # Étape 2: Simulation controller
        if not self.start_simulation_controller():
            logger.error("❌ Échec démarrage simulation")
            return False

        # Étape 3: Dashboard
        if not self.start_dashboard():
            logger.warning("⚠️  Dashboard non démarré - Continuons sans interface web")

        # Étape 4: Monitoring
        self.start_monitoring()

        # Résumé démarrage
        logger.info("✅ SYSTÈME DÉMARRÉ AVEC SUCCÈS")
        logger.info(f"   👥 Patients: {self.config['patient_count']}")
        logger.info(f"   ⏱️  Durée prévue: {self.config.get('duration_hours', 24)}h")
        dashboard_port = self.config.get('dashboard_port', '8501')
        logger.info(f"   📊 Dashboard: http://localhost:{dashboard_port}")
        logger.info(f"   📱 SMS alertes: {'✅' if self.config.get('twilio_account_sid') else '❌'}")
        logger.info(f"   📧 Email alertes: {'✅' if self.config.get('smtp_username') else '❌'}")
        logger.info("   🛑 Arrêt: Ctrl+C")

        return True

    def stop_complete_system(self):
        """Arrêt complet du système"""
        logger.info("🛑 ARRÊT SYSTÈME EN COURS...")

        self.running = False

        # Arrêt simulation
        if self.simulation_controller:
            logger.info("⏹️  Arrêt contrôleur simulation...")
            self.simulation_controller.stop_simulation()

        # Arrêt dashboard
        if self.dashboard_process:
            logger.info("⏹️  Arrêt dashboard Streamlit...")
            self.dashboard_process.terminate()
            try:
                self.dashboard_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.dashboard_process.kill()

        # Arrêt monitoring
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            logger.info("⏹️  Arrêt monitoring...")
            self.monitoring_thread.join(timeout=5)

        # Rapport final
        self._generate_final_report()

        logger.info("✅ SYSTÈME ARRÊTÉ PROPREMENT")

    def _generate_final_report(self):
        """Génère rapport final de session"""
        duration = (datetime.now() - self.start_time).total_seconds() / 3600

        final_report = {
            'session_summary': {
                'start_time': self.start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration_hours': round(duration, 2),
                'patients_simulated': self.stats['patients_simulated'],
                'total_measurements': self.stats['total_measurements'],
                'total_alerts': self.stats['total_alerts'],
                'average_performance': round(self.stats['performance_score'], 1)
            },
            'statistics': {
                'measurements_per_patient': self.stats['total_measurements'] / max(1, self.stats['patients_simulated']),
                'alerts_per_patient': self.stats['total_alerts'] / max(1, self.stats['patients_simulated']),
                'measurement_rate_per_hour': self.stats['total_measurements'] / max(1, duration),
                'alert_rate_per_hour': self.stats['total_alerts'] / max(1, duration)
            },
            'configuration': self.config
        }

        # Sauvegarde rapport final
        report_file = f"reports/final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(final_report, f, indent=2)

        logger.info(f"📊 Rapport final sauvegardé: {report_file}")

        # Affichage résumé
        logger.info("📈 RÉSUMÉ SESSION:")
        logger.info(f"   ⏱️  Durée: {duration:.2f}h")
        logger.info(f"   📊 Mesures: {self.stats['total_measurements']:,}")
        logger.info(f"   🚨 Alertes: {self.stats['total_alerts']}")
        logger.info(f"   📈 Performance: {self.stats['performance_score']:.1f}%")

def parse_arguments():
    """Parse des arguments ligne de commande"""
    parser = argparse.ArgumentParser(
        description='Simulateur Massif IoT Patients KIDJAMO - Système Complet'
    )

    # Configuration simulation
    parser.add_argument('--patients', '-p', type=int, default=50,
                        help='Nombre de patients à simuler (défaut: 50)')
    parser.add_argument('--duration', '-d', type=float, default=24,
                        help='Durée simulation en heures (défaut: 24h, 0=infini, 0.083=5min)')

    # Configuration base de données
    parser.add_argument('--db-host', default='localhost',
                        help='Host PostgreSQL')
    parser.add_argument('--db-port', type=int, default=5432,
                        help='Port PostgreSQL')
    parser.add_argument('--db-name', default='kidjamo-db',
                        help='Nom base de données')
    parser.add_argument('--db-user', default='postgres',
                        help='Utilisateur PostgreSQL')
    parser.add_argument('--db-password', default='kidjamo@',
                        help='Mot de passe PostgreSQL')

    # Configuration notifications
    parser.add_argument('--twilio-sid', help='Twilio Account SID')
    parser.add_argument('--twilio-token', help='Twilio Auth Token')
    parser.add_argument('--twilio-from', help='Numéro Twilio source')
    parser.add_argument('--smtp-username', help='Username SMTP pour emails')
    parser.add_argument('--smtp-password', help='Mot de passe SMTP')
    parser.add_argument('--smtp-server', default='smtp.gmail.com', help='Serveur SMTP')
    parser.add_argument('--smtp-port', type=int, default=587, help='Port SMTP')

    # Options avancées
    parser.add_argument('--no-dashboard', action='store_true',
                        help='Désactiver dashboard Streamlit')
    parser.add_argument('--test-alerts', action='store_true',
                        help='Déclencher alertes de test au démarrage')
    parser.add_argument('--config-file', help='Fichier configuration JSON')

    return parser.parse_args()

def load_config_from_file(config_file: str) -> dict:
    """Charge configuration depuis fichier JSON"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ Erreur chargement configuration: {e}")
        return {}

def main():
    """Point d'entrée principal"""
    args = parse_arguments()

    # Configuration depuis arguments et fichier
    config = {
        'patient_count': args.patients,
        'duration_hours': args.duration,
        'db_host': args.db_host,
        'db_port': args.db_port,
        'db_name': args.db_name,
        'db_user': args.db_user,
        'db_password': args.db_password,
        'enable_dashboard': not args.no_dashboard,
        'test_alerts': args.test_alerts
    }

    # Configuration notifications
    if args.twilio_sid:
        config.update({
            'twilio_account_sid': args.twilio_sid,
            'twilio_auth_token': args.twilio_token,
            'twilio_from_number': args.twilio_from
        })
    else:
        # Utiliser variables d'environnement par défaut si non spécifiés
        config.update({
            'twilio_account_sid': os.getenv('TWILIO_ACCOUNT_SID', ''),
            'twilio_auth_token': os.getenv('TWILIO_AUTH_TOKEN', ''),
            'twilio_from_number': os.getenv('TWILIO_FROM_NUMBER', ''),
            'twilio_messaging_service_sid': os.getenv('TWILIO_MESSAGING_SERVICE_SID', '')
        })

    if args.smtp_username:
        config.update({
            'smtp_username': args.smtp_username,
            'smtp_password': args.smtp_password,
            'smtp_server': args.smtp_server,
            'smtp_port': args.smtp_port
        })
    else:
        # Utiliser SendGrid par défaut via variables d'environnement
        config.update({
            'sendgrid_api_key': os.getenv('SENDGRID_API_KEY', ''),
            'sendgrid_from_email': 'support@kidjamo.app',
            'sendgrid_from_name': 'KidJamo-team'
        })

    # Override avec fichier config si spécifié
    if args.config_file:
        file_config = load_config_from_file(args.config_file)
        config.update(file_config)

    # Affichage configuration
    print("🏥 SIMULATEUR MASSIF IoT PATIENTS - KIDJAMO")
    print("=" * 60)
    print(f"📊 Configuration:")
    print(f"   👥 Patients: {config['patient_count']}")
    print(f"   ⏱️  Durée: {config['duration_hours']}h {'(infini)' if config['duration_hours'] == 0 else ''}")
    print(f"   💾 Base: {config['db_host']}:{config['db_port']}/{config['db_name']}")
    print(f"   📊 Dashboard: {'✅' if config['enable_dashboard'] else '❌'}")
    print(f"   📱 SMS: {'✅' if config.get('twilio_account_sid') else '❌'}")
    print(f"   📧 Email: {'✅' if config.get('smtp_username') else '❌'}")
    print()

    # Initialisation orchestrateur
    orchestrator = MassiveSimulationOrchestrator(config)

    # Gestionnaire signal pour arrêt propre
    def signal_handler(sig, frame):
        print(f"\n🛑 Signal reçu: {sig}")
        orchestrator.stop_complete_system()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Démarrage système complet
        if not orchestrator.start_complete_system():
            logger.error("❌ Échec démarrage système")
            sys.exit(1)

        # Boucle principale
        if config['duration_hours'] > 0:
            duration_seconds = config['duration_hours'] * 3600
            logger.info(f"⏱️  Simulation programmée pour {config['duration_hours']}h")
            time.sleep(duration_seconds)
            logger.info("⏰ Durée atteinte - Arrêt automatique")
        else:
            logger.info("♾️  Mode simulation infinie - Arrêt: Ctrl+C")
            while True:
                time.sleep(60)

        orchestrator.stop_complete_system()

    except KeyboardInterrupt:
        print("\n🛑 Interruption clavier")
        orchestrator.stop_complete_system()

    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
        orchestrator.stop_complete_system()
        raise

if __name__ == "__main__":
    main()
