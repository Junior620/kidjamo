"""
Simulateur Massif de Patients IoT - 50+ Patients en Temps Réel

Rôle :
    Simulateur IoT haute performance pour génération simultanée de données médicales
    pour 50+ patients virtuels avec cycles circadiens, scénarios de crise et alertes.
    Intégration complète avec notifications SMS/Email via Twilio et SMTP.

Objectifs :
    - Génération simultanée de 50+ patients virtuels avec profils médicaux diversifiés
    - Émission de mesures physiologiques toutes les 5 secondes pendant 24h continues
    - Détection automatique d'anomalies et génération d'alertes critiques
    - Notifications en temps réel (SMS Twilio + Email) pour toute alerte
    - Insertion directe en base de données avec gestion des performances
    - Dashboard temps réel compatible avec WebSocket/SSE

Caractéristiques techniques :
    - Threading pool pour 50+ patients simultanés
    - Gestion mémoire optimisée pour 24h de données continues
    - Batch insert en base pour performances (1000 mesures/batch)
    - Circuit breaker pour notifications (éviter spam)
    - Monitoring temps réel des performances et métriques

Variables physiologiques simulées :
    - SpO2 (%), fréquence cardiaque (bpm), température corporelle (°C)
    - Fréquence respiratoire (/min), hydratation (%), température ambiante (°C)
    - Niveau d'activité (0-10), douleur (0-10), qualité signal (%)
    - Batterie dispositif (%), index de chaleur calculé

Notifications configurées :
    - SMS Twilio vers +237695607089 pour alertes critiques
    - Email SMTP vers christianouragan@gmail.com 
    - Base de données : table alerts avec métadonnées complètes
"""

import asyncio
import json
import logging
import math
import os
import sys
import random
import smtplib
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from statistics import mean, median
from typing import Dict, List, Optional, Tuple
from queue import Queue, Empty
import psycopg2
from psycopg2.extras import execute_batch
import requests

# Import Twilio avec gestion gracieuse
try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("⚠️  Twilio non disponible. Installation : pip install twilio")

# Import Kafka avec gestion gracieuse
try:
    from kafka import KafkaProducer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False
    print("⚠️  Kafka non disponible. Installation : pip install kafka-python")

# Configuration logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =====================================================
# CONFIGURATION GLOBALE - MODIFIABLE SELON ENVIRONNEMENT
# =====================================================

# Configuration base de données PostgreSQL
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'kidjamo-db'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', 'kidjamo@')
}

# Configuration Twilio (SMS) - UTILISER VARIABLES D'ENVIRONNEMENT
TWILIO_CONFIG = {
    'account_sid': os.getenv('TWILIO_ACCOUNT_SID', ''),
    'auth_token': os.getenv('TWILIO_AUTH_TOKEN', ''),
    'from_number': os.getenv('TWILIO_FROM_NUMBER', ''),
    'to_number': os.getenv('TWILIO_TO_NUMBER', '')  # Numéro cible pour SMS alertes
}

# Configuration Email (SMTP) - UTILISER VARIABLES D'ENVIRONNEMENT
EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('SMTP_PORT', '587')),
    'username': os.getenv('SMTP_USERNAME', 'apikey'),
    'password': os.getenv('SMTP_PASSWORD', ''),
    'from_email': os.getenv('FROM_EMAIL', 'support@kidjamo.app'),
    'to_email': os.getenv('TO_EMAIL', '')  # Email cible pour alertes
}

# Configuration Kafka
KAFKA_CONFIG = {
    'bootstrap_servers': ['localhost:9092'],
    'topics': {
        'measurements': 'kidjamo-iot-measurements',
        'alerts': 'kidjamo-iot-alerts',
        'device_status': 'kidjamo-iot-device-status'
    }
}

# Configuration API d'ingestion
API_CONFIG = {
    'base_url': 'http://localhost:8001',
    'endpoints': {
        'measurements': '/iot/measurements',
        'ingest': '/ingest'
    }
}

