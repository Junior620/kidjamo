"""
Lambda Function: Kidjamo Alert Processor Enhanced
Traite les données IoT en temps réel et génère des alertes médicales
Nouveaux capteurs: temp_object, heart_rate, spo2
"""

import json
import boto3
import base64
import logging
from datetime import datetime
from decimal import Decimal
import os
from typing import Dict, List, Any

# Configuration logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients AWS
s3_client = boto3.client('s3')
sns_client = boto3.client('sns')

# Configuration depuis variables d'environnement
S3_BUCKET = os.environ.get('S3_BUCKET', 'kidjamo-dev-datalake-e75d5213')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
DEVICE_ID = os.environ.get('DEVICE_ID', 'MPU_Christian_8266MOD')
ALERT_EMAIL = os.environ.get('ALERT_EMAIL', 'christianouragan@gmail.com')

# Seuils médicaux basés sur kidjamo_seuil.json
MEDICAL_THRESHOLDS = {
    "temperature": {
        "normal": [36.5, 37.5],
        "vigilance": [37.6, 37.9],
        "alert": 38.0,
        "emergency": 39.0,
        "hypothermia": 35.0
    },
    "heart_rate": {
        "normal": [60, 100],  # Adulte par défaut
        "vigilance": [101, 110],
        "alert": 111,
        "emergency": 130,
        "bradycardia": 50
    },
    "spo2": {
        "normal": 95,
        "vigilance": [93, 94],
        "alert": 92,
        "emergency": 90,
        "critical": 88
    },
    "acceleration": {
        "fall_threshold": 15.0,  # m/s² pour détection chute
        "hyperactivity_threshold": 12.0
    }
}

def lambda_handler(event, context):
    """Handler principal Lambda"""
    logger.info("🚀 Démarrage Kidjamo Alert Processor Enhanced")

    processed_records = 0
    generated_alerts = 0

    try:
        # Traitement des records Kinesis
        for record in event.get('Records', []):
            if record.get('eventSource') == 'aws:kinesis':
                processed_records += 1
                alerts = process_kinesis_record(record)
                generated_alerts += len(alerts)

                # Sauvegarder et envoyer les alertes
                for alert in alerts:
                    save_alert_to_s3(alert)
                    send_alert_notification(alert)

        logger.info(f"✅ Traité {processed_records} records, généré {generated_alerts} alertes")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Alertes traitées avec succès',
                'records_processed': processed_records,
                'alerts_generated': generated_alerts,
                'timestamp': datetime.utcnow().isoformat()
            })
        }

    except Exception as e:
        logger.error(f"❌ Erreur traitement: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })
        }

def process_kinesis_record(record) -> List[Dict]:
    """Traiter un record Kinesis et détecter les alertes"""
    alerts = []

    try:
        # Décoder les données Kinesis
        kinesis_data = record['kinesis']
        data_str = base64.b64decode(kinesis_data['data']).decode('utf-8')
        sensor_data = json.loads(data_str)

        logger.info(f"📊 Données capteur: {sensor_data.get('device_id', 'UNKNOWN')}")

        # Vérifier que c'est notre device
        if sensor_data.get('device_id') != DEVICE_ID:
            logger.info(f"⏭️ Device ignoré: {sensor_data.get('device_id')}")
            return alerts

        # Analyser chaque paramètre médical
        timestamp = datetime.utcnow()

        # 1. Température corporelle (temp_object)
        if 'temp_object' in sensor_data:
            temp_alerts = check_temperature_alerts(sensor_data['temp_object'], timestamp, sensor_data)
            alerts.extend(temp_alerts)

        # 2. Fréquence cardiaque
        if 'heart_rate' in sensor_data:
            hr_alerts = check_heart_rate_alerts(sensor_data['heart_rate'], timestamp, sensor_data)
            alerts.extend(hr_alerts)

        # 3. Oxygénation (SpO2)
        if 'spo2' in sensor_data:
            spo2_alerts = check_spo2_alerts(sensor_data['spo2'], timestamp, sensor_data)
            alerts.extend(spo2_alerts)

        # 4. Détection de chute (accéléromètre)
        if all(key in sensor_data for key in ['accel_x', 'accel_y', 'accel_z']):
            fall_alerts = check_fall_detection(sensor_data, timestamp)
            alerts.extend(fall_alerts)

        # 5. Activité excessive (gyroscope + accéléromètre)
        if all(key in sensor_data for key in ['gyro_x', 'gyro_y', 'gyro_z']):
            activity_alerts = check_activity_alerts(sensor_data, timestamp)
            alerts.extend(activity_alerts)

        logger.info(f"🚨 Alertes générées: {len(alerts)}")
        return alerts

    except Exception as e:
        logger.error(f"❌ Erreur traitement record: {str(e)}")
        return []

