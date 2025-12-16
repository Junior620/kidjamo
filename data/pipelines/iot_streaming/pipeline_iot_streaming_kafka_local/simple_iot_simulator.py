"""
Version simplifiée pour démarrage rapide local.

Rôle :
    Version simplifiée du simulateur IoT pour tests et démonstrations locales.
    Génère des profils patients fixes avec scénarios médicaux réalistes
    et envoie des mesures vers l'API d'ingestion via requêtes HTTP POST.

Objectifs :
    - Simulation 3 patients fixes avec génotypes différents (SS, AS, SC)
    - Génération mesures vitales réalistes avec variations circadiennes
    - Scénarios médicaux : normal, stress, activité, crise drépanocytaire
    - Envoi POST vers endpoint /iot/measurements de l'API
    - Logging des alertes critiques détectées par l'API

Entrées :
    - Profils patients prédéfinis (âge, génotype, constantes vitales de base)
    - Configuration simulation (durée, intervalle entre mesures)
    - Endpoint API d'ingestion (configurable via paramètre)
    - Distributions aléatoires pour variabilité physiologique

Sorties :
    - POST JSON vers /iot/measurements avec structure IoTMeasurement complète
    - Logs formatés avec statut envoi et alertes critiques détectées
    - Statistiques finales (total envoyé, taux de succès)
    - Simulation de crises avec SpO2 < 88% et température > 38°C

Effets de bord :
    - Requêtes HTTP POST vers API (network I/O)
    - Génération UUID pour device_id à chaque mesure
    - Horodatage ISO automatique (datetime.now().isoformat())
    - Sleep configurable entre cycles de mesures
    - Logs avec niveaux INFO/WARNING selon criticité

Garanties :
    Scénarios et distributions aléatoires inchangés ; seuils de simulation
    de crise identiques (SpO2 -5 à -15%, T° +1.5 à +3.0°C) ; structure
    JSON POST conforme au modèle IoTMeasurement de l'API.
"""

# Imports standard library (triés alphabétiquement)
import json
import logging
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List

# Imports third-party (triés alphabétiquement)
import requests

# Configuration logging avec logger nommé
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PatientProfile:
    """
    Profil patient pour simulation IoT avec constantes physiologiques.

    Profil simplifié pour simulation rapide avec paramètres de base
    individualisés selon génotype drépanocytaire et âge.
    """
    patient_id: str
    age: int
    genotype: str  # SS, AS, SC
    base_heart_rate: int
    base_spo2: float
    base_temperature: float