# Seuils médicaux pour détection d'alertes (inchangés - validés médicalement)
MEDICAL_THRESHOLDS = {
    "spo2_critical_ss": 85,      # SpO2 critique pour drépanocytose SS
    "spo2_critical_general": 88,  # SpO2 critique général
    "spo2_low": 90,              # SpO2 basse (surveillance)
    "temperature_fever": 38.0,    # Fièvre
    "temperature_high_fever": 39.5,  # Fièvre élevée
    "heart_rate_tachycardia_adult": 120,   # Tachycardie adulte
    "heart_rate_tachycardia_child": 140,   # Tachycardie enfant
    "heart_rate_bradycardia": 50,          # Bradycardie
    "respiratory_rate_high_adult": 24,     # Tachypnée adulte
    "respiratory_rate_high_child": 30,     # Tachypnée enfant
    "dehydration_threshold": 40,           # Seuil déshydratation critique
    "pain_severe": 7,                      # Douleur sévère
    "battery_critical": 15,                # Batterie critique
}

# Génotypes drépanocytaires avec caractéristiques physiologiques
GENOTYPES = {
    "SS": {
        "base_spo2_range": (92, 96),
        "crisis_frequency": 0.15,
        "pain_sensitivity": 1.8,
        "infection_risk": 1.5,
        "description": "Drépanocytose homozygote - Forme la plus sévère"
    },
    "SC": {
        "base_spo2_range": (94, 98),
        "crisis_frequency": 0.08,
        "pain_sensitivity": 1.3,
        "infection_risk": 1.2,
        "description": "Drépanocytose hétérozygote SC"
    },
    "AS": {
        "base_spo2_range": (96, 100),
        "crisis_frequency": 0.01,
        "pain_sensitivity": 1.0,
        "infection_risk": 1.0,
        "description": "Trait drépanocytaire - Porteur sain"
    },
    "Sβ0": {
        "base_spo2_range": (93, 97),
        "crisis_frequency": 0.12,
        "pain_sensitivity": 1.6,
        "infection_risk": 1.4,
        "description": "Drépanocytose bêta-thalassémie"
    }
}

# =====================================================
# MODÈLES DE DONNÉES
# =====================================================

@dataclass
class PatientProfile:
    """Profil complet d'un patient virtuel avec caractéristiques médicales"""
    patient_id: str
    user_id: str
    first_name: str
    last_name: str
    age: int
    gender: str
    genotype: str
    weight_kg: float
    height_cm: float
    device_id: str
    
    # Paramètres physiologiques de base
    base_heart_rate: int
    base_spo2_range: Tuple[int, int]
    base_temperature: float
    base_respiratory_rate: int
    base_hydration: float
    
    # État médical actuel
    is_in_crisis: bool = False
    crisis_start_time: Optional[datetime] = None
    pain_level: int = 0
    infection_risk_factor: float = 1.0
    last_measurement_time: Optional[datetime] = None
    
    # Métadonnées
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_db_record(self) -> Dict:
        """Convertit le profil en enregistrement pour insertion DB"""
        return {
            'patient_id': self.patient_id,
            'user_id': self.user_id,
            'genotype': self.genotype,
            'birth_date': (datetime.now() - timedelta(days=self.age * 365)).date(),
            'weight_kg': self.weight_kg,
            'height_cm': self.height_cm,
            'current_device_id': self.device_id,
            'medical_notes': f"Patient virtuel - Simulation IoT - Génotype {self.genotype}",
            'created_at': self.created_at,
            'updated_at': self.created_at
        }

@dataclass 
class MeasurementRecord:
    """Enregistrement de mesure physiologique complète"""
    measurement_id: Optional[int]
    patient_id: str
    device_id: str
    message_id: str
    recorded_at: datetime
    received_at: datetime
    
    # Variables physiologiques principales
    heart_rate_bpm: int
    respiratory_rate_min: int
    spo2_percent: float
    temperature_celsius: float
    ambient_temp_celsius: float
    hydration_percent: float
    activity_level: int
    heat_index_celsius: float
    
    # Variables additionnelles
    pain_scale: int
    battery_percent: int
    signal_quality: int
    
    # Métadonnées qualité
    quality_flag: str = 'ok'
    data_source: str = 'device'
    is_validated: bool = False
    
    def to_db_record(self) -> Tuple:
        """Convertit en tuple pour insertion batch PostgreSQL"""
        return (
            self.patient_id, self.device_id, self.message_id,
            self.recorded_at, self.received_at,
            self.heart_rate_bpm, self.respiratory_rate_min,
            self.spo2_percent, self.temperature_celsius,
            self.ambient_temp_celsius, self.hydration_percent,
            self.activity_level, self.heat_index_celsius,
            self.pain_scale, self.battery_percent, self.signal_quality,
            self.quality_flag, self.data_source, self.is_validated
        )