def check_temperature_alerts(temperature: float, timestamp: datetime, sensor_data: Dict) -> List[Dict]:
    """Analyser température corporelle et générer alertes"""
    alerts = []
    thresholds = MEDICAL_THRESHOLDS["temperature"]

    try:
        if temperature >= thresholds["emergency"]:
            # Urgence médicale - Fièvre très élevée
            alerts.append(create_alert(
                alert_type="MEDICAL_EMERGENCY",
                severity="CRITICAL",
                title="🚨 FIÈVRE CRITIQUE DÉTECTÉE",
                message=f"Température corporelle: {temperature}°C (≥{thresholds['emergency']}°C)\n"
                       f"RISQUE DE CRISE DRÉPANOCYTAIRE MAJEURE\n"
                       f"Action immédiate requise: Contactez le 1510 ou rendez-vous au CHU de Yaoundé",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="temperature",
                measured_value=temperature,
                threshold_exceeded=thresholds["emergency"]
            ))

        elif temperature >= thresholds["alert"]:
            # Alerte - Fièvre modérée
            alerts.append(create_alert(
                alert_type="MEDICAL_ALERT",
                severity="HIGH",
                title="⚠️ Fièvre Détectée",
                message=f"Température corporelle: {temperature}°C (≥{thresholds['alert']}°C)\n"
                       f"Risque de crise drépanocytaire\n"
                       f"Actions: Hydratation, repos, surveillance, contact médecin si aggravation",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="temperature",
                measured_value=temperature,
                threshold_exceeded=thresholds["alert"]
            ))

        elif temperature <= thresholds["hypothermia"]:
            # Hypothermie
            alerts.append(create_alert(
                alert_type="MEDICAL_ALERT",
                severity="HIGH",
                title="🥶 HYPOTHERMIE DÉTECTÉE",
                message=f"Température corporelle: {temperature}°C (≤{thresholds['hypothermia']}°C)\n"
                       f"Risque de complications vasculaires\n"
                       f"Actions: Réchauffement progressif, surveillance, contact médecin",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="temperature",
                measured_value=temperature,
                threshold_exceeded=thresholds["hypothermia"]
            ))

    except Exception as e:
        logger.error(f"❌ Erreur analyse température: {e}")

    return alerts

def check_heart_rate_alerts(heart_rate: int, timestamp: datetime, sensor_data: Dict) -> List[Dict]:
    """Analyser fréquence cardiaque et générer alertes"""
    alerts = []
    thresholds = MEDICAL_THRESHOLDS["heart_rate"]

    try:
        if heart_rate >= thresholds["emergency"]:
            # Tachycardie sévère
            alerts.append(create_alert(
                alert_type="MEDICAL_EMERGENCY",
                severity="CRITICAL",
                title="🚨 TACHYCARDIE SÉVÈRE",
                message=f"Fréquence cardiaque: {heart_rate} bpm (≥{thresholds['emergency']} bpm)\n"
                       f"RISQUE CARDIAQUE MAJEUR pour patient drépanocytaire\n"
                       f"Action immédiate: Repos complet, contact médecin urgent",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="heart_rate",
                measured_value=heart_rate,
                threshold_exceeded=thresholds["emergency"]
            ))

        elif heart_rate >= thresholds["alert"]:
            # Tachycardie modérée
            alerts.append(create_alert(
                alert_type="MEDICAL_ALERT",
                severity="HIGH",
                title="⚠️ Tachycardie Détectée",
                message=f"Fréquence cardiaque: {heart_rate} bpm (≥{thresholds['alert']} bpm)\n"
                       f"Risque de stress cardiaque\n"
                       f"Actions: Repos, hydratation, éviter efforts physiques",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="heart_rate",
                measured_value=heart_rate,
                threshold_exceeded=thresholds["alert"]
            ))

        elif heart_rate <= thresholds["bradycardia"]:
            # Bradycardie
            alerts.append(create_alert(
                alert_type="MEDICAL_ALERT",
                severity="MEDIUM",
                title="💓 BRADYCARDIE DÉTECTÉE",
                message=f"Fréquence cardiaque: {heart_rate} bpm (≤{thresholds['bradycardia']} bpm)\n"
                       f"Rythme cardiaque lent détecté\n"
                       f"Actions: Surveillance, contact médecin si symptômes",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="heart_rate",
                measured_value=heart_rate,
                threshold_exceeded=thresholds["bradycardia"]
            ))

    except Exception as e:
        logger.error(f"❌ Erreur analyse fréquence cardiaque: {e}")

    return alerts

