#!/usr/bin/env python3
"""
Configuration et modèles de données pour l'API Kidjamo
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class ActivityLevelEnum(str, Enum):
    """Énumération des niveaux d'activité"""
    REPOS = "repos"
    MOUVEMENT_LEGER = "mouvement_leger"
    ACTIVITE_INTENSE = "activite_intense"
    RISQUE_CHUTE = "risque_chute"

class AlertSeverityEnum(str, Enum):
    """Énumération des niveaux de sévérité d'alerte"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AlertTypeEnum(str, Enum):
    """Types d'alertes possibles"""
    FALL_RISK = "fall_risk"
    INTENSE_ACTIVITY = "intense_activity"
    LOW_BATTERY = "low_battery"
    DEVICE_OFFLINE = "device_offline"
    TEMPERATURE_ANOMALY = "temperature_anomaly"
    HEART_RATE_ANOMALY = "heart_rate_anomaly"
    SPO2_LOW = "spo2_low"

# === MODÈLES POUR DÉVELOPPEURS MOBILE ===

class MobileActivityCard(BaseModel):
    """Carte d'activité optimisée pour mobile"""
    emoji: str = Field(..., description="Emoji de l'activité")
    title: str = Field(..., description="Titre court")
    subtitle: str = Field(..., description="Description")
    value: str = Field(..., description="Valeur principale")
    color: str = Field(..., description="Couleur (#hex)")
    timestamp: datetime = Field(..., description="Dernière mise à jour")

class MobileAlertCard(BaseModel):
    """Carte d'alerte optimisée pour mobile"""
    id: str
    icon: str = Field(..., description="Icône d'alerte")
    title: str
    message: str
    severity: AlertSeverityEnum
    timestamp: datetime
    actionable: bool = Field(default=True, description="Peut être acquittée")
    color: str

class MobileDashboard(BaseModel):
    """Dashboard mobile complet"""
    patient_info: Dict[str, Any]
    current_activity: MobileActivityCard
    environmental: Dict[str, Any]
    alerts: List[MobileAlertCard]
    daily_stats: Dict[str, Any]
    recommendations: List[str]
    last_updated: datetime

# === MODÈLES POUR DÉVELOPPEURS WEB ===

class WebChartDataPoint(BaseModel):
    """Point de données pour graphiques web"""
    timestamp: datetime
    value: float
    label: str
    color: Optional[str] = None

class WebActivityChart(BaseModel):
    """Données de graphique d'activité pour web"""
    chart_type: str = Field(..., description="line|bar|pie|area")
    title: str
    data_points: List[WebChartDataPoint]
    x_axis_label: str
    y_axis_label: str
    colors: List[str]

class WebDashboard(BaseModel):
    """Dashboard web complet"""
    patient_id: str
    overview: Dict[str, Any]
    activity_chart: WebActivityChart
    accelerometer_chart: WebActivityChart
    alerts_summary: Dict[str, Any]
    historical_trends: List[WebChartDataPoint]
    device_status: Dict[str, Any]

# === CONFIGURATION API ===

class APIConfig:
    """Configuration de l'API"""

    # Endpoints principaux
    BASE_URL = "https://api.kidjamo.com"  # À configurer
    VERSION = "v1"

    # Rate limiting
    RATE_LIMIT_PER_MINUTE = 100
    RATE_LIMIT_BURST = 20

    # Cache
    CACHE_TTL_SECONDS = 60
    CACHE_TTL_HISTORICAL = 300

    # WebSocket
    WS_HEARTBEAT_INTERVAL = 30
    WS_MAX_CONNECTIONS = 1000

    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100

    # Couleurs pour l'interface
    ACTIVITY_COLORS = {
        "repos": "#22c55e",           # Vert
        "mouvement_leger": "#3b82f6", # Bleu
        "activite_intense": "#f97316", # Orange
        "risque_chute": "#ef4444"     # Rouge
    }

    ALERT_COLORS = {
        "low": "#10b981",      # Vert clair
        "medium": "#f59e0b",   # Jaune
        "high": "#f97316",     # Orange
        "critical": "#ef4444"  # Rouge
    }

# === HELPERS POUR DÉVELOPPEURS ===

