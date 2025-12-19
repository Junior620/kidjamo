"""
Fonction Lambda pour le traitement NLP médical avec Amazon Comprehend Medical
Chatbot Santé Kidjamo - MVP
"""

import json
import boto3
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients AWS
comprehend_medical = boto3.client('comprehendmedical')
sns = boto3.client('sns')

# Variables d'environnement
MEDICAL_ALERTS_TOPIC = os.environ['MEDICAL_ALERTS_TOPIC']

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Point d'entrée pour l'analyse NLP médicale
    """
    try:
        logger.info(f"Événement NLP reçu: {json.dumps(event, ensure_ascii=False)}")

        text = event.get('text', '')
        user_id = event.get('user_id', 'anonymous')
        analysis_type = event.get('analysis_type', 'full')

        if not text:
            return {
                'success': False,
                'error': 'Texte manquant pour l\'analyse'
            }

        # Analyse complète du texte médical
        analysis_result = analyze_medical_text(text, analysis_type)

        # Évaluation des risques basée sur l'analyse
        risk_assessment = assess_medical_risk(analysis_result, user_id)

        # Envoi d'alertes si nécessaire
        if risk_assessment.get('alert_required', False):
            send_medical_alert(user_id, analysis_result, risk_assessment)

        return {
            'success': True,
            'analysis': analysis_result,
            'risk_assessment': risk_assessment,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler NLP: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def analyze_medical_text(text: str, analysis_type: str = 'full') -> Dict[str, Any]:
    """
    Analyse complète du texte médical avec Comprehend Medical
    """
    try:
        result = {
            'entities': {},
            'icd10_codes': [],
            'rxnorm_codes': [],
            'phi_detected': [],
            'confidence_scores': {}
        }

        # Détection des entités médicales
        if analysis_type in ['full', 'entities']:
            entities_response = comprehend_medical.detect_entities_v2(Text=text)
            result['entities'] = process_medical_entities(entities_response)
            result['confidence_scores']['entities'] = calculate_average_confidence(entities_response)

        # Inférence des codes ICD-10 (diagnostics)
        if analysis_type in ['full', 'icd10']:
            try:
                icd10_response = comprehend_medical.infer_icd10_cm(Text=text)
                result['icd10_codes'] = process_icd10_codes(icd10_response)
                result['confidence_scores']['icd10'] = calculate_average_confidence(icd10_response)
            except Exception as e:
                logger.warning(f"Erreur ICD-10: {str(e)}")

        # Inférence des codes RxNorm (médicaments)
        if analysis_type in ['full', 'rxnorm']:
            try:
                rxnorm_response = comprehend_medical.infer_rx_norm(Text=text)
                result['rxnorm_codes'] = process_rxnorm_codes(rxnorm_response)
                result['confidence_scores']['rxnorm'] = calculate_average_confidence(rxnorm_response)
            except Exception as e:
                logger.warning(f"Erreur RxNorm: {str(e)}")

        # Détection des informations personnelles de santé (PHI)
        if analysis_type in ['full', 'phi']:
            try:
                phi_response = comprehend_medical.detect_phi(Text=text)
                result['phi_detected'] = process_phi_detection(phi_response)
                result['confidence_scores']['phi'] = calculate_average_confidence(phi_response)
            except Exception as e:
                logger.warning(f"Erreur PHI: {str(e)}")

        return result

    except Exception as e:
        logger.error(f"Erreur analyse médicale: {str(e)}")
        return {}

def process_medical_entities(response: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Traite et organise les entités médicales détectées
    """
    entities = {
        'symptoms': [],
        'medical_conditions': [],
        'medications': [],
        'anatomy': [],
        'procedures': [],
        'protected_health_info': []
    }

    for entity in response.get('Entities', []):
        entity_info = {
            'text': entity.get('Text', ''),
            'category': entity.get('Category', ''),
            'type': entity.get('Type', ''),
            'score': entity.get('Score', 0),
            'begin_offset': entity.get('BeginOffset', 0),
            'end_offset': entity.get('EndOffset', 0)
        }

        # Traitement des attributs spécifiques
        attributes = []
        for attr in entity.get('Attributes', []):
            attributes.append({
                'type': attr.get('Type', ''),
                'text': attr.get('Text', ''),
                'score': attr.get('Score', 0),
                'relationship_type': attr.get('RelationshipType', '')
            })
        entity_info['attributes'] = attributes

        # Classification par catégorie
        category = entity.get('Category', '').lower()
        if category == 'medical_condition':
            entities['medical_conditions'].append(entity_info)
        elif category == 'medication':
            entities['medications'].append(entity_info)
        elif category == 'anatomy':
            entities['anatomy'].append(entity_info)
        elif category == 'test_treatment_procedure':
            entities['procedures'].append(entity_info)
        elif category == 'protected_health_information':
            entities['protected_health_info'].append(entity_info)
        else:
            # Catégorie générique pour les symptômes
            entities['symptoms'].append(entity_info)

    return entities

