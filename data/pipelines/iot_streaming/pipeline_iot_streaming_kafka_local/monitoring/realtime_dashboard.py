"""
lÉtape Visualisation — Streamlit lit Kafka et affiche métriques/alertes temps réel.

Rôle :
    Dashboard de monitoring en temps réel pour pipeline IoT Kidjamo.
    Surveille les métriques critiques du système et des patients via
    consommation Kafka et appels API pour observabilité complète.

Objectifs :
    - Lecture topics Kafka (measurements, alerts) en arrière-plan
    - Affichage graphiques temps réel des signes vitaux (SpO2, FC, T°, FR)
    - Tableau des alertes récentes avec classification par sévérité
    - Métriques système (API health, patients actifs, qualité signal)
    - Interface Streamlit responsive avec auto-refresh configurable

Entrées :
    - Topics Kafka : kidjamo-iot-measurements, kidjamo-iot-alerts
    - Endpoint API : /health pour statut système
    - Configuration : buffer mémoire (deque), fenêtres temporelles
    - Variables d'environnement : KAFKA_SERVERS, API_ENDPOINT

Sorties :
    - Graphiques Plotly interactifs (température, FC, SpO2, fréquence respiratoire)
    - Tableau alertes avec codes couleur sévérité (🔴🟠🟡🟢)
    - Métriques agrégées (patients actifs, qualité moyenne, alertes critiques)
    - Interface web Streamlit sur port configuré

Effets de bord :
    - Threads de consommation Kafka en arrière-plan (daemon=True)
    - Buffers mémoire circulaires (deque maxlen) pour historique
    - Appels HTTP GET vers API health check
    - Auto-refresh Streamlit selon intervalle configuré

Garanties :
    Seuils UI (lignes hachurées) et mise en forme inchangés ; fenêtres
    temporelles et tailles de buffer identiques ; aucun side-effect data
    (lecture seule) ; threads daemon pour arrêt propre.
"""

# Imports standard library (triés alphabétiquement)
import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Imports third-party (triés alphabétiquement)
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Import Kafka avec gestion gracieuse d'erreur
try:
    from kafka import KafkaConsumer
except ImportError:
    KafkaConsumer = None

# Configuration Kafka et API - ne pas modifier ces valeurs
KAFKA_SERVERS = ['localhost:9092']
API_ENDPOINT = "http://localhost:8001"

