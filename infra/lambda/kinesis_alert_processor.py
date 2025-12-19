#!/usr/bin/env python3
"""
AWS Lambda - Processeur d'Alertes Kinesis Temps Réel ENHANCED + DATABASE STORAGE
Version 3.0 - Intégration capteurs médicaux + stockage automatique en base PostgreSQL
Surveillance: accélération, température corporelle, fréquence cardiaque, SpO2
"""

import json
import boto3
import base64
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
import os

# Import du gestionnaire de base de données des alertes
from alert_database_manager import store_alert_to_database, update_alert_delivery_status, initialize_alert_database

# Configuration depuis les variables d'environnement
REGION = os.environ.get('KIDJAMO_REGION', 'eu-west-1')
BUCKET_NAME = os.environ.get('S3_BUCKET', 'kidjamo-dev-datalake-e75d5213')
DEVICE_ID = os.environ.get('DEVICE_ID', 'MPU_Christian_8266MOD')

# Clients AWS
s3_client = boto3.client('s3', region_name=REGION)
ses_client = boto3.client('ses', region_name=REGION)

# Configuration SES
SES_CONFIG = {
    'sender_email': 'support@kidjamo.app',
    'sender_name': 'Kidjamo Medical Alert',
    'recipient_email': 'christianouragan@gmail.com',
    'reply_to': 'support@kidjamo.app'
}

# Seuils médicaux basés sur kidjamo_seuil.json
MEDICAL_THRESHOLDS = {
    # Groupes d'âge (estimation par défaut: adulte jeune G5)
    'age_groups': {
        'G1': {'min_age': 0, 'max_age': 1, 'name': '0-1 ans'},
        'G2': {'min_age': 1, 'max_age': 5, 'name': '1-5 ans'},
        'G3': {'min_age': 6, 'max_age': 12, 'name': '6-12 ans'},
        'G4': {'min_age': 13, 'max_age': 17, 'name': '13-17 ans'},
        'G5': {'min_age': 18, 'max_age': 59, 'name': '18-59 ans'},
        'G6': {'min_age': 60, 'max_age': 80, 'name': '60-80 ans'}
    },

    # Seuils par paramètre et groupe d'âge
    'temperature': {
        'G5': {'normal': [36.5, 37.5], 'vigilance': [37.6, 37.9], 'alert': 38.0, 'emergency': 39.0, 'hypothermia': 35.0}
    },
    'spo2': {
        'G5': {'normal': 95, 'vigilance': [93, 94], 'alert': 92, 'emergency': 90, 'critical': 88}
    },
    'heart_rate': {
        'G5': {'normal': [60, 100], 'vigilance': [101, 110], 'alert': 111, 'emergency': 130, 'bradycardia': 50}
    },

    # Seuils d'activité (conservés)
    'motion': {
        'fall_detection': 15.0,      # m/s² - chute
        'hyperactivity': 12.0        # m/s² - hyperactivité
    }
}

