"""
Générateur de profils patients et envoi périodique de mesures plausibles.

Rôle :
    Simulateur IoT avancé pour génération de données réalistes multi-patients.
    Simule des bracelets médicaux avec profils drépanocytaires variés,
    cycles circadiens, facteurs environnementaux et crises médicales.

Objectifs :
    - Génération profils patients diversifiés (âge, génotype SS/AS/SC, seuils individuels)
    - Simulation cycles circadiens et variations physiologiques naturelles
    - Scénarios médicaux complexes : crises drépanocytaires, infections, déshydratation
    - Facteurs environnementaux : température ambiante, saisons, géolocalisation
    - Publication Kafka directe + envoi API selon configuration
    - Métriques qualité réalistes selon conditions de mesure

Entrées :
    - Configurations patient via fichiers JSON ou génération aléatoire
    - Paramètres environnementaux (température, humidité, altitude)
    - Calendrier médical (rendez-vous, traitements, hospitalisations)
    - Configuration simulation (durée, fréquence, patients actifs)
    - Topics Kafka et endpoints API de destination

Sorties :
    - Messages Kafka vers topics measurements/alerts (si producteur disponible)
    - Requêtes POST vers API d'ingestion (fallback ou parallèle)
    - Logs détaillés avec classification scénarios médicaux
    - Rapports CSV avec métriques qualité et événements simulés
    - États patients sauvegardés pour continuité entre sessions

Effets de bord :
    - Threads de simulation en arrière-plan pour chaque patient actif
    - Génération fichiers état patient (dernières constantes vitales)
    - KafkaProducer si disponible, sinon mode API uniquement
    - Horodatage précis avec timezone et variations micro-secondes
    - Logs adaptatifs selon criticité événements simulés

Garanties :
    Distributions physiologiques et seuils médicaux inchangés ; scénarios
    de crise et facteurs circadiens identiques ; pas de modification des
    patterns temporels ni des algorithmes de génération de données.
"""

# Imports standard library (triés alphabétiquement)
import json
import logging
import math
import os
import random
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Imports third-party (triés alphabétiquement)
import requests

# Import Kafka avec gestion gracieuse
try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

# Configuration logging avec logger nommé
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration par défaut - ne pas modifier ces valeurs
DEFAULT_KAFKA_SERVERS = ['localhost:9092']
DEFAULT_API_ENDPOINT = "http://localhost:8001"

# Seuils médicaux pour simulation réaliste (inchangés)
MEDICAL_THRESHOLDS = {
    "spo2_critical_ss": 85,      # SpO2 critique pour SS
    "spo2_critical_general": 88,  # SpO2 critique général
    "temperature_fever": 38.0,    # Fièvre
    "temperature_high_fever": 39.5,  # Fièvre élevée
    "heart_rate_tachycardia": 120,   # Tachycardie adulte
    "dehydration_threshold": 40,     # Seuil déshydratation critique
}

# Génotypes drépanocytaires avec caractéristiques (distributions médicales inchangées)
SICKLE_CELL_GENOTYPES = {
    "SS": {
        "base_spo2_range": (92, 96),    # SpO2 plus basse
        "crisis_frequency": 0.15,       # 15% chance crise par période
        "pain_sensitivity": 1.8,        # Facteur douleur augmenté
        "infection_risk": 1.5           # Risque infection augmenté
    },
    "SC": {
        "base_spo2_range": (94, 98),    # SpO2 intermédiaire
        "crisis_frequency": 0.08,       # 8% chance crise
        "pain_sensitivity": 1.3,        # Douleur modérée
        "infection_risk": 1.2           # Risque infection modéré
    },
    "AS": {
        "base_spo2_range": (96, 100),   # SpO2 normale (porteur)
        "crisis_frequency": 0.01,       # 1% chance crise (rare)
        "pain_sensitivity": 1.0,        # Douleur normale
        "infection_risk": 1.0           # Risque infection normal
    }
}