def process_icd10_codes(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Traite les codes ICD-10 inférés
    """
    icd10_codes = []

    for entity in response.get('Entities', []):
        for concept in entity.get('ICD10CMConcepts', []):
            icd10_codes.append({
                'code': concept.get('Code', ''),
                'description': concept.get('Description', ''),
                'score': concept.get('Score', 0),
                'entity_text': entity.get('Text', ''),
                'entity_category': entity.get('Category', ''),
                'entity_type': entity.get('Type', '')
            })

    # Tri par score de confiance décroissant
    icd10_codes.sort(key=lambda x: x['score'], reverse=True)

    return icd10_codes

def process_rxnorm_codes(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Traite les codes RxNorm inférés pour les médicaments
    """
    rxnorm_codes = []

    for entity in response.get('Entities', []):
        for concept in entity.get('RxNormConcepts', []):
            rxnorm_codes.append({
                'code': concept.get('Code', ''),
                'description': concept.get('Description', ''),
                'score': concept.get('Score', 0),
                'entity_text': entity.get('Text', ''),
                'entity_category': entity.get('Category', ''),
                'entity_type': entity.get('Type', '')
            })

    # Tri par score de confiance décroissant
    rxnorm_codes.sort(key=lambda x: x['score'], reverse=True)

    return rxnorm_codes

def process_phi_detection(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Traite la détection des informations personnelles de santé
    """
    phi_entities = []

    for entity in response.get('Entities', []):
        phi_entities.append({
            'text': entity.get('Text', ''),
            'category': entity.get('Category', ''),
            'type': entity.get('Type', ''),
            'score': entity.get('Score', 0),
            'begin_offset': entity.get('BeginOffset', 0),
            'end_offset': entity.get('EndOffset', 0)
        })

    return phi_entities

def calculate_average_confidence(response: Dict[str, Any]) -> float:
    """
    Calcule le score de confiance moyen
    """
    try:
        entities = response.get('Entities', [])
        if not entities:
            return 0.0

        total_score = sum(entity.get('Score', 0) for entity in entities)
        return total_score / len(entities)

    except Exception:
        return 0.0

def assess_medical_risk(analysis_result: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """
    Évalue les risques médicaux basés sur l'analyse NLP
    """
    try:
        risk_assessment = {
            'risk_level': 'LOW',
            'alert_required': False,
            'urgency_score': 0,
            'risk_factors': [],
            'recommendations': []
        }

        entities = analysis_result.get('entities', {})

        # Analyse des conditions médicales
        medical_conditions = entities.get('medical_conditions', [])
        high_risk_conditions = [
            'crise drépanocytaire', 'syndrome thoracique aigu', 'priapisme',
            'accident vasculaire', 'infarctus', 'embolie pulmonaire'
        ]

        for condition in medical_conditions:
            condition_text = condition.get('text', '').lower()
            for risk_condition in high_risk_conditions:
                if risk_condition in condition_text and condition.get('score', 0) > 0.7:
                    risk_assessment['risk_level'] = 'HIGH'
                    risk_assessment['alert_required'] = True
                    risk_assessment['urgency_score'] += 3
                    risk_assessment['risk_factors'].append(f"Condition à risque détectée: {condition_text}")

        # Analyse des symptômes
        symptoms = entities.get('symptoms', [])
        high_risk_symptoms = [
            'douleur thoracique', 'dyspnée', 'essoufflement', 'malaise',
            'palpitations', 'syncope', 'vertiges sévères'
        ]

        for symptom in symptoms:
            symptom_text = symptom.get('text', '').lower()
            for risk_symptom in high_risk_symptoms:
                if risk_symptom in symptom_text and symptom.get('score', 0) > 0.7:
                    risk_assessment['urgency_score'] += 2
                    risk_assessment['risk_factors'].append(f"Symptôme préoccupant: {symptom_text}")
                    if risk_assessment['risk_level'] == 'LOW':
                        risk_assessment['risk_level'] = 'MEDIUM'

        # Analyse des médicaments
        medications = entities.get('medications', [])
        for medication in medications:
            med_text = medication.get('text', '').lower()
            if any(opioid in med_text for opioid in ['morphine', 'oxycodone', 'tramadol']):
                risk_assessment['risk_factors'].append(f"Médication opioïde détectée: {med_text}")

        # Évaluation finale
        if risk_assessment['urgency_score'] >= 5:
            risk_assessment['risk_level'] = 'HIGH'
            risk_assessment['alert_required'] = True
        elif risk_assessment['urgency_score'] >= 3:
            risk_assessment['risk_level'] = 'MEDIUM'

        # Recommandations basées sur le niveau de risque
        if risk_assessment['risk_level'] == 'HIGH':
            risk_assessment['recommendations'] = [
                "Contactez immédiatement votre médecin",
                "Envisagez un appel au  (115) si urgence vitale",
                "Surveillez étroitement les symptômes"
            ]
        elif risk_assessment['risk_level'] == 'MEDIUM':
            risk_assessment['recommendations'] = [
                "Consultez votre médecin dans les 24h",
                "Surveillez l'évolution des symptômes",
                "Prenez votre traitement si prescrit"
            ]
        else:
            risk_assessment['recommendations'] = [
                "Surveillez l'évolution",
                "Contactez votre médecin si aggravation"
            ]

        return risk_assessment

    except Exception as e:
        logger.error(f"Erreur évaluation risque médical: {str(e)}")
        return {
            'risk_level': 'UNKNOWN',
            'alert_required': False,
            'urgency_score': 0,
            'risk_factors': [],
            'recommendations': []
        }

def send_medical_alert(user_id: str, analysis_result: Dict[str, Any], risk_assessment: Dict[str, Any]):
    """
    Envoie une alerte médicale basée sur l'analyse NLP
    """
    try:
        alert_data = {
            'type': 'NLP_MEDICAL_ALERT',
            'user_id': user_id,
            'risk_level': risk_assessment.get('risk_level'),
            'urgency_score': risk_assessment.get('urgency_score'),
            'risk_factors': risk_assessment.get('risk_factors', []),
            'detected_conditions': [
                condition.get('text') for condition in
                analysis_result.get('entities', {}).get('medical_conditions', [])
                if condition.get('score', 0) > 0.7
            ],
            'detected_symptoms': [
                symptom.get('text') for symptom in
                analysis_result.get('entities', {}).get('symptoms', [])
                if symptom.get('score', 0) > 0.7
            ],
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        sns.publish(
            TopicArn=MEDICAL_ALERTS_TOPIC,
            Message=json.dumps(alert_data, ensure_ascii=False),
            Subject=f"Alerte NLP Médicale - Patient {user_id} - {risk_assessment.get('risk_level')}"
        )

        logger.warning(f"Alerte médicale NLP envoyée pour {user_id}: {risk_assessment.get('risk_level')}")

    except Exception as e:
        logger.error(f"Erreur envoi alerte NLP: {str(e)}")

def extract_medical_insights(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait des insights médicaux structurés de l'analyse
    """
    try:
        insights = {
            'pain_assessment': extract_pain_details(analysis_result),
            'medication_mentioned': extract_medication_details(analysis_result),
            'symptom_severity': assess_symptom_severity(analysis_result),
            'anatomical_regions': extract_anatomical_regions(analysis_result)
        }

        return insights

    except Exception as e:
        logger.error(f"Erreur extraction insights: {str(e)}")
        return {}

def extract_pain_details(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrait les détails spécifiques à la douleur
    """
    pain_details = {
        'intensity': None,
        'location': [],
        'quality': [],
        'duration': None
    }

    entities = analysis_result.get('entities', {})

    # Recherche d'intensité dans les attributs
    for category in entities.values():
        for entity in category:
            for attr in entity.get('attributes', []):
                if attr.get('type') == 'STRENGTH':
                    pain_details['intensity'] = attr.get('text')
                elif attr.get('type') == 'DIRECTION':
                    pain_details['location'].append(attr.get('text'))

    return pain_details

def extract_medication_details(analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extrait les détails des médicaments mentionnés
    """
    medications = []

    med_entities = analysis_result.get('entities', {}).get('medications', [])
    rxnorm_codes = analysis_result.get('rxnorm_codes', [])

    for med in med_entities:
        med_detail = {
            'name': med.get('text'),
            'confidence': med.get('score'),
            'dosage': None,
            'frequency': None,
            'route': None
        }

        # Extraction des attributs
        for attr in med.get('attributes', []):
            attr_type = attr.get('type')
            if attr_type == 'DOSAGE':
                med_detail['dosage'] = attr.get('text')
            elif attr_type == 'FREQUENCY':
                med_detail['frequency'] = attr.get('text')
            elif attr_type == 'ROUTE_OR_MODE':
                med_detail['route'] = attr.get('text')

        medications.append(med_detail)

    return medications

def assess_symptom_severity(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Évalue la sévérité des symptômes détectés
    """
    severity_assessment = {
        'overall_severity': 'MILD',
        'symptom_count': 0,
        'high_severity_symptoms': [],
        'confidence_average': 0.0
    }

    symptoms = analysis_result.get('entities', {}).get('symptoms', [])
    severity_assessment['symptom_count'] = len(symptoms)

    if symptoms:
        confidence_sum = sum(s.get('score', 0) for s in symptoms)
        severity_assessment['confidence_average'] = confidence_sum / len(symptoms)

    # Identification des symptômes sévères
    severe_keywords = ['sévère', 'intense', 'aigu', 'grave', 'insupportable']
    for symptom in symptoms:
        symptom_text = symptom.get('text', '').lower()
        if any(keyword in symptom_text for keyword in severe_keywords):
            severity_assessment['high_severity_symptoms'].append(symptom_text)
            severity_assessment['overall_severity'] = 'SEVERE'

    return severity_assessment

def extract_anatomical_regions(analysis_result: Dict[str, Any]) -> List[str]:
    """
    Extrait les régions anatomiques mentionnées
    """
    anatomical_regions = []

    anatomy_entities = analysis_result.get('entities', {}).get('anatomy', [])

    for anatomy in anatomy_entities:
        if anatomy.get('score', 0) > 0.6:
            anatomical_regions.append(anatomy.get('text'))

    return list(set(anatomical_regions))  # Suppression des doublons