def check_spo2_alerts(spo2: int, timestamp: datetime, sensor_data: Dict) -> List[Dict]:
    """Analyser oxygénation SpO2 et générer alertes"""
    alerts = []
    thresholds = MEDICAL_THRESHOLDS["spo2"]

    try:
        if spo2 <= thresholds["critical"]:
            # Hypoxie critique
            alerts.append(create_alert(
                alert_type="MEDICAL_EMERGENCY",
                severity="CRITICAL",
                title="🚨 HYPOXIE CRITIQUE",
                message=f"Oxygénation: {spo2}% (≤{thresholds['critical']}%)\n"
                       f"URGENCE RESPIRATOIRE - Patient drépanocytaire\n"
                       f"Action immédiate: Oxygène, position assise, urgences médicales",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="spo2",
                measured_value=spo2,
                threshold_exceeded=thresholds["critical"]
            ))

        elif spo2 <= thresholds["emergency"]:
            # Hypoxie sévère
            alerts.append(create_alert(
                alert_type="MEDICAL_EMERGENCY",
                severity="HIGH",
                title="🆘 HYPOXIE SÉVÈRE",
                message=f"Oxygénation: {spo2}% (≤{thresholds['emergency']}%)\n"
                       f"Risque de crise vaso-occlusive\n"
                       f"Actions: Position assise, respiration profonde, contact médecin urgent",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="spo2",
                measured_value=spo2,
                threshold_exceeded=thresholds["emergency"]
            ))

        elif spo2 <= thresholds["alert"]:
            # Hypoxie modérée
            alerts.append(create_alert(
                alert_type="MEDICAL_ALERT",
                severity="MEDIUM",
                title="⚠️ Hypoxie Détectée",
                message=f"Oxygénation: {spo2}% (≤{thresholds['alert']}%)\n"
                       f"Saturation en oxygène réduite\n"
                       f"Actions: Repos, respiration calme, surveillance",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="spo2",
                measured_value=spo2,
                threshold_exceeded=thresholds["alert"]
            ))

    except Exception as e:
        logger.error(f"❌ Erreur analyse SpO2: {e}")

    return alerts

def check_fall_detection(sensor_data: Dict, timestamp: datetime) -> List[Dict]:
    """Détecter les chutes via accéléromètre"""
    alerts = []

    try:
        # Calculer magnitude d'accélération totale
        accel_x = float(sensor_data.get('accel_x', 0))
        accel_y = float(sensor_data.get('accel_y', 0))
        accel_z = float(sensor_data.get('accel_z', 0))

        magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5
        threshold = MEDICAL_THRESHOLDS["acceleration"]["fall_threshold"]

        if magnitude > threshold:
            alerts.append(create_alert(
                alert_type="FALL_DETECTION",
                severity="HIGH",
                title="🚨 CHUTE DÉTECTÉE",
                message=f"Chute potentielle détectée (accélération: {magnitude:.2f} m/s²)\n"
                       f"Patient drépanocytaire à risque de traumatisme\n"
                       f"Vérifiez l'état du patient immédiatement",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="acceleration_magnitude",
                measured_value=magnitude,
                threshold_exceeded=threshold
            ))

    except Exception as e:
        logger.error(f"❌ Erreur détection chute: {e}")

    return alerts

def check_activity_alerts(sensor_data: Dict, timestamp: datetime) -> List[Dict]:
    """Détecter activité excessive"""
    alerts = []

    try:
        # Calculer activité gyroscopique
        gyro_x = float(sensor_data.get('gyro_x', 0))
        gyro_y = float(sensor_data.get('gyro_y', 0))
        gyro_z = float(sensor_data.get('gyro_z', 0))

        gyro_magnitude = (gyro_x**2 + gyro_y**2 + gyro_z**2)**0.5

        # Combiné avec accélération pour détecter hyperactivité
        accel_x = float(sensor_data.get('accel_x', 0))
        accel_y = float(sensor_data.get('accel_y', 0))
        accel_z = float(sensor_data.get('accel_z', 0))
        accel_magnitude = (accel_x**2 + accel_y**2 + accel_z**2)**0.5

        activity_threshold = MEDICAL_THRESHOLDS["acceleration"]["hyperactivity_threshold"]

        if accel_magnitude > activity_threshold and gyro_magnitude > 0.5:
            alerts.append(create_alert(
                alert_type="HYPERACTIVITY_ALERT",
                severity="MEDIUM",
                title="⚡ ACTIVITÉ EXCESSIVE",
                message=f"Activité physique intense détectée\n"
                       f"Patient drépanocytaire: risque de crise par surmenage\n"
                       f"Recommandation: Repos, hydratation, éviter efforts prolongés",
                timestamp=timestamp,
                sensor_data=sensor_data,
                medical_parameter="activity_level",
                measured_value=accel_magnitude,
                threshold_exceeded=activity_threshold
            ))

    except Exception as e:
        logger.error(f"❌ Erreur détection activité: {e}")

    return alerts

