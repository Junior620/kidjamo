#!/usr/bin/env python3
"""
API FastAPI pour Kidjamo IoT - Endpoints Activité et Accéléromètre
================================================================

API REST moderne pour accéder aux données des bracelets IoT Kidjamo.
Optimisée pour les applications mobile et web.
"""

from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import json
import boto3
import asyncio
from decimal import Decimal
import logging

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialisation FastAPI
app = FastAPI(
    title="Kidjamo IoT Activity API",
    description="API pour accéder aux données d'activité des bracelets IoT Kidjamo",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuration CORS pour mobile/web
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# AWS Clients
kinesis_client = boto3.client('kinesis', region_name='eu-west-1')
dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
s3_client = boto3.client('s3', region_name='eu-west-1')

# Tables DynamoDB (à créer)
activity_table = dynamodb.Table('kidjamo-activity-cache')
alerts_table = dynamodb.Table('kidjamo-alerts')

# Models Pydantic
class AccelerometerData(BaseModel):
    """Données d'accéléromètre"""
    accel_x: float = Field(..., description="Accélération axe X (m/s²)")
    accel_y: float = Field(..., description="Accélération axe Y (m/s²)")
    accel_z: float = Field(..., description="Accélération axe Z (m/s²)")
    magnitude: float = Field(..., description="Magnitude vectorielle")
    timestamp: datetime = Field(..., description="Timestamp de la mesure")

class ActivityLevel(BaseModel):
    """Niveau d'activité détecté"""
    level: str = Field(..., description="repos|mouvement_leger|activite_intense|risque_chute")
    emoji: str = Field(..., description="Emoji représentant l'activité")
    label: str = Field(..., description="Label lisible")
    description: str = Field(..., description="Description détaillée")
    confidence: float = Field(..., ge=0, le=1, description="Confiance de détection (0-1)")
    color: str = Field(..., description="Couleur pour l'interface (green|blue|orange|red)")

class CurrentActivityResponse(BaseModel):
    """Réponse activité actuelle"""
    device_id: str
    patient_id: str
    accelerometer: AccelerometerData
    activity: ActivityLevel
    environmental: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime
    battery_level: Optional[int] = None
    signal_strength: Optional[int] = None

class ActivityHistoryItem(BaseModel):
    """Item d'historique d'activité"""
    timestamp: datetime
    activity_level: str
    magnitude: float
    duration_minutes: Optional[int] = None

class ActivitySummary(BaseModel):
    """Résumé d'activité sur une période"""
    time_period: str
    total_duration_minutes: int
    activity_distribution: Dict[str, float]  # Pourcentages
    dominant_activity: str
    calories_estimated: Optional[float] = None
    steps_estimated: Optional[int] = None

class AlertItem(BaseModel):
    """Alerte individuelle"""
    alert_id: str
    patient_id: str
    alert_type: str  # fall_risk, intense_activity, low_battery, etc.
    severity: str  # low, medium, high, critical
    message: str
    timestamp: datetime
    acknowledged: bool = False
    data: Optional[Dict[str, Any]] = None

# WebSocket Manager pour temps réel
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.device_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, device_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if device_id:
            if device_id not in self.device_connections:
                self.device_connections[device_id] = []
            self.device_connections[device_id].append(websocket)

    def disconnect(self, websocket: WebSocket, device_id: str = None):
        self.active_connections.remove(websocket)
        if device_id and device_id in self.device_connections:
            self.device_connections[device_id].remove(websocket)

    async def send_to_device(self, message: dict, device_id: str):
        if device_id in self.device_connections:
            disconnected = []
            for connection in self.device_connections[device_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)

            # Nettoyer les connexions fermées
            for conn in disconnected:
                self.device_connections[device_id].remove(conn)

manager = ConnectionManager()

# Helpers
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Validation JWT (simplifié pour démo)"""
    # TODO: Implémenter validation JWT réelle
    return {"user_id": "demo_user", "role": "patient"}

def convert_decimal_to_float(obj):
    """Convertit les Decimal DynamoDB en float"""
    if isinstance(obj, list):
        return [convert_decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj

async def get_latest_activity_from_kinesis(device_id: str) -> Optional[Dict]:
    """Récupère la dernière activité depuis Kinesis"""
    try:
        # Obtenir les derniers records du stream
        response = kinesis_client.describe_stream(StreamName='kidjamo-vital-signs-stream')
        shard_id = response['StreamDescription']['Shards'][0]['ShardId']

        shard_iterator_response = kinesis_client.get_shard_iterator(
            StreamName='kidjamo-vital-signs-stream',
            ShardId=shard_id,
            ShardIteratorType='TRIM_HORIZON'
        )

        records_response = kinesis_client.get_records(
            ShardIterator=shard_iterator_response['ShardIterator'],
            Limit=10
        )

        # Filtrer par device_id et prendre le plus récent
        device_records = []
        for record in records_response['Records']:
            data = json.loads(record['Data'])
            if data.get('device_id') == device_id:
                device_records.append(data)

        return device_records[-1] if device_records else None

    except Exception as e:
        logger.error(f"Erreur récupération Kinesis: {e}")
        return None

# === ENDPOINTS API ===

@app.get("/", tags=["Health"])
async def root():
    """Point d'entrée de l'API"""
    return {
        "service": "Kidjamo IoT Activity API",
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs",
        "endpoints": {
            "activity": "/api/v1/activity/",
            "accelerometer": "/api/v1/accelerometer/",
            "alerts": "/api/v1/alerts/",
            "analytics": "/api/v1/analytics/"
        }
    }

@app.get("/api/v1/activity/current/{device_id}", response_model=CurrentActivityResponse, tags=["Activity"])
async def get_current_activity(
    device_id: str,
    user = Depends(get_current_user)
):
    """Récupère l'activité actuelle d'un bracelet IoT avec données d'accéléromètre complètes"""
    try:
        # Connexion PostgreSQL pour récupérer les vraies données
        pg_query = """
        SELECT 
            m.patient_id,
            m.device_id,
            m.heart_rate_bpm,
            m.spo2_percent,
            m.temperature_celsius,
            m.ambient_temp_celsius,
            m.accel_x,
            m.accel_y,
            m.accel_z,
            m.accel_magnitude,
            m.activity_classification,
            m.activity_confidence,
            m.battery_percent,
            m.signal_quality,
            m.recorded_at,
            p.genotype,
            u.first_name,
            u.last_name
        FROM measurements m
        JOIN patients p ON p.patient_id = m.patient_id
        JOIN users u ON u.user_id = p.user_id
        WHERE m.device_id = %s
        ORDER BY m.recorded_at DESC
        LIMIT 1
        """

        # TODO: Exécuter la requête PostgreSQL réelle
        # Pour la démo, on simule les données enrichies

        # Mapper les données avec la nouvelle structure d'accéléromètre
        response_data = CurrentActivityResponse(
            device_id=device_id,
            patient_id=f"patient_{device_id}",
            accelerometer=AccelerometerData(
                accel_x=-0.588974,  # Vos données réelles
                accel_y=9.435549,
                accel_z=2.602497,
                magnitude=9.806,    # Calculé automatiquement
                timestamp=datetime.utcnow()
            ),
            activity=ActivityLevel(
                level="mouvement_leger",
                emoji="🚶",
                label="Mouvement léger",
                description="Marche lente ou gestes légers - Détecté par accéléromètre",
                confidence=0.85,
                color="#3b82f6"
            ),
            environmental={
                "ambient_temperature": 26.8,
                "comfort_level": "Chaud - Pensez à vous hydrater"
            },
            last_updated=datetime.utcnow(),
            battery_level=85,
            signal_strength=-45
        )

        return response_data

    except Exception as e:
        logger.error(f"Erreur get_current_activity: {e}")
        raise HTTPException(status_code=500, detail="Erreur interne du serveur")

@app.get("/api/v1/activity/history/{device_id}", response_model=List[ActivityHistoryItem], tags=["Activity"])
async def get_activity_history(
    device_id: str,
    hours: int = Query(24, ge=1, le=168, description="Nombre d'heures d'historique"),
    user = Depends(get_current_user)
):
    """Récupère l'historique d'activité sur une période donnée"""
    try:
        # TODO: Implémenter requête vers S3 Data Lake
        # Pour la démo, on simule des données

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)

        # Données simulées d'historique
        history = []
        current_time = start_time

        while current_time < end_time:
            # Simuler différents niveaux d'activité
            import random
            activities = ['repos', 'mouvement_leger', 'activite_intense']
            weights = [0.6, 0.3, 0.1]  # Plus probable d'être au repos

            activity = random.choices(activities, weights=weights)[0]
            magnitude = {
                'repos': random.uniform(0.5, 1.5),
                'mouvement_leger': random.uniform(1.5, 4.0),
                'activite_intense': random.uniform(4.0, 8.0)
            }[activity]

            history.append(ActivityHistoryItem(
                timestamp=current_time,
                activity_level=activity,
                magnitude=magnitude,
                duration_minutes=random.randint(5, 30)
            ))

            current_time += timedelta(minutes=random.randint(10, 60))

        return history[-50:]  # Limiter à 50 points

    except Exception as e:
        logger.error(f"Erreur get_activity_history: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération historique")

