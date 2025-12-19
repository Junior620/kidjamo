#!/usr/bin/env python3
"""
Simulateur de Bracelet IoT Kidjamo
Simule les données réelles de votre bracelet pour tester la pipeline MQTT → Kinesis
"""

import json
import asyncio
import ssl
import time
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, Any
import logging
import os

# Simulateur MQTT (utilise paho-mqtt pour les tests)
try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("⚠️ paho-mqtt non installé. Utilisez: pip install paho-mqtt")

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "bracelet_simulator", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

class BraceletIoTSimulator:
    """Simule un bracelet IoT réel avec données physiologiques"""

    def __init__(self, device_id: str, patient_id: str):
        self.device_id = device_id
        self.patient_id = patient_id

        # États physiologiques simulés
        self.baseline_hr = random.randint(60, 80)  # Fréquence cardiaque de base
        self.baseline_spo2 = random.uniform(95.0, 99.0)  # SpO2 de base
        self.baseline_temp = random.uniform(36.2, 37.0)  # Température de base

        # État de l'accéléromètre
        self.activity_state = "repos"  # repos, marche, course, chute
        self.battery_level = random.randint(70, 100)

        # Simulation de scenarios médicaux
        self.scenarios = {
            "normal": {"weight": 0.7, "duration": 300},  # 70% du temps normal
            "stress": {"weight": 0.15, "duration": 120},  # 15% stress
            "exercise": {"weight": 0.10, "duration": 180},  # 10% exercice
            "crisis": {"weight": 0.05, "duration": 60}   # 5% crise drépanocytose
        }

        self.current_scenario = "normal"
        self.scenario_start = time.time()

    def _select_scenario(self):
        """Sélectionne un scénario médical aléatoire"""
        if time.time() - self.scenario_start > self.scenarios[self.current_scenario]["duration"]:
            # Changer de scénario
            weights = [s["weight"] for s in self.scenarios.values()]
            scenarios = list(self.scenarios.keys())

            self.current_scenario = random.choices(scenarios, weights=weights)[0]
            self.scenario_start = time.time()

            logger.info(f"🔄 Bracelet {self.device_id}: Nouveau scénario → {self.current_scenario}")

    def generate_vitals(self) -> Dict[str, Any]:
        """Génère des données vitales selon le scénario actuel"""
        self._select_scenario()

        # Ajustements selon le scénario
        if self.current_scenario == "normal":
            hr_variance = random.randint(-5, 5)
            spo2_variance = random.uniform(-1.0, 1.0)
            temp_variance = random.uniform(-0.2, 0.2)

        elif self.current_scenario == "stress":
            hr_variance = random.randint(10, 25)
            spo2_variance = random.uniform(-2.0, 0.5)
            temp_variance = random.uniform(0.1, 0.5)

        elif self.current_scenario == "exercise":
            hr_variance = random.randint(30, 60)
            spo2_variance = random.uniform(-1.0, 2.0)
            temp_variance = random.uniform(0.2, 0.8)

        elif self.current_scenario == "crisis":
            # Simulation crise drépanocytose
            hr_variance = random.randint(20, 40)
            spo2_variance = random.uniform(-8.0, -3.0)  # Chute significative
            temp_variance = random.uniform(0.5, 1.5)

        return {
            "device_id": self.device_id,
            "patient_id": self.patient_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "heart_rate": max(40, min(200, self.baseline_hr + hr_variance)),
            "spo2": max(70.0, min(100.0, self.baseline_spo2 + spo2_variance)),
            "temperature": max(35.0, min(42.0, self.baseline_temp + temp_variance)),
            "scenario": self.current_scenario,
            "battery": self.battery_level,
            "signal": random.randint(70, 100)
        }

    def generate_accelerometer(self) -> Dict[str, Any]:
        """Génère des données d'accéléromètre selon l'activité"""

        # Détecter l'activité selon le scénario
        if self.current_scenario == "normal":
            # Repos/mouvement léger
            accel_x = random.uniform(-0.5, 0.5)
            accel_y = random.uniform(9.2, 9.8)  # Gravité dominante
            accel_z = random.uniform(-0.3, 0.3)
            self.activity_state = "repos"

        elif self.current_scenario == "exercise":
            # Activité intense
            accel_x = random.uniform(-3.0, 3.0)
            accel_y = random.uniform(7.0, 12.0)
            accel_z = random.uniform(-2.0, 2.0)
            self.activity_state = "course"

        elif self.current_scenario == "stress":
            # Mouvement agité
            accel_x = random.uniform(-1.5, 1.5)
            accel_y = random.uniform(8.5, 10.5)
            accel_z = random.uniform(-1.0, 1.0)
            self.activity_state = "marche"

        elif self.current_scenario == "crisis":
            # Possible chute ou mouvement brusque
            if random.random() < 0.3:  # 30% de chance de chute
                accel_x = random.uniform(-15.0, 15.0)
                accel_y = random.uniform(-5.0, 20.0)
                accel_z = random.uniform(-10.0, 10.0)
                self.activity_state = "chute_detectee"
            else:
                accel_x = random.uniform(-2.0, 2.0)
                accel_y = random.uniform(8.0, 11.0)
                accel_z = random.uniform(-1.5, 1.5)
                self.activity_state = "mouvement_anormal"

        magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5

        return {
            "device_id": self.device_id,
            "patient_id": self.patient_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "x": round(accel_x, 3),
            "y": round(accel_y, 3),
            "z": round(accel_z, 3),
            "magnitude": round(magnitude, 3),
            "activity": self.activity_state
        }

    def generate_status(self) -> Dict[str, Any]:
        """Génère des données de statut du device"""
        # Décharge progressive de la batterie
        if random.random() < 0.1:  # 10% de chance de décharger
            self.battery_level = max(10, self.battery_level - 1)

        return {
            "device_id": self.device_id,
            "patient_id": self.patient_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "battery": self.battery_level,
            "signal": random.randint(60, 100),
            "firmware": "v2.1.3",
            "uptime_hours": random.randint(24, 720)
        }