class SimpleIoTSimulator:
    """
    Simulateur IoT simplifié pour démarrage rapide local.

    Gère 3 patients prédéfinis avec génotypes différents et simule
    des scénarios médicaux réalistes incluant les crises drépanocytaires.
    Version allégée du simulateur avancé pour tests et démonstrations.
    """

    def __init__(self, api_endpoint: str = "http://localhost:8001") -> None:
        """
        Initialise le simulateur avec endpoint API configurable.

        Args:
            api_endpoint: URL de base de l'API d'ingestion (sans trailing slash)
        """
        self.api_endpoint = api_endpoint
        self.patients = self._create_test_patients()
        self.running = False

    def _create_test_patients(self) -> List[PatientProfile]:
        """
        Crée 3 patients de test avec profils physiologiques différents.

        Profils représentatifs selon génotypes drépanocytaires :
        - Patient SS (8 ans) : SpO2 base plus basse, surveillance critique
        - Patient AS (15 ans) : profil normal avec porteur trait
        - Patient SC (12 ans) : profil intermédiaire

        Returns:
            List[PatientProfile]: Liste des 3 patients de test
        """
        return [
            PatientProfile(
                patient_id="patient-001-ss",
                age=8,
                genotype="SS",
                base_heart_rate=110,  # Plus élevée chez enfant SS
                base_spo2=94.0,      # Plus bas pour SS (surveillance critique)
                base_temperature=36.7
            ),
            PatientProfile(
                patient_id="patient-002-as",
                age=15,
                genotype="AS",
                base_heart_rate=85,   # Normal adolescent
                base_spo2=97.5,      # Normal porteur trait
                base_temperature=36.8
            ),
            PatientProfile(
                patient_id="patient-003-sc",
                age=12,
                genotype="SC",
                base_heart_rate=95,   # Légèrement élevée
                base_spo2=96.0,      # Intermédiaire
                base_temperature=36.9
            )
        ]

    def _generate_realistic_vitals(self, patient: PatientProfile) -> Dict:
        """
        Génère des signes vitaux réalistes avec variations et scénarios médicaux.

        Scénarios simulés avec pondération inchangée :
        - normal (70%) : variations physiologiques normales
        - stress (15%) : FC et T° augmentées, SpO2 légèrement baissée
        - activity (10%) : FC élevée, T° augmentée, activité haute
        - crisis (5%) : simulation crise drépanocytaire (SpO2 critique, fièvre)

        Args:
            patient: Profil patient avec constantes de base

        Returns:
            Dict: Mesures vitales générées avec toutes les métriques IoT
        """
        # Sélection scénario selon distribution pondérée (inchangée)
        scenario = random.choices(
            ['normal', 'stress', 'activity', 'crisis'],
            weights=[70, 15, 10, 5]  # 5% chance de crise
        )[0]

        if scenario == 'normal':
            # Variations physiologiques normales autour baseline
            heart_rate = patient.base_heart_rate + random.randint(-10, 10)
            spo2 = patient.base_spo2 + random.uniform(-1, 1)
            temperature = patient.base_temperature + random.uniform(-0.2, 0.3)
            activity = random.randint(10, 40)

        elif scenario == 'activity':
            # Simulation activité physique
            heart_rate = patient.base_heart_rate + random.randint(20, 40)
            spo2 = patient.base_spo2 + random.uniform(-0.5, 0.5)
            temperature = patient.base_temperature + random.uniform(0.2, 0.8)
            activity = random.randint(70, 95)

        elif scenario == 'stress':
            # Simulation stress émotionnel/physique
            heart_rate = patient.base_heart_rate + random.randint(15, 30)
            spo2 = patient.base_spo2 + random.uniform(-2, 0)
            temperature = patient.base_temperature + random.uniform(0, 0.5)
            activity = random.randint(30, 60)

        else:  # crisis - simulation de crise drépanocytaire
            # Simulation crise avec paramètres critiques (seuils inchangés)
            heart_rate = patient.base_heart_rate + random.randint(30, 50)
            spo2 = patient.base_spo2 - random.uniform(5, 15)  # Désaturation sévère
            temperature = patient.base_temperature + random.uniform(1.5, 3.0)  # Fièvre importante
            activity = random.randint(5, 25)  # Faible activité (fatigue)

            logger.warning(f"🚨 SIMULATION CRISE pour {patient.patient_id}: "
                          f"SpO2={spo2:.1f}%, T°={temperature:.1f}°C")

        # Contraintes physiologiques pour éviter valeurs impossibles
        return {
            'freq_card': max(40, min(200, int(heart_rate))),
            'freq_resp': random.randint(12, 25),  # Indépendant pour simplicité
            'spo2_pct': round(max(75, min(100, spo2)), 1),
            'temp_corp': round(max(35, min(42, temperature)), 1),
            'temp_ambiente': round(random.uniform(20, 25), 1),
            'pct_hydratation': round(random.uniform(65, 85), 1),
            'activity': activity,
            'heat_index': round(temperature + random.uniform(-1, 3), 1)
        }

    def _generate_device_info(self) -> Dict:
        """
        Génère les informations techniques du dispositif IoT.

        Simule un bracelet connecté avec :
        - UUID unique par mesure (device_id)
        - Firmware version fixe pour cohérence
        - Batterie et signal aléatoires mais réalistes
        - Statut connecté et sync récente

        Returns:
            Dict: Informations techniques dispositif
        """
        return {
            'device_id': str(uuid.uuid4()),  # Nouveau UUID à chaque mesure
            'firmware_version': '2.1.3',
            'battery_level': random.randint(60, 95),
            'signal_strength': random.randint(75, 100),
            'status': 'connected',
            'last_sync': datetime.now().isoformat()
        }

    def _generate_quality_indicators(self, activity_level: int) -> Dict:
        """
        Génère les indicateurs de qualité selon niveau d'activité.

        Logique de qualité inchangée :
        - Activité élevée (>80) : mouvement affecte qualité capteurs
        - Activité très faible (<10) : possible problème signal
        - Activité normale : qualité optimale

        Args:
            activity_level: Niveau d'activité (0-100)

        Returns:
            Dict: Indicateurs de qualité des mesures
        """
        if activity_level > 80:
            # Mouvement affecte la qualité des capteurs
            quality_flag = 'motion'
            confidence = random.uniform(60, 80)
        elif activity_level < 10:
            # Très faible activité = possible problème signal
            quality_flag = 'low_signal'
            confidence = random.uniform(70, 85)
        else:
            # Conditions normales = qualité optimale
            quality_flag = 'ok'
            confidence = random.uniform(85, 98)

        return {
            'quality_flag': quality_flag,
            'confidence_score': round(confidence, 1),
            'data_completeness': round(random.uniform(90, 100), 1),
            'sensor_contact_quality': round(random.uniform(80, 95), 1)
        }

    def generate_measurement(self, patient: PatientProfile) -> Dict:
        """
        Génère une mesure IoT complète conforme au modèle API.

        Assemble toutes les sous-structures :
        - measurements : signes vitaux générés selon scénario
        - device_info : informations techniques simulées
        - quality_indicators : métriques de qualité contextuelles

        Args:
            patient: Profil patient pour génération mesures

        Returns:
            Dict: Mesure complète au format IoTMeasurement API
        """
        measurements = self._generate_realistic_vitals(patient)
        device_info = self._generate_device_info()
        quality_indicators = self._generate_quality_indicators(measurements['activity'])

        return {
            'device_id': device_info['device_id'],
            'patient_id': patient.patient_id,
            'timestamp': datetime.now().isoformat(),
            'measurements': measurements,
            'device_info': device_info,
            'quality_indicators': quality_indicators
        }

    def send_measurement(self, measurement: Dict) -> bool:
        """
        Envoie une mesure vers l'API d'ingestion via POST.

        Appelle l'endpoint /iot/measurements avec timeout de 5s.
        Parse la réponse pour extraire le nombre d'alertes critiques.
        Log adaptatif selon présence d'alertes.

        Args:
            measurement: Mesure IoT complète à envoyer

        Returns:
            bool: True si envoi réussi, False sinon
        """
        try:
            response = requests.post(
                f"{self.api_endpoint}/iot/measurements",
                json=measurement,
                timeout=5
            )

            if response.status_code == 200:
                result = response.json()
                alerts_count = result.get('critical_alerts', 0)
                quality_score = result.get('quality_score', 0)

                # Extraction données pour logging
                patient_id = measurement['patient_id']
                spo2 = measurement['measurements']['spo2_pct']
                hr = measurement['measurements']['freq_card']
                temp = measurement['measurements']['temp_corp']

                # Log adaptatif selon présence d'alertes (inchangé)
                if alerts_count > 0:
                    logger.warning(f"🚨 {patient_id}: SpO2={spo2}%, HR={hr}, T°={temp}°C - {alerts_count} alertes!")
                else:
                    logger.info(f"✅ {patient_id}: SpO2={spo2}%, HR={hr}, T°={temp}°C - Normal")

                return True
            else:
                logger.error(f"❌ API Error {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Connexion API impossible: {e}")
            return False

    def run_simulation(self, duration_minutes: int = 10, interval_seconds: int = 30) -> None:
        """
        Lance la simulation pour une durée donnée avec cycles réguliers.

        Processus :
        1. Boucle pendant duration_minutes
        2. Pour chaque patient : génère et envoie une mesure
        3. Attente interval_seconds entre cycles
        4. Statistiques finales (total, succès, taux)

        Args:
            duration_minutes: Durée totale simulation (défaut: 10)
            interval_seconds: Intervalle entre cycles (défaut: 30)
        """
        logger.info(f"🚀 Démarrage simulation IoT: {len(self.patients)} patients, {duration_minutes} min")

        self.running = True
        start_time = datetime.now()

        # Compteurs pour statistiques
        total_measurements = 0
        successful_measurements = 0

        try:
            while self.running:
                # Vérification durée écoulée
                elapsed = (datetime.now() - start_time).total_seconds() / 60
                if elapsed >= duration_minutes:
                    break

                # Cycle de mesures pour tous les patients
                for patient in self.patients:
                    if not self.running:
                        break

                    try:
                        # Génération et envoi mesure
                        measurement = self.generate_measurement(patient)
                        success = self.send_measurement(measurement)

                        total_measurements += 1
                        if success:
                            successful_measurements += 1

                    except Exception as e:
                        logger.error(f"❌ Erreur pour {patient.patient_id}: {e}")
                        total_measurements += 1

                # Pause entre cycles si simulation continue
                if self.running and elapsed < duration_minutes:
                    time.sleep(interval_seconds)

        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé par utilisateur")
        finally:
            self.running = False

            # Statistiques finales
            duration_actual = (datetime.now() - start_time).total_seconds() / 60
            success_rate = (successful_measurements / total_measurements * 100) if total_measurements > 0 else 0

            logger.info(f"📊 Simulation terminée:")
            logger.info(f"   Durée: {duration_actual:.1f} minutes")
            logger.info(f"   Total mesures: {total_measurements}")
            logger.info(f"   Succès: {successful_measurements}")
            logger.info(f"   Taux de succès: {success_rate:.1f}%")

    def stop_simulation(self) -> None:
        """Arrête la simulation en cours."""
        self.running = False
        logger.info("🛑 Arrêt de la simulation demandé")