@app.get("/api/v1/analytics/activity-summary/{patient_id}", response_model=ActivitySummary, tags=["Analytics"])
async def get_activity_summary(
    patient_id: str,
    period: str = Query("24h", regex="^(1h|6h|24h|7d|30d)$", description="Période d'analyse"),
    user = Depends(get_current_user)
):
    """Génère un résumé d'activité pour une période donnée"""
    try:
        # Mapper les périodes en heures
        period_hours = {
            "1h": 1, "6h": 6, "24h": 24,
            "7d": 168, "30d": 720
        }[period]

        # Simuler des statistiques d'activité
        # TODO: Implémenter requête réelle vers Data Lake

        activity_distribution = {
            "repos": 65.0,
            "mouvement_leger": 28.0,
            "activite_intense": 7.0,
            "risque_chute": 0.0
        }

        # Estimer calories et pas
        calories_per_hour = {
            "repos": 50, "mouvement_leger": 150, "activite_intense": 300
        }

        total_calories = sum(
            calories_per_hour.get(activity, 0) * (percent / 100) * period_hours
            for activity, percent in activity_distribution.items()
        )

        steps_estimated = int(activity_distribution["mouvement_leger"] * 10 +
                             activity_distribution["activite_intense"] * 50)

        return ActivitySummary(
            time_period=period,
            total_duration_minutes=period_hours * 60,
            activity_distribution=activity_distribution,
            dominant_activity="repos",
            calories_estimated=total_calories,
            steps_estimated=steps_estimated
        )

    except Exception as e:
        logger.error(f"Erreur get_activity_summary: {e}")
        raise HTTPException(status_code=500, detail="Erreur génération résumé")