class MQTTBraceletPublisher:
    """Publie les données du bracelet via MQTT vers AWS IoT Core"""

    def __init__(self,
                 endpoint: str,
                 cert_path: str,
                 key_path: str,
                 ca_path: str,
                 client_id: str = None):

        self.endpoint = endpoint
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path
        self.client_id = client_id or f"bracelet-sim-{uuid.uuid4()}"

        self.client = None
        self.is_connected = False

        self.logger = logging.getLogger(f"{__name__}.MQTTPublisher")

    def _on_connect(self, client, userdata, flags, rc):
        """Callback de connexion MQTT"""
        if rc == 0:
            self.is_connected = True
            self.logger.info(f"✅ Connecté à AWS IoT Core: {self.client_id}")
        else:
            self.logger.error(f"❌ Erreur connexion MQTT: {rc}")

    def _on_disconnect(self, client, userdata, rc):
        """Callback de déconnexion MQTT"""
        self.is_connected = False
        self.logger.info(f"🔌 Déconnecté de AWS IoT Core: {self.client_id}")

    def _on_publish(self, client, userdata, mid):
        """Callback de publication réussie"""
        self.logger.debug(f"📤 Message publié: {mid}")

    def connect(self) -> bool:
        """Établit la connexion MQTT sécurisée"""
        try:
            self.client = mqtt.Client(self.client_id)

            # Configuration SSL/TLS
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(self.ca_path)
            context.load_cert_chain(self.cert_path, self.key_path)

            self.client.tls_set_context(context)

            # Callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_publish = self._on_publish

            # Connexion
            self.client.connect(self.endpoint, 8883, 60)
            self.client.loop_start()

            # Attendre la connexion
            timeout = 10
            while not self.is_connected and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1

            return self.is_connected

        except Exception as e:
            self.logger.error(f"❌ Erreur connexion MQTT: {e}")
            return False

    def publish_message(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Publie un message MQTT"""
        if not self.is_connected:
            return False

        try:
            message = json.dumps(payload)
            result = self.client.publish(topic, message, qos=1)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                return True
            else:
                self.logger.error(f"❌ Erreur publication: {result.rc}")
                return False

        except Exception as e:
            self.logger.error(f"❌ Erreur publication message: {e}")
            return False

    def disconnect(self):
        """Ferme la connexion MQTT"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()

class BraceletFleetSimulator:
    """Simule une flotte de bracelets IoT"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)
        self.publishers = {}
        self.bracelets = {}
        self.is_running = False

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Charge la configuration"""
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r') as f:
                return json.load(f)

        # Configuration par défaut
        return {
            "aws_iot": {
                "endpoint": os.environ.get('AWS_IOT_ENDPOINT', 'your-endpoint.iot.eu-west-1.amazonaws.com'),
                "cert_path": os.environ.get('AWS_IOT_CERT_PATH', './certs/device-cert.pem'),
                "key_path": os.environ.get('AWS_IOT_KEY_PATH', './certs/private-key.pem'),
                "ca_path": os.environ.get('AWS_IOT_CA_PATH', './certs/root-ca.pem')
            },
            "simulation": {
                "bracelet_count": 5,
                "vitals_interval": 30,  # secondes
                "accelerometer_interval": 5,  # secondes
                "status_interval": 300  # secondes
            }
        }

    async def start_simulation(self):
        """Démarre la simulation de la flotte"""
        logger.info("🚀 Démarrage simulation flotte de bracelets IoT")

        # Créer les bracelets simulés
        for i in range(self.config["simulation"]["bracelet_count"]):
            device_id = f"bracelet-{i+1:03d}"
            patient_id = f"patient-{i+1:03d}"

            # Créer le simulateur de bracelet
            bracelet = BraceletIoTSimulator(device_id, patient_id)
            self.bracelets[device_id] = bracelet

            # Créer le publisher MQTT
            publisher = MQTTBraceletPublisher(
                endpoint=self.config["aws_iot"]["endpoint"],
                cert_path=self.config["aws_iot"]["cert_path"],
                key_path=self.config["aws_iot"]["key_path"],
                ca_path=self.config["aws_iot"]["ca_path"],
                client_id=f"kidjamo-bracelet-{device_id}"
            )

            if publisher.connect():
                self.publishers[device_id] = publisher
                logger.info(f"✅ Bracelet {device_id} connecté")
            else:
                logger.error(f"❌ Impossible de connecter {device_id}")

        self.is_running = True

        # Démarrer les tâches de publication
        tasks = [
            self._publish_vitals_loop(),
            self._publish_accelerometer_loop(),
            self._publish_status_loop()
        ]

        await asyncio.gather(*tasks)

    async def _publish_vitals_loop(self):
        """Boucle de publication des données vitales"""
        while self.is_running:
            for device_id, bracelet in self.bracelets.items():
                if device_id in self.publishers:
                    vitals = bracelet.generate_vitals()
                    topic = f"kidjamo/bracelet/{device_id}/vitals"

                    success = self.publishers[device_id].publish_message(topic, vitals)
                    if success:
                        logger.info(f"📊 {device_id}: Vitals → HR:{vitals['heart_rate']} SpO2:{vitals['spo2']:.1f}% T:{vitals['temperature']:.1f}°C")

            await asyncio.sleep(self.config["simulation"]["vitals_interval"])

    async def _publish_accelerometer_loop(self):
        """Boucle de publication des données d'accéléromètre"""
        while self.is_running:
            for device_id, bracelet in self.bracelets.items():
                if device_id in self.publishers:
                    accel = bracelet.generate_accelerometer()
                    topic = f"kidjamo/bracelet/{device_id}/accelerometer"

                    success = self.publishers[device_id].publish_message(topic, accel)
                    if success:
                        logger.info(f"🏃 {device_id}: Accel → {accel['activity']} (mag:{accel['magnitude']:.2f})")

            await asyncio.sleep(self.config["simulation"]["accelerometer_interval"])

    async def _publish_status_loop(self):
        """Boucle de publication du statut des devices"""
        while self.is_running:
            for device_id, bracelet in self.bracelets.items():
                if device_id in self.publishers:
                    status = bracelet.generate_status()
                    topic = f"kidjamo/bracelet/{device_id}/status"

                    success = self.publishers[device_id].publish_message(topic, status)
                    if success:
                        logger.info(f"🔋 {device_id}: Status → Battery:{status['battery']}% Signal:{status['signal']}%")

            await asyncio.sleep(self.config["simulation"]["status_interval"])

    async def stop_simulation(self):
        """Arrête la simulation"""
        logger.info("🛑 Arrêt de la simulation")
        self.is_running = False

        for publisher in self.publishers.values():
            publisher.disconnect()

        logger.info("✅ Simulation arrêtée")

# Point d'entrée
async def main():
    """Démarre la simulation de bracelets IoT"""
    simulator = BraceletFleetSimulator()

    try:
        await simulator.start_simulation()
    except KeyboardInterrupt:
        logger.info("🔄 Arrêt demandé par l'utilisateur")
    finally:
        await simulator.stop_simulation()

if __name__ == "__main__":
    asyncio.run(main())
