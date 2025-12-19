"""
Fonction Lambda pour l'intégration avec le pipeline IoT
Chatbot Santé Kidjamo - MVP
"""

import json
import boto3
import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

# Configuration du logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients AWS
kinesis = boto3.client('kinesis')
dynamodb = boto3.resource('dynamodb')
secretsmanager = boto3.client('secretsmanager')

# Variables d'environnement
IOT_KINESIS_STREAM = os.environ['IOT_KINESIS_STREAM']
PATIENT_CONTEXT_TABLE = os.environ['PATIENT_CONTEXT_TABLE']
POSTGRES_SECRET_ARN = os.environ.get('POSTGRES_SECRET_ARN')

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Point d'entrée pour l'intégration IoT
    """
    try:
        logger.info(f"Événement IoT reçu: {json.dumps(event, ensure_ascii=False)}")

        action = event.get('action')
        user_id = event.get('user_id')

        if action == 'get_recent_vitals':
            return get_recent_vitals(user_id, event.get('timeframe', '24h'))
        elif action == 'get_device_status':
            return get_device_status(user_id)
        elif action == 'get_alert_context':
            return get_alert_context(user_id, event.get('alert_id'))
        elif action == 'correlate_symptoms_vitals':
            return correlate_symptoms_vitals(user_id, event.get('symptoms', []))
        else:
            return {
                'success': False,
                'error': f'Action non supportée: {action}'
            }

    except Exception as e:
        logger.error(f"Erreur dans lambda_handler IoT: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }

def get_recent_vitals(user_id: str, timeframe: str = '24h') -> Dict[str, Any]:
    """
    Récupère les données vitales récentes depuis Kinesis Data Streams
    """
    try:
        # Calcul de la fenêtre temporelle
        hours = int(timeframe.replace('h', ''))
        start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Description du stream Kinesis
        stream_response = kinesis.describe_stream(StreamName=IOT_KINESIS_STREAM)
        stream_description = stream_response['StreamDescription']

        # Récupération des données depuis tous les shards
        vitals_data = []
        for shard in stream_description['Shards']:
            shard_iterator_response = kinesis.get_shard_iterator(
                StreamName=IOT_KINESIS_STREAM,
                ShardId=shard['ShardId'],
                ShardIteratorType='AT_TIMESTAMP',
                Timestamp=start_time
            )

            shard_iterator = shard_iterator_response['ShardIterator']

            # Lecture des enregistrements
            while shard_iterator:
                records_response = kinesis.get_records(
                    ShardIterator=shard_iterator,
                    Limit=100
                )

                for record in records_response['Records']:
                    try:
                        data = json.loads(record['Data'])

                        # Filtrage par user_id
                        if data.get('patient_id') == user_id or data.get('device_id', '').startswith(user_id):
                            vitals_data.append({
                                'timestamp': data.get('timestamp'),
                                'heart_rate': data.get('hr'),
                                'spo2': data.get('spo2'),
                                'temperature': data.get('temp_c'),
                                'respiratory_rate': data.get('resp_rate'),
                                'battery_level': data.get('battery_pct'),
                                'device_id': data.get('device_id'),
                                'sequence': data.get('seq')
                            })
                    except json.JSONDecodeError:
                        continue

                shard_iterator = records_response.get('NextShardIterator')
                if not records_response['Records']:
                    break

        # Tri par timestamp et sélection des plus récentes
        vitals_data.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_vitals = vitals_data[:10] if vitals_data else []

        # Calcul des statistiques
        stats = calculate_vitals_statistics(vitals_data) if vitals_data else {}

        # Détection d'anomalies
        anomalies = detect_vitals_anomalies(vitals_data, user_id) if vitals_data else []

        return {
            'success': True,
            'data': {
                'recent_vitals': recent_vitals,
                'latest': recent_vitals[0] if recent_vitals else None,
                'statistics': stats,
                'anomalies': anomalies,
                'total_records': len(vitals_data),
                'timeframe': timeframe
            }
        }

    except Exception as e:
        logger.error(f"Erreur récupération vitales: {str(e)}")
        return {
            'success': False,
            'error': f"Impossible de récupérer les données vitales: {str(e)}"
        }

def get_device_status(user_id: str) -> Dict[str, Any]:
    """
    Récupère le statut du dispositif IoT du patient
    """
    try:
        # Récupération du contexte patient depuis DynamoDB
        table = dynamodb.Table(PATIENT_CONTEXT_TABLE)

        response = table.get_item(
            Key={'patient_id': user_id}
        )

        patient_context = response.get('Item', {})
        device_info = patient_context.get('device_info', {})

        # Récupération des dernières données vitales pour le statut
        recent_vitals_response = get_recent_vitals(user_id, '1h')

        last_communication = None
        device_status = 'UNKNOWN'
        battery_level = None

        if recent_vitals_response.get('success'):
            latest_vital = recent_vitals_response['data'].get('latest')
            if latest_vital:
                last_communication = latest_vital.get('timestamp')
                battery_level = latest_vital.get('battery_level')

                # Détermination du statut basé sur la dernière communication
                if last_communication:
                    last_time = datetime.fromisoformat(last_communication.replace('Z', '+00:00'))
                    time_diff = datetime.now(timezone.utc) - last_time

                    if time_diff.total_seconds() < 300:  # 5 minutes
                        device_status = 'ONLINE'
                    elif time_diff.total_seconds() < 3600:  # 1 heure
                        device_status = 'DELAYED'
                    else:
                        device_status = 'OFFLINE'

        return {
            'success': True,
            'data': {
                'device_id': device_info.get('device_id'),
                'status': device_status,
                'last_communication': last_communication,
                'battery_level': battery_level,
                'firmware_version': device_info.get('firmware_version'),
                'device_model': device_info.get('model', 'Bracelet Kidjamo'),
                'connection_quality': assess_connection_quality(recent_vitals_response.get('data', {}))
            }
        }

    except Exception as e:
        logger.error(f"Erreur statut dispositif: {str(e)}")
        return {
            'success': False,
            'error': f"Impossible de récupérer le statut du dispositif: {str(e)}"
        }

def get_alert_context(user_id: str, alert_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Récupère le contexte d'une alerte avec les données vitales associées
    """
    try:
        # Récupération des vitales récentes autour de l'alerte
        vitals_response = get_recent_vitals(user_id, '2h')

        if not vitals_response.get('success'):
            return vitals_response

        vitals_data = vitals_response['data']['recent_vitals']

        # Analyse du contexte de l'alerte
        alert_context = {
            'vitals_around_alert': vitals_data,
            'trends': analyze_vitals_trends(vitals_data),
            'risk_factors': identify_risk_factors(vitals_data, user_id),
            'recommendations': generate_alert_recommendations(vitals_data)
        }

        return {
            'success': True,
            'data': alert_context
        }

    except Exception as e:
        logger.error(f"Erreur contexte alerte: {str(e)}")
        return {
            'success': False,
            'error': f"Impossible de récupérer le contexte de l'alerte: {str(e)}"
        }

