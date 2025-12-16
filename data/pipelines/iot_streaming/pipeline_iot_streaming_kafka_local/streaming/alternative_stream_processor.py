"""
Processeur de streaming IoT pour Kidjamo - Version Alternative
Fonctionne sans dépendance Kafka pour éviter les problèmes de compatibilité
"""

import json
import logging
import os
import time
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
import glob

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('../logs/streaming.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AlternativeStreamingProcessor:
    """
    Processeur de streaming IoT alternatif pour Kidjamo
    Utilise une file d'attente locale au lieu de Kafka pour éviter les problèmes de dépendances
    """

    def __init__(self, input_folder="../data_lake/raw", watch_api_logs=True):
        self.input_folder = Path(input_folder)
        self.watch_api_logs = watch_api_logs
        self.data_lake_path = Path("../data_lake")
        self.running = False
        self.message_queue = queue.Queue()
        self.processed_files = set()

        # Seuils médicaux pour alertes
        self.medical_thresholds = {
            "heart_rate": {"low": 60, "high": 100, "critical_high": 120},
            "spo2": {"critical_low": 90, "low": 95},
            "body_temperature": {"low": 36.0, "high": 38.0, "critical_high": 39.0},
            "hydration_level": {"critical_low": 50, "low": 70}
        }

        # Créer les dossiers du data lake
        self._setup_data_lake()

    def _setup_data_lake(self):
        """Créer la structure du data lake"""
        folders = ["raw", "bronze", "silver", "gold", "alerts"]
        for folder in folders:
            (self.data_lake_path / folder).mkdir(parents=True, exist_ok=True)
        logger.info("Structure du data lake créée")

    def _watch_for_new_files(self):
        """Surveiller les nouveaux fichiers dans le dossier d'entrée"""
        while self.running:
            try:
                # Chercher tous les fichiers JSON dans le dossier raw
                pattern = str(self.input_folder / "*.json")
                current_files = set(glob.glob(pattern))

                # Identifier les nouveaux fichiers
                new_files = current_files - self.processed_files

                for file_path in new_files:
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)

                        # Ajouter à la queue de traitement
                        self.message_queue.put(data)
                        self.processed_files.add(file_path)
                        logger.info(f"📁 Nouveau fichier détecté: {Path(file_path).name}")

                    except Exception as e:
                        logger.error(f"Erreur lecture fichier {file_path}: {e}")

                time.sleep(2)  # Vérifier toutes les 2 secondes

            except Exception as e:
                logger.error(f"Erreur surveillance fichiers: {e}")
                time.sleep(5)

    def _simulate_kafka_messages(self):
        """Simuler des messages IoT pour le test (alternative au simulateur Kafka)"""
        test_patients = [
            "123e4567-e89b-12d3-a456-426614174000",
            "456e7890-e89b-12d3-a456-426614174001",
            "789e0123-e89b-12d3-a456-426614174002"
        ]

        counter = 0
        while self.running:
            try:
                # Générer des données de test variées
                patient_id = test_patients[counter % len(test_patients)]

                # Variations pour créer des scénarios différents
                if counter % 10 == 0:  # Cas critique tous les 10 messages
                    # Données critiques (alerte)
                    test_data = {
                        "patient_id": patient_id,
                        "device_id": f"device_test_{counter}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "measurements": {
                            "heart_rate": 125,  # Critique
                            "respiratory_rate": 28,
                            "spo2": 87.0,      # Critique
                            "body_temperature": 39.5,  # Critique
                            "ambient_temperature": 35.0,
                            "hydration_level": 45.0,   # Critique
                            "activity_level": 1,
                            "heat_index": 42.0
                        },
                        "location": {
                            "latitude": 14.6928,
                            "longitude": -17.4467
                        }
                    }
                else:
                    # Données normales
                    test_data = {
                        "patient_id": patient_id,
                        "device_id": f"device_test_{counter}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "measurements": {
                            "heart_rate": 75 + (counter % 20),
                            "respiratory_rate": 16 + (counter % 8),
                            "spo2": 96.0 + (counter % 4),
                            "body_temperature": 36.8 + (counter % 10) * 0.1,
                            "ambient_temperature": 25.0 + (counter % 10),
                            "hydration_level": 75.0 + (counter % 20),
                            "activity_level": (counter % 5) + 1,
                            "heat_index": 28.0 + (counter % 15)
                        },
                        "location": {
                            "latitude": 14.6928 + (counter % 100) * 0.001,
                            "longitude": -17.4467 + (counter % 100) * 0.001
                        }
                    }

                # Ajouter à la queue de traitement
                self.message_queue.put(test_data)
                counter += 1

                # Attendre entre 3-8 secondes pour simuler un flux réaliste
                time.sleep(5 + (counter % 3))

            except Exception as e:
                logger.error(f"Erreur simulation messages: {e}")
                time.sleep(5)

    def _process_to_bronze(self, raw_data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Traitement Bronze: nettoyage et validation"""
        try:
            bronze_data = {
                "patient_id": raw_data.get("patient_id"),
                "device_id": raw_data.get("device_id"),
                "timestamp": raw_data.get("timestamp"),
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "measurements": {},
                "location": raw_data.get("location", {}),
                "quality_flags": []
            }

            # Traitement des mesures
            measurements = raw_data.get("measurements", {})
            for key, value in measurements.items():
                if value is not None and isinstance(value, (int, float)):
                    bronze_data["measurements"][key] = round(float(value), 2)
                else:
                    bronze_data["quality_flags"].append(f"invalid_{key}")

            # Validation des valeurs critiques
            if not bronze_data["patient_id"]:
                bronze_data["quality_flags"].append("missing_patient_id")

            if not bronze_data["device_id"]:
                bronze_data["quality_flags"].append("missing_device_id")

            return bronze_data
        except Exception as e:
            logger.error(f"Erreur traitement bronze: {e}")
            return None

    def _process_to_silver(self, bronze_data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Traitement Silver: enrichissement et calculs"""
        try:
            silver_data = bronze_data.copy()
            measurements = silver_data.get("measurements", {})

            # Calculs dérivés
            silver_data["derived_metrics"] = {}

            # Calcul du Heat Index si température ambiante disponible
            if "ambient_temperature" in measurements and "hydration_level" in measurements:
                heat_index = measurements["ambient_temperature"] * 1.2 - (measurements["hydration_level"] / 100) * 5
                silver_data["derived_metrics"]["heat_stress_index"] = round(heat_index, 2)

            # Score de risque global (0-100)
            risk_factors = []

            # Facteur SpO2
            spo2 = measurements.get("spo2", 100)
            if spo2 < 90:
                risk_factors.append(30)  # Risque critique
            elif spo2 < 95:
                risk_factors.append(15)  # Risque moyen

            # Facteur température
            temp = measurements.get("body_temperature", 37.0)
            if temp > 39.0:
                risk_factors.append(25)  # Risque critique
            elif temp > 38.0:
                risk_factors.append(10)  # Risque moyen

            # Facteur hydratation
            hydration = measurements.get("hydration_level", 100)
            if hydration < 50:
                risk_factors.append(20)  # Risque critique
            elif hydration < 70:
                risk_factors.append(8)   # Risque moyen

            # Score final
            risk_score = min(sum(risk_factors), 100)
            silver_data["derived_metrics"]["risk_score"] = risk_score

            # Classification du risque
            if risk_score >= 50:
                silver_data["risk_level"] = "critical"
            elif risk_score >= 25:
                silver_data["risk_level"] = "high"
            elif risk_score >= 10:
                silver_data["risk_level"] = "medium"
            else:
                silver_data["risk_level"] = "low"

            return silver_data
        except Exception as e:
            logger.error(f"Erreur traitement silver: {e}")
            return None

    def _check_alerts(self, silver_data: Dict[Any, Any]) -> List[Dict[Any, Any]]:
        """Vérifier et générer les alertes"""
        alerts = []
        measurements = silver_data.get("measurements", {})
        patient_id = silver_data.get("patient_id")
        device_id = silver_data.get("device_id")
        timestamp = silver_data.get("timestamp")

        try:
            # Alerte SpO2 critique
            spo2 = measurements.get("spo2")
            if spo2 and spo2 < self.medical_thresholds["spo2"]["critical_low"]:
                alerts.append({
                    "alert_id": f"spo2_critical_{device_id}_{timestamp}",
                    "patient_id": patient_id,
                    "device_id": device_id,
                    "timestamp": timestamp,
                    "alert_type": "spo2_critical",
                    "severity": "critical",
                    "message": f"SpO2 critique: {spo2}% (< {self.medical_thresholds['spo2']['critical_low']}%)",
                    "value": spo2,
                    "threshold": self.medical_thresholds["spo2"]["critical_low"]
                })

            # Alerte température élevée
            temp = measurements.get("body_temperature")
            if temp and temp > self.medical_thresholds["body_temperature"]["critical_high"]:
                alerts.append({
                    "alert_id": f"temp_critical_{device_id}_{timestamp}",
                    "patient_id": patient_id,
                    "device_id": device_id,
                    "timestamp": timestamp,
                    "alert_type": "temperature_critical",
                    "severity": "critical",
                    "message": f"Température critique: {temp}°C (> {self.medical_thresholds['body_temperature']['critical_high']}°C)",
                    "value": temp,
                    "threshold": self.medical_thresholds["body_temperature"]["critical_high"]
                })

            # Alerte déshydratation
            hydration = measurements.get("hydration_level")
            if hydration and hydration < self.medical_thresholds["hydration_level"]["critical_low"]:
                alerts.append({
                    "alert_id": f"hydration_critical_{device_id}_{timestamp}",
                    "patient_id": patient_id,
                    "device_id": device_id,
                    "timestamp": timestamp,
                    "alert_type": "dehydration_critical",
                    "severity": "critical",
                    "message": f"Déshydratation critique: {hydration}% (< {self.medical_thresholds['hydration_level']['critical_low']}%)",
                    "value": hydration,
                    "threshold": self.medical_thresholds["hydration_level"]["critical_low"]
                })

            # Alerte rythme cardiaque
            hr = measurements.get("heart_rate")
            if hr and hr > self.medical_thresholds["heart_rate"]["critical_high"]:
                alerts.append({
                    "alert_id": f"hr_critical_{device_id}_{timestamp}",
                    "patient_id": patient_id,
                    "device_id": device_id,
                    "timestamp": timestamp,
                    "alert_type": "heart_rate_critical",
                    "severity": "critical",
                    "message": f"Rythme cardiaque élevé: {hr} bpm (> {self.medical_thresholds['heart_rate']['critical_high']} bpm)",
                    "value": hr,
                    "threshold": self.medical_thresholds["heart_rate"]["critical_high"]
                })

            return alerts
        except Exception as e:
            logger.error(f"Erreur vérification alertes: {e}")
            return []

    def _save_data(self, data: Dict[Any, Any], layer: str, timestamp: str):
        """Sauvegarder les données dans une couche spécifique du data lake"""
        try:
            filename = f"iot_{layer}_{timestamp}_{data.get('device_id', 'unknown')}.json"
            filepath = self.data_lake_path / layer / filename

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Données {layer} sauvegardées: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Erreur sauvegarde {layer}: {e}")
            return None

    def _save_alerts(self, alerts: List[Dict[Any, Any]], timestamp: str):
        """Sauvegarder les alertes"""
        if not alerts:
            return

        try:
            filename = f"alerts_{timestamp}.json"
            filepath = self.data_lake_path / "alerts" / filename

            with open(filepath, 'w') as f:
                json.dump(alerts, f, indent=2, default=str)

            logger.warning(f"🚨 {len(alerts)} alerte(s) générée(s) et sauvegardée(s): {filename}")

            # Log des alertes critiques
            for alert in alerts:
                if alert.get("severity") == "critical":
                    logger.warning(f"🚨 ALERTE CRITIQUE: {alert['message']}")

        except Exception as e:
            logger.error(f"Erreur sauvegarde alertes: {e}")

    def _process_message(self, message_data: Dict[Any, Any]):
        """Traiter un message IoT complet (pipeline bronze → silver → alertes)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            # 1. Traitement bronze
            bronze_data = self._process_to_bronze(message_data)
            if bronze_data:
                self._save_data(bronze_data, "bronze", timestamp)

                # 2. Traitement silver
                silver_data = self._process_to_silver(bronze_data)
                if silver_data:
                    self._save_data(silver_data, "silver", timestamp)

                    # 3. Vérification alertes
                    alerts = self._check_alerts(silver_data)
                    if alerts:
                        self._save_alerts(alerts, timestamp)

                    logger.info(f"✅ Message traité: {message_data.get('device_id', 'unknown')} - Risque: {silver_data.get('risk_level', 'unknown')}")
                else:
                    logger.warning("❌ Échec traitement silver")
            else:
                logger.warning("❌ Échec traitement bronze")

        except Exception as e:
            logger.error(f"Erreur traitement message: {e}")

    def start_processing(self, simulate_data=True):
        """Démarrer le traitement en continu"""
        logger.info("🚀 Démarrage du processeur de streaming IoT Kidjamo (Version Alternative)")

        self.running = True
        processed_count = 0

        # Démarrer les threads de surveillance
        threads = []

        # Thread pour surveiller les nouveaux fichiers
        file_watcher = threading.Thread(target=self._watch_for_new_files)
        file_watcher.daemon = True
        file_watcher.start()
        threads.append(file_watcher)

        # Thread pour simuler des données (optionnel)
        if simulate_data:
            simulator = threading.Thread(target=self._simulate_kafka_messages)
            simulator.daemon = True
            simulator.start()
            threads.append(simulator)
            logger.info("📊 Simulateur de données IoT démarré")

        try:
            while self.running:
                try:
                    # Traiter les messages dans la queue
                    try:
                        message_data = self.message_queue.get(timeout=1)
                        self._process_message(message_data)
                        processed_count += 1

                        if processed_count % 5 == 0:
                            logger.info(f"📊 Messages traités: {processed_count}")

                    except queue.Empty:
                        # Pas de nouveaux messages, continuer
                        pass

                    time.sleep(0.1)  # Petite pause pour éviter la surcharge CPU

                except Exception as e:
                    logger.error(f"Erreur dans la boucle de traitement: {e}")
                    time.sleep(5)  # Pause plus longue en cas d'erreur

        except KeyboardInterrupt:
            logger.info("Arrêt demandé par l'utilisateur")
        finally:
            self.stop_processing()
            logger.info(f"🏁 Processeur arrêté. Total messages traités: {processed_count}")

    def stop_processing(self):
        """Arrêter le traitement"""
        self.running = False
        logger.info("Processeur de streaming arrêté")

def main():
    """Point d'entrée principal"""
    processor = AlternativeStreamingProcessor()

    try:
        logger.info("🔧 Mode: Alternative Stream Processor (sans Kafka)")
        logger.info("📁 Surveillance: ../data_lake/raw/")
        logger.info("🤖 Simulation: Données de test générées automatiquement")
        logger.info("⚡ Ctrl+C pour arrêter")
        processor.start_processing(simulate_data=True)
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
    finally:
        processor.stop_processing()

if __name__ == "__main__":
    main()