def lambda_handler(event, context):
    """
    Handler principal Lambda ENHANCED v3.0 - Traite les événements Kinesis + Stockage BDD
    Surveillance médicale complète + détection d'activité + stockage automatique
    """
    print(f"🚀 Lambda Medical Alert Processor v3.0 (DB Storage) - Records: {len(event.get('Records', []))}")

    # Initialiser la base de données des alertes si nécessaire
    initialize_alert_database()

    alerts_generated = 0
    records_processed = 0
    alerts_stored_in_db = 0

    try:
        for record in event.get('Records', []):
            if record.get('eventSource') == 'aws:kinesis':
                kinesis_data = record.get('kinesis', {})
                encoded_data = kinesis_data.get('data', '')

                if encoded_data:
                    # Décoder base64 → JSON
                    decoded_data = base64.b64decode(encoded_data).decode('utf-8')
                    sensor_data = json.loads(decoded_data)

                    print(f"🔍 Traitement données: {sensor_data.get('device_id', 'UNKNOWN')}")

                    # Vérifier que c'est bien des données du bracelet
                    if is_valid_sensor_data(sensor_data):
                        # Détecter toutes les alertes (médicales + activité)
                        alerts = detect_comprehensive_alerts(sensor_data)

                        if alerts:
                            print(f"🚨 {len(alerts)} alerte(s) médicale(s) détectée(s)!")

                            for alert in alerts:
                                try:
                                    # 1. NOUVEAU: Stocker l'alerte en base de données AVANT l'envoi
                                    alert_id = store_alert_to_database(alert, sensor_data)
                                    if alert_id:
                                        print(f"💾 Alerte stockée en base: ID={alert_id}")
                                        alerts_stored_in_db += 1

                                        # Ajouter l'ID de l'alerte pour le suivi
                                        alert['database_id'] = alert_id
                                    else:
                                        print(f"⚠️ Échec stockage en base pour alerte {alert['type']}")

                                    # 2. Envoyer les notifications (email, SMS, etc.)
                                    email_sent = False
                                    sms_sent = False
                                    notification_sent = False

                                    try:
                                        send_medical_alert(alert, sensor_data)
                                        email_sent = True
                                        notification_sent = True
                                        print(f"📧 Email envoyé pour alerte {alert.get('type')}")
                                    except Exception as e:
                                        print(f"❌ Erreur envoi email: {e}")

                                    try:
                                        store_alert_s3(alert)
                                        print(f"📁 Alerte archivée en S3")
                                    except Exception as e:
                                        print(f"❌ Erreur archivage S3: {e}")

                                    # 3. NOUVEAU: Mettre à jour le statut d'envoi en base
                                    if alert_id:
                                        update_alert_delivery_status(
                                            alert_id,
                                            email_sent=email_sent,
                                            sms_sent=sms_sent,
                                            notification_sent=notification_sent
                                        )

                                    alerts_generated += 1
                                    print(f"✅ Alerte complète: {alert['type']} - {alert['severity']} (DB ID: {alert_id})")

                                except Exception as e:
                                    print(f"❌ Erreur traitement alerte: {e}")

                        records_processed += 1

        # Rapport final avec statistiques BDD
        print(f"\n📊 RAPPORT FINAL TRAITEMENT:")
        print(f"   📋 Records traités: {records_processed}")
        print(f"   🚨 Alertes générées: {alerts_generated}")
        print(f"   💾 Alertes stockées en base: {alerts_stored_in_db}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'records_processed': records_processed,
                'alerts_generated': alerts_generated,
                'alerts_stored_in_database': alerts_stored_in_db,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': '3.0-database-storage'
            })
        }

    except Exception as e:
        print(f"💥 ERREUR CRITIQUE Lambda: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'records_processed': records_processed,
                'alerts_generated': alerts_generated,
                'alerts_stored_in_database': alerts_stored_in_db
            })
        }

def is_valid_sensor_data(data: Dict) -> bool:
    """Vérifie si les données contiennent les capteurs requis"""
    # Capteurs minimum requis (anciens + nouveaux)
    motion_fields = ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z']
    medical_fields = ['temp_object', 'heart_rate', 'spo2']  # temp_object = température corporelle

    has_device_id = data.get('device_id') == DEVICE_ID
    has_motion = any(field in data for field in motion_fields)
    has_medical = any(field in data for field in medical_fields)

    return has_device_id and (has_motion or has_medical)

def get_age_group(age: Optional[int] = None) -> str:
    """Détermine le groupe d'âge (par défaut: adulte jeune G5)"""
    if age is None:
        return 'G5'  # Adulte jeune par défaut

    for group_id, group_info in MEDICAL_THRESHOLDS['age_groups'].items():
        if group_info['min_age'] <= age <= group_info['max_age']:
            return group_id

    return 'G5'  # Fallback

def detect_comprehensive_alerts(data: Dict) -> List[Dict]:
    """Détection complète: alertes médicales + activité"""
    alerts = []
    age_group = get_age_group()  # Par défaut G5

    try:
        # 1. ALERTES MÉDICALES (nouvelles)
        alerts.extend(detect_temperature_alerts(data, age_group))
        alerts.extend(detect_heart_rate_alerts(data, age_group))
        alerts.extend(detect_spo2_alerts(data, age_group))

        # 2. ALERTES D'ACTIVITÉ (conservées)
        alerts.extend(detect_motion_alerts(data))

        # 3. ALERTES COMBINÉES CRITIQUES
        alerts.extend(detect_critical_combinations(data, age_group))

    except Exception as e:
        print(f"❌ Erreur détection alertes: {e}")

    return alerts