# Configuration logging avec logger nommé
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RealTimeMonitor:
    """
    Moniteur en temps réel pour la pipeline IoT.

    Gère la consommation Kafka en arrière-plan via threads daemon
    et maintient des buffers circulaires pour historique récent.
    """

    def __init__(self) -> None:
        """
        Initialise le moniteur avec buffers vides.

        Buffers circulaires (deque) :
        - metrics_buffer : 1000 dernières mesures IoT
        - alerts_buffer : 100 dernières alertes
        - device_status : statut technique par device_id
        """
        # Buffer circulaire pour mesures IoT (taille fixe 1000)
        self.metrics_buffer = deque(maxlen=1000)
        # Buffer circulaire pour alertes (taille fixe 100)
        self.alerts_buffer = deque(maxlen=100)
        # Statut devices par device_id (dict)
        self.device_status: Dict[str, Dict] = {}
        self.running = False

    def start_monitoring(self) -> None:
        """
        Démarre le monitoring en arrière-plan via threads daemon.

        Threads créés :
        - metrics_thread : consommation topic measurements
        - alerts_thread : consommation topic alerts

        Les threads sont marqués daemon=True pour arrêt propre avec Streamlit.
        """
        if KafkaConsumer is None:
            logger.warning("Kafka library unavailable; running in offline mode")
            return

        self.running = True

        # Thread pour écouter les métriques IoT (daemon pour arrêt propre)
        metrics_thread = threading.Thread(target=self._monitor_metrics)
        metrics_thread.daemon = True
        metrics_thread.start()

        # Thread pour écouter les alertes critiques (daemon pour arrêt propre)
        alerts_thread = threading.Thread(target=self._monitor_alerts)
        alerts_thread.daemon = True
        alerts_thread.start()

        logger.info("✅ Started Kafka monitoring threads")

    def _monitor_metrics(self) -> None:
        """
        Monitore les métriques depuis topic kidjamo-iot-measurements.

        Parse les messages JSON et extrait :
        - patient_id, timestamp pour traçabilité
        - signes vitaux (SpO2, FC, FR, température) pour graphiques
        - quality_score pour métriques qualité globale

        Gestion d'erreur : continue en cas d'erreur Kafka isolée.
        """
        try:
            # Configuration consumer avec offset latest (données récentes uniquement)
            consumer = KafkaConsumer(
                'kidjamo-iot-measurements',
                bootstrap_servers=KAFKA_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',  # Données récentes seulement
                enable_auto_commit=True
            )

            logger.info("📊 Started metrics monitoring from Kafka")

            for message in consumer:
                if not self.running:
                    break

                try:
                    data = message.value
                    # Extraction des mesures selon structure API inchangée
                    measurements = data.get('measurements', {})
                    quality_indicators = data.get('quality_indicators', {})

                    # Ajout au buffer circulaire (auto-éviction anciennes données)
                    self.metrics_buffer.append({
                        'timestamp': datetime.now(),
                        'patient_id': data.get('patient_id'),
                        'spo2': measurements.get('spo2_pct'),
                        'heart_rate': measurements.get('freq_card'),
                        'respiratory_rate': measurements.get('freq_resp'),
                        'temperature': measurements.get('temp_corp'),
                        'quality_score': quality_indicators.get('confidence_score', 0)
                    })
                except Exception as e:
                    logger.warning(f"Error parsing metrics message: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Error monitoring metrics: {e}")

    def _monitor_alerts(self) -> None:
        """
        Monitore les alertes depuis topic kidjamo-iot-alerts.

        Parse les alertes critiques et extrait :
        - patient_id, alert_type, severity pour classification
        - message d'alerte pour affichage utilisateur
        - timestamp pour tri chronologique

        Gestion d'erreur : continue en cas d'erreur Kafka isolée.
        """
        try:
            # Configuration consumer avec offset latest (alertes récentes uniquement)
            consumer = KafkaConsumer(
                'kidjamo-iot-alerts',
                bootstrap_servers=KAFKA_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',  # Alertes récentes seulement
                enable_auto_commit=True
            )

            logger.info("🚨 Started alerts monitoring from Kafka")

            for message in consumer:
                if not self.running:
                    break

                try:
                    alert = message.value
                    # Ajout au buffer circulaire alertes
                    self.alerts_buffer.append({
                        'timestamp': datetime.now(),
                        'patient_id': alert.get('patient_id'),
                        'type': alert.get('alert_type'),
                        'severity': alert.get('severity'),
                        'message': alert.get('message')
                    })
                except Exception as e:
                    logger.warning(f"Error parsing alert message: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Error monitoring alerts: {e}")

    def get_recent_metrics(self, minutes: int = 10) -> List[Dict]:
        """
        Récupère les métriques des N dernières minutes.

        Filtre le buffer selon fenêtre temporelle pour graphiques
        temps réel avec historique configurable.

        Args:
            minutes: Fenêtre temporelle en minutes (défaut: 10)

        Returns:
            List[Dict]: Métriques filtrées par timestamp
        """
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [m for m in self.metrics_buffer if m['timestamp'] > cutoff]

    def get_recent_alerts(self, minutes: int = 60) -> List[Dict]:
        """
        Récupère les alertes des N dernières minutes.

        Filtre le buffer selon fenêtre temporelle pour tableau
        alertes récentes avec historique configurable.

        Args:
            minutes: Fenêtre temporelle en minutes (défaut: 60)

        Returns:
            List[Dict]: Alertes filtrées par timestamp
        """
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [a for a in self.alerts_buffer if a['timestamp'] > cutoff]

    def stop_monitoring(self) -> None:
        """Arrête le monitoring (threads daemon se terminent automatiquement)."""
        self.running = False
        logger.info("🛑 Stopped monitoring")


