"""
API d'ingestion pour recevoir les données des capteurs IoT
Point d'entrée cloud avant la pipeline Kidjamo
"""

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer
from pydantic import BaseModel, validator
from typing import Optional, Dict, Any
import json
import boto3
from datetime import datetime
import uuid
import logging

app = FastAPI(title="Kidjamo IoT Ingestion API", version="1.0.0")
security = HTTPBearer()

# Configuration
LANDING_BUCKET = "kidjamo-landing-zone"
SQS_QUEUE = "kidjamo-iot-queue"

# Modèles de données
class VitalsData(BaseModel):
    spo2: Optional[float] = None
    heart_rate: Optional[int] = None
    temperature: Optional[float] = None
    ambient_temp_celsius: Optional[float] = None
    respiratory_rate: Optional[int] = None
    hydration_percent: Optional[float] = None
    activity_level: Optional[int] = None
    pain_scale: Optional[int] = None
    
    @validator('spo2')
    def validate_spo2(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('SpO2 must be between 0 and 100')
        return v
    
    @validator('heart_rate')
    def validate_heart_rate(cls, v):
        if v is not None and (v < 30 or v > 250):
            raise ValueError('Heart rate must be between 30 and 250')
        return v

class MetadataData(BaseModel):
    battery_level: Optional[int] = None
    signal_quality: Optional[int] = None
    firmware_version: Optional[str] = None
    
class IoTMessage(BaseModel):
    device_id: str
    patient_id: str
    timestamp: datetime
    vitals: VitalsData
    metadata: Optional[MetadataData] = None

@app.post("/v1/vitals")
async def receive_vitals(
    message: IoTMessage,
    token: str = Security(security)
):
    """
    Point d'entrée pour les données des capteurs IoT
    Stocke dans Landing Zone et déclenche la pipeline
    """
    try:
        # 1. Validation supplémentaire
        if not message.device_id or not message.patient_id:
            raise HTTPException(status_code=400, detail="Device ID and Patient ID required")
        
        # 2. Enrichissement avec métadonnées cloud
        enriched_message = {
            **message.dict(),
            "received_at": datetime.utcnow().isoformat(),
            "ingestion_id": str(uuid.uuid4()),
            "api_version": "v1.0.0"
        }
        
        # 3. Stockage en Landing Zone (S3)
        s3_key = f"vitals/{message.patient_id}/{datetime.utcnow().strftime('%Y/%m/%d/%H')}/{message.device_id}_{int(datetime.utcnow().timestamp())}.json"
        
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=LANDING_BUCKET,
            Key=s3_key,
            Body=json.dumps(enriched_message),
            ContentType='application/json'
        )
        
        # 4. Envoi dans la file d'attente pour processing
        sqs_client = boto3.client('sqs')
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE,
            MessageBody=json.dumps({
                "s3_bucket": LANDING_BUCKET,
                "s3_key": s3_key,
                "patient_id": message.patient_id,
                "device_id": message.device_id,
                "priority": "high" if needs_immediate_processing(message.vitals) else "normal"
            })
        )
        
        # 5. Vérification alertes urgence immédiate
        emergency_alerts = check_emergency_conditions(message.vitals)
        if emergency_alerts:
            await send_emergency_alerts(message.patient_id, emergency_alerts)
        
        return {
            "status": "success",
            "ingestion_id": enriched_message["ingestion_id"],
            "message": "Data received and queued for processing"
        }
        
    except Exception as e:
        logging.error(f"Error processing IoT message: {e}")
        raise HTTPException(status_code=500, detail="Internal processing error")

def needs_immediate_processing(vitals: VitalsData) -> bool:
    """Détermine si les données nécessitent un traitement prioritaire"""
    critical_conditions = [
        vitals.spo2 and vitals.spo2 < 88,
        vitals.temperature and vitals.temperature > 39.0,
        vitals.pain_scale and vitals.pain_scale >= 8
    ]
    return any(critical_conditions)

def check_emergency_conditions(vitals: VitalsData) -> list:
    """Vérification d'urgence immédiate (avant pipeline complète)"""
    alerts = []
    
    if vitals.spo2 and vitals.spo2 < 85:
        alerts.append({
            "type": "critical_hypoxia",
            "value": vitals.spo2,
            "threshold": 85,
            "action": "immediate_oxygen"
        })
    
    if vitals.temperature and vitals.temperature > 39.5:
        alerts.append({
            "type": "critical_fever", 
            "value": vitals.temperature,
            "threshold": 39.5,
            "action": "immediate_cooling"
        })
    
    return alerts

async def send_emergency_alerts(patient_id: str, alerts: list):
    """Envoi d'alertes d'urgence immédiate"""
    # SNS pour notifications push urgentes
    sns_client = boto3.client('sns')
    
    for alert in alerts:
        message = f"URGENCE Patient {patient_id}: {alert['type']} - Valeur: {alert['value']}"
        
        sns_client.publish(
            TopicArn="arn:aws:sns:region:account:kidjamo-emergency-alerts",
            Message=message,
            Subject="Kidjamo - Alerte Urgence Médicale"
        )

@app.get("/health")
async def health_check():
    """Health check pour monitoring"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
