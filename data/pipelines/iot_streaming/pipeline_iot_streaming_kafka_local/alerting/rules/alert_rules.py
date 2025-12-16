"""
Système de Règles d'Alertes Médicales
Gère les règles de seuils, tendances et corrélations
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class RuleType(Enum):
    THRESHOLD = "THRESHOLD"
    TREND = "TREND"
    CORRELATION = "CORRELATION"
    COMPOSITE = "COMPOSITE"

class RuleSeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class AlertRule:
    """Représente une règle d'alerte médicale"""
    rule_id: str
    rule_name: str
    rule_type: RuleType
    enabled: bool
    priority: int
    conditions: Dict
    actions: Dict
    medical_context: str
    created_at: datetime
    updated_at: datetime

class MedicalAlertRules:
    """Gestionnaire principal des règles d'alertes médicales"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.rules = self._initialize_default_rules()

        # Contextes médicaux par paramètre
        self.medical_contexts = self._load_medical_contexts()

    def _initialize_default_rules(self) -> Dict[str, AlertRule]:
        """Initialise les règles d'alerte par défaut"""
        rules = {}

        # === RÈGLES DE SEUILS CRITIQUES ===

        # Fréquence cardiaque critique
        rules['hr_critical_high'] = AlertRule(
            rule_id='hr_critical_high',
            rule_name='Tachycardie Critique',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=1,
            conditions={
                'parameter': 'freq_card',
                'operator': '>',
                'threshold': 140,
                'duration_minutes': 2
            },
            actions={
                'severity': 'CRITICAL',
                'notify_urgence': True,
                'auto_escalate': True
            },
            medical_context='Tachycardie sévère pouvant indiquer un stress cardiaque majeur',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['hr_critical_low'] = AlertRule(
            rule_id='hr_critical_low',
            rule_name='Bradycardie Critique',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=1,
            conditions={
                'parameter': 'freq_card',
                'operator': '<',
                'threshold': 40,
                'duration_minutes': 2
            },
            actions={
                'severity': 'CRITICAL',
                'notify_urgence': True,
                'auto_escalate': True
            },
            medical_context='Bradycardie sévère pouvant indiquer un trouble du rythme grave',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # SpO2 critique
        rules['spo2_critical'] = AlertRule(
            rule_id='spo2_critical',
            rule_name='Hypoxémie Critique',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=1,
            conditions={
                'parameter': 'spo2_pct',
                'operator': '<',
                'threshold': 85,
                'duration_minutes': 1
            },
            actions={
                'severity': 'CRITICAL',
                'notify_urgence': True,
                'auto_escalate': True
            },
            medical_context='Hypoxémie sévère nécessitant une oxygénothérapie immédiate',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # Température corporelle critique
        rules['temp_critical_high'] = AlertRule(
            rule_id='temp_critical_high',
            rule_name='Hyperthermie Critique',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=1,
            conditions={
                'parameter': 'temp_corp',
                'operator': '>',
                'threshold': 40.0,
                'duration_minutes': 3
            },
            actions={
                'severity': 'CRITICAL',
                'notify_urgence': True,
                'auto_escalate': True
            },
            medical_context='Hyperthermie dangereuse pouvant causer des dommages neurologiques',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['temp_critical_low'] = AlertRule(
            rule_id='temp_critical_low',
            rule_name='Hypothermie Critique',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=1,
            conditions={
                'parameter': 'temp_corp',
                'operator': '<',
                'threshold': 34.0,
                'duration_minutes': 3
            },
            actions={
                'severity': 'CRITICAL',
                'notify_urgence': True,
                'auto_escalate': True
            },
            medical_context='Hypothermie sévère pouvant compromettre les fonctions vitales',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # === RÈGLES DE SEUILS ÉLEVÉS ===

        rules['hr_high'] = AlertRule(
            rule_id='hr_high',
            rule_name='Tachycardie',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=2,
            conditions={
                'parameter': 'freq_card',
                'operator': '>',
                'threshold': 120,
                'duration_minutes': 5
            },
            actions={
                'severity': 'HIGH',
                'notify_medical': True
            },
            medical_context='Fréquence cardiaque élevée nécessitant une surveillance',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['spo2_low'] = AlertRule(
            rule_id='spo2_low',
            rule_name='Désaturation',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=2,
            conditions={
                'parameter': 'spo2_pct',
                'operator': '<',
                'threshold': 92,
                'duration_minutes': 3
            },
            actions={
                'severity': 'HIGH',
                'notify_medical': True
            },
            medical_context='Désaturation nécessitant une évaluation respiratoire',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['temp_fever'] = AlertRule(
            rule_id='temp_fever',
            rule_name='Fièvre',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=2,
            conditions={
                'parameter': 'temp_corp',
                'operator': '>',
                'threshold': 38.5,
                'duration_minutes': 10
            },
            actions={
                'severity': 'HIGH',
                'notify_medical': True
            },
            medical_context='Fièvre modérée nécessitant une surveillance',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # Température ambiante critique
        rules['temp_ambient_high'] = AlertRule(
            rule_id='temp_ambient_high',
            rule_name='Température Ambiante Élevée',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=3,
            conditions={
                'parameter': 'temp_ambiante',
                'operator': '>',
                'threshold': 32.0,
                'duration_minutes': 15
            },
            actions={
                'severity': 'MEDIUM',
                'notify_environment': True
            },
            medical_context='Température ambiante élevée pouvant affecter le confort patient',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['temp_ambient_low'] = AlertRule(
            rule_id='temp_ambient_low',
            rule_name='Température Ambiante Basse',
            rule_type=RuleType.THRESHOLD,
            enabled=True,
            priority=3,
            conditions={
                'parameter': 'temp_ambiante',
                'operator': '<',
                'threshold': 16.0,
                'duration_minutes': 15
            },
            actions={
                'severity': 'MEDIUM',
                'notify_environment': True
            },
            medical_context='Température ambiante basse pouvant affecter le confort patient',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # === RÈGLES DE TENDANCES ===

        rules['hr_trending_up'] = AlertRule(
            rule_id='hr_trending_up',
            rule_name='Augmentation Progressive FC',
            rule_type=RuleType.TREND,
            enabled=True,
            priority=3,
            conditions={
                'parameter': 'freq_card',
                'trend_type': 'increasing',
                'min_change': 20,
                'time_window_minutes': 30,
                'min_measurements': 5
            },
            actions={
                'severity': 'MEDIUM',
                'notify_trend': True
            },
            medical_context='Augmentation progressive de la fréquence cardiaque',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['spo2_trending_down'] = AlertRule(
            rule_id='spo2_trending_down',
            rule_name='Dégradation Progressive SpO2',
            rule_type=RuleType.TREND,
            enabled=True,
            priority=2,
            conditions={
                'parameter': 'spo2_pct',
                'trend_type': 'decreasing',
                'min_change': -5,
                'time_window_minutes': 20,
                'min_measurements': 4
            },
            actions={
                'severity': 'HIGH',
                'notify_trend': True
            },
            medical_context='Dégradation progressive de la saturation en oxygène',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        rules['temp_trending_up'] = AlertRule(
            rule_id='temp_trending_up',
            rule_name='Montée Progressive Température',
            rule_type=RuleType.TREND,
            enabled=True,
            priority=3,
            conditions={
                'parameter': 'temp_corp',
                'trend_type': 'increasing',
                'min_change': 1.5,
                'time_window_minutes': 60,
                'min_measurements': 6
            },
            actions={
                'severity': 'MEDIUM',
                'notify_trend': True
            },
            medical_context='Augmentation progressive de la température corporelle',
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        return rules

    def _load_medical_contexts(self) -> Dict:
        """Charge les contextes médicaux pour chaque paramètre"""
        return {
            'freq_card': {
                'normal': 'Fréquence cardiaque dans la normale (60-100 bpm)',
                'low': 'Bradycardie - Fréquence cardiaque ralentie',
                'high': 'Tachycardie - Fréquence cardiaque accélérée',
                'critical_low': 'Bradycardie sévère - Risque d\'arrêt cardiaque',
                'critical_high': 'Tachycardie critique - Risque d\'arythmie grave'
            },
            'spo2_pct': {
                'normal': 'Saturation en oxygène normale (95-100%)',
                'low': 'Désaturation légère - Surveillance requise',
                'critical': 'Hypoxémie sévère - Oxygénothérapie immédiate'
            },
            'temp_corp': {
                'normal': 'Température corporelle normale (36.1-37.2°C)',
                'fever': 'Fièvre - Réaction inflammatoire possible',
                'high_fever': 'Fièvre élevée - Risque de complications',
                'hypothermia': 'Hypothermie - Risque de dysfonctions organiques',
                'critical_high': 'Hyperthermie critique - Urgence médicale'
            },
            'temp_ambiante': {
                'normal': 'Température ambiante confortable (18-25°C)',
                'high': 'Température ambiante élevée - Stress thermique possible',
                'low': 'Température ambiante basse - Risque d\'hypothermie',
                'critical': 'Conditions environnementales extrêmes'
            },
            'freq_resp': {
                'normal': 'Fréquence respiratoire normale (12-20/min)',
                'low': 'Bradypnée - Respiration ralentie',
                'high': 'Tachypnée - Respiration accélérée',
                'critical': 'Détresse respiratoire - Intervention requise'
            },
            'pct_hydratation': {
                'normal': 'Niveau d\'hydratation normal (60-80%)',
                'low': 'Déshydratation légère',
                'critical': 'Déshydratation sévère - Réhydratation urgente'
            }
        }

    def get_rules_by_type(self, rule_type: RuleType) -> List[AlertRule]:
        """Retourne les règles filtrées par type"""
        return [rule for rule in self.rules.values() if rule.rule_type == rule_type]

    def get_rule_by_id(self, rule_id: str) -> Optional[AlertRule]:
        """Retourne une règle par son ID"""
        return self.rules.get(rule_id)

    def get_active_rules(self) -> List[AlertRule]:
        """Retourne toutes les règles actives"""
        return [rule for rule in self.rules.values() if rule.enabled]

    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Retourne une règle par son ID (alias pour get_rule_by_id)"""
        return self.get_rule_by_id(rule_id)

    def evaluate_threshold_rule(self, rule: AlertRule, value: float) -> Dict:
        """Évalue une règle de seuil"""
        conditions = rule.conditions
        threshold = conditions['threshold']
        operator = conditions['operator']
        parameter = conditions['parameter']

        triggered = False
        threshold_exceeded = None

        if operator == '>' and value > threshold:
            triggered = True
            threshold_exceeded = f"> {threshold}"
        elif operator == '<' and value < threshold:
            triggered = True
            threshold_exceeded = f"< {threshold}"
        elif operator == '>=' and value >= threshold:
            triggered = True
            threshold_exceeded = f">= {threshold}"
        elif operator == '<=' and value <= threshold:
            triggered = True
            threshold_exceeded = f"<= {threshold}"
        elif operator == '==' and value == threshold:
            triggered = True
            threshold_exceeded = f"= {threshold}"

        return {
            'triggered': triggered,
            'parameter': parameter,
            'value': value,
            'threshold_exceeded': threshold_exceeded,
            'severity': rule.actions.get('severity', 'MEDIUM'),
            'rule_name': rule.rule_name,
            'medical_context': rule.medical_context
        }

    def evaluate_composite_rule(self, rule: AlertRule, vitals: Dict) -> Dict:
        """Évalue une règle composée"""
        conditions = rule.conditions
        matched_conditions = 0
        total_conditions = len(conditions)

        for param, condition in conditions.items():
            if param in vitals:
                value = vitals[param]
                if 'min' in condition and value >= condition['min']:
                    matched_conditions += 1
                elif 'max' in condition and value <= condition['max']:
                    matched_conditions += 1

        match_score = (matched_conditions / total_conditions) * 100
        triggered = match_score >= 80  # 80% des conditions remplies

        return {
            'triggered': triggered,
            'match_score': match_score,
            'matched_conditions': matched_conditions,
            'total_conditions': total_conditions,
            'rule_name': rule.rule_name
        }

    def get_medical_context(self, parameter: str, value: float) -> str:
        """Retourne le contexte médical approprié pour un paramètre et sa valeur"""
        contexts = self.medical_contexts.get(parameter, {})

        if parameter == 'freq_card':
            if value < 40:
                return contexts.get('critical_low', 'Valeur critique')
            elif value < 60:
                return contexts.get('low', 'Valeur basse')
            elif value <= 100:
                return contexts.get('normal', 'Valeur normale')
            elif value <= 140:
                return contexts.get('high', 'Valeur élevée')
            else:
                return contexts.get('critical_high', 'Valeur critique')

        elif parameter == 'spo2_pct':
            if value < 85:
                return contexts.get('critical', 'Valeur critique')
            elif value < 95:
                return contexts.get('low', 'Valeur basse')
            else:
                return contexts.get('normal', 'Valeur normale')

        elif parameter == 'temp_corp':
            if value < 34:
                return contexts.get('critical_high', 'Hypothermie critique')
            elif value < 36.1:
                return contexts.get('hypothermia', 'Hypothermie')
            elif value <= 37.2:
                return contexts.get('normal', 'Valeur normale')
            elif value <= 38.5:
                return contexts.get('fever', 'Fièvre légère')
            elif value <= 40:
                return contexts.get('high_fever', 'Fièvre élevée')
            else:
                return contexts.get('critical_high', 'Hyperthermie critique')

        elif parameter == 'temp_ambiante':
            if value < 15 or value > 32:
                return contexts.get('critical', 'Conditions extrêmes')
            elif value < 18 or value > 25:
                return contexts.get('high' if value > 25 else 'low', 'Conditions défavorables')
            else:
                return contexts.get('normal', 'Conditions normales')

        elif parameter == 'freq_resp':
            if value < 8 or value > 30:
                return contexts.get('critical', 'Valeur critique')
            elif value < 12 or value > 20:
                return contexts.get('high' if value > 20 else 'low', 'Valeur anormale')
            else:
                return contexts.get('normal', 'Valeur normale')

        elif parameter == 'pct_hydratation':
            if value < 45:
                return contexts.get('critical', 'Déshydratation sévère')
            elif value < 60:
                return contexts.get('low', 'Déshydratation légère')
            else:
                return contexts.get('normal', 'Hydratation normale')

        return f"Contexte médical pour {parameter}: {value}"

    def add_custom_rule(self, rule: AlertRule) -> bool:
        """Ajoute une règle personnalisée"""
        try:
            if rule.rule_id in self.rules:
                self.logger.warning(f"Règle {rule.rule_id} existe déjà, mise à jour")

            self.rules[rule.rule_id] = rule
            self.logger.info(f"Règle ajoutée/mise à jour: {rule.rule_id}")
            return True

        except Exception as e:
            self.logger.error(f"Erreur lors de l'ajout de la règle: {e}")
            return False

    def disable_rule(self, rule_id: str) -> bool:
        """Désactive une règle"""
        rule = self.rules.get(rule_id)
        if rule:
            rule.enabled = False
            rule.updated_at = datetime.now()
            self.logger.info(f"Règle désactivée: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Active une règle"""
        rule = self.rules.get(rule_id)
        if rule:
            rule.enabled = True
            rule.updated_at = datetime.now()
            self.logger.info(f"Règle activée: {rule_id}")
            return True
        return False

    def get_rules_summary(self) -> Dict:
        """Retourne un résumé des règles configurées"""
        summary = {
            'total_rules': len(self.rules),
            'enabled_rules': len([r for r in self.rules.values() if r.enabled]),
            'disabled_rules': len([r for r in self.rules.values() if not r.enabled]),
            'by_type': {},
            'by_severity': {}
        }

        for rule in self.rules.values():
            # Compter par type
            rule_type = rule.rule_type.value
            if rule_type not in summary['by_type']:
                summary['by_type'][rule_type] = 0
            summary['by_type'][rule_type] += 1

            # Compter par sévérité
            severity = rule.actions.get('severity', 'UNKNOWN')
            if severity not in summary['by_severity']:
                summary['by_severity'][severity] = 0
            summary['by_severity'][severity] += 1

        return summary

    def export_rules_config(self) -> Dict:
        """Exporte la configuration des règles"""
        config = {}
        for rule_id, rule in self.rules.items():
            config[rule_id] = {
                'rule_name': rule.rule_name,
                'rule_type': rule.rule_type.value,
                'enabled': rule.enabled,
                'priority': rule.priority,
                'conditions': rule.conditions,
                'actions': rule.actions,
                'medical_context': rule.medical_context,
                'created_at': rule.created_at.isoformat(),
                'updated_at': rule.updated_at.isoformat()
            }
        return config

    def import_rules_config(self, config: Dict) -> int:
        """Importe une configuration de règles"""
        imported_count = 0

        for rule_id, rule_data in config.items():
            try:
                rule = AlertRule(
                    rule_id=rule_id,
                    rule_name=rule_data['rule_name'],
                    rule_type=RuleType(rule_data['rule_type']),
                    enabled=rule_data['enabled'],
                    priority=rule_data['priority'],
                    conditions=rule_data['conditions'],
                    actions=rule_data['actions'],
                    medical_context=rule_data['medical_context'],
                    created_at=datetime.fromisoformat(rule_data['created_at']),
                    updated_at=datetime.fromisoformat(rule_data['updated_at'])
                )

                if self.add_custom_rule(rule):
                    imported_count += 1

            except Exception as e:
                self.logger.error(f"Erreur lors de l'import de la règle {rule_id}: {e}")

        self.logger.info(f"{imported_count} règles importées avec succès")
        return imported_count
