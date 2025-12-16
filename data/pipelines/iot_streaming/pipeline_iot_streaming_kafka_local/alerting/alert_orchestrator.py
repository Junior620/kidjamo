"""
Orchestrateur Principal du Système d'Alertes Composées
Coordonne l'analyse, la détection et les notifications
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import psycopg2
from contextlib import asynccontextmanager

# Imports absolus corrigés
from engines.composite_alerts import CompositeAlertEngine, AlertSeverity, AlertType
from notifications.aws_notification_service import AWSNotificationService
from notifications.twilio_notification_service import TwilioNotificationService
from rules.alert_rules import MedicalAlertRules, RuleType

class AlertOrchestrator:
    """Orchestrateur principal du système d'alertes"""

    def __init__(self, db_config: Dict, aws_region: str = 'eu-west-1', use_twilio: bool = True):
        self.db_config = db_config
        self.aws_region = aws_region
        self.use_twilio = use_twilio  # Nouveau paramètre pour choisir le service
        self.logger = logging.getLogger(__name__)

        # Initialisation des composants
        self.notification_service = None
        self.alert_engine = None
        self.rules_manager = MedicalAlertRules()

        # Configuration de monitoring
        self.monitoring_interval = 30  # secondes
        self.is_running = False
        self.active_patients = set()

        # Métriques de performance
        self.metrics = {
            'alerts_generated': 0,
            'notifications_sent': 0,
            'errors_count': 0,
            'processing_time_avg': 0,
            'last_run': None,
            'notification_service': 'twilio' if use_twilio else 'aws'
        }

    async def initialize(self):
        """Initialise tous les composants du système"""

        try:
            self.logger.info("Initialisation de l'orchestrateur d'alertes...")

            # Initialiser la connexion DB
            self.db_connection = psycopg2.connect(**self.db_config)

            # Choisir le service de notifications
            if self.use_twilio:
                self.logger.info("Utilisation du service de notifications Twilio")
                self.notification_service = TwilioNotificationService(
                    test_mode=getattr(self, '_test_mode', False)
                )
                await self.notification_service.initialize_services()
            else:
                self.logger.info("Utilisation du service de notifications AWS")
                self.notification_service = AWSNotificationService(self.aws_region)

                # En mode test, ne pas initialiser AWS réellement
                if hasattr(self, '_test_mode') and self._test_mode:
                    self.logger.info("Mode test activé - initialisation AWS ignorée")
                else:
                    await self.notification_service.initialize_aws_services()

            # Initialiser le moteur d'alertes composées
            self.alert_engine = CompositeAlertEngine(
                self.db_connection,
                self.notification_service
            )

            # Vérifier les tables nécessaires
            await self._ensure_database_schema()
            await self.alert_engine.ensure_database_schema()

            self.logger.info(f"Orchestrateur initialisé avec succès (service: {'Twilio' if self.use_twilio else 'AWS'})")

        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation: {e}")
            raise

    def set_test_mode(self, test_mode: bool = True):
        """Active le mode test pour éviter les appels réels aux services externes"""
        self._test_mode = test_mode

    async def send_test_notification(self, severity: str = "HIGH") -> bool:
        """Envoie une notification de test"""
        try:
            if self.notification_service:
                return await self.notification_service.send_test_notification(severity)
            else:
                self.logger.error("Service de notification non initialisé")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors du test de notification: {e}")
            return False

    def get_notification_metrics(self) -> Dict:
        """Retourne les métriques du service de notifications"""
        if self.notification_service:
            return self.notification_service.get_metrics()
        return {}

    async def start_monitoring(self):
        """Démarre le monitoring continu des patients"""

        if self.is_running:
            self.logger.warning("Le monitoring est déjà en cours")
            return

        self.is_running = True
        self.logger.info("Démarrage du monitoring des alertes composées")

        try:
            while self.is_running:
                start_time = datetime.now()

                # Récupérer la liste des patients actifs
                await self._update_active_patients()

                # Traiter chaque patient
                tasks = []
                for patient_id in self.active_patients:
                    task = self._process_patient_alerts(patient_id)
                    tasks.append(task)

                # Exécuter en parallèle avec limite
                if tasks:
                    await self._execute_with_semaphore(tasks, max_concurrent=5)

                # Nettoyer les alertes expirées
                await self._cleanup_expired_alerts()

                # Mettre à jour les métriques
                processing_time = (datetime.now() - start_time).total_seconds()
                await self._update_metrics(processing_time)

                # Attendre avant la prochaine itération
                await asyncio.sleep(self.monitoring_interval)

        except Exception as e:
            self.logger.error(f"Erreur dans la boucle de monitoring: {e}")
            self.is_running = False
            raise

    async def stop_monitoring(self):
        """Arrête le monitoring"""

        self.logger.info("Arrêt du monitoring des alertes")
        self.is_running = False

    async def _update_active_patients(self):
        """Met à jour la liste des patients actifs"""

        query = """
        SELECT DISTINCT patient_id 
        FROM measurements 
        WHERE recorded_at >= %s
        AND quality_flag != 'ERROR'
        """

        cutoff_time = datetime.now() - timedelta(minutes=30)

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (cutoff_time,))

            new_active_patients = {row[0] for row in cursor.fetchall()}

            # Log les nouveaux patients
            new_patients = new_active_patients - self.active_patients
            if new_patients:
                self.logger.info(f"Nouveaux patients actifs: {new_patients}")

            # Log les patients déconnectés
            disconnected_patients = self.active_patients - new_active_patients
            if disconnected_patients:
                self.logger.info(f"Patients déconnectés: {disconnected_patients}")

            self.active_patients = new_active_patients
            cursor.close()

        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour des patients actifs: {e}")

    async def _process_patient_alerts(self, patient_id: str):
        """Traite les alertes pour un patient spécifique"""

        try:
            # Analyser les signes vitaux pour les alertes composées
            composite_alerts = await self.alert_engine.analyze_patient_vitals(patient_id)

            if composite_alerts:
                self.logger.info(f"Patient {patient_id}: {len(composite_alerts)} alertes composées détectées")
                self.metrics['alerts_generated'] += len(composite_alerts)

            # Analyser les alertes simples (seuils)
            simple_alerts = await self._check_simple_threshold_alerts(patient_id)

            if simple_alerts:
                self.logger.info(f"Patient {patient_id}: {len(simple_alerts)} alertes simples détectées")
                self.metrics['alerts_generated'] += len(simple_alerts)

            # Analyser les tendances
            trend_alerts = await self._check_trend_alerts(patient_id)

            if trend_alerts:
                self.logger.info(f"Patient {patient_id}: {len(trend_alerts)} alertes de tendance détectées")
                self.metrics['alerts_generated'] += len(trend_alerts)

        except Exception as e:
            self.logger.error(f"Erreur lors du traitement des alertes pour {patient_id}: {e}")
            self.metrics['errors_count'] += 1

    async def _check_simple_threshold_alerts(self, patient_id: str) -> List[Dict]:
        """Vérifie les alertes de seuils simples"""

        # Récupérer les dernières mesures
        query = """
        SELECT * FROM measurements 
        WHERE patient_id = %s 
        ORDER BY recorded_at DESC 
        LIMIT 1
        """

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (patient_id,))

            row = cursor.fetchone()
            if not row:
                return []

            columns = [desc[0] for desc in cursor.description]
            latest_vitals = dict(zip(columns, row))
            cursor.close()

            # Récupérer les règles de seuils actives
            threshold_rules = self.rules_manager.get_rules_by_type(RuleType.THRESHOLD)

            alerts = []

            for rule in threshold_rules:
                if not rule.enabled:
                    continue

                parameter = rule.conditions["parameter"]
                value = latest_vitals.get(parameter)

                if value is None:
                    continue

                # Évaluer la règle
                evaluation = self.rules_manager.evaluate_threshold_rule(rule, value)

                if evaluation["triggered"]:
                    # Vérifier si l'alerte n'existe pas déjà
                    if not await self._alert_already_exists(patient_id, rule.rule_id):
                        alert = await self._create_simple_alert(
                            patient_id, rule, evaluation, latest_vitals
                        )
                        alerts.append(alert)

                        # Sauvegarder et notifier
                        await self._save_and_notify_simple_alert(alert)

            return alerts

        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification des seuils pour {patient_id}: {e}")
            return []

    async def _check_trend_alerts(self, patient_id: str) -> List[Dict]:
        """Vérifie les alertes de tendances"""

        # Récupérer les mesures des 30 dernières minutes
        query = """
        SELECT * FROM measurements 
        WHERE patient_id = %s 
        AND recorded_at >= %s
        ORDER BY recorded_at ASC
        """

        cutoff_time = datetime.now() - timedelta(minutes=30)

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (patient_id, cutoff_time))

            columns = [desc[0] for desc in cursor.description]
            measurements = []

            for row in cursor.fetchall():
                measurement = dict(zip(columns, row))
                measurements.append(measurement)

            cursor.close()

            if len(measurements) < 3:
                return []  # Pas assez de données pour analyser les tendances

            # Récupérer les règles de tendances
            trend_rules = self.rules_manager.get_rules_by_type(RuleType.TREND)

            alerts = []

            for rule in trend_rules:
                if not rule.enabled:
                    continue

                # Analyser la tendance pour ce paramètre
                trend_analysis = await self._analyze_trend(rule, measurements)

                if trend_analysis["trend_detected"]:
                    # Vérifier si l'alerte n'existe pas déjà
                    if not await self._alert_already_exists(patient_id, rule.rule_id):
                        alert = await self._create_trend_alert(
                            patient_id, rule, trend_analysis, measurements
                        )
                        alerts.append(alert)

                        # Sauvegarder et notifier
                        await self._save_and_notify_simple_alert(alert)

            return alerts

        except Exception as e:
            self.logger.error(f"Erreur lors de l'analyse des tendances pour {patient_id}: {e}")
            return []

    async def _analyze_trend(self, rule, measurements: List[Dict]) -> Dict:
        """Analyse une tendance pour un paramètre donné"""

        conditions = rule.conditions
        parameter = conditions["parameter"]
        trend_type = conditions["trend_type"]
        min_change = conditions["min_change"]
        time_window_minutes = conditions["time_window_minutes"]
        min_measurements = conditions["min_measurements"]

        # Filtrer les mesures dans la fenêtre temporelle
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_measurements = [
            m for m in measurements
            if m["recorded_at"] >= cutoff_time and m.get(parameter) is not None
        ]

        if len(recent_measurements) < min_measurements:
            return {"trend_detected": False, "reason": "Pas assez de mesures"}

        # Extraire les valeurs
        values = [m[parameter] for m in recent_measurements]

        # Calculer la tendance
        first_value = values[0]
        last_value = values[-1]
        change = last_value - first_value

        # Vérifier si la tendance correspond aux critères
        trend_detected = False

        if trend_type == "increasing" and change >= min_change:
            trend_detected = True
        elif trend_type == "decreasing" and change <= min_change:
            trend_detected = True

        return {
            "trend_detected": trend_detected,
            "change": change,
            "first_value": first_value,
            "last_value": last_value,
            "num_measurements": len(recent_measurements),
            "time_span_minutes": time_window_minutes
        }

    async def _create_simple_alert(self, patient_id: str, rule, evaluation: Dict, vitals: Dict) -> Dict:
        """Crée une alerte simple"""

        return {
            "alert_id": f"{rule.rule_id}_{patient_id}_{int(datetime.now().timestamp())}",
            "patient_id": patient_id,
            "device_id": vitals.get("device_id", "unknown"),
            "alert_type": "SIMPLE",
            "rule_id": rule.rule_id,
            "severity": evaluation["severity"],
            "title": f"⚠️ {rule.rule_name}",
            "message": f"Patient {patient_id}: {rule.rule_name} - {evaluation['parameter']} = {evaluation['value']} (seuil: {evaluation['threshold_exceeded']})",
            "vitals_snapshot": vitals,
            "medical_context": self.rules_manager.get_medical_context(
                evaluation['parameter'], evaluation['value']
            ),
            "created_at": datetime.now(),
            "ack_deadline": datetime.now() + timedelta(minutes=10)
        }

    async def _create_trend_alert(self, patient_id: str, rule, trend_analysis: Dict, measurements: List[Dict]) -> Dict:
        """Crée une alerte de tendance"""

        latest_vitals = measurements[-1]
        parameter = rule.conditions["parameter"]

        return {
            "alert_id": f"{rule.rule_id}_{patient_id}_{int(datetime.now().timestamp())}",
            "patient_id": patient_id,
            "device_id": latest_vitals.get("device_id", "unknown"),
            "alert_type": "TREND",
            "rule_id": rule.rule_id,
            "severity": "MEDIUM",
            "title": f"📈 {rule.rule_name}",
            "message": f"Patient {patient_id}: Tendance {parameter} - Changement de {trend_analysis['change']:.1f} sur {trend_analysis['time_span_minutes']} min",
            "vitals_snapshot": latest_vitals,
            "trend_data": trend_analysis,
            "medical_context": f"Évolution du paramètre {parameter}: {trend_analysis['first_value']} → {trend_analysis['last_value']}",
            "created_at": datetime.now(),
            "ack_deadline": datetime.now() + timedelta(minutes=15)
        }

    async def _save_and_notify_simple_alert(self, alert: Dict):
        """Sauvegarde et notifie une alerte simple"""

        try:
            # Sauvegarder en base
            query = """
            INSERT INTO alerts (
                patient_id, alert_type, severity, title, message,
                vitals_snapshot, created_at, ack_deadline
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            cursor = self.db_connection.cursor()
            cursor.execute(query, (
                alert["patient_id"],
                alert["alert_type"],
                alert["severity"],
                alert["title"],
                alert["message"],
                json.dumps(alert["vitals_snapshot"], default=str),  # Correction sérialisation JSON
                alert["created_at"],
                alert["ack_deadline"]
            ))
            self.db_connection.commit()
            cursor.close()

            # Notifier seulement si gravité suffisante
            if alert["severity"] in ["HIGH", "CRITICAL"]:
                # Créer un objet compatible pour le service de notification
                mock_composite_alert = type('MockAlert', (), {
                    'alert_id': alert["alert_id"],
                    'patient_id': alert["patient_id"],
                    'device_id': alert["device_id"],
                    'severity': type('MockSeverity', (), {'value': alert["severity"]})(),
                    'alert_type': type('MockType', (), {'value': alert["alert_type"]})(),
                    'vitals_snapshot': alert["vitals_snapshot"],
                    'medical_context': alert["medical_context"],
                    'recommended_action': "Évaluation médicale recommandée",
                    'created_at': alert["created_at"],
                    'correlation_score': 0,
                    'message': alert["message"]  # Ajout du message manquant
                })()

                await self.notification_service.send_alert_notification(mock_composite_alert)
                self.metrics['notifications_sent'] += 1

            self.logger.info(f"Alerte simple sauvegardée: {alert['alert_id']}")

        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde/notification de l'alerte simple: {e}")

    async def _alert_already_exists(self, patient_id: str, rule_id: str) -> bool:
        """Vérifie si une alerte existe déjà pour ce patient et cette règle"""

        query = """
        SELECT COUNT(*) FROM alerts 
        WHERE patient_id = %s 
        AND title LIKE %s
        AND ack_deadline > %s
        """

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (
                patient_id,
                f"%{rule_id}%",
                datetime.now()
            ))

            count = cursor.fetchone()[0]
            cursor.close()

            return count > 0

        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de doublons d'alertes: {e}")
            return False

    async def _cleanup_expired_alerts(self):
        """Nettoie les alertes expirées"""

        query = """
        DELETE FROM alerts 
        WHERE ack_deadline < %s 
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
                self.logger.info(f"Nettoyage: {deleted_count} alertes expirées supprimées")

        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des alertes: {e}")

    async def _update_metrics(self, processing_time: float):
        """Met à jour les métriques de performance"""

        # Calculer la moyenne mobile du temps de traitement
        if self.metrics['processing_time_avg'] == 0:
            self.metrics['processing_time_avg'] = processing_time
        else:
            # Moyenne pondérée (80% ancien, 20% nouveau)
            self.metrics['processing_time_avg'] = (
                0.8 * self.metrics['processing_time_avg'] +
                0.2 * processing_time
            )

        self.metrics['last_run'] = datetime.now()

        # Log des métriques toutes les 10 itérations
        if self.metrics['last_run'].minute % 10 == 0:
            self.logger.info(f"Métriques système: {self.metrics}")

    async def _execute_with_semaphore(self, tasks: List, max_concurrent: int = 5):
        """Exécute les tâches avec limitation de concurrence"""

        semaphore = asyncio.Semaphore(max_concurrent)

        async def limited_task(task):
            async with semaphore:
                return await task

        limited_tasks = [limited_task(task) for task in tasks]
        await asyncio.gather(*limited_tasks, return_exceptions=True)

    async def _ensure_database_schema(self):
        """Vérifie et crée les tables nécessaires"""

        # Vérifier si la table alerts existe
        check_table_query = """
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'alerts'
        )
        """

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(check_table_query)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                self.logger.info("Création de la table alerts...")

                create_table_query = """
                CREATE TABLE alerts (
                    id SERIAL PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    alert_type TEXT ,
                    severity TEXT NOT NULL,
                    title TEXT ,
                    message TEXT ,
                    vitals_snapshot TEXT,
                    created_at TIMESTAMP NOT NULL,
                    ack_deadline TIMESTAMP NOT NULL,
                    acknowledged BOOLEAN DEFAULT FALSE,
                    acknowledged_at TIMESTAMP,
                    acknowledged_by TEXT
                )
                """

                cursor.execute(create_table_query)
                self.db_connection.commit()

                self.logger.info("Table alerts créée avec succès")

            cursor.close()

        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification du schéma: {e}")
            raise

    async def get_system_status(self) -> Dict:
        """Retourne le statut du système d'alertes"""

        active_alerts_count = 0

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM alerts WHERE ack_deadline > %s",
                (datetime.now(),)
            )
            active_alerts_count = cursor.fetchone()[0]
            cursor.close()

        except Exception as e:
            self.logger.error(f"Erreur lors du calcul des alertes actives: {e}")

        return {
            "status": "RUNNING" if self.is_running else "STOPPED",
            "active_patients": len(self.active_patients),
            "active_alerts": active_alerts_count,
            "monitoring_interval": self.monitoring_interval,
            "metrics": self.metrics,
            "last_update": datetime.now().isoformat()
        }

    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """Accuse réception d'une alerte"""

        query = """
        UPDATE alerts 
        SET acknowledged = TRUE, 
            acknowledged_at = %s, 
            acknowledged_by = %s
        WHERE id = %s
        """

        try:
            cursor = self.db_connection.cursor()
            cursor.execute(query, (datetime.now(), acknowledged_by, alert_id))

            affected_rows = cursor.rowcount
            self.db_connection.commit()
            cursor.close()

            if affected_rows > 0:
                self.logger.info(f"Alerte {alert_id} accusée de réception par {acknowledged_by}")
                return True
            else:
                self.logger.warning(f"Alerte {alert_id} non trouvée pour accusé de réception")
                return False

        except Exception as e:
            self.logger.error(f"Erreur lors de l'accusé de réception: {e}")
            return False

    def __del__(self):
        """Nettoyage lors de la destruction de l'objet"""
        if hasattr(self, 'db_connection') and self.db_connection:
            self.db_connection.close()