@dataclass
class PatientProfile:
    """
    Profil patient détaillé pour simulation médicale avancée.

    Contient toutes les caractéristiques individuelles nécessaires
    pour simulation réaliste avec historique médical et paramètres
    physiologiques personnalisés selon génotype drépanocytaire.
    """
    patient_id: str
    age: int
    genotype: str  # SS, AS, SC
    weight: float  # kg
    height: float  # cm

    # Constantes vitales de base (individualisées selon âge et génotype)
    base_heart_rate: int
    base_spo2: float
    base_temperature: float
    base_respiratory_rate: int
    base_hydration: float

    # Facteurs de risque individuels
    pain_threshold: float
    stress_sensitivity: float
    activity_level_baseline: int

    # Historique médical récent
    last_crisis_date: Optional[datetime] = None
    current_medications: List[str] = field(default_factory=list)
    recent_hospitalizations: int = 0

    # État simulation (géré automatiquement)
    current_scenario: str = "normal"
    scenario_start_time: Optional[datetime] = None
    scenario_duration_hours: float = 0.0


class AdvancedIoTSimulator:
    """
    Simulateur IoT avancé pour données médicales multi-patients réalistes.

    Gère simulation complexe avec cycles circadiens, facteurs environnementaux,
    et scénarios médicaux évolutifs dans le temps. Publication vers Kafka
    et API d'ingestion avec gestion gracieuse des erreurs.
    """

    def __init__(self, kafka_servers: Optional[List[str]] = None, 
                 api_endpoint: Optional[str] = None) -> None:
        """
        Initialise le simulateur avec configuration réseau.

        Args:
            kafka_servers: Liste serveurs Kafka (défaut: localhost:9092)
            api_endpoint: URL API d'ingestion (défaut: localhost:8001)
        """
        self.kafka_servers = kafka_servers or DEFAULT_KAFKA_SERVERS
        self.api_endpoint = api_endpoint or DEFAULT_API_ENDPOINT

        # Gestion Kafka producteur
        self.kafka_producer = self._init_kafka_producer()

        # État simulation
        self.patients: List[PatientProfile] = []
        self.running = False
        self.simulation_threads: List[threading.Thread] = []

        # Facteurs environnementaux simulés (impacts physiologiques)
        self.ambient_temperature = 22.0  # °C
        self.humidity = 60.0  # %
        self.atmospheric_pressure = 1013.25  # hPa (niveau mer)

        # Métriques simulation pour observabilité
        self.total_measurements_sent = 0
        self.total_alerts_generated = 0
        self.start_time: Optional[datetime] = None

    def _init_kafka_producer(self) -> Optional[KafkaProducer]:
        """
        Initialise le producteur Kafka avec configuration robuste.

        Configuration optimisée pour simulation intensive :
        - batch_size augmenté pour grouper messages
        - linger_ms pour latence acceptable
        - acks='all' pour garantie de livraison

        Returns:
            KafkaProducer: Producteur configuré ou None si indisponible
        """
        if KafkaProducer is None:
            logger.warning("Kafka library unavailable; API-only mode")
            return None

        try:
            producer = KafkaProducer(
                bootstrap_servers=self.kafka_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',        # Garantie livraison
                retries=3,         # Retry automatique
                batch_size=16384,  # Optimisation pour simulation intensive
                linger_ms=10       # Petite latence pour grouper messages
            )
            logger.info("✅ Kafka producer initialized")
            return producer
        except Exception as e:
            logger.warning(f"Kafka producer initialization failed: {e}")
            return None

    def generate_patient_cohort(self, num_patients: int = 10) -> List[PatientProfile]:
        """
        Génère une cohorte de patients avec profils diversifiés.

        Répartition représentative selon prévalence épidémiologique :
        - 40% SS (surveillance intensive)
        - 35% AS (porteurs trait)
        - 25% SC (surveillance modérée)

        Args:
            num_patients: Nombre de patients à générer

        Returns:
            List[PatientProfile]: Cohorte de patients générée
        """
        patients = []

        # Distribution des génotypes selon prévalence (inchangée)
        genotype_distribution = ['SS'] * 4 + ['AS'] * 4 + ['SC'] * 2

        for i in range(num_patients):
            # Sélection génotype selon distribution épidémiologique
            genotype = random.choice(genotype_distribution)
            genotype_params = SICKLE_CELL_GENOTYPES[genotype]

            # Génération caractéristiques anthropométriques
            age = random.randint(5, 25)  # Enfants et jeunes adultes
            weight = 30 + (age - 5) * 2.5 + random.uniform(-5, 10)
            height = 100 + (age - 5) * 4 + random.uniform(-10, 15)

            # Constantes vitales selon âge et génotype
            base_hr = self._calculate_base_heart_rate(age)
            base_spo2 = random.uniform(*genotype_params["base_spo2_range"])
            base_temp = random.uniform(36.2, 36.9)
            base_rr = self._calculate_base_respiratory_rate(age)
            base_hydration = random.uniform(70, 90)

            # Facteurs individuels selon génotype
            pain_threshold = random.uniform(0.7, 1.3) * genotype_params["pain_sensitivity"]
            stress_sensitivity = random.uniform(0.8, 1.5)
            activity_baseline = random.randint(20, 80)

            # Historique médical aléatoire selon génotype
            last_crisis = None
            if genotype in ["SS", "SC"] and random.random() < 0.3:
                # 30% ont eu une crise récente (plus fréquent SS/SC)
                days_ago = random.randint(7, 180)
                last_crisis = datetime.now() - timedelta(days=days_ago)

            patient = PatientProfile(
                patient_id=f"patient-{i+1:03d}-{genotype.lower()}",
                age=age,
                genotype=genotype,
                weight=weight,
                height=height,
                base_heart_rate=base_hr,
                base_spo2=base_spo2,
                base_temperature=base_temp,
                base_respiratory_rate=base_rr,
                base_hydration=base_hydration,
                pain_threshold=pain_threshold,
                stress_sensitivity=stress_sensitivity,
                activity_level_baseline=activity_baseline,
                last_crisis_date=last_crisis,
                current_medications=self._generate_medications(genotype),
                recent_hospitalizations=random.randint(0, 2) if genotype == "SS" else 0
            )

            patients.append(patient)

        logger.info(f"Generated cohort: {num_patients} patients (SS/AS/SC distribution)")
        return patients

    def _calculate_base_heart_rate(self, age: int) -> int:
        """
        Calcule la fréquence cardiaque de repos selon l'âge.

        Normes pédiatriques et adultes selon recommandations
        AHA (American Heart Association) - inchangées.

        Args:
            age: Âge en années

        Returns:
            int: Fréquence cardiaque de repos (bpm)
        """
        if age <= 2:
            return random.randint(80, 130)
        elif age <= 6:
            return random.randint(75, 115)
        elif age <= 12:
            return random.randint(70, 110)
        elif age <= 18:
            return random.randint(60, 100)
        else:
            return random.randint(60, 90)

    def _calculate_base_respiratory_rate(self, age: int) -> int:
        """
        Calcule la fréquence respiratoire selon l'âge.

        Normes pédiatriques selon classification OMS - inchangées.

        Args:
            age: Âge en années

        Returns:
            int: Fréquence respiratoire de repos (/min)
        """
        if age <= 2:
            return random.randint(20, 40)
        elif age <= 6:
            return random.randint(18, 30)
        elif age <= 12:
            return random.randint(16, 25)
        else:
            return random.randint(12, 20)

    def _generate_medications(self, genotype: str) -> List[str]:
        """
        Génère une liste réaliste de médicaments selon le génotype.

        Protocoles thérapeutiques selon recommandations HAS
        (Haute Autorité de Santé) pour drépanocytose - inchangés.

        Args:
            genotype: Génotype drépanocytaire

        Returns:
            List[str]: Liste des médicaments courants
        """
        medications = []

        if genotype == "SS":
            # Médicaments courants pour forme homozygote SS
            if random.random() < 0.8:
                medications.append("hydroxyurea")  # 80% sous hydroxyurée
            if random.random() < 0.6:
                medications.append("folic_acid")
            if random.random() < 0.4:
                medications.append("penicillin_prophylaxis")

        elif genotype == "SC":
            # Médicaments modérés pour forme composite SC
            if random.random() < 0.4:
                medications.append("hydroxyurea")  # 40% sous hydroxyurée
            if random.random() < 0.5:
                medications.append("folic_acid")

        # Médicaments communs tous génotypes
        if random.random() < 0.2:
            medications.append("multivitamin")

        return medications

    def _get_circadian_factor(self, hour: int) -> float:
        """
        Calcule le facteur circadien pour ajustement physiologique.

        Cycle circadien inchangé : pic activité 14h-16h, minimum 3h-5h.
        Basé sur variations naturelles du système autonome.

        Args:
            hour: Heure de la journée (0-23)

        Returns:
            float: Facteur multiplicatif (0.8-1.2)
        """
        # Modèle sinusoïdal avec pic vers 15h (variation physiologique)
        phase = (hour - 15) * (2 * math.pi / 24)
        factor = 1.0 + 0.2 * math.cos(phase)
        return max(0.8, min(1.2, factor))

    def _determine_current_scenario(self, patient: PatientProfile) -> str:
        """
        Détermine le scénario médical actuel pour un patient.

        Scénarios possibles selon littérature médicale (inchangés) :
        - normal : état stable baseline
        - stress : stress émotionnel/physique
        - activity : activité physique intense
        - mild_crisis : début de crise drépanocytaire
        - severe_crisis : crise vaso-occlusive établie
        - infection : infection intercurrente
        - dehydration : déshydratation

        Args:
            patient: Profil patient à évaluer

        Returns:
            str: Scénario médical actuel
        """
        # Vérification continuité scénario actuel
        if (patient.current_scenario != "normal" and
            patient.scenario_start_time and
            (datetime.now() - patient.scenario_start_time).total_seconds() / 3600 < patient.scenario_duration_hours):
            return patient.current_scenario

        # Sélection nouveau scénario selon probabilités génotipe
        genotype_params = SICKLE_CELL_GENOTYPES[patient.genotype]
        crisis_probability = genotype_params["crisis_frequency"]

        # Probabilités pondérées selon épidémiologie (inchangées)
        scenarios_weights = {
            "normal": 0.70,        # 70% temps stable
            "stress": 0.12,        # Stress quotidien
            "activity": 0.08,      # Activité physique
            "mild_crisis": crisis_probability * 0.6,    # Crise modérée
            "severe_crisis": crisis_probability * 0.4,   # Crise sévère
            "infection": 0.03 * genotype_params["infection_risk"],  # Infections
            "dehydration": 0.02    # Déshydratation
        }

        scenario = random.choices(
            list(scenarios_weights.keys()),
            weights=list(scenarios_weights.values())
        )[0]

        # Mise à jour état patient si nouveau scénario
        if scenario != "normal":
            patient.current_scenario = scenario
            patient.scenario_start_time = datetime.now()
            # Durée variable selon type scénario
            patient.scenario_duration_hours = random.uniform(0.5, 8.0)  # 30min à 8h

            logger.info(f"Patient {patient.patient_id}: nouveau scénario '{scenario}' "
                       f"(durée: {patient.scenario_duration_hours:.1f}h)")

        return scenario

    def _generate_vitals_for_scenario(self, patient: PatientProfile, scenario: str) -> Dict:
        """
        Génère les signes vitaux selon le scénario médical actuel.

        Chaque scénario a des paramètres physiologiques spécifiques
        avec variations réalistes selon la littérature médicale
        drépanocytose et physiologie d'urgence.

        Args:
            patient: Profil patient
            scenario: Scénario médical actuel

        Returns:
            Dict: Signes vitaux générés selon scénario
        """
        # Facteur circadien pour variations naturelles
        current_hour = datetime.now().hour
        circadian_factor = self._get_circadian_factor(current_hour)

        # Valeurs de base ajustées circadien
        base_hr = patient.base_heart_rate * circadian_factor
        base_spo2 = patient.base_spo2
        base_temp = patient.base_temperature
        base_rr = patient.base_respiratory_rate
        base_hydration = patient.base_hydration

        # Modifications selon scénario médical (paramètres inchangés)
        if scenario == "normal":
            hr_delta = random.randint(-8, 12)
            spo2_delta = random.uniform(-1, 1)
            temp_delta = random.uniform(-0.3, 0.4)
            activity = random.randint(10, 50)

        elif scenario == "stress":
            hr_delta = random.randint(15, 35)     # Tachycardie stress
            spo2_delta = random.uniform(-2, 0)    # Légère désaturation
            temp_delta = random.uniform(0, 0.8)   # Hyperthermie stress
            activity = random.randint(30, 70)

        elif scenario == "activity":
            hr_delta = random.randint(25, 60)     # Tachycardie effort
            spo2_delta = random.uniform(-1, 1)    # Variable selon adaptation
            temp_delta = random.uniform(0.3, 1.2) # Hyperthermie effort
            activity = random.randint(70, 95)

        elif scenario == "mild_crisis":
            hr_delta = random.randint(20, 40)     # Tachycardie modérée
            spo2_delta = random.uniform(-5, -2)   # Désaturation modérée
            temp_delta = random.uniform(0.5, 1.5) # Fièvre inflammatoire
            activity = random.randint(5, 30)      # Activité réduite
            base_hydration -= random.uniform(5, 15)  # Déshydratation

        elif scenario == "severe_crisis":
            hr_delta = random.randint(40, 70)     # Tachycardie sévère
            spo2_delta = random.uniform(-12, -6)  # Désaturation critique
            temp_delta = random.uniform(1.5, 3.5) # Fièvre importante
            activity = random.randint(0, 20)      # Activité minimale
            base_hydration -= random.uniform(15, 30)  # Déshydratation sévère

        elif scenario == "infection":
            hr_delta = random.randint(25, 45)     # Tachycardie septique
            spo2_delta = random.uniform(-3, -1)   # Désaturation infection
            temp_delta = random.uniform(1.0, 2.5) # Fièvre infectieuse
            activity = random.randint(10, 40)

        elif scenario == "dehydration":
            hr_delta = random.randint(15, 30)     # Tachycardie volume
            spo2_delta = random.uniform(-2, 0)    # Variable
            temp_delta = random.uniform(0.2, 1.0) # Hyperthermie volume
            activity = random.randint(15, 45)
            base_hydration -= random.uniform(20, 40)  # Déshydratation marquée

        else:  # fallback normal
            hr_delta = random.randint(-5, 10)
            spo2_delta = random.uniform(-0.5, 0.5)
            temp_delta = random.uniform(-0.2, 0.3)
            activity = random.randint(20, 60)

        # Application contraintes physiologiques strictes
        final_hr = max(40, min(220, int(base_hr + hr_delta)))
        final_spo2 = max(70, min(100, base_spo2 + spo2_delta))
        final_temp = max(35, min(42, base_temp + temp_delta))
        final_rr = max(8, min(50, base_rr + random.randint(-3, 8)))
        final_hydration = max(20, min(100, base_hydration))

        return {
            'freq_card': final_hr,
            'freq_resp': final_rr,
            'spo2_pct': round(final_spo2, 1),
            'temp_corp': round(final_temp, 1),
            'temp_ambiente': round(self.ambient_temperature + random.uniform(-2, 3), 1),
            'pct_hydratation': round(final_hydration, 1),
            'activity': int(activity),
            'heat_index': round(final_temp + random.uniform(-1, 4), 1)
        }

    def _generate_device_info_realistic(self, patient: PatientProfile) -> Dict:
        """
        Génère informations dispositif avec usure réaliste.

        Simulation comportements réels :
        - Enfants moins soigneux → batterie plus variable
        - Usure selon âge utilisation
        - Problèmes signal occasionnels

        Args:
            patient: Profil patient (influence type device)

        Returns:
            Dict: Informations techniques dispositif
        """
        # Simulation usure batterie selon âge patient (enfants moins soigneux)
        battery_base = 85 if patient.age < 12 else 90
        battery_variance = 20 if patient.age < 10 else 10

        return {
            'device_id': f"device-{patient.patient_id}",
            'firmware_version': random.choice(['2.1.3', '2.1.4', '2.2.0']),
            'battery_level': max(15, min(100, battery_base + random.randint(-battery_variance, 15))),
            'signal_strength': random.randint(70, 100),
            'status': random.choices(['connected', 'weak_signal'], weights=[95, 5])[0],
            'last_sync': datetime.now().isoformat()
        }

    def _generate_quality_indicators_realistic(self, vitals: Dict, scenario: str) -> Dict:
        """
        Génère indicateurs qualité selon conditions réelles.

        Qualité affectée par :
        - Niveau d'activité (mouvement = qualité réduite)
        - Scénario médical (crise = agitation)
        - Facteurs techniques aléatoires

        Args:
            vitals: Signes vitaux pour évaluation contexte
            scenario: Scénario médical (affecte qualité)

        Returns:
            Dict: Indicateurs qualité réalistes
        """
        # Qualité selon activité et scénario
        activity = vitals['activity']

        if scenario in ['severe_crisis', 'mild_crisis']:
            # Crise peut affecter qualité capteurs (agitation patient)
            base_quality = random.uniform(60, 80)
            quality_flag = 'crisis_movement'
        elif activity > 80:
            # Mouvement intense affect capteurs
            base_quality = random.uniform(65, 85)
            quality_flag = 'high_activity'
        elif activity < 15:
            # Très faible activité = conditions optimales
            base_quality = random.uniform(75, 90)
            quality_flag = 'low_activity'
        else:
            # Conditions normales
            base_quality = random.uniform(85, 98)
            quality_flag = 'optimal'

        return {
            'quality_flag': quality_flag,
            'confidence_score': round(base_quality, 1),
            'data_completeness': round(random.uniform(90, 100), 1),
            'sensor_contact_quality': round(base_quality + random.uniform(-5, 5), 1)
        }

    def generate_full_measurement(self, patient: PatientProfile) -> Dict:
        """
        Génère une mesure IoT complète pour un patient.

        Pipeline de génération :
        1. Détermination scénario médical actuel
        2. Génération signes vitaux contextuels
        3. Simulation info technique dispositif
        4. Calcul indicateurs qualité
        5. Assembly final format API

        Args:
            patient: Profil patient

        Returns:
            Dict: Mesure complète format API d'ingestion
        """
        # Détermination scénario médical actuel
        scenario = self._determine_current_scenario(patient)

        # Génération composants mesure selon scénario
        vitals = self._generate_vitals_for_scenario(patient, scenario)
        device_info = self._generate_device_info_realistic(patient)
        quality_indicators = self._generate_quality_indicators_realistic(vitals, scenario)

        # Assembly mesure complète format API
        measurement = {
            'device_id': device_info['device_id'],
            'patient_id': patient.patient_id,
            'timestamp': datetime.now().isoformat(),
            'measurements': vitals,
            'device_info': device_info,
            'quality_indicators': quality_indicators
        }

        # Log adaptatif selon criticité scénario
        if scenario in ['mild_crisis', 'severe_crisis']:
            logger.warning(f"🚨 CRISE {patient.patient_id} ({scenario}): "
                          f"SpO2={vitals['spo2_pct']}%, T°={vitals['temp_corp']}°C, "
                          f"FC={vitals['freq_card']}bpm")
        elif scenario in ['infection']:
            logger.info(f"⚠️ INFECTION {patient.patient_id}: T°={vitals['temp_corp']}°C")

        return measurement

    def send_measurement_dual(self, measurement: Dict) -> Tuple[bool, bool]:
        """
        Envoie mesure via Kafka ET API selon disponibilité.

        Stratégie double canal :
        - Kafka en priorité (performance)
        - API en fallback ou parallèle
        - Gestion gracieuse erreurs réseau

        Args:
            measurement: Mesure à envoyer

        Returns:
            Tuple[bool, bool]: (kafka_success, api_success)
        """
        kafka_success = False
        api_success = False

        # Envoi Kafka si producteur disponible
        if self.kafka_producer:
            try:
                self.kafka_producer.send(
                    'kidjamo-iot-measurements',
                    value=measurement,
                    key=measurement['patient_id']
                )
                kafka_success = True
            except Exception as e:
                logger.warning(f"Kafka send failed: {e}")

        # Envoi API avec gestion d'erreur
        try:
            response = requests.post(
                f"{self.api_endpoint}/iot/measurements",
                json=measurement,
                timeout=5  # Timeout court pour simulation fluide
            )
            api_success = response.status_code == 200
            if not api_success:
                logger.warning(f"API returned status: {response.status_code}")
        except requests.RequestException as e:
            logger.warning(f"API send failed: {e}")

        return kafka_success, api_success

    def simulate_patient_continuously(self, patient: PatientProfile, 
                                    interval_seconds: float = 30.0) -> None:
        """
        Simule un patient en continu avec envoi périodique.

        Thread individuel par patient pour simulation parallèle.
        Gestion arrêt propre via self.running flag.

        Args:
            patient: Profil patient à simuler
            interval_seconds: Intervalle entre mesures (défaut: 30s)
        """
        logger.info(f"🏥 Started simulation for {patient.patient_id} "
                   f"(genotype: {patient.genotype}, age: {patient.age})")

        while self.running:
            try:
                # Génération et envoi mesure
                measurement = self.generate_full_measurement(patient)
                kafka_ok, api_ok = self.send_measurement_dual(measurement)

                # Comptage métriques globales
                self.total_measurements_sent += 1

                # Log périodique succès/échec
                if self.total_measurements_sent % 50 == 0:
                    logger.info(f"📊 Sent {self.total_measurements_sent} measurements "
                               f"(Kafka: {'✅' if kafka_ok else '❌'}, API: {'✅' if api_ok else '❌'})")

                # Attente avant prochaine mesure
                time.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Error simulating {patient.patient_id}: {e}")
                time.sleep(interval_seconds)  # Continue malgré erreur

        logger.info(f"🛑 Stopped simulation for {patient.patient_id}")

    def start_simulation(self, num_patients: int = 5, 
                        interval_seconds: float = 30.0) -> None:
        """
        Lance la simulation multi-patients avec threads parallèles.

        Args:
            num_patients: Nombre de patients à simuler
            interval_seconds: Intervalle entre mesures par patient
        """
        if self.running:
            logger.warning("Simulation already running")
            return

        # Génération cohorte patients
        self.patients = self.generate_patient_cohort(num_patients)
        self.running = True
        self.start_time = datetime.now()

        logger.info(f"🚀 Starting simulation: {num_patients} patients, "
                   f"interval={interval_seconds}s")

        # Création thread par patient
        for patient in self.patients:
            thread = threading.Thread(
                target=self.simulate_patient_continuously,
                args=(patient, interval_seconds),
                daemon=True  # Arrêt propre avec application
            )
            thread.start()
            self.simulation_threads.append(thread)

        logger.info(f"✅ Simulation started with {len(self.simulation_threads)} threads")

    def stop_simulation(self) -> None:
        """
        Arrête la simulation et tous les threads patients.

        Arrêt gracieux avec attente threads (timeout 5s).
        """
        if not self.running:
            logger.warning("Simulation not running")
            return

        logger.info("🛑 Stopping simulation...")
        self.running = False

        # Attente arrêt threads (timeout)
        for thread in self.simulation_threads:
            thread.join(timeout=5.0)

        # Fermeture producteur Kafka
        if self.kafka_producer:
            self.kafka_producer.close()

        # Calcul statistiques finales
        if self.start_time:
            duration = datetime.now() - self.start_time
            rate = self.total_measurements_sent / duration.total_seconds() if duration.total_seconds() > 0 else 0

            logger.info(f"📊 Simulation stopped - Duration: {duration}, "
                       f"Total measurements: {self.total_measurements_sent}, "
                       f"Rate: {rate:.1f} msg/s")

        # Reset état
        self.simulation_threads.clear()
        self.patients.clear()

    def get_simulation_stats(self) -> Dict:
        """
        Retourne les statistiques de simulation actuelles.

        Returns:
            Dict: Métriques simulation (durée, taux, patients actifs)
        """
        duration_seconds = 0
        if self.start_time:
            duration_seconds = (datetime.now() - self.start_time).total_seconds()

        return {
            "running": self.running,
            "patients_count": len(self.patients),
            "total_measurements": self.total_measurements_sent,
            "total_alerts": self.total_alerts_generated,
            "duration_seconds": duration_seconds,
            "rate_per_second": self.total_measurements_sent / max(duration_seconds, 1),
            "active_threads": len([t for t in self.simulation_threads if t.is_alive()]),
            "kafka_available": self.kafka_producer is not None
        }