def detect_temperature_alerts(data: Dict, age_group: str) -> List[Dict]:
    """Détection alertes température corporelle"""
    alerts = []

    # temp_object = température corporelle selon votre mapping
    body_temp = data.get('temp_object')
    if body_temp is None:
        return alerts

    thresholds = MEDICAL_THRESHOLDS['temperature'][age_group]

    if body_temp >= thresholds['emergency']:
        alerts.append({
            'type': 'HYPERTHERMIA_EMERGENCY',
            'severity': 'CRITICAL',
            'message': f'Hyperthermie sévère: {body_temp}°C (>= {thresholds["emergency"]}°C)',
            'value': body_temp,
            'threshold': thresholds['emergency'],
            'recommendation': 'Hospitalisation urgente, investigations infectieuses, perfusion, surveillance neurologique',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'temperature_body'
        })
    elif body_temp >= thresholds['alert']:
        alerts.append({
            'type': 'FEVER_ALERT',
            'severity': 'HIGH',
            'message': f'Fièvre détectée: {body_temp}°C (>= {thresholds["alert"]}°C)',
            'value': body_temp,
            'threshold': thresholds['alert'],
            'recommendation': 'Antipyrétique, surveillance, consulter si persistance >24h',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'temperature_body'
        })
    elif body_temp <= thresholds['hypothermia']:
        alerts.append({
            'type': 'HYPOTHERMIA_ALERT',
            'severity': 'HIGH',
            'message': f'Hypothermie: {body_temp}°C (<= {thresholds["hypothermia"]}°C)',
            'value': body_temp,
            'threshold': thresholds['hypothermia'],
            'recommendation': 'Réchauffement progressif, surveillance fonctions vitales',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'temperature_body'
        })

    return alerts

def detect_heart_rate_alerts(data: Dict, age_group: str) -> List[Dict]:
    """Détection alertes fréquence cardiaque"""
    alerts = []

    heart_rate = data.get('heart_rate')
    if heart_rate is None:
        return alerts

    thresholds = MEDICAL_THRESHOLDS['heart_rate'][age_group]

    if heart_rate >= thresholds['emergency']:
        alerts.append({
            'type': 'TACHYCARDIA_EMERGENCY',
            'severity': 'CRITICAL',
            'message': f'Tachycardie sévère: {heart_rate} bpm (>= {thresholds["emergency"]} bpm)',
            'value': heart_rate,
            'threshold': thresholds['emergency'],
            'recommendation': 'Soins intensifs, monitorage continu, support hémodynamique',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'heart_rate'
        })
    elif heart_rate >= thresholds['alert']:
        alerts.append({
            'type': 'TACHYCARDIA_ALERT',
            'severity': 'HIGH',
            'message': f'Tachycardie: {heart_rate} bpm (>= {thresholds["alert"]} bpm)',
            'value': heart_rate,
            'threshold': thresholds['alert'],
            'recommendation': 'Rechercher cause (infection, choc, hypoxie), ECG, monitorage',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'heart_rate'
        })
    elif heart_rate <= thresholds['bradycardia']:
        alerts.append({
            'type': 'BRADYCARDIA_ALERT',
            'severity': 'HIGH',
            'message': f'Bradycardie: {heart_rate} bpm (<= {thresholds["bradycardia"]} bpm)',
            'value': heart_rate,
            'threshold': thresholds['bradycardia'],
            'recommendation': 'Évaluer perfusion tissulaire, pression artérielle, envisager ACLS',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'heart_rate'
        })

    return alerts

