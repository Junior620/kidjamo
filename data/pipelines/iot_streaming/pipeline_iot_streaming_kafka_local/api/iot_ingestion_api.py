"""
Étape Ingestion — API FastAPI recevant des mesures IoT et les publie vers Kafka.

Rôle :
    API d'ingestion temps réel pour bracelets médicaux IoT. Reçoit les données
    des dispositifs, valide selon seuils critiques immédiats, et publie vers
    bus Kafka (équivalent "RAW streaming").

Objectifs :
    - Réception JSON IoT via endpoints FastAPI (/iot/measurements, /ingest)
    - Validation immédiate des seuils critiques (SpO2 < 88%, T° >= 38°C)
    - Publication vers topics Kafka spécialisés (measurements, alerts, device_status, errors)
    - Métriques en mémoire et export CSV pour observabilité
    - Gestion mode offline gracieux (pas de blocage si Kafka indisponible)

Entrées :
    - POST JSON sur /iot/measurements (modèle IoTMeasurement complet)
    - POST JSON sur /ingest (modèle FlatIngestPayload pour tests)
    - Configuration via variables d'environnement (API_HOST, API_PORT, DB)

Sorties :
    - Messages Kafka enrichis (ingestion_timestamp, api_version, message_id)
    - Topics : kidjamo-iot-measurements, kidjamo-iot-alerts, kidjamo-iot-device-status, kidjamo-iot-errors
    - Métriques CSV dans evidence/metrics/ingestion_metrics.csv
    - Tables PostgreSQL : measurements, alerts (best-effort)

Effets de bord :
    - Création tables DB automatique (measurements, alerts)
    - Génération UUID pour message_id
    - Horodatage UTC automatique (ingestion_timestamp)
    - Tâches en arrière-plan pour alertes critiques et statut dispositifs
    - Pseudonymisation RGPD via hachage SHA-256 + salt (si module disponible)

Garanties :
    Aucune transformation métier des valeurs ; seuils d'alerte médicaux inchangés ;
    endpoints et signature de réponse identiques ; graceful degradation si
    services externes (Kafka/DB) indisponibles.
"""

import csv
import json
import logging
import os
import sys
import time
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import Json
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

# Import Kafka avec gestion gracieuse si non disponible
try:
    from kafka import KafkaProducer
except ImportError:
    KafkaProducer = None

# Import sécurité (pseudonymisation RGPD) avec fallback
try:
    from data.security.pseudonymization_secure import hash_patient_id as secure_hash_patient_id
except ImportError:
    secure_hash_patient_id = None

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Kafka (topics et serveurs)
KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']
KAFKA_TOPICS = {
    'measurements': 'kidjamo-iot-measurements',
    'alerts': 'kidjamo-iot-alerts',
    'device_status': 'kidjamo-iot-device-status',
    'errors': 'kidjamo-iot-errors'
}

# Configuration base de données PostgreSQL (avec fallbacks via env)
DB_DEFAULTS = {
    'host': 'localhost',
    'database': 'kidjamo-db',
    'user': 'postgres',
    'password': 'kidjamo@'
}

# Métriques observabilité en mémoire + export CSV
API_START_TIME = time.time()
METRICS = {
    "latencies_s": [],          # Latences de traitement API (dernières N)
    "alerts_by_type": Counter(), # Compteur alertes par type
    "total_count": 0,           # Nombre total de mesures traitées
    "valid_count": 0,           # Nombre de mesures considérées valides
}
METRICS_MAX_LEN = 2000  # Taille max buffer latences


def _percentile(values: List[float], p: float) -> Optional[float]:
    """
    Calcule le percentile p d'une liste de valeurs.

    Args:
        values: Liste des valeurs numériques
        p: Percentile à calculer (0-100)

    Returns:
        float: Valeur du percentile ou None si liste vide
    """
    if not values:
        return None
    arr = sorted(values)
    k = (len(arr) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(arr) - 1)
    if f == c:
        return arr[int(k)]
    return arr[f] + (k - f) * (arr[c] - arr[f])


def _export_metrics_row(latency_s: float, alerts: List[Dict], measurement: "IoTMeasurement") -> None:
    """
    Exporte une ligne de métriques vers CSV pour observabilité.

    CSV contient : timestamp, latency_s, alerts_count, alert_types, quality_score,
    valid_flag, device_id pour analyse post-traitement.

    Args:
        latency_s: Latence de traitement de la mesure
        alerts: Liste des alertes détectées pour cette mesure
        measurement: Mesure IoT traitée
    """
    try:
        metrics_dir = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..', '..', 'evidence', 'metrics'
        ))
        os.makedirs(metrics_dir, exist_ok=True)

        csv_path = os.path.join(metrics_dir, 'ingestion_metrics.csv')
        header = [
            'timestamp', 'latency_s', 'alerts_count', 'alert_types',
            'quality_score', 'valid_flag', 'device_id'
        ]

        file_exists = os.path.exists(csv_path)
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)

            # Calcul flag validité selon seuils qualité
            is_valid = (measurement.quality_indicators.confidence_score >= 80.0 and
                       measurement.quality_indicators.sensor_contact_quality >= 60.0)

            writer.writerow([
                datetime.now().isoformat(),
                round(latency_s, 4),
                len(alerts),
                '|'.join([a.get('type', 'unknown') for a in alerts]),
                measurement.quality_indicators.confidence_score,
                1 if is_valid else 0,
                measurement.device_id
            ])
    except Exception as ex:
        logger.warning(f"Unable to export metrics row: {ex}")