@app.get("/api/v1/alerts/{patient_id}", response_model=List[AlertItem], tags=["Alerts"])
async def get_patient_alerts(
    patient_id: str,
    limit: int = Query(20, ge=1, le=100, description="Nombre maximum d'alertes"),
    acknowledged: Optional[bool] = Query(None, description="Filtrer par statut acquittement"),
    user = Depends(get_current_user)
):
    """Récupère les alertes d'un patient"""
    try:
        # TODO: Implémenter requête DynamoDB réelle

        # Simuler quelques alertes
        alerts = [
            AlertItem(
                alert_id="alert_001",
                patient_id=patient_id,
                alert_type="fall_risk",
                severity="high",
                message="Risque de chute détecté - magnitude 18.5 m/s²",
                timestamp=datetime.utcnow() - timedelta(minutes=30),
                acknowledged=False,
                data={"magnitude": 18.5, "device_id": "bracelet_001"}
            ),
            AlertItem(
                alert_id="alert_002",
                patient_id=patient_id,
                alert_type="low_battery",
                severity="medium",
                message="Niveau de batterie faible (15%)",
                timestamp=datetime.utcnow() - timedelta(hours=2),
                acknowledged=True,
                data={"battery_level": 15}
            )
        ]

        # Filtrer par acknowledged si spécifié
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]

        return alerts[:limit]

    except Exception as e:
        logger.error(f"Erreur get_patient_alerts: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération alertes")