def detect_spo2_alerts(data: Dict, age_group: str) -> List[Dict]:
    """Détection alertes oxygénation (SpO2)"""
    alerts = []

    spo2 = data.get('spo2')
    if spo2 is None:
        return alerts

    thresholds = MEDICAL_THRESHOLDS['spo2'][age_group]

    if spo2 <= thresholds['critical']:
        alerts.append({
            'type': 'HYPOXIA_CRITICAL',
            'severity': 'CRITICAL',
            'message': f'Hypoxie critique: {spo2}% (<= {thresholds["critical"]}%)',
            'value': spo2,
            'threshold': thresholds['critical'],
            'recommendation': 'Protocoles hypoxie sévère, envisager intubation, prise en charge multidisciplinaire',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'spo2'
        })
    elif spo2 <= thresholds['emergency']:
        alerts.append({
            'type': 'HYPOXIA_EMERGENCY',
            'severity': 'CRITICAL',
            'message': f'Hypoxie sévère: {spo2}% (<= {thresholds["emergency"]}%)',
            'value': spo2,
            'threshold': thresholds['emergency'],
            'recommendation': 'Oxygène haut débit, ventilation non invasive, soins intensifs',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'spo2'
        })
    elif spo2 <= thresholds['alert']:
        alerts.append({
            'type': 'HYPOXIA_ALERT',
            'severity': 'HIGH',
            'message': f'Hypoxie modérée: {spo2}% (<= {thresholds["alert"]}%)',
            'value': spo2,
            'threshold': thresholds['alert'],
            'recommendation': 'Oxygénothérapie d\'appoint, maintenir SpO₂ ≥ 92%, surveiller',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'device_id': DEVICE_ID,
            'parameter': 'spo2'
        })

    return alerts

def detect_motion_alerts(data: Dict) -> List[Dict]:
    """Détection alertes d'activité (conservé de l'ancienne version)"""
    alerts = []

    try:
        # Vérifier si on a les données d'accélération
        if not all(key in data for key in ['accel_x', 'accel_y', 'accel_z']):
            return alerts

        # Calculer magnitude accélération
        accel_magnitude = math.sqrt(
            data['accel_x']**2 + data['accel_y']**2 + data['accel_z']**2
        )

        # Calculer magnitude gyroscope si disponible
        gyro_magnitude = 0
        if all(key in data for key in ['gyro_x', 'gyro_y', 'gyro_z']):
            gyro_magnitude = math.sqrt(
                data['gyro_x']**2 + data['gyro_y']**2 + data['gyro_z']**2
            )

        print(f"📊 Magnitudes - Accel: {accel_magnitude:.2f}, Gyro: {gyro_magnitude:.2f}")

        # Détection de chute
        if accel_magnitude > MEDICAL_THRESHOLDS['motion']['fall_detection']:
            alerts.append({
                'type': 'FALL_DETECTION',
                'severity': 'HIGH',
                'message': f'Chute détectée - Accélération: {accel_magnitude:.2f} m/s²',
                'value': accel_magnitude,
                'threshold': MEDICAL_THRESHOLDS['motion']['fall_detection'],
                'recommendation': 'Vérifier état du patient, rechercher blessures, évaluer conscience',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'device_id': DEVICE_ID,
                'parameter': 'acceleration'
            })

        # Détection hyperactivité
        if accel_magnitude > MEDICAL_THRESHOLDS['motion']['hyperactivity'] and gyro_magnitude > 3.0:
            alerts.append({
                'type': 'HYPERACTIVITY_DETECTED',
                'severity': 'MEDIUM',
                'message': f'Activité élevée - Accel: {accel_magnitude:.2f} m/s², Gyro: {gyro_magnitude:.2f} rad/s',
                'value': accel_magnitude,
                'threshold': MEDICAL_THRESHOLDS['motion']['hyperactivity'],
                'recommendation': 'Surveiller fatigue, encourager repos, vérifier hydratation',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'device_id': DEVICE_ID,
                'parameter': 'acceleration'
            })

    except Exception as e:
        print(f"❌ Erreur détection mouvement: {e}")

    return alerts