# Instance globale du moniteur avec cache Streamlit
@st.cache_resource
def get_monitor() -> RealTimeMonitor:
    """
    Factory function cached par Streamlit pour singleton monitor.

    Démarre automatiquement le monitoring à la première utilisation.
    Le cache Streamlit garantit une seule instance par session.

    Returns:
        RealTimeMonitor: Instance singleton du moniteur
    """
    monitor = RealTimeMonitor()
    monitor.start_monitoring()
    return monitor


def check_api_health() -> Tuple[bool, Dict]:
    """
    Vérifie la santé de l'API d'ingestion.

    Appelle l'endpoint /health pour statut Kafka, compteurs et uptime.
    Timeout court (5s) pour éviter blocage interface utilisateur.

    Returns:
        tuple: (is_healthy: bool, status_data: Dict)
    """
    try:
        response = requests.get(f"{API_ENDPOINT}/health", timeout=5)
        return response.status_code == 200, response.json()
    except requests.RequestException as e:
        logger.warning(f"API health check failed: {e}")
        return False, {"status": "unreachable", "error": str(e)}


def create_vitals_chart(metrics_data: List[Dict]) -> go.Figure:
    """
    Crée un graphique de la température corporelle temps réel.

    Affiche courbe température avec seuils médicaux :
    - Ligne rouge pointillée : fièvre (≥ 38°C)
    - Ligne bleue pointillée : hypothermie (≤ 35°C)

    Args:
        metrics_data: Données de mesures récentes

    Returns:
        go.Figure: Graphique Plotly configuré
    """
    if not metrics_data:
        return go.Figure()

    df = pd.DataFrame(metrics_data)
    # Filtre données avec température valide
    if 'temperature' not in df.columns:
        return go.Figure()
    df = df[df['temperature'].notna()]

    fig = go.Figure()

    # Courbe principale température
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['temperature'],
        mode='lines+markers',
        name='Température (°C)',
        line=dict(color='orange'),
        hovertemplate='Température: %{y}°C<br>%{x}<extra></extra>'
    ))

    # Seuils médicaux inchangés pour cohérence clinique
    fig.add_hline(y=38.0, line_dash="dash", line_color="red",
                  annotation_text="Fièvre (≥ 38°C)")
    fig.add_hline(y=35.0, line_dash="dot", line_color="blue",
                  annotation_text="Hypothermie (≤ 35°C)")

    fig.update_layout(
        title="Température Corporelle - Temps Réel",
        xaxis_title="Temps",
        yaxis_title="Température (°C)",
        height=400
    )

    return fig


def create_heart_rate_chart(metrics_data: List[Dict]) -> go.Figure:
    """
    Crée un graphique de la fréquence cardiaque temps réel.

    Affiche courbe FC avec zones critiques :
    - Ligne rouge pointillée : FC Max (150 bpm)
    - Ligne rouge pointillée : FC Min (50 bpm)

    Args:
        metrics_data: Données de mesures récentes

    Returns:
        go.Figure: Graphique Plotly configuré
    """
    if not metrics_data:
        return go.Figure()

    df = pd.DataFrame(metrics_data)
    if 'heart_rate' not in df.columns:
        return go.Figure()
    df = df[df['heart_rate'].notna()]

    fig = go.Figure()

    # Courbe principale fréquence cardiaque
    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['heart_rate'],
        mode='lines+markers',
        name='Fréquence Cardiaque',
        line=dict(color='red'),
        hovertemplate='FC: %{y} bpm<br>%{x}<extra></extra>'
    ))

    # Zones critiques inchangées pour cohérence médicale
    fig.add_hline(y=150, line_dash="dash", line_color="red",
                  annotation_text="FC Max (150 bpm)")
    fig.add_hline(y=50, line_dash="dash", line_color="red",
                  annotation_text="FC Min (50 bpm)")

    fig.update_layout(
        title="Fréquence Cardiaque - Temps Réel",
        xaxis_title="Temps",
        yaxis_title="Fréquence (bpm)",
        height=400
    )

    return fig