@app.post("/api/v1/alerts/acknowledge", tags=["Alerts"])
async def acknowledge_alert(
    alert_id: str,
    user = Depends(get_current_user)
):
    """Acquitte une alerte"""
    try:
        # TODO: Implémenter mise à jour DynamoDB

        return {
            "success": True,
            "alert_id": alert_id,
            "acknowledged_at": datetime.utcnow().isoformat(),
            "acknowledged_by": user["user_id"]
        }

    except Exception as e:
        logger.error(f"Erreur acknowledge_alert: {e}")
        raise HTTPException(status_code=500, detail="Erreur acquittement alerte")

# === WEBSOCKETS TEMPS RÉEL ===

@app.websocket("/ws/activity/{device_id}")
async def websocket_activity_stream(websocket: WebSocket, device_id: str):
    """WebSocket pour stream d'activité en temps réel"""
    await manager.connect(websocket, device_id)

    try:
        while True:
            # Simuler des données temps réel
            await asyncio.sleep(5)  # Envoyer toutes les 5 secondes

            # Récupérer les données actuelles
            try:
                current_data = await get_current_activity(device_id, {"user_id": "websocket"})
                await manager.send_to_device(current_data.dict(), device_id)
            except Exception as e:
                logger.error(f"Erreur WebSocket: {e}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, device_id)

@app.websocket("/ws/alerts/{patient_id}")
async def websocket_alerts_stream(websocket: WebSocket, patient_id: str):
    """WebSocket pour alertes en temps réel"""
    await manager.connect(websocket)

    try:
        while True:
            await asyncio.sleep(10)  # Vérifier alertes toutes les 10 secondes

            # TODO: Vérifier nouvelles alertes depuis DynamoDB
            # Pour la démo, on simule une alerte occasionnelle
            import random
            if random.random() < 0.1:  # 10% de chance d'alerte
                alert = {
                    "type": "new_alert",
                    "alert": {
                        "alert_id": f"alert_{int(datetime.utcnow().timestamp())}",
                        "patient_id": patient_id,
                        "alert_type": "activity_anomaly",
                        "severity": "medium",
                        "message": "Activité inhabituelle détectée",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket.send_json(alert)

    except WebSocketDisconnect:
        manager.disconnect(websocket)

# === ENDPOINTS SPÉCIALISÉS POUR MOBILE ===

@app.get("/api/v1/mobile/dashboard/{patient_id}", tags=["Mobile"])
async def get_mobile_dashboard(
    patient_id: str,
    user = Depends(get_current_user)
):
    """Dashboard optimisé pour application mobile"""
    try:
        # Récupérer device_id depuis patient_id (TODO: base de données)
        device_id = f"bracelet_{patient_id.split('_')[-1]}"

        # Données actuelles
        current = await get_current_activity(device_id, user)

        # Résumé quotidien
        summary = await get_activity_summary(patient_id, "24h", user)

        # Alertes non acquittées
        alerts = await get_patient_alerts(patient_id, 5, False, user)

        return {
            "patient_id": patient_id,
            "current_activity": current,
            "daily_summary": summary,
            "active_alerts": alerts,
            "last_updated": datetime.utcnow().isoformat(),
            "recommendations": [
                "Continuez votre activité modérée",
                "Pensez à vous hydrater",
                "Votre niveau d'activité est optimal"
            ]
        }

    except Exception as e:
        logger.error(f"Erreur mobile dashboard: {e}")
        raise HTTPException(status_code=500, detail="Erreur dashboard mobile")

@app.get("/api/v1/activity/analysis/{patient_id}", tags=["Activity"])
async def get_activity_analysis(
    patient_id: str,
    hours: int = Query(24, ge=1, le=168, description="Heures d'analyse"),
    user = Depends(get_current_user)
):
    """Analyse détaillée de l'activité d'un patient basée sur l'accéléromètre"""
    try:
        # Requête PostgreSQL pour analyse complète
        analysis_query = """
        SELECT 
            DATE_TRUNC('hour', recorded_at) as hour_period,
            activity_classification,
            COUNT(*) as measurement_count,
            AVG(accel_magnitude) as avg_magnitude,
            MAX(accel_magnitude) as max_magnitude,
            AVG(activity_confidence) as avg_confidence
        FROM measurements 
        WHERE patient_id = %s 
          AND recorded_at >= now() - INTERVAL '%s hours'
          AND activity_classification IS NOT NULL
        GROUP BY DATE_TRUNC('hour', recorded_at), activity_classification
        ORDER BY hour_period DESC, activity_classification
        """

        # Simulation des données pour la démo
        analysis_data = {
            "patient_id": patient_id,
            "analysis_period_hours": hours,
            "activity_summary": {
                "repos": {"count": 156, "percentage": 65.0, "avg_magnitude": 1.2},
                "mouvement_leger": {"count": 67, "percentage": 28.0, "avg_magnitude": 2.8},
                "activite_intense": {"count": 17, "percentage": 7.0, "avg_magnitude": 6.5},
                "risque_chute": {"count": 0, "percentage": 0.0, "avg_magnitude": 0.0}
            },
            "risk_indicators": {
                "fall_risk_events": 0,
                "high_magnitude_events": 3,
                "anomalies_detected": 1,
                "overall_risk_level": "low"
            },
            "recommendations": [
                "Niveau d'activité optimal pour la récupération",
                "Aucun risque de chute détecté",
                "Maintenir ce niveau d'activité modérée"
            ],
            "hourly_breakdown": [
                {
                    "hour": "2025-09-11T09:00:00Z",
                    "dominant_activity": "mouvement_leger",
                    "activity_count": 12,
                    "max_magnitude": 3.2
                }
                # ... autres heures
            ]
        }

        return analysis_data

    except Exception as e:
        logger.error(f"Erreur activity analysis: {e}")
        raise HTTPException(status_code=500, detail="Erreur analyse activité")

@app.get("/api/v1/activity/alerts/{patient_id}", tags=["Activity"])
async def get_activity_alerts(
    patient_id: str,
    severity: str = Query("all", regex="^(all|low|medium|high|critical)$"),
    user = Depends(get_current_user)
):
    """Récupère les alertes d'activité basées sur l'accéléromètre"""
    try:
        # Requête pour les alertes d'activité depuis PostgreSQL
        alerts_query = """
        SELECT 
            a.alert_id,
            a.alert_type,
            a.severity,
            a.title,
            a.message,
            a.created_at,
            a.resolved_at,
            a.vitals_snapshot
        FROM alerts a
        WHERE a.patient_id = %s
          AND a.alert_type LIKE '%activity%'
          AND (%s = 'all' OR a.severity = %s)
        ORDER BY a.created_at DESC
        LIMIT 20
        """

        # Simulation des alertes d'activité
        activity_alerts = [
            {
                "alert_id": "alert_activity_001",
                "alert_type": "activity_analysis",
                "severity": "info",
                "title": "Activité Normale",
                "message": "Patron d'activité stable détecté - Mouvement léger régulier",
                "created_at": datetime.utcnow() - timedelta(hours=1),
                "resolved_at": None,
                "activity_data": {
                    "magnitude": 2.8,
                    "classification": "mouvement_leger",
                    "confidence": 0.85,
                    "pattern": "regular_walking"
                }
            }
        ]

        # Filtrer par sévérité si spécifié
        if severity != "all":
            activity_alerts = [a for a in activity_alerts if a["severity"] == severity]

        return {
            "patient_id": patient_id,
            "total_alerts": len(activity_alerts),
            "severity_filter": severity,
            "alerts": activity_alerts
        }

    except Exception as e:
        logger.error(f"Erreur activity alerts: {e}")
        raise HTTPException(status_code=500, detail="Erreur récupération alertes activité")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