def format_activity_for_mobile(activity_data: Dict[str, Any]) -> MobileActivityCard:
    """Convertit les données d'activité en format mobile"""
    activity_level = activity_data.get('activity', {}).get('level', 'repos')

    emoji_map = {
        'repos': '😴',
        'mouvement_leger': '🚶',
        'activite_intense': '🏃',
        'risque_chute': '⚠️'
    }

    title_map = {
        'repos': 'Au repos',
        'mouvement_leger': 'Actif',
        'activite_intense': 'Très actif',
        'risque_chute': 'Alerte'
    }

    magnitude = activity_data.get('accelerometer', {}).get('magnitude', 0)

    return MobileActivityCard(
        emoji=emoji_map.get(activity_level, '❓'),
        title=title_map.get(activity_level, 'Inconnu'),
        subtitle=activity_data.get('activity', {}).get('description', ''),
        value=f"{magnitude:.1f} m/s²",
        color=APIConfig.ACTIVITY_COLORS.get(activity_level, '#gray'),
        timestamp=datetime.fromisoformat(activity_data.get('last_updated', datetime.utcnow().isoformat()).replace('Z', '+00:00'))
    )

def format_alert_for_mobile(alert_data: Dict[str, Any]) -> MobileAlertCard:
    """Convertit une alerte en format mobile"""
    alert_type = alert_data.get('alert_type', 'unknown')

    icon_map = {
        'fall_risk': '⚠️',
        'intense_activity': '🏃',
        'low_battery': '🔋',
        'device_offline': '📱',
        'temperature_anomaly': '🌡️',
        'heart_rate_anomaly': '💓',
        'spo2_low': '🫁'
    }

    return MobileAlertCard(
        id=alert_data.get('alert_id', ''),
        icon=icon_map.get(alert_type, '⚠️'),
        title=alert_data.get('message', ''),
        message=alert_data.get('message', ''),
        severity=AlertSeverityEnum(alert_data.get('severity', 'medium')),
        timestamp=datetime.fromisoformat(alert_data.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00')),
        actionable=not alert_data.get('acknowledged', False),
        color=APIConfig.ALERT_COLORS.get(alert_data.get('severity', 'medium'), '#f59e0b')
    )

def format_history_for_web_chart(history_data: List[Dict]) -> WebActivityChart:
    """Convertit l'historique en graphique web"""
    data_points = []

    for item in history_data:
        data_points.append(WebChartDataPoint(
            timestamp=datetime.fromisoformat(item.get('timestamp', datetime.utcnow().isoformat()).replace('Z', '+00:00')),
            value=item.get('magnitude', 0),
            label=item.get('activity_level', 'unknown'),
            color=APIConfig.ACTIVITY_COLORS.get(item.get('activity_level', 'repos'), '#gray')
        ))

    return WebActivityChart(
        chart_type="line",
        title="Activité au cours du temps",
        data_points=data_points,
        x_axis_label="Temps",
        y_axis_label="Magnitude (m/s²)",
        colors=list(APIConfig.ACTIVITY_COLORS.values())
    )

# === EXEMPLES POUR DÉVELOPPEURS ===

class ExampleResponses:
    """Exemples de réponses API pour la documentation"""

    MOBILE_DASHBOARD_EXAMPLE = {
        "patient_info": {
            "patient_id": "PAT_12345678",
            "name": "Patient Demo",
            "age": 25,
            "device_id": "bracelet_001"
        },
        "current_activity": {
            "emoji": "🚶",
            "title": "Actif",
            "subtitle": "Marche lente ou gestes légers",
            "value": "2.5 m/s²",
            "color": "#3b82f6",
            "timestamp": "2025-09-11T10:30:00Z"
        },
        "environmental": {
            "temperature": 24.5,
            "comfort_level": "Confortable"
        },
        "alerts": [],
        "daily_stats": {
            "steps_estimated": 4500,
            "calories_burned": 320,
            "active_minutes": 180,
            "rest_minutes": 960
        },
        "recommendations": [
            "Votre niveau d'activité est optimal",
            "Pensez à vous hydrater",
            "Continuez vos efforts !"
        ],
        "last_updated": "2025-09-11T10:30:00Z"
    }

    WEB_CHART_EXAMPLE = {
        "chart_type": "line",
        "title": "Activité des dernières 24h",
        "data_points": [
            {
                "timestamp": "2025-09-11T08:00:00Z",
                "value": 1.2,
                "label": "repos",
                "color": "#22c55e"
            },
            {
                "timestamp": "2025-09-11T09:00:00Z",
                "value": 2.8,
                "label": "mouvement_leger",
                "color": "#3b82f6"
            }
        ],
        "x_axis_label": "Heure",
        "y_axis_label": "Magnitude (m/s²)",
        "colors": ["#22c55e", "#3b82f6", "#f97316", "#ef4444"]
    }