def create_spo2_chart(metrics_data: List[Dict]) -> go.Figure:
    """
    Crée un graphique SpO2 en temps réel.

    Affiche courbe saturation oxygène avec seuil critique :
    - Ligne rouge pointillée : SpO2 Critique (≤ 90%)
    - Échelle Y fixe : 75-100% pour cohérence visuelle

    Args:
        metrics_data: Données de mesures récentes

    Returns:
        go.Figure: Graphique Plotly configuré
    """
    if not metrics_data:
        return go.Figure()

    df = pd.DataFrame(metrics_data)
    if 'spo2' not in df.columns:
        return go.Figure()
    df = df[df['spo2'].notna()]

    fig = go.Figure()

    # Courbe principale SpO2
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['spo2'],
            mode='lines+markers',
            name='SpO2 (%)',
            line=dict(color='green'),
            hovertemplate='SpO2: %{y}%<br>%{x}<extra></extra>'
        )
    )

    # Seuil critique inchangé pour cohérence médicale
    fig.add_hline(y=90, line_dash="dash", line_color="red",
                  annotation_text="SpO2 Critique (≤ 90%)")

    fig.update_layout(
        title="Saturation en Oxygène (SpO2) - Temps Réel",
        xaxis_title="Temps",
        yaxis_title="SpO2 (%)",
        height=400,
        yaxis=dict(range=[75, 100])  # Échelle fixe pour cohérence visuelle
    )

    return fig


def create_respiratory_rate_chart(metrics_data: List[Dict]) -> go.Figure:
    """
    Crée un graphique de la fréquence respiratoire temps réel.

    Affiche courbe FR avec seuils indicatifs :
    - Ligne rouge pointillée : Tachypnée (≥ 30/min)
    - Ligne orange pointillée : Bradypnée (≤ 8/min)

    Args:
        metrics_data: Données de mesures récentes

    Returns:
        go.Figure: Graphique Plotly configuré
    """
    if not metrics_data:
        return go.Figure()

    df = pd.DataFrame(metrics_data)
    if 'respiratory_rate' not in df.columns:
        return go.Figure()
    df = df[df['respiratory_rate'].notna()]

    fig = go.Figure()

    # Courbe principale fréquence respiratoire
    fig.add_trace(
        go.Scatter(
            x=df['timestamp'],
            y=df['respiratory_rate'],
            mode='lines+markers',
            name='Fréquence Respiratoire (/min)',
            line=dict(color='teal'),
            hovertemplate='FR: %{y} /min<br>%{x}<extra></extra>'
        )
    )

    # Seuils indicatifs inchangés pour cohérence médicale
    fig.add_hline(y=30, line_dash="dash", line_color="red",
                  annotation_text="Tachypnée (≥ 30/min)")
    fig.add_hline(y=8, line_dash="dash", line_color="orange",
                  annotation_text="Bradypnée (≤ 8/min)")

    fig.update_layout(
        title="Fréquence Respiratoire - Temps Réel",
        xaxis_title="Temps",
        yaxis_title="Respirations (/min)",
        height=400
    )

    return fig