class KafkaManager:
    """
    Gestionnaire Kafka pour publication des messages IoT vers topics spécialisés.

    Gère la connexion, sérialisation JSON et enrichissement automatique des messages
    avec métadonnées d'ingestion (ingestion_timestamp, api_version, message_id).
    """

    def __init__(self):
        self.producer: Optional[KafkaProducer] = None
        self._connect()

    def _connect(self) -> None:
        """
        Établit la connexion au producer Kafka avec configuration robuste.

        Configuration : acks='all' pour garantie de durabilité, retries=3,
        max_in_flight_requests=1 pour ordre des messages.
        """
        try:
            if KafkaProducer is None:
                logger.warning("Kafka library unavailable; running in offline mode (no producer)")
                self.producer = None
                return

            self.producer = KafkaProducer(
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',        # Attendre accusé de réception de tous les replicas
                retries=3,         # Retry automatique en cas d'erreur temporaire
                max_in_flight_requests_per_connection=1  # Maintenir ordre des messages
            )
            logger.info("✅ Connected to Kafka")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Kafka: {e}")
            self.producer = None

    def send_message(self, topic: str, message: dict, key: str = None) -> bool:
        """
        Envoie un message vers un topic Kafka avec enrichissement automatique.

        Enrichit automatiquement avec :
        - ingestion_timestamp : timestamp UTC d'ingestion
        - api_version : version de l'API pour compatibilité
        - message_id : UUID unique pour traçabilité

        Args:
            topic: Nom du topic Kafka de destination
            message: Dictionnaire du message à envoyer
            key: Clé de partitionnement (optionnelle, généralement patient_id)

        Returns:
            bool: True si message envoyé avec succès, False sinon
        """
        if not self.producer:
            logger.error("❌ Kafka producer not available")
            return False

        try:
            # Enrichissement avec métadonnées d'ingestion
            enriched_message = {
                **message,
                'ingestion_timestamp': datetime.now().isoformat(),
                'api_version': '1.0.0',
                'message_id': str(uuid.uuid4())
            }

            future = self.producer.send(topic, value=enriched_message, key=key)

            # Callback d'erreur asynchrone pour monitoring
            def _on_send_error(ex):
                logger.error(f"❌ Failed to send message to {topic}: {ex}")

            try:
                future.add_errback(_on_send_error)
            except Exception:
                pass  # Callback optionnel, ne pas faire échouer l'envoi

            logger.info(f"📤 Message queued to {topic}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send message to {topic}: {e}")
            return False

    def close(self) -> None:
        """Ferme proprement la connexion Kafka."""
        if self.producer:
            self.producer.close()


# Instance globale Kafka (initialisée une seule fois)
kafka_manager = KafkaManager()

# Variables globales pour gestion base de données
_db_conn = None
_tables_ready = False


def _get_db_connection():
    """
    Obtient une connexion PostgreSQL avec configuration depuis variables d'environnement.

    Crée automatiquement les tables nécessaires au premier accès.
    Configuration via PGHOST, PGDATABASE, PGUSER, PGPASSWORD, PGCONNECT_TIMEOUT.

    Returns:
        psycopg2.connection: Connexion PostgreSQL configurée
    """
    global _db_conn

    db_config = {
        'host': os.environ.get('PGHOST', DB_DEFAULTS['host']),
        'database': os.environ.get('PGDATABASE', DB_DEFAULTS['database']),
        'user': os.environ.get('PGUSER', DB_DEFAULTS['user']),
        'password': os.environ.get('PGPASSWORD', DB_DEFAULTS['password']),
        'connect_timeout': int(os.environ.get('PGCONNECT_TIMEOUT', '2'))
    }

    if _db_conn is None or _db_conn.closed:
        _db_conn = psycopg2.connect(**db_config)
        _db_conn.autocommit = True
        _ensure_db_tables(_db_conn)

    return _db_conn


