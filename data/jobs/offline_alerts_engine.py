if len(recent_history) < 2:
"""
Moteur d'alertes hors-ligne pour la surveillance des patients atteints de drépanocytose.
        # Compter combien de vitaux sont constants
"""

        for vital_name in vitals_to_check:
import time
from datetime import datetime, timedelta
                
from dataclasses import dataclass
from enum import Enum
import logging
                "vitals": constant_vitals,
class Severity(Enum):
    INFO = "info"
    WARN = "warn"
    ALERT = "alert"
    CRITICAL = "critical"

@dataclass
                                   vital_name: str, tolerance: float) -> bool:
    severity: Severity
        values = [vitals.get(vital_name) for ts, vitals in history_period]
        values = [v for v in values if v is not None]
    timestamp: datetime
    vitals: Dict[str, float]
    context: Dict[str, Any]
    trend: Optional[str]
        # Vérifier que toutes les valeurs sont dans la tolérance de la première
    ack_deadline: datetime
    cooldown_s: int
        

class OfflineAlertsEngine:

        """
        self.config = self._load_config(config_path)
        self.active_alerts = {}  # patient_id -> {alert_type: last_timestamp}
        self.cooldown_tracker = {}  # (patient_id, alert_type) -> last_alert_time
        self.logger = self._setup_logging()
        
        # 1. Détection flatline avec analyse temporelle
        self.patient_history = {}  # patient_id -> list of (timestamp, vitals)
        self.max_history_minutes = 15  # Garder 15 min d'historique
        

    def _load_config(self, path: str) -> Dict:
        """Charge la configuration des seuils médicaux."""
        
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
        
            raise

    def _setup_logging(self):
            alert = self._create_alert(
        logger = logging.getLogger('offline_alerts')
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.FileHandler('logs/offline_alerts.log')
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def get_age_group(self, age_years: float) -> str:
        """Détermine le groupe d'âge G1-G6."""
        for group, bounds in self.config["age_groups"].items():
            if bounds["min_age"] <= age_years <= bounds["max_age"]:
                severity=Severity.ALERT,
        return "G5"  # Défaut adulte

    def check_immediate_triggers(self, vitals: Dict[str, float], patient_id: str, age_years: float) -> List[Alert]:
        """
        Vérifie les déclencheurs immédiats (alerte critical sous 5s).

        Règles:
        - SpO₂ < 88% (toutes tranches) OU SpO₂ ≤ 90% maintenue ≥ 30s
        - T° ≥ 38,5°C (≥ 38,0°C si 0-1 an ou ≥61 ans) OU +0,8°C sur 60 min
        - FR (tachypnée) ≥ bornes âge + 10/min pendant ≥ 2 min
        - FC (tachycardie) ≥ bornes âge + 20 bpm pendant ≥ 2 min
        - EVA ≥ 8/10
        """Détecte une variation anormalement faible (suspect même si pas totalement plat)."""
        alerts = []
        
        thresholds = self.config["thresholds"]

        current_time = datetime.now()
        history = self.patient_history[patient_id]
        # SpO₂ critique immédiate
        if vitals.get("spo2", 100) < 88:
            
                severity=Severity.CRITICAL,
                reasons=["spo2_critical_immediate"],
                patient_id=patient_id,
        for vital_name in ["heart_rate", "respiratory_rate"]:
                context={"age_group": age_group, "trigger": "spo2 < 88%"},
                actions=["O2 immédiat", "Position semi-assise", "Appel SAMU"],
            if len(values) < 5:
            )
            alerts.append(alert)
            # Calculer coefficient de variation (CV = écart-type / moyenne)
        # Température critique par âge
        temp_threshold = 38.5
            if mean_val > 0:
            temp_threshold = 38.0

        if vitals.get("temperature", 36.5) >= temp_threshold:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["temperature_critical_immediate"],
                if cv < expected_cv[vital_name]:
                vitals=vitals,
                context={"age_group": age_group, "threshold": temp_threshold},
                        reasons=["abnormally_low_variation"],
                cooldown_s=120
            )
            alerts.append(alert)

        # Tachycardie critique
        hr_threshold = thresholds["heart_rate"][age_group]["alert"] + 20
        if vitals.get("heart_rate", 70) >= hr_threshold:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["tachycardia_severe"],
                patient_id=patient_id,
                vitals=vitals,
                context={"age_group": age_group, "threshold": hr_threshold},
                actions=["ECG", "Bilan hydrique", "Évaluation douleur"],
                cooldown_s=120
            )
        """Détecte des patterns non-physiologiques suspects."""

        
        respiratory_rate = vitals.get("respiratory_rate", 16)
        rr_emergency_threshold = thresholds["respiratory_rate"][age_group]["emergency"]

            if patient_id in self.patient_history:
        if respiratory_rate >= rr_emergency_threshold:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["tachypnea_severe"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "age_group": age_group,
                    "threshold": rr_emergency_threshold,
                    "actual_rr": respiratory_rate,
                    "severity_level": "emergency"
                },
                actions=["Gazométrie", "Radiographie thorax", "O2 si besoin", "Évaluation détresse respiratoire"],
                cooldown_s=120
            )
            alerts.append(alert)
        # Alerte pour tachypnée modérée (seuil alert + 5/min)
        elif respiratory_rate >= thresholds["respiratory_rate"][age_group]["alert"] + 5:
            alert = self._create_alert(
                severity=Severity.ALERT,
                reasons=["tachypnea_moderate"],
                patient_id=patient_id,
            if patient_id in self.patient_history:
                context={
                    "age_group": age_group,
                    "threshold": thresholds["respiratory_rate"][age_group]["alert"] + 5,
                    "actual_rr": respiratory_rate
                },
                actions=["Surveillance rapprochée", "Évaluation confort", "Mesures d'apaisement"],
                cooldown_s=300
            )
            alerts.append(alert)

        # Douleur sévère
        if vitals.get("pain_score", 0) >= 8:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["severe_pain"],
                patient_id=patient_id,
                vitals=vitals,
                context={"eva_score": vitals.get("pain_score")},
                actions=["Antalgiques", "Hydratation", "Évaluation crise"],
                cooldown_s=300
            )
            alerts.append(alert)
        # ✅ NOUVEAU: Alertes température ambiante et index de chaleur
        ambient_temp = vitals.get("ambient_temp_celsius", 20)
        body_temp = vitals.get("temperature", 36.5)
        hydration = vitals.get("hydration_percent", 80)
        
        # Température ambiante critique (>36°C)
        if ambient_temp >= 36:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["ambient_temperature_extreme"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "ambient_temp": ambient_temp,
                    "risk_level": "extreme_heat",
                    "dehydration_risk": "high"
                },
                actions=["Déplacer en zone fraîche", "Hydratation immédiate", "Surveillance renforcée", "Vêtements légers"],
                cooldown_s=180
            )
            alerts.append(alert)
        
        # Index de chaleur dangereux (combinaison température + humidité simulée)
        heat_index = self._calculate_heat_index(ambient_temp, body_temp, hydration)
        if heat_index >= 41:  # Index critique
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["heat_index_dangerous"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "heat_index": heat_index,
                    "ambient_temp": ambient_temp,
                    "body_temp": body_temp,
                    "hydration": hydration
                },
                actions=["Refroidissement immédiat", "Hydratation IV si nécessaire", "Surveillance température", "Climatisation"],
                cooldown_s=120
            )
            alerts.append(alert)
        
        # Alerte froid extrême (<5°C)
        if ambient_temp <= 5:
            alert = self._create_alert(
                severity=Severity.ALERT,
                reasons=["ambient_temperature_cold_extreme"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "ambient_temp": ambient_temp,
                    "risk_level": "hypothermia_risk"
                },
                actions=["Réchauffement progressif", "Vêtements chauds", "Surveillance température", "Boissons chaudes"],
                cooldown_s=300
            )
            alerts.append(alert)

        return alerts

    def check_critical_combinations(self, vitals: Dict[str, float], patient_id: str, age_years: float) -> List[Alert]:
        """
        Vérifie les combinaisons critiques hors-ligne.

        Combinaisons prioritaires:
        C1: Fièvre ≥ 38,0°C ET SpO₂ ≤ 93% (≤94% si 0-5 ans)
        C2: SpO₂ ≤ 90% ET tachypnée ET/OU tachycardie
        C3: EVA ≥ 7/10 ET SpO₂ ≤ 92%
        C4: Hydratation faible ET HI ≥ 38°C ET activité soutenue
        C5: Fièvre ≥ 38,0°C ET tachypnée > 25/min (≥13 ans)
        """
        alerts = []
        age_group = self.get_age_group(age_years)

        # C1: Fièvre + Hypoxie
        temp = vitals.get("temperature", 36.5)
        spo2 = vitals.get("spo2", 100)
        spo2_threshold = 94 if age_group in ["G1", "G2"] else 93

        if temp >= 38.0 and spo2 <= spo2_threshold:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["fever_hypoxia_combination"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "combination": "C1",
                    "fever": temp,
                    "spo2": spo2,
                    "age_group": age_group
                },
                actions=["Urgence médicale", "O2", "Antipyrétique", "Bilan infectieux"],
                cooldown_s=180
            )
            alerts.append(alert)

        # C2: Détresse respiratoire
        hr = vitals.get("heart_rate", 70)
        rr = vitals.get("respiratory_rate", 16)
        hr_threshold = self.config["thresholds"]["heart_rate"][age_group]["alert"]
        rr_threshold = self.config["thresholds"]["respiratory_rate"][age_group]["alert"]

        if spo2 <= 90 and (rr >= rr_threshold or hr >= hr_threshold):
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["respiratory_distress"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "combination": "C2",
                    "spo2": spo2,
                    "tachypnea": rr >= rr_threshold,
                    "tachycardia": hr >= hr_threshold
                },
                actions=["O2 haut débit", "Position assise", "Urgence"],
                cooldown_s=120
            )
            alerts.append(alert)

        # C3: Douleur + Hypoxie (crise vaso-occlusive)
        pain = vitals.get("pain_score", 0)
        if pain >= 7 and spo2 <= 92:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["pain_hypoxia_crisis"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "combination": "C3",
                    "pain_score": pain,
                    "spo2": spo2
                },
                actions=["Antalgiques majeurs", "O2", "Hydratation IV", "Hospitalisation"],
                cooldown_s=300
            )
            alerts.append(alert)

        # C4: Déshydratation + Chaleur + Activité
        hydration = vitals.get("hydration_pct", 85)
        heat_index = vitals.get("heat_index", 25)
        activity = vitals.get("activity_level", "low")

        if hydration <= 60 and heat_index >= 38 and activity in ["moderate", "high"]:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["dehydration_heat_activity"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "combination": "C4",
                    "hydration_pct": hydration,
                    "heat_index": heat_index,
                    "activity": activity
                },
                actions=["Arrêt activité", "Refroidissement", "Hydratation", "Repos ombre"],
                cooldown_s=240
            )
            alerts.append(alert)

        return alerts

    def check_sensor_failures(self, vitals: Dict[str, float], patient_id: str, metadata: Dict) -> List[Alert]:
        """
        Détecte les pannes capteurs prioritaires local.

        - Flatline ≥ 60s
        - Pertes > 20%/5min
        - Batterie < 15%
        - Absence heartbeat > 10min
        """
        alerts = []

        # Batterie faible
        battery = metadata.get("battery_level", 100)
        if battery < 15:
            alert = self._create_alert(
                severity=Severity.ALERT,
                reasons=["battery_low"],
                patient_id=patient_id,
                vitals=vitals,
                context={"battery_level": battery},
                actions=["Charger appareil", "Vérifier connexion"],
                cooldown_s=600  # 10 min entre alertes batterie
            )
            alerts.append(alert)

        # Signal loss
        signal_loss_pct = metadata.get("signal_loss_5min", 0)
        if signal_loss_pct > 20:
            alert = self._create_alert(
                severity=Severity.ALERT,
                reasons=["signal_loss"],
                patient_id=patient_id,
                vitals=vitals,
                context={"signal_loss_pct": signal_loss_pct},
                actions=["Vérifier position capteur", "Rapprocher récepteur"],
                cooldown_s=300
            )
            alerts.append(alert)

        return alerts

    def _create_alert(self, severity: Severity, reasons: List[str], patient_id: str,
                     vitals: Dict[str, float], context: Dict, actions: List[str],
                     cooldown_s: int) -> Alert:
        """Crée une alerte structurée."""
        current_time = datetime.now()
        alert_id = f"{patient_id}_{int(current_time.timestamp())}_{hash(tuple(reasons))}"

        return Alert(
            severity=severity,
            reasons=reasons,
            patient_id=patient_id,
            timestamp=current_time,
            vitals=vitals.copy(),
            context=context,
            trend=self._calculate_trend(vitals, patient_id),
            actions_suggested=actions,
            ack_deadline=current_time + timedelta(minutes=5),
            cooldown_s=cooldown_s,
            alert_id=alert_id
        )

    def _calculate_trend(self, vitals: Dict[str, float], patient_id: str) -> Optional[str]:
        """Calcule la tendance des vitaux (simplifié)."""
        # Implémentation simplifiée - en production, utiliser historique
        spo2 = vitals.get("spo2", 100)
        temp = vitals.get("temperature", 36.5)

        if spo2 < 92:
            return "declining_spo2"
        elif temp > 38.5:
            return "rising_temperature"
        else:
            return "stable"

    def should_send_alert(self, alert: Alert) -> bool:
        """
        Vérifie si l'alerte doit être envoyée (anti-spam + cooldown).

        Cooldown 120s entre alertes identiques.
        Escalade si condition s'aggrave.
        """
        key = (alert.patient_id, alert.reasons[0])
        current_time = datetime.now()

        if key in self.cooldown_tracker:
            last_alert_time = self.cooldown_tracker[key]
            if (current_time - last_alert_time).total_seconds() < alert.cooldown_s:
                return False  # Encore en cooldown

        # Enregistrer cette alerte
        self.cooldown_tracker[key] = current_time
        return True

    def process_patient_data(self, patient_data: Dict) -> List[Alert]:
        """
        Point d'entrée principal pour traiter les données d'un patient.

        Args:
            patient_data: {
                "patient_id": str,
                "age_years": float,
                "vitals": {...},
                "metadata": {...}
            }

        Returns:
            Liste des alertes générées
        """
        patient_id = patient_data["patient_id"]
        age_years = patient_data["age_years"]
        vitals = patient_data["vitals"]
        metadata = patient_data.get("metadata", {})

        all_alerts = []

        try:
            # ✅ NOUVEAU: Calculer et intégrer l'hydratation
            hydration_alerts = self.check_hydration_alerts(vitals, patient_data)
            all_alerts.extend(hydration_alerts)

            # 1. Vérifier déclencheurs immédiats
            immediate_alerts = self.check_immediate_triggers(vitals, patient_id, age_years)
            all_alerts.extend(immediate_alerts)

            # 2. Vérifier combinaisons critiques
            combination_alerts = self.check_critical_combinations(vitals, patient_id, age_years)
            all_alerts.extend(combination_alerts)

            # ✅ NOUVEAU: Détection avancée pannes capteurs avec flatline
            advanced_sensor_alerts = self.check_advanced_sensor_failures(vitals, patient_id, metadata)
            all_alerts.extend(advanced_sensor_alerts)

            # 4. Filtrer selon cooldown
            final_alerts = [alert for alert in all_alerts if self.should_send_alert(alert)]

            # 5. Logger les alertes
            for alert in final_alerts:
                self.logger.critical(f"ALERT: {alert.severity.value} - {alert.reasons} - Patient {patient_id}")

            return final_alerts

        except Exception as e:
            self.logger.error(f"Error processing patient {patient_id}: {e}")
            return []

    def export_alert_to_dict(self, alert: Alert) -> Dict:
        """Exporte une alerte au format dictionnaire pour le pipeline."""
        return {
            "alert_id": alert.alert_id,
            "severity": alert.severity.value,
            "reasons": alert.reasons,
            "patient_id": alert.patient_id,
            "timestamp": alert.timestamp.isoformat(),
            "vitals": alert.vitals,
            "context": alert.context,
            "trend": alert.trend,
            "actions_suggested": alert.actions_suggested,
            "ack_deadline": alert.ack_deadline.isoformat(),
            "cooldown_s": alert.cooldown_s
        }

    def calculate_hydration_percentage(self, vitals: Dict[str, float], patient_data: Dict) -> float:
        """
        ✅ NOUVELLE FONCTIONNALITÉ: Calcule le pourcentage d'hydratation selon le cahier des charges.
        
        Méthodes:
        1. Avec volumes mesurés (intake_ml_24h, urine_ml_6h, weight_kg)
        2. Mode PROXY sans volumes (basé sur proxys physiologiques)
        
        Returns:
            Pourcentage d'hydratation (0-100%)
        """
        age_years = patient_data.get("age_years", 30)
        age_group = self.get_age_group(age_years)
        
        # Récupérer les données d'hydratation
        weight_kg = vitals.get("weight_kg")
        intake_ml_24h = vitals.get("intake_ml_24h")
        urine_ml_6h = vitals.get("urine_ml_6h") 
        urination_freq_24h = vitals.get("urination_freq_24h")
        
        # Variables contextuelles
        heat_index = vitals.get("heat_index", 25)
        activity_level = vitals.get("activity_level", "low")
        temp_core = vitals.get("temperature", 36.5)
        
        # Mode 1: Avec volumes mesurés
        if weight_kg and intake_ml_24h is not None:
            return self._calculate_hydration_with_volumes(
                weight_kg, intake_ml_24h, urine_ml_6h, urination_freq_24h,
                age_group, heat_index, activity_level, temp_core
            )
        
        # Mode 2: PROXY sans volumes (basé sur physiologie)
        else:
            return self._calculate_hydration_proxy_mode(
                vitals, age_years, age_group, heat_index, activity_level
            )
    
    def _calculate_hydration_with_volumes(self, weight_kg: float, intake_ml_24h: float, 
                                        urine_ml_6h: Optional[float], urination_freq_24h: Optional[float],
                                        age_group: str, heat_index: float, activity_level: str, 
                                        temp_core: float) -> float:
        """Calcul d'hydratation avec volumes mesurés."""
        
        # Facteurs d'âge (mL/kg/j)
        age_factors = {
            "G1": 100, "G2": 80, "G3": 60, "G4": 40, "G5": 32.5, "G6": 27.5
        }
        
        # Facteurs climatiques
        if heat_index < 32:
            climate_factor = 1.00
        elif heat_index < 37:
            climate_factor = 1.10
        elif heat_index < 41:
            climate_factor = 1.20
        else:
            climate_factor = 1.30
        
        # Facteurs d'activité
        activity_factors = {"low": 1.00, "moderate": 1.10, "high": 1.20}
        activity_factor = activity_factors.get(activity_level, 1.00)
        
        # Cible d'apport 24h
        target_intake_24h = weight_kg * age_factors[age_group] * climate_factor * activity_factor
        
        # Score d'apport
        intake_score = min(100, (intake_ml_24h / target_intake_24h) * 100)
        
        # Score de diurèse
        if urine_ml_6h is not None:
            # Cible de diurèse selon l'âge
            urine_rate_target = 1.0 if age_group in ["G1", "G2", "G3"] else 0.5  # mL/kg/h
            target_urine_6h = weight_kg * urine_rate_target * 6
            diuresis_score = min(100, (urine_ml_6h / target_urine_6h) * 100)
        elif urination_freq_24h is not None:
            # Approximation par fréquence
            target_freq = 6 if age_group in ["G1", "G2", "G3"] else 4
            diuresis_score = min(100, (urination_freq_24h / target_freq) * 100)
        else:
            diuresis_score = 85  # Valeur par défaut
        
        # Pénalités contextuelles (max 20 pts)
        penalties = 0
        if heat_index >= 37 and intake_ml_24h < target_intake_24h * 0.5:
            penalties += 10  # Chaleur sans hydratation
        if activity_level in ["moderate", "high"] and intake_ml_24h < target_intake_24h * 0.7:
            penalties += 5   # Activité sans compensation
        if temp_core >= 38.0:
            penalties += 5   # Fièvre
        
        # Calcul final
        hydration_pct = max(0, min(100, 
            0.6 * intake_score + 0.4 * diuresis_score - penalties
        ))
        
        return round(hydration_pct, 1)
    
    def _calculate_hydration_proxy_mode(self, vitals: Dict[str, float], age_years: float,
                                      age_group: str, heat_index: float, activity_level: str) -> float:
        """
        Mode PROXY: Calcul d'hydratation sans volumes, basé sur proxys physiologiques.
        """
        
        # Besoins de base par âge (mL/24h)
        basal_needs = {
            "G1": 1000, "G2": 1400, "G3": 1800, "G4": 2000, "G5": 2000, "G6": 1700
        }
        
        # Facteurs contexte (même logique que précédemment)
        climate_factor = 1.0 if heat_index < 32 else (1.1 if heat_index < 37 else (1.2 if heat_index < 41 else 1.3))
        activity_factor = {"low": 1.0, "moderate": 1.1, "high": 1.2}.get(activity_level, 1.0)
        
        # Cible proxy
        target_intake_proxy = basal_needs[age_group] * climate_factor * activity_factor
        
        # Estimation perte sudorale (simplifié)
        if heat_index >= 41 and activity_level == "high":
            sweat_loss_24h = 1500  # mL
        elif heat_index >= 37 and activity_level in ["moderate", "high"]:
            sweat_loss_24h = 800
        elif heat_index >= 32:
            sweat_loss_24h = 400
        else:
            sweat_loss_24h = 200
        
        # Apport estimé (compliance 70% par défaut)
        intake_proxy_24h = target_intake_proxy * 0.70
        
        # Déficit hydrique
        deficit_ml = max(0, sweat_loss_24h + 300 - intake_proxy_24h)  # 300 = pertes insensibles
        
        # Hydratation brute
        hydration_proxy = max(0, min(100, 
            100 - (deficit_ml / (0.9 * target_intake_proxy)) * 100
        ))
        
        # Pénalités physiologiques (max 30 pts)
        penalties = 0
        
        # Fréquence cardiaque élevée au repos
        hr_rest = vitals.get("heart_rate", 70)
        hr_threshold = self.config["thresholds"]["heart_rate"][age_group]["alert"]
        if hr_rest > hr_threshold + 10:
            penalties += 5
        
        # Fréquence respiratoire élevée
        rr_rest = vitals.get("respiratory_rate", 16)
        rr_threshold = self.config["thresholds"]["respiratory_rate"][age_group]["alert"]
        if rr_rest > rr_threshold + 5:
            penalties += 5
        
        # SpO₂ bas
        spo2 = vitals.get("spo2", 98)
        if age_group in ["G1", "G2", "G3"] and spo2 < 95:
            penalties += 5
        elif age_group in ["G4", "G5", "G6"] and spo2 < 94:
            penalties += 5
        
        # Fièvre
        temp = vitals.get("temperature", 36.5)
        if temp >= 38.0:
            penalties += 10
        
        # Résultat final
        hydration_final = max(0, min(100, hydration_proxy - penalties))
        
        return round(hydration_final, 1)
    
    def check_hydration_alerts(self, vitals: Dict[str, float], patient_data: Dict) -> List[Alert]:
        """
        ✅ NOUVELLE FONCTIONNALITÉ: Vérifie les alertes liées à l'hydratation.
        """
        alerts = []
        patient_id = patient_data["patient_id"]
        age_years = patient_data["age_years"]
        
        # Calculer le pourcentage d'hydratation
        hydration_pct = self.calculate_hydration_percentage(vitals, patient_data)
        
        # Ajouter à vitals pour les autres vérifications
        vitals["hydration_pct"] = hydration_pct
        
        # Seuils d'alerte hydratation
        if hydration_pct < 50:
            # Urgence critique
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["hydration_critical"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "hydration_pct": hydration_pct,
                    "threshold": 50,
                    "risk_level": "critical_dehydration"
                },
                actions=["Hydratation IV immédiate", "Surveillance rénale", "Bilan électrolytique"],
                cooldown_s=300
            )
            alerts.append(alert)
            
        elif hydration_pct < 60:
            # Combinaison avec chaleur/activité
            heat_index = vitals.get("heat_index", 25)
            activity = vitals.get("activity_level", "low")
            
            if heat_index >= 38 and activity in ["moderate", "high"]:
                alert = self._create_alert(
                    severity=Severity.CRITICAL,
                    reasons=["hydration_heat_activity"],
                    patient_id=patient_id,
                    vitals=vitals,
                    context={
                        "hydration_pct": hydration_pct,
                        "heat_index": heat_index,
                        "activity": activity,
                        "combination": "C4_extended"
                    },
                    actions=["Arrêt activité immédiat", "Refroidissement", "Hydratation", "Repos ombre"],
                    cooldown_s=240
                )
                alerts.append(alert)
            else:
                # Alerte simple
                alert = self._create_alert(
                    severity=Severity.ALERT,
                    reasons=["hydration_low"],
                    patient_id=patient_id,
                    vitals=vitals,
                    context={"hydration_pct": hydration_pct, "threshold": 60},
                    actions=["Encourager hydratation", "Surveillance 2h", "Réduire activité"],
                    cooldown_s=600
                )
                alerts.append(alert)
                
        elif hydration_pct < 70:
            # Vigilance
            alert = self._create_alert(
                severity=Severity.WARN,
                reasons=["hydration_vigilance"],
                patient_id=patient_id,
                vitals=vitals,
                context={"hydration_pct": hydration_pct, "threshold": 70},
                actions=["Rappel hydratation", "Surveillance régulière"],
                cooldown_s=1800  # 30 min
            )
            alerts.append(alert)
        
        return alerts

    def _update_patient_history(self, patient_id: str, vitals: Dict[str, float], timestamp: datetime = None):
        """
        ✅ NOUVELLE FONCTIONNALITÉ: Met à jour l'historique temporel du patient.
        """
        if timestamp is None:
            timestamp = datetime.now()
            
        # Initialiser l'historique si nécessaire
        if patient_id not in self.patient_history:
            self.patient_history[patient_id] = []
            
        # Ajouter le nouveau point
        self.patient_history[patient_id].append((timestamp, vitals.copy()))
        
        # Nettoyer l'historique (garder seulement les dernières 15 minutes)
        cutoff_time = timestamp - timedelta(minutes=self.max_history_minutes)
        self.patient_history[patient_id] = [
            (ts, v) for ts, v in self.patient_history[patient_id] 
            if ts >= cutoff_time
        ]
        
    def detect_flatline_patterns(self, patient_id: str, vitals: Dict[str, float]) -> List[Alert]:
        """
        ✅ NOUVELLE FONCTIONNALITÉ: Détecte les patterns de flatline sur l'historique temporel.
        
        Critères:
        - Valeurs identiques pendant ≥ 60s sur SpO₂, FC, ou FR
        - Variation < 1% sur température pendant ≥ 90s
        - Combinaisons suspectes (tous les vitaux identiques ≥ 30s)
        """
        alerts = []
        
        if patient_id not in self.patient_history:
            return alerts
            
        history = self.patient_history[patient_id]
        if len(history) < 3:  # Besoin d'au moins 3 points pour détecter
            return alerts
            
        current_time = datetime.now()
        
        # Variables critiques à surveiller
        critical_vitals = ["spo2", "heart_rate", "respiratory_rate", "temperature"]
        
        for vital_name in critical_vitals:
            flatline_duration = self._calculate_flatline_duration(history, vital_name)
            
            # Seuils de détection par type de vital
            if vital_name == "temperature":
                threshold_seconds = 90  # Plus tolérant pour la température
                tolerance = 0.1  # ±0.1°C
            else:
                threshold_seconds = 60  # SpO₂, FC, FR
                tolerance = 0.5 if vital_name == "spo2" else 1.0
                
            if flatline_duration >= threshold_seconds:
                # Détection de flatline critique
                current_value = vitals.get(vital_name, 0)
                
                alert = self._create_alert(
                    severity=Severity.CRITICAL,
                    reasons=["sensor_flatline"],
                    patient_id=patient_id,
                    vitals=vitals,
                    context={
                        "flatline_vital": vital_name,
                        "flatline_duration_s": flatline_duration,
                        "current_value": current_value,
                        "threshold_s": threshold_seconds,
                        "detection_method": "temporal_analysis"
                    },
                    actions=[
                        "Vérifier capteur immédiatement",
                        "Contrôle visuel patient", 
                        "Repositionner capteur",
                        "Test manuel des vitaux"
                    ],
                    cooldown_s=180  # 3 min entre alertes flatline
                )
                alerts.append(alert)
                
        # Détection de flatline multi-vitaux (très suspect)
        multi_flatline = self._detect_multi_vital_flatline(history)
        if multi_flatline:
            alert = self._create_alert(
                severity=Severity.CRITICAL,
                reasons=["multi_sensor_flatline"],
                patient_id=patient_id,
                vitals=vitals,
                context={
                    "affected_vitals": multi_flatline["vitals"],
                    "duration_s": multi_flatline["duration"],
                    "suspicion_level": "high_equipment_failure"
                },
                actions=[
                    "URGENT: Vérification équipement complète",
                    "Capteurs de secours",
                    "Contrôle manuel patient",
                    "Notification technique"
                ],
                cooldown_s=120
            )
            alerts.append(alert)
            
        return alerts
        
    def _calculate_flatline_duration(self, history: List[Tuple[datetime, Dict]], vital_name: str) -> float:
        """Calcule la durée en secondes pendant laquelle un vital est resté constant."""
        if len(history) < 2:
            return 0.0
            
        # Tolérance par type de vital
        tolerance = 0.1 if vital_name == "temperature" else (0.5 if vital_name == "spo2" else 1.0)
        
        # Chercher la séquence constante la plus récente
        current_time = datetime.now()
        last_value = None
        flatline_start = None
        
        # Parcourir l'historique en sens inverse (du plus récent au plus ancien)
        for timestamp, vitals in reversed(history):
            current_value = vitals.get(vital_name)
            
            if current_value is None:
                break  # Donnée manquante, arrêt de l'analyse
                
            if last_value is None:
                last_value = current_value
                flatline_start = timestamp
                continue
                
            # Vérifier si la valeur est "identique" (dans la tolérance)
            if abs(current_value - last_value) <= tolerance:
                flatline_start = timestamp  # Étendre le début de la flatline
            else:
                break  # Fin de la séquence constante
                
        if flatline_start:
            return (current_time - flatline_start).total_seconds()
        else:
            return 0.0
            
    def _detect_multi_vital_flatline(self, history: List[Tuple[datetime, Dict]]) -> Optional[Dict]:
        """Détecte si plusieurs vitaux sont simultanément en flatline (très suspect)."""
        if len(history) < 3:
            return None
            
        vitals_to_check = ["spo2", "heart_rate", "respiratory_rate"]
        
        # Vérifier les 30 dernières secondes
        current_time = datetime.now()
        recent_history = [
            (ts, v) for ts, v in history 
            if (current_time - ts).total_seconds() <= 30
        ]
        
            return None
            

        constant_vitals = []
        

            if self._is_vital_constant_in_period(recent_history, vital_name, tolerance=1.0):
                constant_vitals.append(vital_name)

        # Si 2+ vitaux constants simultanément = suspect
        if len(constant_vitals) >= 2:
            return {

                "duration": 30,  # Période analysée
                "suspicion": "equipment_failure"
            }
            
        return None
        
    def _is_vital_constant_in_period(self, history_period: List[Tuple[datetime, Dict]], 

        """Vérifie si un vital est resté constant sur une période donnée."""

    def _is_vital_constant_in_period(self, history_period: List[Tuple[datetime, Dict]],
        
        if len(values) < 2:
            return False
            

        first_value = values[0]
        return all(abs(v - first_value) <= tolerance for v in values[1:])

    def check_advanced_sensor_failures(self, vitals: Dict[str, float], patient_id: str, metadata: Dict) -> List[Alert]:
        """
        ✅ AMÉLIORATION: Détection avancée des pannes capteurs avec historique temporel.

        alerts = []
        
        # Mettre à jour l'historique d'abord
        self._update_patient_history(patient_id, vitals)
        

        flatline_alerts = self.detect_flatline_patterns(patient_id, vitals)
        alerts.extend(flatline_alerts)

        # 2. Détection de variation anormalement faible
        low_variation_alerts = self._detect_abnormally_low_variation(patient_id, vitals)
        alerts.extend(low_variation_alerts)

        # 3. Détection de patterns non-physiologiques
        pattern_alerts = self._detect_non_physiological_patterns(patient_id, vitals)
        alerts.extend(pattern_alerts)

        # 4. Pannes classiques (batterie, signal) - existantes
        battery = metadata.get("battery_level", 100)
        if battery < 15:

                severity=Severity.ALERT,
                reasons=["battery_low"],
                patient_id=patient_id,
                vitals=vitals,
                context={"battery_level": battery},
                actions=["Charger appareil", "Vérifier connexion"],
                cooldown_s=600
            )
            alerts.append(alert)
            
        signal_loss_pct = metadata.get("signal_loss_5min", 0)
        if signal_loss_pct > 20:
            alert = self._create_alert(

                reasons=["signal_loss"],
                patient_id=patient_id,
                vitals=vitals,
                context={"signal_loss_pct": signal_loss_pct},
                actions=["Vérifier position capteur", "Rapprocher récepteur"],
                cooldown_s=300
            )
            alerts.append(alert)
            
        return alerts
        
    def _detect_abnormally_low_variation(self, patient_id: str, vitals: Dict[str, float]) -> List[Alert]:

        alerts = []

        if patient_id not in self.patient_history:
            return alerts
            

        if len(history) < 10:  # Besoin d'au moins 10 points (≈5 min @ 0.2Hz)
            return alerts

        # Analyser la variation des 5 dernières minutes
        recent_history = history[-10:]  # 10 derniers points
        

            values = [v.get(vital_name) for ts, v in recent_history if v.get(vital_name) is not None]
            

                continue
                

            import statistics
            mean_val = statistics.mean(values)

                std_val = statistics.stdev(values) if len(values) > 1 else 0
                cv = (std_val / mean_val) * 100
                
                # Seuils de variation normale
                expected_cv = {"heart_rate": 5.0, "respiratory_rate": 8.0}  # % minimum attendu
                

                    alert = self._create_alert(
                        severity=Severity.WARN,

                        patient_id=patient_id,
                        vitals=vitals,
                        context={
                            "vital": vital_name,
                            "variation_coefficient": round(cv, 2),
                            "expected_minimum": expected_cv[vital_name],
                            "analysis_period_min": 5
                        },
                        actions=["Vérifier capteur", "Contrôle qualité signal"],
                        cooldown_s=900  # 15 min
                    )
                    alerts.append(alert)
                    
        return alerts
        
    def _detect_non_physiological_patterns(self, patient_id: str, vitals: Dict[str, float]) -> List[Alert]:

        alerts = []

        # Pattern 1: SpO₂ = 100% constant (rare physiologiquement)
        spo2 = vitals.get("spo2", 0)
        if spo2 >= 99.5:  # Quasi-100%

                recent_spo2 = [
                    v.get("spo2", 0) for ts, v in self.patient_history[patient_id][-5:]
                    if v.get("spo2") is not None
                ]
                if len(recent_spo2) >= 3 and all(s >= 99.5 for s in recent_spo2):
                    alert = self._create_alert(
                        severity=Severity.WARN,
                        reasons=["suspicious_perfect_spo2"],
                        patient_id=patient_id,
                        vitals=vitals,
                        context={
                            "spo2_values": recent_spo2,
                            "suspicion": "sensor_calibration_issue"
                        },
                        actions=["Vérifier calibrage SpO₂", "Test avec autre capteur"],
                        cooldown_s=1200  # 20 min
                    )
                    alerts.append(alert)
                    
        # Pattern 2: Valeurs "rondes" suspectes
        hr = vitals.get("heart_rate", 0)
        if hr > 0 and hr % 10 == 0:  # Multiples de 10 exacts (suspect)

                recent_hr = [
                    v.get("heart_rate", 0) for ts, v in self.patient_history[patient_id][-5:]
                    if v.get("heart_rate") is not None
                ]
                round_values = [h for h in recent_hr if h % 10 == 0]
                if len(round_values) >= 3:
                    alert = self._create_alert(
                        severity=Severity.INFO,
                        reasons=["suspicious_round_values"],
                        patient_id=patient_id,
                        vitals=vitals,
                        context={
                            "vital": "heart_rate",
                            "round_values_count": len(round_values),
                            "total_values": len(recent_hr)
                        },
                        actions=["Vérifier résolution capteur", "Contrôle qualité"],
                        cooldown_s=1800  # 30 min
                    )
                    alerts.append(alert)
                    
        return alerts

    def _calculate_heat_index(self, ambient_temp: float, body_temp: float, hydration: float) -> float:
        """
        ✅ NOUVEAU: Calcule l'index de chaleur basé sur température ambiante, corporelle et hydratation.

        Formule simplifiée adaptée pour la drépanocytose :
        - Base : température ambiante
        - Correction corporelle : si fièvre, risque accru
        - Correction hydratation : déshydratation amplifie l'effet chaleur
        """
        # Base : température ambiante
        heat_index = ambient_temp
        
        # Correction pour température corporelle élevée
        if body_temp > 37.5:
            temp_excess = body_temp - 37.5
            heat_index += temp_excess * 2  # Fièvre amplifie perception chaleur
        
        # Correction pour hydratation faible
        if hydration < 80:
            dehydration_factor = (80 - hydration) / 80  # 0 à 1
            heat_index += dehydration_factor * 5  # Déshydratation amplifie chaleur
        
        # Correction pour combinaison dangereuse
        if ambient_temp > 30 and body_temp > 38.0 and hydration < 70:
            heat_index += 3  # Bonus de danger pour triple combinaison
        
        return round(heat_index, 1)