def create_alert(alert_type: str, severity: str, title: str, message: str,
                timestamp: datetime, sensor_data: Dict, medical_parameter: str,
                measured_value: float, threshold_exceeded: float) -> Dict:
    """Créer structure d'alerte standardisée"""

    return {
        "alert_id": f"kidjamo_{timestamp.strftime('%Y%m%d_%H%M%S')}_{alert_type.lower()}",
        "timestamp": timestamp.isoformat(),
        "device_id": sensor_data.get('device_id', DEVICE_ID),
        "alert_type": alert_type,
        "severity": severity,
        "title": title,
        "message": message,
        "medical_data": {
            "parameter": medical_parameter,
            "measured_value": measured_value,
            "threshold_exceeded": threshold_exceeded,
            "patient_context": "drépanocytose"
        },
        "sensor_snapshot": {
            "temp_object": sensor_data.get('temp_object'),
            "heart_rate": sensor_data.get('heart_rate'),
            "spo2": sensor_data.get('spo2'),
            "accel_magnitude": calculate_magnitude(sensor_data, 'accel') if 'accel_x' in sensor_data else None
        },
        "location": {
            "region": "Cameroun",
            "recommended_hospital": "CHU Yaoundé - Service Hématologie"
        },
        "urgency_contacts": {
            "emergency": "1510",
            "chu_yaounde": "+237 222 20 10 29"
        }
    }

def calculate_magnitude(sensor_data: Dict, prefix: str) -> float:
    """Calculer magnitude vectorielle"""
    try:
        x = float(sensor_data.get(f'{prefix}_x', 0))
        y = float(sensor_data.get(f'{prefix}_y', 0))
        z = float(sensor_data.get(f'{prefix}_z', 0))
        return (x**2 + y**2 + z**2)**0.5
    except:
        return 0.0

def save_alert_to_s3(alert: Dict):
    """Sauvegarder alerte dans S3 avec structure existante"""
    try:
        timestamp = datetime.fromisoformat(alert["timestamp"].replace('Z', '+00:00'))

        # Structure S3 EXISTANTE: alerts/mpu_christian/year=YYYY/month=MM/day=DD/hour=HH/
        s3_key = (f"alerts/mpu_christian/year={timestamp.year}/"
                 f"month={timestamp.month:02d}/"
                 f"day={timestamp.day:02d}/"
                 f"hour={timestamp.hour:02d}/"
                 f"{alert['alert_id']}.json")

        # Convertir Decimal pour JSON
        alert_json = json.dumps(alert, indent=2, default=str)

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=alert_json,
            ContentType='application/json',
            Metadata={
                'alert_type': alert['alert_type'],
                'severity': alert['severity'],
                'device_id': alert['device_id'],
                'medical_parameter': alert.get('medical_data', {}).get('parameter', 'unknown'),
                'kidjamo_version': '2.0'
            }
        )

        logger.info(f"💾 Alerte sauvegardée: s3://{S3_BUCKET}/{s3_key}")

    except Exception as e:
        logger.error(f"❌ Erreur sauvegarde S3: {e}")