def _get_severity_color(severity: str) -> str:
    """
    Retourne l'émoji couleur selon la sévérité.

    Mapping inchangé pour cohérence visuelle :
    - critical : 🔴 rouge
    - high : 🟠 orange
    - medium : 🟡 jaune
    - low : 🟢 vert

    Args:
        severity: Niveau de sévérité de l'alerte

    Returns:
        str: Émoji correspondant à la sévérité
    """
    colors = {
        'critical': '🔴',
        'high': '🟠',
        'medium': '🟡',
        'low': '🟢'
    }
    return colors.get(severity, '⚪')  # Blanc par défaut


def display_alerts_table(alerts_data: List[Dict]) -> None:
    """
    Affiche le tableau des alertes avec codes couleur sévérité.

    Codes couleur par sévérité inchangés pour cohérence :
    - critical : 🔴 rouge
    - high : 🟠 orange
    - medium : 🟡 jaune
    - low : 🟢 vert

    Colonnes affichées : Heure, Patient (masqué), Sévérité, Type, Message

    Args:
        alerts_data: Liste des alertes récentes
    """
    if not alerts_data:
        st.info("Aucune alerte récente")
        return

    df = pd.DataFrame(alerts_data)

    # Formatage tableau avec masquage partiel patient_id pour RGPD
    df['Sévérité'] = df['severity'].apply(lambda x: f"{_get_severity_color(x)} {x.upper()}")
    df['Patient'] = df['patient_id'].apply(lambda x: x[:8] + "..." if x else "N/A")
    df['Heure'] = df['timestamp'].apply(lambda x: x.strftime("%H:%M:%S"))
    df['Type'] = df['type']
    df['Message'] = df['message']

    # Affichage tableau Streamlit avec largeur conteneur
    st.dataframe(
        df[['Heure', 'Patient', 'Sévérité', 'Type', 'Message']],
        use_container_width=True
    )


def _display_metrics_summary(recent_metrics: List[Dict]) -> None:
    """
    Affiche les métriques résumées en 4 colonnes.

    Calcule et affiche :
    - Nombre de patients actifs (last 10 min)
    - Qualité moyenne des signaux
    - Nombre d'alertes critiques (last hour)
    - Uptime API en secondes

    Args:
        recent_metrics: Liste des métriques récentes pour calculs
    """
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        # Patients actifs dans les 10 dernières minutes
        active_patients = len(set(m['patient_id'] for m in recent_metrics if m['patient_id']))
        st.metric("Patients Actifs", active_patients)

    with col2:
        # Qualité moyenne des signaux
        quality_scores = [m['quality_score'] for m in recent_metrics if m['quality_score'] is not None]
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
        st.metric("Qualité Moyenne", f"{avg_quality:.1f}%")

    with col3:
        # Nombre d'alertes critiques (dernière heure)
        monitor = get_monitor()
        recent_alerts = monitor.get_recent_alerts(60)
        critical_alerts = len([a for a in recent_alerts if a['severity'] == 'critical'])
        st.metric("Alertes Critiques", critical_alerts)

    with col4:
        # Statut API avec uptime
        api_healthy, api_status = check_api_health()
        if api_healthy:
            uptime = api_status.get('uptime_s', 0)
            st.metric("API Uptime", f"{uptime:.0f}s")
        else:
            st.metric("API Status", "❌ Offline")


