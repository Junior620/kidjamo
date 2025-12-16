"""
Moteur d'Alertes Composées pour Pipeline IoT Médical
Gère les alertes complexes basées sur plusieurs paramètres vitaux
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio

class AlertSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertType(Enum):
    SIMPLE = "SIMPLE"
    COMPOSITE = "COMPOSITE"
    TRENDING = "TRENDING"
    CORRELATION = "CORRELATION"

@dataclass
class VitalSign:
    """Représente un signe vital avec ses seuils"""
    value: float
    timestamp: datetime
    parameter_name: str
    normal_min: float
    normal_max: float
    warning_min: float
    warning_max: float
    critical_min: float
    critical_max: float

@dataclass
class CompositeAlert:
    """Alerte composée avec contexte médical"""
    alert_id: str
    patient_id: str
    device_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    vitals_involved: List[str]
    vitals_snapshot: Dict
    medical_context: str
    recommended_action: str
    correlation_score: float
    created_at: datetime
    expires_at: datetime

class CompositeAlertEngine:
    """Moteur principal d'alertes composées"""

    def __init__(self, db_connection, notification_service):
        self.db_connection = db_connection
        self.notification_service = notification_service
        self.logger = logging.getLogger(__name__)

        # Seuils médicaux par paramètre
        self.medical_thresholds = self._load_medical_thresholds()

        # Patterns d'alertes composées
        self.composite_patterns = self._initialize_composite_patterns()

        # Cache des alertes récentes
        self.recent_alerts = {}

    def _load_medical_thresholds(self) -> Dict:
        """Charge les seuils médicaux de référence"""
        return {
            'freq_card': {
                'normal_min': 60, 'normal_max': 100,
                'warning_min': 50, 'warning_max': 120,
                'critical_min': 40, 'critical_max': 140
            },
            'freq_resp': {
                'normal_min': 12, 'normal_max': 20,
                'warning_min': 8, 'warning_max': 25,
                'critical_min': 6, 'critical_max': 30
            },
            'spo2_pct': {
                'normal_min': 95, 'normal_max': 100,
                'warning_min': 90, 'warning_max': 100,
                'critical_min': 80, 'critical_max': 100
            },
            'temp_corp': {
                'normal_min': 36.1, 'normal_max': 37.2,
                'warning_min': 35.5, 'warning_max': 38.0,
                'critical_min': 34.0, 'critical_max': 40.0
            },
            'temp_ambiante': {
                'normal_min': 18.0, 'normal_max': 25.0,
                'warning_min': 15.0, 'warning_max': 30.0,
                'critical_min': 10.0, 'critical_max': 35.0
            },
            'pct_hydratation': {
                'normal_min': 60, 'normal_max': 80,
                'warning_min': 50, 'warning_max': 90,
                'critical_min': 40, 'critical_max': 95
            }
        }

    def _initialize_composite_patterns(self) -> Dict:
        """Initialise les patterns d'alertes composées"""
        return {
            'hypoxia_pattern': {
                'name': 'Détresse Respiratoire/Hypoxie',
                'conditions': {
                    'spo2_pct': {'max': 88},
                    'freq_resp': {'min': 25},
                    'freq_card': {'min': 110}
                },
                'severity': AlertSeverity.CRITICAL,
                'medical_context': 'Signes de détresse respiratoire sévère avec hypoxémie',
                'action': 'Oxygénothérapie immédiate et évaluation médicale urgente'
            },

            'fever_tachycardia': {
                'name': 'Hyperthermie avec Tachycardie',
                'conditions': {
                    'temp_corp': {'min': 38.5},
                    'freq_card': {'min': 120},
                    'freq_resp': {'min': 22}
                },
                'severity': AlertSeverity.HIGH,
                'medical_context': 'Réaction fébrile avec impact cardiovasculaire',
                'action': 'Antipyrétiques et surveillance cardiaque renforcée'
            },

            'hypothermia_bradycardia': {
                'name': 'Hypothermie avec Bradycardie',
                'conditions': {
                    'temp_corp': {'max': 35.0},
                    'freq_card': {'max': 50},
                    'temp_ambiante': {'max': 18.0}
                },
                'severity': AlertSeverity.HIGH,
                'medical_context': 'Hypothermie avec ralentissement cardiovasculaire',
                'action': 'Réchauffement progressif et surveillance cardiaque'
            },

            'dehydration_pattern': {
                'name': 'Déshydratation Sévère',
                'conditions': {
                    'pct_hydratation': {'max': 45},
                    'freq_card': {'min': 100},
                    'temp_corp': {'min': 37.5}
                },
                'severity': AlertSeverity.HIGH,
                'medical_context': 'Signes de déshydratation avec impact hémodynamique',
                'action': 'Réhydratation IV et bilan électrolytique'
            },

            'respiratory_distress': {
                'name': 'Détresse Respiratoire',
                'conditions': {
                    'freq_resp': {'min': 28},
                    'spo2_pct': {'max': 92},
                    'freq_card': {'min': 100}
                },
                'severity': AlertSeverity.HIGH,
                'medical_context': 'Détresse respiratoire avec désaturation',
                'action': 'Support ventilatoire et évaluation pulmonaire'
            },

            'environmental_stress': {
                'name': 'Stress Environnemental',
                'conditions': {
                    'temp_ambiante': {'min': 30.0},
                    'temp_corp': {'min': 38.0},
                    'freq_card': {'min': 90}
                },
                'severity': AlertSeverity.MEDIUM,
                'medical_context': 'Stress thermique lié à l\'environnement',
                'action': 'Modification de l\'environnement et surveillance'
            }
        }

    async def analyze_patient_vitals(self, patient_id: str) -> List[CompositeAlert]:
        """Analyse les signes vitaux d'un patient pour détecter les alertes composées"""
        try:
            # Récupérer les dernières mesures
            vitals_data = await self._get_recent_vitals(patient_id)

            if not vitals_data:
                return []

            alerts = []

            # Analyser chaque pattern d'alerte composée
            for pattern_id, pattern in self.composite_patterns.items():
                alert = await self._evaluate_composite_pattern(
                    patient_id, pattern_id, pattern, vitals_data
                )

                if alert:
                    alerts.append(alert)

                    # Sauvegarder l'alerte
                    await self._save_composite_alert(alert)

                    # Envoyer la notification
                    await self.notification_service.send_alert_notification(alert)

                    self.logger.info(f"Alerte composée générée: {alert.alert_id}")

            return alerts

        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse des signes vitaux: {e}")
            return []

    async def _get_recent_vitals(self, patient_id: str) -> Optional[Dict]:
        """Récupère les signes vitaux récents d'un patient"""
        query = """
        SELECT * FROM measurements 
        WHERE patient_id = %s 
        AND recorded_at >= %s
        ORDER BY recorded_at DESC 
        LIMIT 1
        """

        cutoff_time = datetime.now() - timedelta(minutes=10)

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (patient_id, cutoff_time))

            row = cursor.fetchone()
            if not row:
                return None

            columns = [desc[0] for desc in cursor.description]
            vitals = dict(zip(columns, row))
            cursor.close()

            return vitals

        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des signes vitaux: {e}")
            return None

    async def _evaluate_composite_pattern(self, patient_id: str, pattern_id: str,
                                        pattern: Dict, vitals: Dict) -> Optional[CompositeAlert]:
        """Évalue un pattern d'alerte composée"""

        conditions = pattern['conditions']
        matched_conditions = []
        total_conditions = len(conditions)

        # Vérifier chaque condition
        for param, condition in conditions.items():
            value = vitals.get(param)

            if value is None:
                continue

            condition_met = False

            if 'min' in condition and value >= condition['min']:
                condition_met = True
            elif 'max' in condition and value <= condition['max']:
                condition_met = True
            elif 'range' in condition:
                min_val, max_val = condition['range']
                if min_val <= value <= max_val:
                    condition_met = True

            if condition_met:
                matched_conditions.append(param)

        # Calculer le score de correspondance
        match_score = len(matched_conditions) / total_conditions * 100

        # Seuil de déclenchement (80% des conditions doivent être remplies)
        if match_score >= 80:
            # Vérifier s'il n'y a pas déjà une alerte similaire récente
            if not await self._is_duplicate_alert(patient_id, pattern_id):
                return await self._create_composite_alert(
                    patient_id, pattern_id, pattern, vitals, matched_conditions, match_score
                )

        return None

    async def _create_composite_alert(self, patient_id: str, pattern_id: str,
                                    pattern: Dict, vitals: Dict,
                                    matched_conditions: List[str],
                                    match_score: float) -> CompositeAlert:
        """Crée une alerte composée"""

        alert_id = f"COMP_{pattern_id}_{patient_id}_{int(datetime.now().timestamp())}"

        # Construire le message détaillé
        condition_details = []
        for param in matched_conditions:
            value = vitals.get(param)
            thresholds = self.medical_thresholds.get(param, {})

            if value < thresholds.get('normal_min', 0):
                status = "⬇️ BAS"
            elif value > thresholds.get('normal_max', 999):
                status = "⬆️ ÉLEVÉ"
            else:
                status = "⚠️ LIMITE"

            condition_details.append(f"{param}: {value} {status}")

        message = f"Pattern '{pattern['name']}' détecté.\nConditions: {', '.join(condition_details)}"

        return CompositeAlert(
            alert_id=alert_id,
            patient_id=patient_id,
            device_id=vitals.get('device_id', 'unknown'),
            alert_type=AlertType.COMPOSITE,
            severity=pattern['severity'],
            title=f"🔴 {pattern['name']}",
            message=message,
            vitals_involved=matched_conditions,
            vitals_snapshot=vitals,
            medical_context=pattern['medical_context'],
            recommended_action=pattern['action'],
            correlation_score=match_score,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=2)
        )

    async def _is_duplicate_alert(self, patient_id: str, pattern_id: str) -> bool:
        """Vérifie s'il existe déjà une alerte similaire récente"""

        # Vérifier le cache local
        cache_key = f"{patient_id}_{pattern_id}"
        if cache_key in self.recent_alerts:
            last_alert_time = self.recent_alerts[cache_key]
            if datetime.now() - last_alert_time < timedelta(minutes=30):
                return True

        # Vérifier en base de données
        query = """
        SELECT COUNT(*) FROM composite_alerts 
        WHERE patient_id = %s 
        AND pattern_id = %s 
        AND created_at >= %s
        """

        cutoff_time = datetime.now() - timedelta(minutes=30)

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (patient_id, pattern_id, cutoff_time))

            count = cursor.fetchone()[0]
            cursor.close()

            return count > 0

        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de doublons: {e}")
            return False

    async def _save_composite_alert(self, alert: CompositeAlert):
        """Sauvegarde une alerte composée en base"""

        query = """
        INSERT INTO composite_alerts (
            alert_id, patient_id, device_id, pattern_id, severity, title, message,
            vitals_involved, vitals_snapshot, medical_context, recommended_action,
            correlation_score, created_at, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        # Extraire le pattern_id de l'alert_id
        pattern_id = alert.alert_id.split('_')[1]

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (
                alert.alert_id,
                alert.patient_id,
                alert.device_id,
                pattern_id,
                alert.severity.value,
                alert.title,
                alert.message,
                json.dumps(alert.vitals_involved),
                json.dumps(alert.vitals_snapshot, default=str),  # Correction sérialisation JSON
                alert.medical_context,
                alert.recommended_action,
                alert.correlation_score,
                alert.created_at,
                alert.expires_at
            ))

            self.db_connection.commit()
            cursor.close()

            # Mettre à jour le cache
            cache_key = f"{alert.patient_id}_{pattern_id}"
            self.recent_alerts[cache_key] = alert.created_at

            self.logger.info(f"Alerte composée sauvegardée: {alert.alert_id}")

        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde de l'alerte composée: {e}")

    async def get_active_alerts(self, patient_id: Optional[str] = None) -> List[Dict]:
        """Récupère les alertes composées actives"""

        base_query = """
        SELECT * FROM composite_alerts 
        WHERE expires_at > %s
        """
        params = [datetime.now()]

        if patient_id:
            base_query += " AND patient_id = %s"
            params.append(patient_id)

        base_query += " ORDER BY created_at DESC"

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(base_query, params)

            columns = [desc[0] for desc in cursor.description]
            alerts = []

            for row in cursor.fetchall():
                alert_data = dict(zip(columns, row))
                # Désérialiser les champs JSON
                alert_data['vitals_involved'] = json.loads(alert_data['vitals_involved'])
                alert_data['vitals_snapshot'] = json.loads(alert_data['vitals_snapshot'])
                alerts.append(alert_data)

            cursor.close()
            return alerts

        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des alertes actives: {e}")
            return []

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Accuse réception d'une alerte composée"""

        query = """
        UPDATE composite_alerts 
        SET acknowledged = TRUE, 
            acknowledged_at = %s, 
            acknowledged_by = %s
        WHERE alert_id = %s
        """

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (datetime.now(), acknowledged_by, alert_id))

            affected_rows = cursor.rowcount
            self.db_connection.commit()
            cursor.close()

            if affected_rows > 0:
                self.logger.info(f"Alerte composée {alert_id} accusée de réception par {acknowledged_by}")
                return True
            else:
                self.logger.warning(f"Alerte composée {alert_id} non trouvée")
                return False

        except Exception as e:
            self.logger.error(f"Erreur lors de l'accusé de réception: {e}")
            return False

    async def cleanup_expired_alerts(self):
        """Nettoie les alertes expirées"""

        query = """
        DELETE FROM composite_alerts 
        WHERE expires_at < %s
        AND created_at < %s
        """

        # Supprimer les alertes expirées depuis plus de 24h
        expiry_time = datetime.now() - timedelta(hours=24)

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (datetime.now(), expiry_time))

            deleted_count = cursor.rowcount
            self.db_connection.commit()
            cursor.close()

            if deleted_count > 0:
                self.logger.info(f"Nettoyage: {deleted_count} alertes composées expirées supprimées")

            # Nettoyer aussi le cache local
            current_time = datetime.now()
            expired_keys = [
                key for key, timestamp in self.recent_alerts.items()
                if current_time - timestamp > timedelta(hours=1)
            ]

            for key in expired_keys:
                del self.recent_alerts[key]

        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des alertes: {e}")

    async def ensure_database_schema(self):
        """Vérifie et crée les tables nécessaires"""

        create_table_query = """
        CREATE TABLE IF NOT EXISTS composite_alerts (
            id SERIAL PRIMARY KEY,
            alert_id TEXT UNIQUE NOT NULL,
            patient_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            pattern_id TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            vitals_involved TEXT NOT NULL,
            vitals_snapshot TEXT NOT NULL,
            medical_context TEXT NOT NULL,
            recommended_action TEXT NOT NULL,
            correlation_score FLOAT NOT NULL,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            acknowledged BOOLEAN DEFAULT FALSE,
            acknowledged_at TIMESTAMP,
            acknowledged_by TEXT
        )
        """

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(create_table_query)
            self.db_connection.commit()
            cursor.close()

            self.logger.info("Schéma de base de données vérifié/créé")

        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du schéma: {e}")
            raise

    def get_pattern_statistics(self) -> Dict:
        """Retourne les statistiques des patterns d'alertes"""

        query = """
        SELECT pattern_id, severity, COUNT(*) as count
        FROM composite_alerts 
        WHERE created_at >= %s
        GROUP BY pattern_id, severity
        ORDER BY count DESC
        """

        # Statistiques des 7 derniers jours
        cutoff_time = datetime.now() - timedelta(days=7)

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (cutoff_time,))

            stats = {}
            for row in cursor.fetchall():
                pattern_id, severity, count = row
                if pattern_id not in stats:
                    stats[pattern_id] = {}
                stats[pattern_id][severity] = count

            cursor.close()
            return stats

        except Exception as e:
            self.logger.error(f"Erreur lors du calcul des statistiques: {e}")
            return {}