def _ensure_db_tables(conn) -> None:
    """
    Crée les tables PostgreSQL nécessaires si elles n'existent pas.

    Tables créées :
    - measurements : stockage des mesures IoT avec colonnes compatibles tests
    - alerts : stockage des alertes avec snapshot des vitaux en JSONB

    Args:
        conn: Connexion PostgreSQL active
    """
    global _tables_ready
    if _tables_ready:
        return

    try:
        with conn.cursor() as cur:
            # Table des mesures IoT
            cur.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id SERIAL PRIMARY KEY,
                    patient_id UUID,
                    device_id UUID,
                    recorded_at TIMESTAMP,
                    heart_rate_bpm INT,
                    respiratory_rate_min INT,
                    spo2_percent DOUBLE PRECISION,
                    temperature_celsius DOUBLE PRECISION,
                    ambient_temp_celsius DOUBLE PRECISION,
                    hydration_percent DOUBLE PRECISION,
                    activity_level INT,
                    pain_scale INT,
                    battery_percent INT,
                    signal_quality INT,
                    quality_flag TEXT
                );
            """)

            # Colonne de compatibilité pour tests (timestamp générique)
            cur.execute("""
                ALTER TABLE measurements
                ADD COLUMN IF NOT EXISTS tz_timestamp TIMESTAMP;
            """)
            cur.execute("""
                ALTER TABLE measurements
                ALTER COLUMN tz_timestamp SET DEFAULT NOW();
            """)

            # Table des alertes avec snapshot vitaux
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    patient_id UUID,
                    alert_type TEXT,
                    severity TEXT,
                    title TEXT,
                    message TEXT,
                    vitals_snapshot JSONB,
                    created_at TIMESTAMP,
                    ack_deadline TIMESTAMP
                );
            """)

        _tables_ready = True
    except Exception as e:
        logger.warning(f"DB table ensure failed (continuing): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestionnaire de cycle de vie de l'application FastAPI.

    Startup: log démarrage
    Shutdown: fermeture propre connexions Kafka
    """
    # Startup
    logger.info("Starting Kidjamo IoT API")
    yield
    # Shutdown
    logger.info("Shutting down Kidjamo IoT API")
    kafka_manager.close()


# Initialisation FastAPI avec middleware CORS
app = FastAPI(
    title="Kidjamo IoT Ingestion API",
    description="API pour l'ingestion des données IoT des bracelets médicaux",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compteur global de messages traités (pour métriques)
processed_count = 0


# === MODÈLES PYDANTIC POUR VALIDATION ===

class DeviceInfo(BaseModel):
    """
    Information du dispositif IoT bracelet médical.

    Contient identifiant, version firmware, niveau batterie, qualité signal
    et statut de connexion pour monitoring technique.
    """
    device_id: str = Field(..., description="Identifiant unique du dispositif")
    firmware_version: str = Field(..., description="Version du firmware")
    battery_level: int = Field(..., ge=0, le=100, description="Niveau de batterie (%)")
    signal_strength: int = Field(..., ge=0, le=100, description="Force du signal (%)")
    status: str = Field(..., description="Statut du dispositif")
    last_sync: str = Field(..., description="Dernière synchronisation")


class MedicalMeasurements(BaseModel):
    """
    Mesures médicales du bracelet IoT avec seuils de validation physiologiques.

    Valide les plages acceptables pour éviter valeurs aberrantes évidentes :
    - Fréquence cardiaque : 30-250 bpm (large pour cas pathologiques)
    - SpO2 : 70-100% (minimum pour survie)
    - Températures : plages physiologiques étendues
    """
    freq_card: int = Field(..., ge=30, le=250, description="Fréquence cardiaque (bpm)")
    freq_resp: int = Field(..., ge=5, le=80, description="Fréquence respiratoire (/min)")
    spo2_pct: float = Field(..., ge=70.0, le=100.0, description="Saturation en oxygène (%)")
    temp_corp: float = Field(..., ge=30.0, le=45.0, description="Température corporelle (°C)")
    temp_ambiente: float = Field(..., ge=-10.0, le=50.0, description="Température ambiante (°C)")
    pct_hydratation: float = Field(..., ge=30.0, le=100.0, description="Pourcentage d'hydratation (%)")
    activity: int = Field(..., ge=0, le=100, description="Niveau d'activité")
    heat_index: float = Field(..., description="Index de chaleur")


class QualityIndicators(BaseModel):
    """
    Indicateurs de qualité des mesures pour filtrage et fiabilité.

    Permet d'évaluer la confiance dans les données reçues selon
    la qualité du contact capteur et la complétude des données.
    """
    quality_flag: str = Field(..., description="Flag de qualité")
    confidence_score: float = Field(..., ge=0.0, le=100.0, description="Score de confiance (%)")
    data_completeness: float = Field(..., ge=0.0, le=100.0, description="Complétude des données (%)")
    sensor_contact_quality: float = Field(..., ge=0.0, le=100.0, description="Qualité du contact capteur (%)")


class IoTMeasurement(BaseModel):
    """
    Modèle complet d'une mesure IoT reçue par l'API principale.

    Structure hiérarchique avec mesures médicales, info dispositif
    et indicateurs qualité pour traitement complet.
    """
    device_id: str = Field(..., description="Identifiant du dispositif")
    patient_id: str = Field(..., description="Identifiant du patient")
    timestamp: str = Field(..., description="Timestamp de la mesure")
    measurements: MedicalMeasurements
    device_info: DeviceInfo
    quality_indicators: QualityIndicators

    @field_validator('timestamp', mode='before')
    def validate_timestamp(cls, v):
        """
        Valide le format du timestamp avec support ISO et 'Z' UTC.

        Accepte formats ISO 8601 incluant terminaison 'Z' pour UTC.
        """
        try:
            # Supporte les timestamps ISO, y compris ceux terminant par 'Z'
            datetime.fromisoformat(str(v).replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError('Invalid timestamp format')


class AlertRequest(BaseModel):
    """Modèle pour création d'alertes manuelles via API."""
    patient_id: str
    alert_type: str
    severity: str = Field(..., pattern="^(low|medium|high|critical)$")
    message: str
    measurements: Optional[Dict] = None


class HealthStatus(BaseModel):
    """Modèle de réponse pour endpoint /health."""
    status: str
    timestamp: str
    kafka_connected: bool
    processed_messages: int


class FlatIngestPayload(BaseModel):
    """
    Modèle plat pour endpoint /ingest (compatibilité tests d'intégration).

    Structure simplifiée sans hiérarchie pour faciliter les tests
    automatisés et la compatibilité avec systèmes externes.
    """
    patient_id: str
    device_id: str
    timestamp: str
    freq_card: int = Field(..., ge=0, le=300)
    freq_resp: int = Field(..., ge=0, le=200)
    spo2_pct: float = Field(..., ge=0.0, le=100.0)
    temp_corp: float
    temp_ambiante: float
    pct_hydratation: float
    activity: int
    heat_index: float
    quality_flag: str = Field(default="ok", description="Indicateur de qualité des données")


# === FONCTIONS DE VALIDATION MÉDICALE ===

def check_critical_vitals(measurement: IoTMeasurement) -> List[Dict]:
    """
    Vérifie les signes vitaux critiques selon règles médicales immédiates.

    Règles offline immédiates (sans dépendance externe) :
    - SpO₂ < 88% → alerte CRITICAL immédiate (hypoxie sévère)
    - Température ≥ 38.0°C → alerte CRITICAL immédiate (fièvre)
    - Fréquence cardiaque < 40 ou > 180 → alerte CRITICAL (arythmie)
    - Combinaison fièvre (≥ 38.0°C) + SpO₂ basse (≤ 92%) → CRITICAL

    Note: Les seuils détaillés par âge sont disponibles dans
    data/configs/medical_thresholds.json, mais l'âge patient n'est pas
    présent dans ce modèle API. L'évaluation fine par âge se fait
    dans le moteur d'alertes hors-ligne.

    Args:
        measurement: Mesure IoT complète à analyser

    Returns:
        List[Dict]: Liste des alertes critiques détectées
    """
    alerts: List[Dict] = []
    vitals = measurement.measurements

    # Chargement des seuils depuis configuration (cache module)
    global _MED_THRESHOLDS
    try:
        _ = _MED_THRESHOLDS
    except NameError:
        config_path = os.path.normpath(os.path.join(
            os.path.dirname(__file__), '..', '..', '..', '..', 'configs', 'medical_thresholds.json'
        ))
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                _MED_THRESHOLDS = json.load(f)
        except Exception:
            _MED_THRESHOLDS = {}  # Fallback si fichier absent

    # Seuils critiques immédiats (indépendants de l'âge pour API temps réel)
    spo2_critical_threshold = 88.0
    temp_critical_threshold = 38.0

    # SpO₂ critique immédiate (hypoxie sévère)
    if vitals.spo2_pct < spo2_critical_threshold:
        alerts.append({
            "type": "CRITICAL_SPO2",
            "severity": "critical",
            "reasons": ["spo2_critical_immediate"],
            "message": f"SpO₂ critique: {vitals.spo2_pct}% < {spo2_critical_threshold}%",
            "value": vitals.spo2_pct,
            "threshold": spo2_critical_threshold
        })

    # Température critique immédiate (fièvre)
    if vitals.temp_corp >= temp_critical_threshold:
        alerts.append({
            "type": "CRITICAL_TEMPERATURE",
            "severity": "critical",
            "reasons": ["temperature_critical_immediate"],
            "message": f"Température critique: {vitals.temp_corp}°C ≥ {temp_critical_threshold}°C",
            "value": vitals.temp_corp,
            "threshold": temp_critical_threshold
        })

    # Fréquence cardiaque très anormale (bornes larges, âge géré hors-ligne)
    if vitals.freq_card < 40 or vitals.freq_card > 180:
        alerts.append({
            "type": "CRITICAL_HEART_RATE",
            "severity": "critical",
            "reasons": ["heart_rate_extreme"],
            "message": f"Fréquence cardiaque critique: {vitals.freq_card} bpm",
            "value": vitals.freq_card,
            "threshold": "<40 or >180 bpm"
        })

    # Combinaison critique (fièvre + SpO₂ basse) - très dangereuse
    if vitals.spo2_pct <= 92.0 and vitals.temp_corp >= 38.0:
        alerts.append({
            "type": "CRITICAL_COMBINATION_FEVER_SPO2",
            "severity": "critical",
            "reasons": ["combo_fever_low_spo2"],
            "message": f"Combinaison critique: SpO₂ {vitals.spo2_pct}%, T° {vitals.temp_corp}°C",
            "values": {"spo2": vitals.spo2_pct, "temperature": vitals.temp_corp},
            "thresholds": {"spo2": "≤92%", "temperature": "≥38.0°C"}
        })

    return alerts


# === FONCTIONS DE TRAITEMENT ASYNCHRONE ===

async def process_critical_alerts(alerts: List[Dict], measurement: IoTMeasurement) -> None:
    """
    Traite les alertes critiques en arrière-plan via publication Kafka.

    Enrichit chaque alerte avec contexte complet (patient, device, measurements)
    et pseudonymisation RGPD si disponible.

    Args:
        alerts: Liste des alertes critiques détectées
        measurement: Mesure source ayant déclenché les alertes
    """
    for alert in alerts:
        alert_message = {
            "patient_id": measurement.patient_id,
            "patient_id_hash": secure_hash_patient_id(measurement.patient_id) if secure_hash_patient_id else None,
            "device_id": measurement.device_id,
            "alert_type": alert.get("type", "unknown"),
            "severity": alert.get("severity", "unknown"),
            "reasons": alert.get("reasons", []),
            "message": alert.get("message", ""),
            "timestamp": measurement.timestamp,
            "measurements": measurement.measurements.model_dump(),
            "quality_score": measurement.quality_indicators.confidence_score,
            "context": alert.get("values") or alert.get("thresholds") or {}
        }

        kafka_manager.send_message(
            topic=KAFKA_TOPICS['alerts'],
            message=alert_message,
            key=measurement.patient_id
        )


async def process_device_status(device_info: DeviceInfo, patient_id: str) -> None:
    """
    Traite le statut du dispositif en arrière-plan.

    Publie les informations de monitoring technique (batterie, signal)
    vers topic dédié pour surveillance infrastructure.

    Args:
        device_info: Informations techniques du dispositif
        patient_id: ID patient pour clé de partitionnement
    """
    status_message = {
        "patient_id": patient_id,
        "device_id": device_info.device_id,
        "battery_level": device_info.battery_level,
        "signal_strength": device_info.signal_strength,
        "status": device_info.status,
        "firmware_version": device_info.firmware_version,
        "timestamp": datetime.now().isoformat()
    }

    kafka_manager.send_message(
        topic=KAFKA_TOPICS['device_status'],
        message=status_message,
        key=patient_id
    )


# === FONCTIONS POUR ENDPOINT /INGEST (TESTS) ===

def _insert_measurement_flat(payload: FlatIngestPayload) -> None:
    """
    Insère une mesure depuis payload plat dans la base de données.

    Tolérant aux erreurs : les erreurs de DB sont journalisées mais
    ne font pas échouer l'API (graceful degradation).

    Args:
        payload: Données de mesure au format plat
    """
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO measurements (
                    patient_id, device_id, recorded_at, heart_rate_bpm,
                    respiratory_rate_min, spo2_percent, temperature_celsius,
                    ambient_temp_celsius, hydration_percent, activity_level,
                    quality_flag, tz_timestamp
                ) VALUES (
                    %s, %s, COALESCE((%s)::timestamptz AT TIME ZONE 'UTC', NOW()),
                    %s, %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                """, (
                    payload.patient_id, payload.device_id,
                    payload.timestamp, int(payload.freq_card), int(payload.freq_resp),
                    float(payload.spo2_pct), float(payload.temp_corp),
                    float(payload.temp_ambiante), float(payload.pct_hydratation),
                    int(payload.activity), payload.quality_flag
                ))
    except Exception as e:
        logger.warning(f"DB insert failed (continuing): {e}")


def _evaluate_critical_alerts_flat(payload: FlatIngestPayload) -> List[Dict]:
    """
    Évalue les règles d'alertes critiques pour payload plat.

    Règles immédiates identiques à check_critical_vitals() pour cohérence.

    Args:
        payload: Données de mesure au format plat

    Returns:
        List[Dict]: Alertes critiques détectées
    """
    alerts: List[Dict] = []

    spo2_critical_threshold = 88.0
    temp_critical_threshold = 38.0

    # SpO2 critique
    try:
        if float(payload.spo2_pct) < spo2_critical_threshold:
            alerts.append({
                "type": "CRITICAL_SPO2",
                "severity": "critical",
                "reasons": ["spo2_critical_immediate"],
                "message": f"SpO₂ critique: {payload.spo2_pct}% < {spo2_critical_threshold}%",
                "value": float(payload.spo2_pct),
                "threshold": spo2_critical_threshold
            })
    except Exception:
        pass

    # Température critique
    try:
        if float(payload.temp_corp) >= temp_critical_threshold:
            alerts.append({
                "type": "CRITICAL_TEMPERATURE",
                "severity": "critical",
                "reasons": ["temperature_critical_immediate"],
                "message": f"Température critique: {payload.temp_corp}°C ≥ {temp_critical_threshold}°C",
                "value": float(payload.temp_corp),
                "threshold": temp_critical_threshold
            })
    except Exception:
        pass

    # FC très anormale
    try:
        if int(payload.freq_card) < 40 or int(payload.freq_card) > 180:
            alerts.append({
                "type": "CRITICAL_HEART_RATE",
                "severity": "critical",
                "reasons": ["heart_rate_extreme"],
                "message": f"Fréquence cardiaque critique: {payload.freq_card} bpm",
                "value": int(payload.freq_card),
                "threshold": "<40 or >180 bpm"
            })
    except Exception:
        pass

    # Combinaison critique (fièvre + SpO2 basse)
    try:
        if float(payload.spo2_pct) <= 92.0 and float(payload.temp_corp) >= 38.0:
            alerts.append({
                "type": "CRITICAL_COMBINATION_FEVER_SPO2",
                "severity": "critical",
                "reasons": ["combo_fever_low_spo2"],
                "message": f"Combinaison critique: SpO₂ {payload.spo2_pct}%, T° {payload.temp_corp}°C",
                "values": {"spo2": float(payload.spo2_pct), "temperature": float(payload.temp_corp)},
                "thresholds": {"spo2": "≤92%", "temperature": "≥38.0°C"}
            })
    except Exception:
        pass

    return alerts


def _insert_alerts_flat(payload: FlatIngestPayload, alerts: List[Dict]) -> None:
    """
    Insère les alertes dans la table alerts (best-effort).

    Args:
        payload: Données source ayant déclenché les alertes
        alerts: Liste des alertes à insérer
    """
    if not alerts:
        return

    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            for alert in alerts:
                # Snapshot des vitaux au moment de l'alerte
                vitals_snapshot = {
                    "freq_card": payload.freq_card,
                    "freq_resp": payload.freq_resp,
                    "spo2_pct": payload.spo2_pct,
                    "temp_corp": payload.temp_corp,
                    "temp_ambiante": payload.temp_ambiante,
                    "pct_hydratation": payload.pct_hydratation,
                    "activity": payload.activity,
                    "heat_index": payload.heat_index
                }

                cur.execute("""
                    INSERT INTO alerts (
                        patient_id, alert_type, severity, title, message,
                        vitals_snapshot, created_at, ack_deadline
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, NOW(), NOW() + INTERVAL '15 minutes'
                    )
                    """, (
                        payload.patient_id,
                        alert.get("type", "unknown"),
                        alert.get("severity", "unknown"),
                        f"Critical alert: {alert.get('type', 'unknown')}",
                        alert.get("message", ""),
                        Json(vitals_snapshot)
                    ))
    except Exception as e:
        logger.warning(f"DB alert insert failed (continuing): {e}")


# === ENDPOINTS FASTAPI ===

@app.get("/", tags=["Health"])
async def root():
    """Point d'entrée principal de l'API."""
    return {
        "service": "Kidjamo IoT Ingestion API",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check():
    """
    Vérification de santé de l'API.

    Retourne toujours 'healthy' même si Kafka est offline pour éviter
    que les load balancers retirent l'API du pool en mode graceful degradation.

    Returns:
        HealthStatus: État de santé avec statut Kafka et compteurs
    """
    global processed_count

    kafka_connected = kafka_manager.producer is not None

    return HealthStatus(
        status="healthy",  # Toujours healthy pour LB, même si Kafka offline
        timestamp=datetime.now().isoformat(),
        kafka_connected=kafka_connected,
        processed_messages=processed_count
    )


@app.post("/iot/measurements", tags=["IoT Ingestion"])
async def receive_measurement(measurement: IoTMeasurement, background_tasks: BackgroundTasks):
    """
    Reçoit une mesure IoT complète et la traite.

    Processus :
    1. Validation critique des signes vitaux (seuils immédiats)
    2. Publication vers Kafka topic measurements (clé = patient_id)
    3. Traitement arrière-plan : alertes critiques et statut device
    4. Mise à jour métriques observabilité et export CSV

    Args:
        measurement: Mesure IoT complète au format hiérarchique
        background_tasks: Gestionnaire tâches asynchrones FastAPI

    Returns:
        dict: Réponse avec statut, ID message, métriques et alertes

    Raises:
        HTTPException: Si erreur de traitement (500)
    """
    global processed_count

    # Début mesure latence pour métriques
    start_time = time.time()

    try:
        # Validation critique des signes vitaux selon seuils immédiats
        critical_alerts = check_critical_vitals(measurement)

        # Envoi vers Kafka topic principal (measurements)
        success = kafka_manager.send_message(
            topic=KAFKA_TOPICS['measurements'],
            message=measurement.model_dump(),
            key=measurement.patient_id
        )

        if not success:
            logger.warning("Kafka publish failed; continuing with local processing (offline mode)")

        # Traitement asynchrone des alertes critiques
        if critical_alerts:
            background_tasks.add_task(process_critical_alerts, critical_alerts, measurement)

        # Traitement asynchrone du statut dispositif
        background_tasks.add_task(process_device_status, measurement.device_info, measurement.patient_id)

        processed_count += 1

        # Mise à jour métriques observabilité
        end_time = time.time()
        latency_s = end_time - start_time

        METRICS["latencies_s"].append(latency_s)
        if len(METRICS["latencies_s"]) > METRICS_MAX_LEN:
            METRICS["latencies_s"] = METRICS["latencies_s"][-METRICS_MAX_LEN:]

        METRICS["total_count"] += 1

        # Calcul validité selon seuils qualité
        is_valid = (measurement.quality_indicators.confidence_score >= 80.0 and
                   measurement.quality_indicators.sensor_contact_quality >= 60.0)
        if is_valid:
            METRICS["valid_count"] += 1

        # Comptage alertes par type
        for alert in critical_alerts:
            METRICS["alerts_by_type"][alert.get("type", "unknown")] += 1

        # Export ligne métriques CSV
        _export_metrics_row(latency_s, critical_alerts, measurement)

        return {
            "status": "success",
            "message_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "critical_alerts": len(critical_alerts),
            "quality_score": measurement.quality_indicators.confidence_score,
            "latency_s": round(latency_s, 4)
        }

    except Exception as e:
        logger.error(f"❌ Error processing measurement: {e}")

        # Publication erreur vers topic errors avec masquage PII
        error_message = {
            "error": str(e),
            "patient_id_hash": secure_hash_patient_id(measurement.patient_id) if secure_hash_patient_id else None,
            "device_id": measurement.device_id,
            "timestamp": datetime.now().isoformat(),
            "original_measurement": {**measurement.model_dump(), "patient_id": "***masked***"}
        }

        kafka_manager.send_message(
            topic=KAFKA_TOPICS['errors'],
            message=error_message,
            key=measurement.patient_id
        )

        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")


@app.post("/iot/alerts", tags=["Alerts"])
async def create_manual_alert(alert: AlertRequest):
    """
    Crée une alerte manuelle via API.

    Permet aux systèmes externes de déclencher des alertes
    personnalisées qui seront intégrées au flux d'alertes.

    Args:
        alert: Requête d'alerte manuelle

    Returns:
        dict: Statut et ID de l'alerte créée

    Raises:
        HTTPException: Si échec publication Kafka (500)
    """
    alert_message = {
        **alert.model_dump(),
        "timestamp": datetime.now().isoformat(),
        "source": "manual",
        "alert_id": str(uuid.uuid4())
    }

    success = kafka_manager.send_message(
        topic=KAFKA_TOPICS['alerts'],
        message=alert_message,
        key=alert.patient_id
    )

    if not success:
        raise HTTPException(status_code=500, detail="Failed to publish alert")

    return {"status": "success", "alert_id": alert_message["alert_id"]}


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Endpoint de métriques observabilité.

    Fournit statistiques en temps réel :
    - Latences (percentiles 50/95/99)
    - Throughput (événements par seconde)
    - Pourcentage de données valides
    - Distribution des alertes par type
    - Uptime de l'API

    Returns:
        dict: Métriques agrégées depuis démarrage API
    """
    global processed_count

    uptime_s = max(1.0, time.time() - API_START_TIME)
    p50 = _percentile(METRICS["latencies_s"], 50) or 0.0
    p95 = _percentile(METRICS["latencies_s"], 95) or 0.0
    p99 = _percentile(METRICS["latencies_s"], 99) or 0.0
    throughput = METRICS["total_count"] / uptime_s
    pct_valid = (METRICS["valid_count"] / METRICS["total_count"] * 100.0) if METRICS["total_count"] else 0.0

    return {
        "processed_messages": processed_count,
        "total_messages": METRICS["total_count"],
        "kafka_connected": kafka_manager.producer is not None,
        "kafka_topics": list(KAFKA_TOPICS.values()),
        "api_uptime_s": round(uptime_s, 1),
        "latency_p50_s": round(p50, 4),
        "latency_p95_s": round(p95, 4),
        "latency_p99_s": round(p99, 4),
        "throughput_eps": round(throughput, 4),
        "valid_pct": round(pct_valid, 2),
        "alerts_by_type": dict(METRICS["alerts_by_type"])
    }


@app.post("/ingest", tags=["IoT Ingestion"])
async def ingest_flat(payload: FlatIngestPayload, background_tasks: BackgroundTasks):
    """
    Endpoint d'ingestion plat compatible avec tests d'intégration.

    Interface simplifiée pour tests automatisés et systèmes legacy :
    - Valide et enregistre en base (best-effort)
    - Publie message simplifié vers Kafka
    - Détecte alertes critiques et les traite
    - Retourne statut de succès avec métriques

    Args:
        payload: Données de mesure au format plat
        background_tasks: Gestionnaire tâches asynchrones

    Returns:
        dict: Statut succès avec latence et nombre d'alertes
    """
    start_time = time.time()

    # Publication vers Kafka (best-effort)
    try:
        message = {
            "patient_id": payload.patient_id,
            "device_id": payload.device_id,
            "timestamp": payload.timestamp,
            "measurements": {
                "freq_card": payload.freq_card,
                "freq_resp": payload.freq_resp,
                "spo2_pct": payload.spo2_pct,
                "temp_corp": payload.temp_corp,
                "temp_ambiante": payload.temp_ambiante,
                "pct_hydratation": payload.pct_hydratation,
                "activity": payload.activity,
                "heat_index": payload.heat_index
            },
            "quality_flag": payload.quality_flag,
        }
        kafka_manager.send_message(
            topic=KAFKA_TOPICS['measurements'],
            message=message,
            key=payload.patient_id
        )
    except Exception as e:
        logger.warning(f"Kafka publish (flat ingest) failed: {e}")

    # Enregistrement en base (best-effort, synchrone pour tests)
    try:
        _insert_measurement_flat(payload)
    except Exception as e:
        logger.warning(f"Synchronous DB insert (flat) failed: {e}")

    # Évaluation et traitement alertes critiques
    alerts = []
    try:
        alerts = _evaluate_critical_alerts_flat(payload)
    except Exception as e:
        logger.warning(f"Critical alerts evaluation (flat) failed: {e}")

    # Publication alertes et insertion DB
    try:
        if alerts:
            # Publication Kafka des alertes
            for alert in alerts:
                alert_message = {
                    "patient_id": payload.patient_id,
                    "patient_id_hash": secure_hash_patient_id(payload.patient_id) if secure_hash_patient_id else None,
                    "device_id": payload.device_id,
                    "alert_type": alert.get("type", "unknown"),
                    "severity": alert.get("severity", "unknown"),
                    "reasons": alert.get("reasons", []),
                    "message": alert.get("message", ""),
                    "timestamp": payload.timestamp,
                    "measurements": {
                        "freq_card": payload.freq_card,
                        "freq_resp": payload.freq_resp,
                        "spo2_pct": payload.spo2_pct,
                        "temp_corp": payload.temp_corp,
                        "temp_ambiante": payload.temp_ambiante,
                        "pct_hydratation": payload.pct_hydratation,
                        "activity": payload.activity,
                        "heat_index": payload.heat_index
                    }
                }
                kafka_manager.send_message(
                    topic=KAFKA_TOPICS['alerts'],
                    message=alert_message,
                    key=payload.patient_id
                )

            # Insertion DB des alertes de manière synchrone pour fiabilité des tests
            _insert_alerts_flat(payload, alerts)

            # Mise à jour métriques alertes
            for alert in alerts:
                METRICS["alerts_by_type"][alert.get("type", "unknown")] += 1

    except Exception as e:
        logger.warning(f"Critical alerts processing (flat) failed: {e}")

    # Mise à jour métriques globales
    global processed_count
    processed_count += 1
    latency_s = time.time() - start_time

    METRICS["latencies_s"].append(latency_s)
    if len(METRICS["latencies_s"]) > METRICS_MAX_LEN:
        METRICS["latencies_s"] = METRICS["latencies_s"][-METRICS_MAX_LEN:]

    METRICS["total_count"] += 1

    # Calcul validité basé sur quality_flag
    try:
        if isinstance(payload.quality_flag, str) and payload.quality_flag.lower() == "ok":
            METRICS["valid_count"] += 1
    except Exception:
        pass

    return {
        "status": "success",
        "message_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "latency_s": round(latency_s, 4),
        "critical_alerts": len(alerts),
        "alerts_detected": len(alerts)
    }


# === POINT D'ENTRÉE PRINCIPAL ===

if __name__ == "__main__":
    # Lancement serveur Uvicorn avec vérification port et fallback optionnel
    host = os.environ.get("API_HOST", "127.0.0.1")
    port_env = os.environ.get("API_PORT", "8001")

    try:
        port = int(port_env)
    except Exception:
        port = 8001

    autofallback = os.environ.get("API_PORT_AUTOFALLBACK", "true").lower() in ("1", "true", "yes", "y")

    try:
        import socket
        import uvicorn

        def _is_port_free(h: str, p: int) -> bool:
            """Vérifie si un port est libre."""
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                return s.connect_ex((h, p)) != 0

        chosen_port = port
        if not _is_port_free(host, port):
            if autofallback:
                for candidate in range(port + 1, port + 11):
                    if _is_port_free(host, candidate):
                        logger.warning(f"[Startup] Port {port} occupé, basculement vers {candidate}")
                        chosen_port = candidate
                        break
            else:
                logger.error(f"[Startup] Port {port} occupé et API_PORT_AUTOFALLBACK désactivé.")

        # Vérification finale disponibilité port
        if chosen_port == port and not _is_port_free(host, port):
            logger.error(f"[Startup] Aucun port disponible pour démarrer le serveur.")
            raise SystemExit(1)

        logger.info(f"Démarrage du serveur sur http://{host}:{chosen_port}")
        uvicorn.run(app, host=host, port=chosen_port, reload=False)

    except SystemExit:
        raise
    except Exception as e:
        logger.error(f"Impossible de démarrer le serveur: {e}")