def correlate_symptoms_vitals(user_id: str, symptoms: List[str]) -> Dict[str, Any]:
    """
    Corrèle les symptômes signalés avec les données vitales récentes
    """
    try:
        # Récupération des vitales récentes
        vitals_response = get_recent_vitals(user_id, '6h')

        if not vitals_response.get('success'):
            return vitals_response

        vitals_data = vitals_response['data']['recent_vitals']

        # Analyse de corrélation
        correlations = []

        for symptom in symptoms:
            correlation = analyze_symptom_vital_correlation(symptom, vitals_data)
            if correlation:
                correlations.append(correlation)

        # Score de cohérence global
        coherence_score = calculate_coherence_score(symptoms, vitals_data)

        return {
            'success': True,
            'data': {
                'correlations': correlations,
                'coherence_score': coherence_score,
                'vitals_summary': summarize_vitals_for_symptoms(vitals_data),
                'recommendations': generate_correlation_recommendations(correlations, coherence_score)
            }
        }

    except Exception as e:
        logger.error(f"Erreur corrélation symptômes-vitales: {str(e)}")
        return {
            'success': False,
            'error': f"Impossible de correler les données: {str(e)}"
        }

def calculate_vitals_statistics(vitals_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calcule les statistiques des données vitales
    """
    if not vitals_data:
        return {}

    stats = {
        'heart_rate': calculate_metric_stats([v.get('heart_rate') for v in vitals_data if v.get('heart_rate')]),
        'spo2': calculate_metric_stats([v.get('spo2') for v in vitals_data if v.get('spo2')]),
        'temperature': calculate_metric_stats([v.get('temperature') for v in vitals_data if v.get('temperature')]),
        'respiratory_rate': calculate_metric_stats([v.get('respiratory_rate') for v in vitals_data if v.get('respiratory_rate')])
    }

    return stats

def calculate_metric_stats(values: List[float]) -> Dict[str, float]:
    """
    Calcule les statistiques pour une métrique donnée
    """
    if not values:
        return {}

    values = [v for v in values if v is not None]
    if not values:
        return {}

    return {
        'min': min(values),
        'max': max(values),
        'avg': sum(values) / len(values),
        'count': len(values),
        'latest': values[0] if values else None
    }

def detect_vitals_anomalies(vitals_data: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
    """
    Détecte les anomalies dans les données vitales
    """
    anomalies = []

    # Seuils de référence pour la drépanocytose (ajustables par patient)
    thresholds = get_patient_thresholds(user_id)

    for vital in vitals_data:
        vital_anomalies = []

        # Vérification fréquence cardiaque
        hr = vital.get('heart_rate')
        if hr:
            if hr > thresholds.get('hr_max', 120):
                vital_anomalies.append({
                    'type': 'HIGH_HEART_RATE',
                    'value': hr,
                    'threshold': thresholds.get('hr_max', 120),
                    'severity': 'HIGH' if hr > 140 else 'MEDIUM'
                })
            elif hr < thresholds.get('hr_min', 50):
                vital_anomalies.append({
                    'type': 'LOW_HEART_RATE',
                    'value': hr,
                    'threshold': thresholds.get('hr_min', 50),
                    'severity': 'MEDIUM'
                })

        # Vérification saturation O2
        spo2 = vital.get('spo2')
        if spo2 and spo2 < thresholds.get('spo2_min', 95):
            vital_anomalies.append({
                'type': 'LOW_OXYGEN_SATURATION',
                'value': spo2,
                'threshold': thresholds.get('spo2_min', 95),
                'severity': 'HIGH' if spo2 < 90 else 'MEDIUM'
            })

        # Vérification température
        temp = vital.get('temperature')
        if temp:
            if temp > thresholds.get('temp_max', 38.0):
                vital_anomalies.append({
                    'type': 'FEVER',
                    'value': temp,
                    'threshold': thresholds.get('temp_max', 38.0),
                    'severity': 'HIGH' if temp > 39.0 else 'MEDIUM'
                })

        if vital_anomalies:
            anomalies.append({
                'timestamp': vital.get('timestamp'),
                'anomalies': vital_anomalies
            })

    return anomalies

def get_patient_thresholds(user_id: str) -> Dict[str, float]:
    """
    Récupère les seuils personnalisés du patient
    """
    try:
        table = dynamodb.Table(PATIENT_CONTEXT_TABLE)
        response = table.get_item(Key={'patient_id': user_id})

        patient_context = response.get('Item', {})
        custom_thresholds = patient_context.get('thresholds', {})

        # Seuils par défaut avec personnalisation possible
        default_thresholds = {
            'hr_min': 50,
            'hr_max': 120,
            'spo2_min': 95,
            'temp_max': 38.0,
            'resp_rate_min': 12,
            'resp_rate_max': 25
        }

        default_thresholds.update(custom_thresholds)
        return default_thresholds

    except Exception as e:
        logger.error(f"Erreur récupération seuils: {str(e)}")
        return {
            'hr_min': 50,
            'hr_max': 120,
            'spo2_min': 95,
            'temp_max': 38.0
        }

def assess_connection_quality(vitals_summary: Dict[str, Any]) -> str:
    """
    Évalue la qualité de la connexion du dispositif
    """
    total_records = vitals_summary.get('total_records', 0)
    timeframe = vitals_summary.get('timeframe', '24h')

    # Calcul du taux de réception attendu
    hours = int(timeframe.replace('h', ''))
    expected_records = hours * 12  # Supposons 1 mesure toutes les 5 minutes

    if total_records == 0:
        return 'POOR'
    elif total_records >= expected_records * 0.8:
        return 'EXCELLENT'
    elif total_records >= expected_records * 0.6:
        return 'GOOD'
    elif total_records >= expected_records * 0.3:
        return 'FAIR'
    else:
        return 'POOR'

def analyze_vitals_trends(vitals_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyse les tendances dans les données vitales
    """
    if len(vitals_data) < 3:
        return {'insufficient_data': True}

    trends = {}

    # Analyse de la fréquence cardiaque
    hr_values = [v.get('heart_rate') for v in vitals_data if v.get('heart_rate')]
    if len(hr_values) >= 3:
        trends['heart_rate'] = analyze_metric_trend(hr_values)

    # Analyse de la saturation O2
    spo2_values = [v.get('spo2') for v in vitals_data if v.get('spo2')]
    if len(spo2_values) >= 3:
        trends['spo2'] = analyze_metric_trend(spo2_values)

    # Analyse de la température
    temp_values = [v.get('temperature') for v in vitals_data if v.get('temperature')]
    if len(temp_values) >= 3:
        trends['temperature'] = analyze_metric_trend(temp_values)

    return trends

def analyze_metric_trend(values: List[float]) -> Dict[str, Any]:
    """
    Analyse la tendance d'une métrique spécifique
    """
    if len(values) < 3:
        return {'trend': 'INSUFFICIENT_DATA'}

    # Calcul de la pente moyenne
    slope_sum = 0
    for i in range(1, len(values)):
        slope_sum += values[i] - values[i-1]

    avg_slope = slope_sum / (len(values) - 1)

    # Détermination de la tendance
    if abs(avg_slope) < 0.5:
        trend = 'STABLE'
    elif avg_slope > 0:
        trend = 'INCREASING'
    else:
        trend = 'DECREASING'

    return {
        'trend': trend,
        'slope': avg_slope,
        'current': values[0],
        'previous': values[-1],
        'change': values[0] - values[-1]
    }

def identify_risk_factors(vitals_data: List[Dict[str, Any]], user_id: str) -> List[str]:
    """
    Identifie les facteurs de risque basés sur les vitales
    """
    risk_factors = []

    if not vitals_data:
        return ['Absence de données vitales récentes']

    # Analyse des moyennes récentes
    recent_vitals = vitals_data[:5]  # 5 dernières mesures

    avg_hr = sum(v.get('heart_rate', 0) for v in recent_vitals if v.get('heart_rate')) / len([v for v in recent_vitals if v.get('heart_rate')])
    avg_spo2 = sum(v.get('spo2', 0) for v in recent_vitals if v.get('spo2')) / len([v for v in recent_vitals if v.get('spo2')])

    if avg_hr > 110:
        risk_factors.append('Fréquence cardiaque élevée persistante')

    if avg_spo2 < 96:
        risk_factors.append('Saturation en oxygène diminuée')

    # Vérification de la variabilité
    hr_values = [v.get('heart_rate') for v in recent_vitals if v.get('heart_rate')]
    if hr_values and (max(hr_values) - min(hr_values)) > 30:
        risk_factors.append('Variabilité cardiaque importante')

    return risk_factors

def generate_alert_recommendations(vitals_data: List[Dict[str, Any]]) -> List[str]:
    """
    Génère des recommandations basées sur les vitales
    """
    recommendations = []

    if not vitals_data:
        return ['Vérifiez que votre bracelet est bien connecté']

    latest = vitals_data[0]

    if latest.get('heart_rate', 0) > 120:
        recommendations.append('Reposez-vous et hydratez-vous')
        recommendations.append('Surveillez votre fréquence cardiaque')

    if latest.get('spo2', 100) < 95:
        recommendations.append('Consultez rapidement votre médecin')
        recommendations.append('Évitez les efforts physiques')

    if latest.get('temperature', 36) > 38:
        recommendations.append('Prenez votre température régulièrement')
        recommendations.append('Contactez votre équipe soignante')

    battery_level = latest.get('battery_level', 100)
    if battery_level < 20:
        recommendations.append('Rechargez votre bracelet')

    return recommendations

def analyze_symptom_vital_correlation(symptom: str, vitals_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Analyse la corrélation entre un symptôme et les vitales
    """
    if not vitals_data:
        return None

    latest_vitals = vitals_data[0]
    correlation = {
        'symptom': symptom,
        'vitals_support': [],
        'confidence': 0.0
    }

    symptom_lower = symptom.lower()

    # Corrélations connues pour la drépanocytose
    if 'douleur' in symptom_lower or 'mal' in symptom_lower:
        hr = latest_vitals.get('heart_rate', 0)
        if hr > 100:
            correlation['vitals_support'].append(f'Tachycardie ({hr} bpm) cohérente avec la douleur')
            correlation['confidence'] += 0.3

    if 'essoufflement' in symptom_lower or 'dyspnée' in symptom_lower:
        spo2 = latest_vitals.get('spo2', 100)
        if spo2 < 96:
            correlation['vitals_support'].append(f'Saturation O₂ basse ({spo2}%) cohérente avec l\'essoufflement')
            correlation['confidence'] += 0.4

    if 'fièvre' in symptom_lower or 'température' in symptom_lower:
        temp = latest_vitals.get('temperature', 36)
        if temp > 37.5:
            correlation['vitals_support'].append(f'Température élevée ({temp}°C) confirme la fièvre')
            correlation['confidence'] += 0.5

    return correlation if correlation['confidence'] > 0 else None

def calculate_coherence_score(symptoms: List[str], vitals_data: List[Dict[str, Any]]) -> float:
    """
    Calcule un score de cohérence entre symptômes et vitales
    """
    if not symptoms or not vitals_data:
        return 0.0

    total_correlations = 0
    significant_correlations = 0

    for symptom in symptoms:
        correlation = analyze_symptom_vital_correlation(symptom, vitals_data)
        total_correlations += 1
        if correlation and correlation['confidence'] > 0.2:
            significant_correlations += 1

    return significant_correlations / total_correlations if total_correlations > 0 else 0.0

def summarize_vitals_for_symptoms(vitals_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Résumé des vitales pertinent pour l'analyse des symptômes
    """
    if not vitals_data:
        return {}

    latest = vitals_data[0]

    return {
        'current_hr': latest.get('heart_rate'),
        'current_spo2': latest.get('spo2'),
        'current_temp': latest.get('temperature'),
        'hr_trend': analyze_metric_trend([v.get('heart_rate') for v in vitals_data[:5] if v.get('heart_rate')]),
        'measurement_time': latest.get('timestamp')
    }

def generate_correlation_recommendations(correlations: List[Dict[str, Any]], coherence_score: float) -> List[str]:
    """
    Génère des recommandations basées sur les corrélations
    """
    recommendations = []

    if coherence_score > 0.7:
        recommendations.append('Vos symptômes sont cohérents avec vos données vitales')
        recommendations.append('Continuez à surveiller votre état')
    elif coherence_score > 0.3:
        recommendations.append('Certains symptômes correspondent à vos vitales')
        recommendations.append('Surveillez l\'évolution de votre état')
    else:
        recommendations.append('Vos symptômes ne sont pas directement reflétés dans vos vitales actuelles')
        recommendations.append('Contactez votre médecin pour une évaluation complète')

    # Recommandations spécifiques basées sur les corrélations
    for correlation in correlations:
        if correlation['confidence'] > 0.4:
            recommendations.append(f"Surveillance recommandée pour: {correlation['symptom']}")

    return recommendations