# === POINT D'ENTRÉE PRINCIPAL ===

def main() -> None:
    """
    Point d'entrée principal pour simulation interactive simple.

    Configuration par défaut :
    - 3 patients fixes (SS, AS, SC)
    - 10 minutes de simulation
    - 30 secondes entre cycles
    - API sur localhost:8001
    """
    import argparse

    # Parser arguments ligne de commande
    parser = argparse.ArgumentParser(description="Simulateur IoT simple pour Kidjamo")
    parser.add_argument("--duration", type=int, default=10,
                       help="Durée simulation en minutes (défaut: 10)")
    parser.add_argument("--interval", type=int, default=30,
                       help="Intervalle entre cycles en secondes (défaut: 30)")
    parser.add_argument("--api-endpoint", default="http://localhost:8001",
                       help="URL API d'ingestion (défaut: http://localhost:8001)")

    args = parser.parse_args()

    # Initialisation et démarrage simulation
    simulator = SimpleIoTSimulator(api_endpoint=args.api_endpoint)

    logger.info("🏥 Kidjamo Simple IoT Simulator")
    logger.info(f"Configuration: {len(simulator.patients)} patients, {args.duration} min, {args.interval}s interval")
    logger.info(f"API endpoint: {args.api_endpoint}")

    try:
        simulator.run_simulation(
            duration_minutes=args.duration,
            interval_seconds=args.interval
        )
    except Exception as e:
        logger.error(f"❌ Erreur simulation: {e}")
        raise SystemExit(1)

    logger.info("🏁 Simulation terminée")


if __name__ == "__main__":
    main()