def detect_critical_combinations(data: Dict, age_group: str) -> List[Dict]:
    """Détection alertes combinées critiques (inspirées kidjamo_seuil.json)"""
    alerts = []

    try:
        temp = data.get('temp_object')  # température corporelle
        spo2 = data.get('spo2')
        heart_rate = data.get('heart_rate')

        temp_thresholds = MEDICAL_THRESHOLDS['temperature'][age_group]
        spo2_thresholds = MEDICAL_THRESHOLDS['spo2'][age_group]

        # C1: Fièvre + Hypoxie (critique selon kidjamo_seuil.json)
        if (temp and temp >= temp_thresholds['alert'] and
            spo2 and spo2 <= spo2_thresholds['alert']):
            alerts.append({
                'type': 'FEVER_HYPOXIA_CRITICAL',
                'severity': 'CRITICAL',
                'message': f'Combinaison critique: Fièvre {temp}°C + Hypoxie {spo2}%',
                'value': {'temperature': temp, 'spo2': spo2},
                'threshold': 'combined_critical',
                'recommendation': 'Antipyrétique + oxygène immédiat, bilan infectieux (hémoculture, CRP), transfert soins intensifs si non amélioration',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'device_id': DEVICE_ID,
                'parameter': 'combined_fever_hypoxia'
            })

        # C2: Tachycardie + Hypoxie (détresse respiratoire)
        hr_thresholds = MEDICAL_THRESHOLDS['heart_rate'][age_group]
        if (heart_rate and heart_rate >= hr_thresholds['alert'] and
            spo2 and spo2 <= spo2_thresholds['emergency']):
            alerts.append({
                'type': 'RESPIRATORY_DISTRESS_CRITICAL',
                'severity': 'CRITICAL',
                'message': f'Détresse respiratoire: FC {heart_rate} bpm + SpO₂ {spo2}%',
                'value': {'heart_rate': heart_rate, 'spo2': spo2},
                'threshold': 'combined_critical',
                'recommendation': 'Oxygène haute concentration, position semi-assise, surveillance continue, envisager ventilation non-invasive',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'device_id': DEVICE_ID,
                'parameter': 'combined_respiratory_distress'
            })

    except Exception as e:
        print(f"❌ Erreur détection combinées: {e}")

    return alerts

def send_medical_alert(alert: Dict, raw_data: Dict):
    """Envoie une alerte médicale via Amazon SES"""
    try:
        severity = alert.get('severity', 'MEDIUM')
        message_details = alert.get('message', 'Alerte détectée')
        recommendation = alert.get('recommendation', 'Consulter un professionnel de santé')

        # Configuration expéditeur
        from_address = f"{SES_CONFIG['sender_name']} <{SES_CONFIG['sender_email']}>"

        if severity == 'CRITICAL':
            subject = f"🚨 ALERTE MÉDICALE CRITIQUE - {alert['type']}"
            bg_color = "#dc3545"
            icon = "🚨"
        elif severity == 'HIGH':
            subject = f"⚠️ ALERTE MÉDICALE ÉLEVÉE - {alert['type']}"
            bg_color = "#fd7e14"
            icon = "⚠️"
        else:
            subject = f"💡 ALERTE MÉDICALE - {alert['type']}"
            bg_color = "#17a2b8"
            icon = "💡"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Alerte Médicale Kidjamo</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: {bg_color}; color: white; padding: 20px; border-radius: 8px; text-align: center;">
                    <h1 style="margin: 0;">{icon} ALERTE MÉDICALE KIDJAMO</h1>
                    <p style="margin: 10px 0 0 0; font-size: 18px;">Surveillance IoT Drépanocytose</p>
                </div>
                
                <div style="background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px;">
                    <h2 style="color: {bg_color}; margin-top: 0;">📊 Détails de l'Alerte</h2>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Patient:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['device_id']}</td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['type']}</td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Paramètre:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('parameter', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Valeur:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('value', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Seuil:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert.get('threshold', 'N/A')}</td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Gravité:</strong></td><td style="padding: 8px; border: 1px solid #ddd;"><span style="color: {bg_color}; font-weight: bold;">{severity}</span></td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Message:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{message_details}</td></tr>
                        <tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Timestamp:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{alert['timestamp']}</td></tr>
                    </table>
                </div>
                
                <div style="background: #fff3cd; border: 1px solid #ffeaa7; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #856404; margin-top: 0;">🩺 RECOMMANDATION MÉDICALE</h3>
                    <p style="margin-bottom: 0;"><strong>{recommendation}</strong></p>
                </div>
                
                <div style="background: #d1ecf1; border: 1px solid #bee5eb; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h4 style="color: #0c5460; margin-top: 0;">📱 Données Brutes du Bracelet</h4>
                    <pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; font-size: 12px; overflow-x: auto;">{json.dumps(raw_data, indent=2)}</pre>
                </div>
                
                <div style="text-align: center; padding: 20px; color: #6c757d; font-size: 12px;">
                    <p><strong>Système d'Alertes Médicales Kidjamo v2.0</strong><br>
                    Surveillance IoT pour Drépanocytose - 24h/24<br>
                    Support: support@kidjamo.app | Urgences: consulter médecin</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Envoyer l'email
        response = ses_client.send_email(
            Source=from_address,
            Destination={'ToAddresses': [SES_CONFIG['recipient_email']]},
            ReplyToAddresses=[SES_CONFIG['reply_to']],
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': {'Html': {'Data': html_body, 'Charset': 'UTF-8'}}
            }
        )

        print(f"✅ Email médical envoyé - MessageId: {response.get('MessageId', 'N/A')}")

    except Exception as e:
        print(f"❌ Erreur envoi email médical: {e}")
        raise