def send_alert_notification(alert: Dict):
    """Envoyer notification par SES avec format HTML visuel (pas SNS)"""
    try:
        # Configuration couleurs UI médicales + accessibilité
        severity = alert['severity']
        title = alert['title']

        if severity == 'CRITICAL':
            email_subject = f"🚨 URGENCE MÉDICALE KIDJAMO - {title.replace('🚨 ', '').upper()}"
            primary_color = "#dc3545"  # Rouge médical
            bg_color = "#fff5f5"       # Fond rouge très clair
            icon = "🚨"
            urgency_text = "CRITIQUE"
            priority = "URGENCE MÉDICALE"
        elif severity == 'HIGH':
            email_subject = f"⚠️ ALERTE IMPORTANTE KIDJAMO - {title.replace('⚠️ ', '').upper()}"
            primary_color = "#fd7e14"  # Orange médical
            bg_color = "#fff8f0"       # Fond orange très clair
            icon = "⚠️"
            urgency_text = "ÉLEVÉE"
            priority = "ALERTE IMPORTANTE"
        else:
            email_subject = f"💡 SURVEILLANCE KIDJAMO - {title.replace('💡 ', '').upper()}"
            primary_color = "#17a2b8"  # Bleu info
            bg_color = "#f0f8ff"       # Fond bleu très clair
            icon = "💡"
            urgency_text = "MODÉRÉE"
            priority = "SURVEILLANCE"

        # Formatage de l'heure en français
        timestamp = datetime.fromisoformat(alert["timestamp"].replace('Z', '+00:00'))
        formatted_time = timestamp.strftime("%d/%m/%Y à %Hh%M")
        formatted_date = timestamp.strftime("%A %d %B %Y")

        # Extraction des données médicales
        sensor_data = alert.get('sensor_snapshot', {})

        # Fonction pour créer cards visuelles des constantes vitales
        def create_vital_card(param, value):
            if param == 'temp_object' and value is not None:
                if value <= 35.0:
                    return {
                        "icon": "🌡️", "label": "Température", "value": f"{value}°C",
                        "status": "Hypothermie", "color": "#dc3545", "bg": "#fff5f5",
                        "pattern": "🔴", "severity": "CRITIQUE", "normal_range": "36.5-37.5°C"
                    }
                elif value >= 39.0:
                    return {
                        "icon": "🌡️", "label": "Température", "value": f"{value}°C",
                        "status": "Fièvre Sévère", "color": "#dc3545", "bg": "#fff5f5",
                        "pattern": "🔴", "severity": "CRITIQUE", "normal_range": "36.5-37.5°C"
                    }
                elif value >= 38.0:
                    return {
                        "icon": "🌡️", "label": "Temp��rature", "value": f"{value}°C",
                        "status": "Fièvre", "color": "#fd7e14", "bg": "#fff8f0",
                        "pattern": "🟠", "severity": "ÉLEVÉE", "normal_range": "36.5-37.5°C"
                    }
                else:
                    return {
                        "icon": "🌡️", "label": "Température", "value": f"{value}°C",
                        "status": "Normale", "color": "#28a745", "bg": "#f0fff0",
                        "pattern": "🟢", "severity": "NORMALE", "normal_range": "36.5-37.5°C"
                    }
            elif param == 'heart_rate' and value is not None:
                if value >= 130:
                    return {
                        "icon": "❤️", "label": "Rythme Cardiaque", "value": f"{value} bpm",
                        "status": "Tachycardie", "color": "#dc3545", "bg": "#fff5f5",
                        "pattern": "🔴", "severity": "CRITIQUE", "normal_range": "60-100 bpm"
                    }
                elif value >= 111:
                    return {
                        "icon": "❤️", "label": "Rythme Cardiaque", "value": f"{value} bpm",
                        "status": "Accéléré", "color": "#fd7e14", "bg": "#fff8f0",
                        "pattern": "🟠", "severity": "ÉLEVÉE", "normal_range": "60-100 bpm"
                    }
                elif value <= 50:
                    return {
                        "icon": "❤️", "label": "Rythme Cardiaque", "value": f"{value} bpm",
                        "status": "Bradycardie", "color": "#dc3545", "bg": "#fff5f5",
                        "pattern": "🔴", "severity": "CRITIQUE", "normal_range": "60-100 bpm"
                    }
                else:
                    return {
                        "icon": "❤️", "label": "Rythme Cardiaque", "value": f"{value} bpm",
                        "status": "Normal", "color": "#28a745", "bg": "#f0fff0",
                        "pattern": "🟢", "severity": "NORMALE", "normal_range": "60-100 bpm"
                    }
            elif param == 'spo2' and value is not None:
                if value <= 88:
                    return {
                        "icon": "🫁", "label": "Oxygénation", "value": f"{value}%",
                        "status": "Hypoxie Sévère", "color": "#dc3545", "bg": "#fff5f5",
                        "pattern": "🔴", "severity": "CRITIQUE", "normal_range": ">95%"
                    }
                elif value <= 90:
                    return {
                        "icon": "🫁", "label": "Oxygénation", "value": f"{value}%",
                        "status": "Hypoxie", "color": "#fd7e14", "bg": "#fff8f0",
                        "pattern": "🟠", "severity": "ÉLEVÉE", "normal_range": ">95%"
                    }
                elif value <= 92:
                    return {
                        "icon": "🫁", "label": "Oxygénation", "value": f"{value}%",
                        "status": "Surveillance", "color": "#ffc107", "bg": "#fffbf0",
                        "pattern": "🟡", "severity": "MODÉRÉE", "normal_range": ">95%"
                    }
                else:
                    return {
                        "icon": "🫁", "label": "Oxygénation", "value": f"{value}%",
                        "status": "Normale", "color": "#28a745", "bg": "#f0fff0",
                        "pattern": "🟢", "severity": "NORMALE", "normal_range": ">95%"
                    }

            return {
                "icon": "❓", "label": "Inconnu", "value": "N/A",
                "status": "Non Disponible", "color": "#6c757d", "bg": "#f8f9fa",
                "pattern": "⚪", "severity": "INCONNUE", "normal_range": "N/A"
            }

        # Génération des cards de constantes vitales
        temp_card = create_vital_card('temp_object', sensor_data.get('temp_object'))
        hr_card = create_vital_card('heart_rate', sensor_data.get('heart_rate'))
        spo2_card = create_vital_card('spo2', sensor_data.get('spo2'))

        # Résumé d'urgence en une ligne (lecture 3 secondes)
        critical_values = []
        if temp_card['severity'] in ['CRITIQUE', 'ÉLEVÉE']:
            critical_values.append(f"Temp: {temp_card['pattern']} {temp_card['value']}")
        if hr_card['severity'] in ['CRITIQUE', 'ÉLEVÉE']:
            critical_values.append(f"FC: {hr_card['pattern']} {hr_card['value']}")
        if spo2_card['severity'] in ['CRITIQUE', 'ÉLEVÉE']:
            critical_values.append(f"SpO2: {spo2_card['pattern']} {spo2_card['value']}")

        quick_summary = " | ".join(critical_values) if critical_values else "Surveillance routine"

        # Template HTML responsive et accessible
        html_body = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alerte Médicale Kidjamo</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif; 
            margin: 0; padding: 15px; background-color: #f8f9fa; line-height: 1.4; 
        }}
        .container {{ 
            max-width: 600px; margin: 0 auto; background: white; 
            border-radius: 16px; overflow: hidden; 
            box-shadow: 0 8px 24px rgba(0,0,0,0.12); 
        }}
        .alert-header {{ 
            background: linear-gradient(135deg, {primary_color} 0%, {primary_color}dd 100%); 
            color: white; padding: 25px 20px; text-align: center; 
        }}
        .alert-header h1 {{ 
            margin: 0; font-size: 22px; font-weight: 700; 
            text-shadow: 0 2px 4px rgba(0,0,0,0.2); 
        }}
        .alert-header .time {{ 
            margin: 8px 0 0 0; opacity: 0.95; font-size: 14px; font-weight: 500; 
        }}
        .quick-summary {{ 
            background: {bg_color}; padding: 20px; 
            border-bottom: 3px solid {primary_color}; 
        }}
        .quick-summary h2 {{ 
            margin: 0 0 12px 0; color: {primary_color}; 
            font-size: 20px; font-weight: 600; 
        }}
        .priority-badge {{ 
            display: inline-block; background: {primary_color}; color: white; 
            padding: 6px 16px; border-radius: 25px; font-size: 13px; 
            font-weight: 700; text-transform: uppercase; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.15); 
        }}
        .summary-line {{ 
            margin: 12px 0 0 0; font-size: 16px; font-weight: 500; 
            color: #495057; 
        }}
        .vitals-dashboard {{ 
            padding: 25px 20px; background: #f8f9fa; 
        }}
        .vitals-title {{ 
            text-align: center; margin: 0 0 20px 0; 
            color: {primary_color}; font-size: 18px; font-weight: 600; 
        }}
        .vitals-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); 
            gap: 15px; 
        }}
        .vital-card {{ 
            background: white; border-radius: 12px; padding: 20px; 
            text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.08); 
            border: 2px solid var(--card-color); 
            transition: transform 0.2s ease; 
        }}
        .vital-icon {{ font-size: 28px; margin-bottom: 10px; }}
        .vital-label {{ 
            font-size: 11px; color: #6c757d; text-transform: uppercase; 
            font-weight: 700; margin-bottom: 8px; letter-spacing: 0.5px; 
        }}
        .vital-value {{ 
            font-size: 26px; font-weight: 800; color: var(--card-color); 
            margin-bottom: 8px; 
        }}
        .vital-status {{ 
            font-size: 11px; font-weight: 600; padding: 6px 12px; 
            border-radius: 20px; color: white; background: var(--card-color); 
            text-transform: uppercase; 
        }}
        .vital-range {{ 
            font-size: 10px; color: #6c757d; margin-top: 8px; 
            font-style: italic; 
        }}
        .medical-situation {{ padding: 25px 20px; }}
        .situation-box {{ 
            background: {bg_color}; padding: 20px; border-radius: 12px; 
            border-left: 6px solid {primary_color}; 
        }}
        .action-zone {{ padding: 20px; }}
        .action-critical {{ 
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%); 
            border: 2px solid #dc3545; border-radius: 12px; padding: 25px; 
            margin: 15px 0; 
        }}
        .action-high {{ 
            background: linear-gradient(135deg, #fff3cd 0%, #ffeaa7 100%); 
            border: 2px solid #fd7e14; border-radius: 12px; padding: 25px; 
            margin: 15px 0; 
        }}
        .action-medium {{ 
            background: linear-gradient(135deg, #d1ecf1 0%, #bee5eb 100%); 
            border: 2px solid #17a2b8; border-radius: 12px; padding: 25px; 
            margin: 15px 0; 
        }}
        .action-title {{ 
            font-size: 18px; font-weight: 700; margin: 0 0 20px 0; 
            text-align: center; 
        }}
        .action-list {{ 
            list-style: none; padding: 0; margin: 0; 
        }}
        .action-item {{ 
            background: white; margin: 12px 0; padding: 16px; 
            border-radius: 8px; border-left: 4px solid currentColor; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.06); 
        }}
        .action-item strong {{ display: block; margin-bottom: 6px; }}
        .action-item small {{ color: #6c757d; line-height: 1.3; }}
        .emergency-zone {{ 
            background: linear-gradient(135deg, #e9ecef 0%, #f8f9fa 100%); 
            padding: 30px 20px; margin: 20px 0; border-radius: 12px; 
            border: 1px solid #dee2e6; 
        }}
        .emergency-title {{ 
            text-align: center; margin: 0 0 20px 0; 
            color: {primary_color}; font-size: 20px; font-weight: 700; 
        }}
        .contact-grid {{ 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 15px; text-align: center; 
        }}
        .contact-button {{ 
            display: block; background: {primary_color}; color: white; 
            padding: 16px 24px; border-radius: 30px; text-decoration: none; 
            font-weight: 700; font-size: 16px; 
            box-shadow: 0 4px 16px rgba(0,0,0,0.15); 
            transition: all 0.3s ease; 
        }}
        .reassurance {{ 
            text-align: center; margin: 20px 0 0 0; 
            padding: 15px; background: #e8f5e8; border-radius: 8px; 
        }}
        .reassurance p {{ 
            margin: 0; font-size: 14px; color: #155724; 
            font-weight: 500; 
        }}
        .footer {{ 
            text-align: center; padding: 25px 20px; 
            background: #f8f9fa; border-top: 1px solid #dee2e6; 
        }}
        .footer .brand {{ 
            font-weight: 700; color: {primary_color}; font-size: 14px; 
        }}
        .footer .tech {{ 
            font-size: 12px; color: #6c757d; 
        }}
        @media (max-width: 600px) {{
            .vitals-grid {{ grid-template-columns: 1fr; }}
            .contact-grid {{ grid-template-columns: 1fr; }}
            .container {{ margin: 10px; border-radius: 12px; }}
            .alert-header {{ padding: 20px 15px; }}
            .vitals-dashboard {{ padding: 20px 15px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="alert-header">
            <h1>{icon} {priority}</h1>
            <div class="time">📅 {formatted_date} • ⏰ {formatted_time}</div>
        </div>
        
        <div class="quick-summary">
            <h2>{title.replace('🚨 ', '').replace('⚠️ ', '').replace('💡 ', '')}</h2>
            <span class="priority-badge">{urgency_text}</span>
            <div class="summary-line">
                <strong>Patient:</strong> {alert['device_id']} | <strong>Résumé:</strong> {quick_summary}
            </div>
        </div>
        
        <div class="vitals-dashboard">
            <h3 class="vitals-title">📊 Constantes Vitales</h3>
            <div class="vitals-grid">
                <div class="vital-card" style="--card-color: {temp_card['color']};">
                    <div class="vital-icon">{temp_card['icon']}</div>
                    <div class="vital-label">{temp_card['label']}</div>
                    <div class="vital-value">{temp_card['value']}</div>
                    <div class="vital-status">{temp_card['pattern']} {temp_card['status']}</div>
                    <div class="vital-range">Normal: {temp_card['normal_range']}</div>
                </div>
                
                <div class="vital-card" style="--card-color: {hr_card['color']};">
                    <div class="vital-icon">{hr_card['icon']}</div>
                    <div class="vital-label">{hr_card['label']}</div>
                    <div class="vital-value">{hr_card['value']}</div>
                    <div class="vital-status">{hr_card['pattern']} {hr_card['status']}</div>
                    <div class="vital-range">Normal: {hr_card['normal_range']}</div>
                </div>
                
                <div class="vital-card" style="--card-color: {spo2_card['color']};">
                    <div class="vital-icon">{spo2_card['icon']}</div>
                    <div class="vital-label">{spo2_card['label']}</div>
                    <div class="vital-value">{spo2_card['value']}</div>
                    <div class="vital-status">{spo2_card['pattern']} {spo2_card['status']}</div>
                    <div class="vital-range">Normal: {spo2_card['normal_range']}</div>
                </div>
            </div>
        </div>
        
        <div class="medical-situation">
            <h3 style="color: {primary_color}; margin: 0 0 15px 0; font-size: 18px;">🩺 Situation Médicale</h3>
            <div class="situation-box">
                <p style="margin: 0; font-size: 15px; line-height: 1.5;">{alert['message']}</p>
            </div>
        </div>"""

        # Actions immédiates avec cartouches colorées selon gravité
        if severity == 'CRITICAL':
            actions_html = f"""
        <div class="action-zone">
            <div class="action-critical">
                <div class="action-title" style="color: #721c24;">🆘 Actions Immédiates Critiques</div>
                <ul class="action-list">
                    <li class="action-item" style="border-left-color: #dc3545;">
                        <strong>🚑 Appeler les urgences immédiatement</strong>
                        <small>Composez le 1510 ou contactez directement le CHU de Yaoundé</small>
                    </li>
                    <li class="action-item" style="border-left-color: #dc3545;">
                        <strong>🏥 Préparer le transport médical</strong>
                        <small>Rassembler dossier médical, carnet de santé et médicaments</small>
                    </li>
                    <li class="action-item" style="border-left-color: #dc3545;">
                        <strong>📊 Surveiller en continu</strong>
                        <small>Noter l'évolution des symptômes et l'heure</small>
                    </li>
                </ul>
            </div>
        </div>"""
        elif severity == 'HIGH':
            actions_html = f"""
        <div class="action-zone">
            <div class="action-high">
                <div class="action-title" style="color: #856404;">⚠️ Actions Urgentes Recommandées</div>
                <ul class="action-list">
                    <li class="action-item" style="border-left-color: #fd7e14;">
                        <strong>📞 Contacter votre médecin traitant</strong>
                        <small>Consultation médicale recommandée dans les 2 heures</small>
                    </li>
                    <li class="action-item" style="border-left-color: #fd7e14;">
                        <strong>🩺 Appliquer les mesures correctives</strong>
                        <small>Repos, hydratation, surveillance des symptômes</small>
                    </li>
                    <li class="action-item" style="border-left-color: #fd7e14;">
                        <strong>📱 Suivre via Kidjamo</strong>
                        <small>Surveiller l'évolution des constantes vitales</small>
                    </li>
                </ul>
            </div>
        </div>"""
        else:
            actions_html = f"""
        <div class="action-zone">
            <div class="action-medium">
                <div class="action-title" style="color: #0c5460;">💡 Surveillance Recommandée</div>
                <ul class="action-list">
                    <li class="action-item" style="border-left-color: #17a2b8;">
                        <strong>📊 Surveillance continue</strong>
                        <small>Suivre l'évolution des paramètres vitaux</small>
                    </li>
                    <li class="action-item" style="border-left-color: #17a2b8;">
                        <strong>🩺 Mesures préventives</strong>
                        <small>Appliquer les bonnes pratiques de santé</small>
                    </li>
                </ul>
            </div>
        </div>"""

        # Zone contacts d'urgence avec boutons CTA optimisés
        contacts_html = f"""
        <div class="emergency-zone">
            <h3 class="emergency-title">📞 Contacts d'Urgence 24h/24</h3>
            <div class="contact-grid">
                <a href="tel:1510" class="contact-button">
                    🚨 Urgences Cameroun<br>
                    <span style="font-size: 18px; font-weight: 900;">1510</span>
                </a>
                <a href="tel:+237222201029" class="contact-button">
                    🏥 CHU Yaoundé<br>
                    <span style="font-size: 14px;">+237 222 20 10 29</span>
                </a>
            </div>
            
            <div class="reassurance">
                <p>💚 <strong>Kidjamo vous guide étape par étape</strong></p>
                <p>Vous n'êtes pas seul • Notre technologie veille sur votre santé</p>
            </div>
        </div>"""

        # Footer avec branding tech4good
        footer_html = f"""
        <div class="footer">
            <p class="brand">⏰ Système Kidjamo • Surveillance IoT Drépanocytose</p>
            <p class="tech">Startup4Good Cameroun • Technologie au service de la santé</p>
            <p style="margin-top: 15px; font-size: 11px; color: #6c757d;">
                Cette alerte a été générée automatiquement par votre bracelet IoT.<br>
                En cas de doute, consultez toujours un professionnel de santé.
            </p>
        </div>
    </div>
</body>
</html>"""

        # Assemblage HTML complet
        html_body += actions_html + contacts_html + footer_html

        # Version texte simple pour fallback
        text_body = f"""
{icon} ALERTE MÉDICALE KIDJAMO - {priority}

{title.replace('🚨 ', '').replace('⚠️ ', '').replace('💡 ', '')}
Gravité: {urgency_text} | {formatted_time}
Patient: {alert['device_id']}

RÉSUMÉ: {quick_summary}

CONSTANTES VITALES:
• {temp_card['icon']} Température: {temp_card['value']} ({temp_card['pattern']} {temp_card['status']})
• {hr_card['icon']} Fréquence cardiaque: {hr_card['value']} ({hr_card['pattern']} {hr_card['status']})
• {spo2_card['icon']} Oxygénation: {spo2_card['value']} ({spo2_card['pattern']} {spo2_card['status']})

SITUATION: {alert['message']}

CONTACTS D'URGENCE:
🚨 Urgences Cameroun: {alert['urgency_contacts']['emergency']}
🏥 CHU Yaoundé: {alert['urgency_contacts']['chu_yaounde']}

💚 Kidjamo vous guide étape par étape
Système Kidjamo - Startup4Good Cameroun
        """

        # ENVOYER DIRECTEMENT VIA SES (pas SNS) pour HTML formaté
        ses_client = boto3.client('ses', region_name='eu-west-1')

        response = ses_client.send_email(
            Source='christianouragan@gmail.com',  # Email vérifié dans SES
            Destination={
                'ToAddresses': ['christianouragan@gmail.com']
            },
            Message={
                'Subject': {
                    'Data': email_subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    },
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )

        logger.info(f"📧 Email HTML SES envoyé: {response.get('MessageId', 'N/A')}")

        # Optionnel: Envoyer aussi via SNS pour SMS si configuré
        if SNS_TOPIC_ARN:
            sns_client.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject=f"{icon} KIDJAMO: {title.replace('🚨 ', '').replace('⚠️ ', '')}",
                Message=f"{icon} ALERTE KIDJAMO: {quick_summary} - Patient: {alert['device_id']} - Urgences: {alert['urgency_contacts']['emergency']}"
            )
            logger.info("📱 SMS SNS envoyé également")

    except Exception as e:
        logger.error(f"❌ Erreur envoi notification SES: {e}")
        # Fallback vers SNS simple en cas d'erreur SES
        if SNS_TOPIC_ARN:
            try:
                sns_client.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Subject=email_subject,
                    Message=text_body
                )
                logger.info("📧 Fallback SNS utilisé")
            except Exception as fallback_error:
                logger.error(f"❌ Erreur fallback SNS: {fallback_error}")