def main() -> None:
    """
    Interface principale Streamlit avec layout responsive.

    Structure :
    - Configuration page (titre, icône, layout wide)
    - Sidebar : paramètres et health check API
    - Métriques principales (4 colonnes)
    - Graphiques vitaux (2x2 grid)
    - Tableau alertes récentes
    - Auto-refresh selon intervalle configuré
    """
    # Configuration page Streamlit
    st.set_page_config(
        page_title="Kidjamo IoT Monitor",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("Kidjamo IoT - Monitoring Temps Réel")
    st.markdown("---")

    # === SIDEBAR : Configuration et santé système ===
    st.sidebar.title("Configuration")

    # Vérification santé API avec affichage statut
    api_healthy, api_status = check_api_health()
    if api_healthy:
        st.sidebar.success("✅ API connectée")
        # Affichage détails API si disponibles
        if 'processed_messages' in api_status:
            st.sidebar.metric("Messages traités", api_status['processed_messages'])
        if 'kafka_connected' in api_status:
            kafka_status = "✅ Connecté" if api_status['kafka_connected'] else "❌ Déconnecté"
            st.sidebar.write(f"Kafka: {kafka_status}")
    else:
        st.sidebar.error("❌ API déconnectée")
        st.sidebar.write(f"Erreur: {api_status.get('error', 'Unknown')}")

    # Configuration fenêtre temporelle pour graphiques
    time_window = st.sidebar.selectbox(
        "Fenêtre temporelle",
        [5, 10, 15, 30, 60],
        index=1  # 10 min par défaut
    )

    # Configuration intervalle auto-refresh
    refresh_interval = st.sidebar.selectbox(
        "Auto-refresh (secondes)",
        [5, 10, 15, 30, 60],
        index=2  # 15s par défaut
    )

    # === SECTION PRINCIPALE ===

    # Récupération données du moniteur
    monitor = get_monitor()
    recent_metrics = monitor.get_recent_metrics(time_window)
    recent_alerts = monitor.get_recent_alerts(60)  # Alertes sur 1h

    # Métriques résumées en 4 colonnes
    _display_metrics_summary(recent_metrics)
    st.markdown("---")

    # === GRAPHIQUES VITAUX (2x2 grid) ===
    st.subheader("📊 Signes Vitaux - Temps Réel")

    # Première ligne : Température et Fréquence Cardiaque
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(create_vitals_chart(recent_metrics), use_container_width=True, key="chart_temp")
    with col2:
        st.plotly_chart(create_heart_rate_chart(recent_metrics), use_container_width=True, key="chart_hr")

    # Deuxième ligne : SpO2 et Fréquence Respiratoire
    col3, col4 = st.columns(2)
    with col3:
        st.plotly_chart(create_spo2_chart(recent_metrics), use_container_width=True, key="chart_spo2")
    with col4:
        st.plotly_chart(create_respiratory_rate_chart(recent_metrics), use_container_width=True, key="chart_resp")

    st.markdown("---")

    # === TABLEAU ALERTES RÉCENTES ===
    st.subheader("🚨 Alertes Récentes")
    display_alerts_table(recent_alerts)

    # === DÉTAILS PATIENTS (Expandeur) ===
    with st.expander("👥 Détails Patients"):
        if recent_metrics:
            # Groupement par patient avec dernières valeurs
            patients_data = {}
            for metric in recent_metrics:
                patient_id = metric.get('patient_id')
                if patient_id:
                    if patient_id not in patients_data:
                        patients_data[patient_id] = []
                    patients_data[patient_id].append(metric)

            # Affichage sous-métriques par patient
            for patient_id, metrics in patients_data.items():
                st.write(f"**Patient:** {patient_id[:8]}...")
                last_metric = max(metrics, key=lambda x: x['timestamp'])

                # Métriques en colonnes pour chaque patient
                pcol1, pcol2, pcol3, pcol4 = st.columns(4)
                with pcol1:
                    st.metric("SpO2", f"{last_metric.get('spo2', 'N/A')}%")
                with pcol2:
                    st.metric("FC", f"{last_metric.get('heart_rate', 'N/A')} bpm")
                with pcol3:
                    st.metric("T°", f"{last_metric.get('temperature', 'N/A')}°C")
                with pcol4:
                    st.metric("Qualité", f"{last_metric.get('quality_score', 'N/A')}%")
                st.markdown("---")
        else:
            st.info("Aucune donnée patient disponible")

    # === AUTO-REFRESH ===
    # Actualisation automatique selon intervalle configuré
    time.sleep(refresh_interval)
    st.rerun()


# === POINT D'ENTRÉE PRINCIPAL ===
if __name__ == "__main__":
    main()