def store_alert_s3(alert: Dict):
    """Stockage alerte dans S3 avec nouveau format médical"""
    try:
        # Génération clé S3 avec partitioning par date
        now = datetime.now(timezone.utc)
        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%d')
        hour = now.strftime('%H')

        # Clé S3 optimisée
        s3_key = f"alerts/medical/year={year}/month={month}/day={day}/hour={hour}/alert_{now.strftime('%Y%m%d_%H%M%S')}_{alert['type'].lower()}.json"

        # Enrichir l'alerte avec métadonnées
        enriched_alert = {
            **alert,
            'alert_id': f"kidjamo_medical_{now.strftime('%Y%m%d_%H%M%S')}",
            'version': '2.0',
            'alert_category': 'medical_iot',
            'processing_timestamp': now.isoformat(),
            'urgency_score': get_urgency_score(alert['severity']),
            'patient_context': {
                'age_group_estimated': 'G5',  # À enrichir avec vraies données patient
                'disease_context': 'drepanocytose',
                'monitoring_type': 'iot_continuous'
            }
        }

        # Upload vers S3
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=json.dumps(enriched_alert, indent=2),
            ContentType='application/json',
            Metadata={
                'alert-type': alert['type'],
                'severity': alert['severity'],
                'device-id': alert['device_id'],
                'parameter': alert.get('parameter', 'unknown'),
                'version': '2.0'
            }
        )

        print(f"✅ Alerte médicale stockée: s3://{BUCKET_NAME}/{s3_key}")

    except Exception as e:
        print(f"❌ Erreur stockage S3: {e}")

def get_urgency_score(severity: str) -> int:
    """Calcul score d'urgence numérique"""
    scores = {
        'CRITICAL': 5,
        'HIGH': 4,
        'MEDIUM': 3,
        'LOW': 2,
        'INFO': 1
    }
    return scores.get(severity, 3)

# Point d'entrée pour tests locaux
if __name__ == "__main__":
    # Test avec nouvelles données
    test_event = {
        'Records': [{
            'eventSource': 'aws:kinesis',
            'kinesis': {
                'data': base64.b64encode(json.dumps({
                    "accel_x": -0.19393,
                    "accel_y": 0.399832,
                    "accel_z": -9.861717,
                    "gyro_x": -0.001332,
                    "gyro_y": -0.002398,
                    "gyro_z": -0.010658,
                    "temp_mpu": 27.61235,
                    "temp_object": 38.5,     # Fièvre test
                    "temp_ambient": 27.61001,
                    "heart_rate": 125,       # Tachycardie test
                    "spo2": 89,              # Hypoxie test
                    "aws_timestamp": 2610527839,
                    "device_id": "MPU_Christian_8266MOD"
                }).encode('utf-8')).decode('utf-8')
            }
        }]
    }

    result = lambda_handler(test_event, None)
    print(f"🧪 Test terminé: {result}")