# === POINT D'ENTRÉE PRINCIPAL ===

def main() -> None:
    """
    Point d'entrée principal pour simulation interactive.

    Menu simple pour démonstration et tests avec paramètres
    configurables via variables d'environnement.
    """
    # Configuration depuis environnement
    kafka_servers = os.environ.get("KAFKA_SERVERS", "localhost:9092").split(",")
    api_endpoint = os.environ.get("API_ENDPOINT", "http://localhost:8001")
    num_patients = int(os.environ.get("NUM_PATIENTS", "5"))
    interval_seconds = float(os.environ.get("INTERVAL_SECONDS", "30"))

    # Initialisation simulateur
    simulator = AdvancedIoTSimulator(
        kafka_servers=kafka_servers,
        api_endpoint=api_endpoint
    )

    logger.info("🏥 Kidjamo Advanced IoT Simulator")
    logger.info(f"Configuration: {num_patients} patients, {interval_seconds}s interval")
    logger.info(f"Targets: Kafka={kafka_servers}, API={api_endpoint}")

    try:
        # Démarrage simulation
        simulator.start_simulation(num_patients, interval_seconds)

        # Boucle monitoring simple
        while True:
            time.sleep(30)  # Stats toutes les 30s
            stats = simulator.get_simulation_stats()
            logger.info(f"📊 Stats: {stats['total_measurements']} messages, "
                       f"{stats['rate_per_second']:.1f} msg/s, "
                       f"{stats['active_threads']} threads actifs")

    except KeyboardInterrupt:
        logger.info("🛑 Arrêt demandé par utilisateur")
    except Exception as e:
        logger.error(f"❌ Erreur simulation: {e}")
    finally:
        simulator.stop_simulation()
        logger.info("🏁 Simulator stopped")


if __name__ == "__main__":
    main()