@dataclass
class AlertRecord:
    """Enregistrement d'alerte médicale avec contexte complet"""
    alert_id: Optional[int]
    patient_id: str
    alert_type: str
    severity: str  # 'info', 'warn', 'alert', 'critical'
    title: str
    message: str
    
    # Contexte médical
    vitals_snapshot: Dict
    trigger_conditions: List[str]
    suggested_actions: List[str]
    
    # Métadonnées temporelles
    created_at: datetime
    first_seen_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    auto_resolved: bool = False
    
    # Escalation
    ack_deadline: Optional[datetime] = None
    escalation_level: int = 0
    
    # Traçabilité
    created_by_system: str = 'massive_simulator'
    related_measurement_id: Optional[int] = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_db_record(self) -> Tuple:
        """Convertit en tuple pour insertion PostgreSQL"""
        return (
            self.patient_id, self.alert_type, self.severity,
            self.title, self.message,
            json.dumps(self.vitals_snapshot),
            self.trigger_conditions, self.suggested_actions,
            self.created_at, self.first_seen_at, self.resolved_at,
            self.auto_resolved, self.ack_deadline, self.escalation_level,
            self.created_by_system, self.related_measurement_id,
            self.correlation_id
        )

# =====================================================
# SERVICES DE NOTIFICATION
# =====================================================

