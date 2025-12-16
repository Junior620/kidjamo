"""
Processeur de streaming IoT simplifié pour Kidjamo
Alternative sans PySpark pour éviter les problèmes de compatibilité Java
"""

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from kafka import KafkaConsumer
from typing import Dict, Any, List
import pandas as pd
import threading
from concurrent.futures import ThreadPoolExecutor


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

class SimpleStreamingProcessor:
    """
    Processeur de streaming simplifié pour données IoT Kidjamo
    Alternative légère sans PySpark
    """

    def __init__(self, kafka_servers="localhost:9092", topics=None):
        self.kafka_servers = kafka_servers
        self.topics = topics or ["iot-raw-data"]
        self.data_lake_path = Path("../data_lake")
        self.running = False
        self.consumer = None

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

    def _create_kafka_consumer(self):
        """Créer le consumer Kafka"""
        try:
            self.consumer = KafkaConsumer(
                *self.topics,
                bootstrap_servers=self.kafka_servers,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')) if x else None,
                auto_offset_reset='latest',
                enable_auto_commit=True,
                group_id='kidjamo-streaming-processor',
                consumer_timeout_ms=1000
            )
            logger.info(f"Consumer Kafka créé pour topics: {self.topics}")
            return True
        except Exception as e:
            logger.error(f"Erreur création consumer Kafka: {e}")
            return False

    def _save_to_raw(self, data: Dict[Any, Any], timestamp: str):
        """Sauvegarder les données brutes"""
        try:
            filename = f"iot_raw_{timestamp}_{data.get('device_id', 'unknown')}.json"
            filepath = self.data_lake_path / "raw" / filename

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Données brutes sauvegardées: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Erreur sauvegarde raw: {e}")
            return None

    def _process_to_bronze(self, raw_data: Dict[Any, Any]) -> Dict[Any, Any]:
        """Traitement Bronze: nettoyage et validation"""
        try:
            # Validation et nettoyage des données
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

    def _save_to_bronze(self, data: Dict[Any, Any], timestamp: str):
        """Sauvegarder les données bronze"""
        try:
            filename = f"iot_bronze_{timestamp}_{data.get('device_id', 'unknown')}.json"
            filepath = self.data_lake_path / "bronze" / filename

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Données bronze sauvegardées: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Erreur sauvegarde bronze: {e}")
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

    def _save_to_silver(self, data: Dict[Any, Any], timestamp: str):
        """Sauvegarder les données silver"""
        try:
            filename = f"iot_silver_{timestamp}_{data.get('device_id', 'unknown')}.json"
            filepath = self.data_lake_path / "silver" / filename

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.debug(f"Données silver sauvegardées: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Erreur sauvegarde silver: {e}")
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

    def _process_message(self, message_value: Dict[Any, Any]):
        """Traiter un message IoT complet (pipeline bronze → silver → alertes)"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            # 1. Sauvegarder en raw
            self._save_to_raw(message_value, timestamp)

            # 2. Traitement bronze
            bronze_data = self._process_to_bronze(message_value)
            if bronze_data:
                self._save_to_bronze(bronze_data, timestamp)

                # 3. Traitement silver
                silver_data = self._process_to_silver(bronze_data)
                if silver_data:
                    self._save_to_silver(silver_data, timestamp)

                    # 4. Vérification alertes
                    alerts = self._check_alerts(silver_data)
                    if alerts:
                        self._save_alerts(alerts, timestamp)

                    logger.info(f"✅ Message traité: {message_value.get('device_id', 'unknown')} - Risque: {silver_data.get('risk_level', 'unknown')}")
                else:
                    logger.warning("❌ Échec traitement silver")
            else:
                logger.warning("❌ Échec traitement bronze")

        except Exception as e:
            logger.error(f"Erreur traitement message: {e}")

    def start_processing(self):
        """Démarrer le traitement en continu"""
        logger.info("🚀 Démarrage du processeur de streaming IoT Kidjamo")

        if not self._create_kafka_consumer():
            logger.error("Impossible de créer le consumer Kafka")
            return

        self.running = True
        processed_count = 0

        try:
            while self.running:
                try:
                    # Consommer les messages par batch
                    message_batch = self.consumer.poll(timeout_ms=1000)

                    if message_batch:
                        with ThreadPoolExecutor(max_workers=4) as executor:
                            futures = []

                            for topic_partition, messages in message_batch.items():
                                for message in messages:
                                    if message.value:
                                        future = executor.submit(self._process_message, message.value)
                                        futures.append(future)
                                        processed_count += 1

                            # Attendre que tous les messages soient traités
                            for future in futures:
                                future.result()

                        if processed_count % 10 == 0:
                            logger.info(f"📊 Messages traités: {processed_count}")

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
        if self.consumer:
            self.consumer.close()
        logger.info("Processeur de streaming arrêté")

def main():
    """Point d'entrée principal"""
    processor = SimpleStreamingProcessor()

    try:
        processor.start_processing()
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
    finally:
        processor.stop_processing()

if __name__ == "__main__":
    main()