class NotificationService:
    """Service centralisé pour notifications SMS et Email avec circuit breaker"""
    
    def __init__(self):
        self.twilio_client = None
        self.email_session = None
        self.notification_queue = Queue()
        self.circuit_breaker = {
            'sms_failures': 0,
            'email_failures': 0,
            'last_sms_success': datetime.now(),
            'last_email_success': datetime.now(),
            'sms_disabled': False,
            'email_disabled': False
        }
        
        # Initialisation Twilio
        if TWILIO_AVAILABLE and TWILIO_CONFIG['account_sid']:
            try:
                self.twilio_client = TwilioClient(
                    TWILIO_CONFIG['account_sid'],
                    TWILIO_CONFIG['auth_token']
                )
                logger.info("✅ Service SMS Twilio initialisé")
            except Exception as e:
                logger.error(f"❌ Erreur initialisation Twilio: {e}")
        
        # Test connexion SMTP
        if EMAIL_CONFIG['username']:
            try:
                self._test_smtp_connection()
                logger.info("✅ Service Email SMTP initialisé")
            except Exception as e:
                logger.error(f"❌ Erreur initialisation SMTP: {e}")
    
    def _test_smtp_connection(self):
        """Test de connexion SMTP"""
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()
        server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
        server.quit()
    
    async def send_alert_notification(self, alert: AlertRecord, patient: PatientProfile):
        """Envoi notifications SMS + Email pour une alerte"""
        try:
            # Préparer contenu notification
            sms_content = self._format_sms_alert(alert, patient)
            email_content = self._format_email_alert(alert, patient)
            
            # Envoi SMS si critique ou alerte
            if alert.severity in ['critical', 'alert'] and not self.circuit_breaker['sms_disabled']:
                await self._send_sms(sms_content)
            
            # Envoi Email pour toutes les alertes
            if not self.circuit_breaker['email_disabled']:
                await self._send_email(alert.title, email_content)
                
            logger.info(f"📤 Notifications envoyées pour alerte {alert.alert_type} - Patient {patient.first_name} {patient.last_name}")
            
        except Exception as e:
            logger.error(f"❌ Erreur envoi notifications: {e}")
    
    def _format_sms_alert(self, alert: AlertRecord, patient: PatientProfile) -> str:
        """Formatage SMS court et informatif"""
        return f"""🚨 ALERTE KIDJAMO {alert.severity.upper()}
Patient: {patient.first_name} {patient.last_name} ({patient.age}ans)
{alert.title}
Signes vitaux: SpO2={alert.vitals_snapshot.get('spo2')}%, FC={alert.vitals_snapshot.get('heart_rate')}bpm
Heure: {alert.created_at.strftime('%H:%M')}
Actions: {', '.join(alert.suggested_actions[:2])}"""
    
    def _format_email_alert(self, alert: AlertRecord, patient: PatientProfile) -> str:
        """Formatage Email détaillé avec contexte médical"""
        return f"""
        <html>
        <body>
        <h2>🚨 Alerte Médicale KIDJAMO - {alert.severity.upper()}</h2>
        
        <h3>Informations Patient</h3>
        <ul>
            <li><strong>Nom:</strong> {patient.first_name} {patient.last_name}</li>
            <li><strong>Âge:</strong> {patient.age} ans</li>
            <li><strong>Génotype:</strong> {patient.genotype}</li>
            <li><strong>Device ID:</strong> {patient.device_id}</li>
        </ul>
        
        <h3>Détails de l'Alerte</h3>
        <ul>
            <li><strong>Type:</strong> {alert.alert_type}</li>
            <li><strong>Titre:</strong> {alert.title}</li>
            <li><strong>Message:</strong> {alert.message}</li>
            <li><strong>Heure:</strong> {alert.created_at.strftime('%d/%m/%Y %H:%M:%S')}</li>
        </ul>
        
        <h3>Signes Vitaux au Moment de l'Alerte</h3>
        <ul>
            <li><strong>SpO2:</strong> {alert.vitals_snapshot.get('spo2', 'N/A')}%</li>
            <li><strong>Fréquence Cardiaque:</strong> {alert.vitals_snapshot.get('heart_rate', 'N/A')} bpm</li>
            <li><strong>Température:</strong> {alert.vitals_snapshot.get('temperature', 'N/A')}°C</li>
            <li><strong>Fréquence Respiratoire:</strong> {alert.vitals_snapshot.get('respiratory_rate', 'N/A')}/min</li>
            <li><strong>Hydratation:</strong> {alert.vitals_snapshot.get('hydration', 'N/A')}%</li>
            <li><strong>Douleur:</strong> {alert.vitals_snapshot.get('pain', 'N/A')}/10</li>
        </ul>
        
        <h3>Conditions de Déclenchement</h3>
        <ul>
            {"".join(f"<li>{condition}</li>" for condition in alert.trigger_conditions)}
        </ul>
        
        <h3>Actions Recommandées</h3>
        <ol>
            {"".join(f"<li>{action}</li>" for action in alert.suggested_actions)}
        </ol>
        
        <hr>
        <p><em>Cet email a été généré automatiquement par le système de surveillance KIDJAMO IoT.</em></p>
        <p><em>ID Corrélation: {alert.correlation_id}</em></p>
        </body>
        </html>
        """
    
    async def _send_sms(self, content: str):
        """Envoi SMS via Twilio avec retry et circuit breaker"""
        if not self.twilio_client:
            logger.warning("⚠️  Client Twilio non disponible")
            return
            
        try:
            message = self.twilio_client.messages.create(
                body=content,
                from_=TWILIO_CONFIG['from_number'],
                to=TWILIO_CONFIG['to_number']
            )
            self.circuit_breaker['sms_failures'] = 0
            self.circuit_breaker['last_sms_success'] = datetime.now()
            logger.info(f"📱 SMS envoyé avec succès: {message.sid}")
            
        except Exception as e:
            self.circuit_breaker['sms_failures'] += 1
            logger.error(f"❌ Erreur envoi SMS: {e}")
            
            # Circuit breaker - désactiver SMS si trop d'échecs
            if self.circuit_breaker['sms_failures'] >= 5:
                self.circuit_breaker['sms_disabled'] = True
                logger.warning("⚠️  Service SMS désactivé temporairement (trop d'échecs)")
    
    async def _send_email(self, subject: str, html_content: str):
        """Envoi Email via SMTP avec retry et circuit breaker"""
        if not EMAIL_CONFIG['username']:
            logger.warning("⚠️  Configuration SMTP manquante")
            return
            
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"KIDJAMO IoT - {subject}"
            msg['From'] = EMAIL_CONFIG['from_email']
            msg['To'] = EMAIL_CONFIG['to_email']
            
            # Ajouter contenu HTML
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Envoi
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
            server.send_message(msg)
            server.quit()
            
            self.circuit_breaker['email_failures'] = 0
            self.circuit_breaker['last_email_success'] = datetime.now()
            logger.info(f"📧 Email envoyé avec succès")
            
        except Exception as e:
            self.circuit_breaker['email_failures'] += 1
            logger.error(f"❌ Erreur envoi Email: {e}")
            
            # Circuit breaker
            if self.circuit_breaker['email_failures'] >= 5:
                self.circuit_breaker['email_disabled'] = True
                logger.warning("⚠️  Service Email désactivé temporairement (trop d'échecs)")

# =====================================================
# SUITE DU CODE DANS LE PROCHAIN FICHIER...
# =====================================================
