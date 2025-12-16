"""
Dashboard Temps Réel IoT Patients - Architecture Kafka TEMPS RÉEL

Version adaptée de l'architecture du dashboard Kafka qui fonctionne :
- Threads daemon en arrière-plan pour consommation Kafka temps réel
- Buffers circulaires (deque) pour maintenir historique récent
- Auto-refresh avec st.rerun() pour interface réactive
- Métriques avancées avec données patients enrichies
"""

import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Imports third-party
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor

# Import Kafka avec gestion gracieuse d'erreur
try:
    from kafka import KafkaConsumer
except ImportError:
    KafkaConsumer = None

# Configuration page Streamlit
st.set_page_config(
    page_title="KIDJAMO IoT - Dashboard Patients",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Configuration logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Kafka et base de données
KAFKA_SERVERS = ['localhost:9092']

# Configuration base de données (gestion sécurisée des secrets)
try:
    DB_CONFIG = {
        'host': st.secrets["POSTGRES_HOST"],
        'port': st.secrets["POSTGRES_PORT"],
        'database': st.secrets["POSTGRES_DB"],
        'user': st.secrets["POSTGRES_USER"],
        'password': st.secrets["POSTGRES_PASSWORD"]
    }
except:
    # Fallback pour développement local
    DB_CONFIG = {
        'host': 'localhost',
        'port': '5432',
        'database': 'kidjamo-db',
        'user': 'postgres',
        'password': 'kidjamo@'
    }

class AdvancedRealTimeMonitor:
    """
    Moniteur temps réel avancé pour IoT médical.

    Combine l'architecture temps réel Kafka avec données enrichies :
    - Consommation Kafka en threads daemon
    - Enrichissement avec données patients depuis PostgreSQL
    - Buffers circulaires pour historique récent
    - Métriques avancées et alertes classifiées
    """

    def __init__(self) -> None:
        """Initialise le moniteur avec buffers et cache patients."""
        # Buffers circulaires pour données temps réel
        self.metrics_buffer = deque(maxlen=2000)  # 2000 dernières mesures
        self.alerts_buffer = deque(maxlen=200)    # 200 dernières alertes
        self.patients_cache = {}  # Cache des données patients
        self.running = False

        # Lock pour synchronisation threads
        self._lock = threading.Lock()

        # Charger données patients au démarrage
        self._load_patients_data()

        # FORCER LA GÉNÉRATION DE DONNÉES IMMÉDIATEMENT
        self._generate_initial_test_data()

    def _load_patients_data(self) -> None:
        """Charge les données patients depuis PostgreSQL pour enrichissement."""
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            query = """
            SELECT 
                p.patient_id,
                u.first_name,
                u.last_name,
                p.genotype,
                EXTRACT(YEAR FROM AGE(p.birth_date)) as age,
                u.gender,
                p.current_device_id
            FROM patients p
            JOIN users u ON p.user_id = u.user_id
            """

            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(query)
                for row in cursor.fetchall():
                    self.patients_cache[row['patient_id']] = dict(row)

            logger.info(f"✅ Loaded {len(self.patients_cache)} patients data")

        except Exception as e:
            logger.error(f"❌ Error loading patients data: {e}")
        finally:
            if 'conn' in locals():
                conn.close()

    def start_monitoring(self) -> None:
        """Démarre le monitoring temps réel avec threads Kafka ou mode test."""
        if KafkaConsumer is None:
            logger.warning("Kafka library unavailable; running in test mode")
            self._start_test_data_generation()
            return

        self.running = True

        # Vérifier si Kafka est accessible
        try:
            # Test de connexion Kafka rapide
            test_consumer = KafkaConsumer(
                bootstrap_servers=KAFKA_SERVERS,
                consumer_timeout_ms=3000  # Timeout rapide pour test
            )
            test_consumer.close()
            logger.info("✅ Kafka accessible - Mode temps réel")

            # Démarrage threads Kafka normaux
            self._start_kafka_monitoring()

        except Exception as e:
            logger.warning(f"⚠️ Kafka non accessible: {e}")
            logger.info("🔄 Démarrage en mode test avec données simulées...")
            self._start_test_data_generation()

    def _start_kafka_monitoring(self):
        """Démarre les threads Kafka normaux."""
        # Thread pour métriques IoT
        metrics_thread = threading.Thread(target=self._monitor_metrics)
        metrics_thread.daemon = True
        metrics_thread.start()

        # Thread pour alertes
        alerts_thread = threading.Thread(target=self._monitor_alerts)
        alerts_thread.daemon = True
        alerts_thread.start()

        logger.info("✅ Started advanced Kafka monitoring threads")

    def _start_test_data_generation(self):
        """Démarre la génération de données de test pour démonstration."""
        self.running = True

        # Thread pour générer des données de test
        test_thread = threading.Thread(target=self._generate_test_data)
        test_thread.daemon = True
        test_thread.start()

        logger.info("✅ Started test data generation mode")

    def _generate_initial_test_data(self):
        """Génère des données de test initiales pour peupler le dashboard."""
        import random

        # Patients de test basés sur le cache
        test_patients = []
        for i in range(8):  # 8 patients de test
            patient_id = f"test-patient-{i+1:03d}"
            patient_data = {
                'patient_id': patient_id,
                'first_name': f'Patient{i+1}',
                'last_name': f'Test{i+1}',
                'genotype': random.choice(['SS', 'SC', 'S-Beta0', 'S-Beta+']),
                'age': random.randint(5, 17),
                'gender': random.choice(['M', 'F'])
            }
            test_patients.append(patient_data)
            # Ajouter au cache
            self.patients_cache[patient_id] = patient_data

        logger.info(f"🧪 Génération de données test pour {len(test_patients)} patients")

        iteration = 0
        while self.running and iteration < 5:  # Générer des données initiales pendant 5 itérations
            try:
                iteration += 1

                # Générer des mesures pour chaque patient de test
                for i, patient in enumerate(test_patients):
                    # Simulation de signes vitaux réalistes avec variations
                    time_factor = iteration * 0.1
                    patient_factor = i * 10

                    # Valeurs de base avec variations
                    base_hr = 80 + patient_factor + 10 * random.sin(time_factor + i)
                    base_spo2 = 96 + 3 * random.sin(time_factor * 0.5 + i)
                    base_temp = 37.0 + 0.5 * random.sin(time_factor * 0.3 + i)
                    base_resp = 18 + 3 * random.sin(time_factor * 0.7 + i)

                    # Ajouter quelques variations aléatoires
                    hr_noise = random.randint(-5, 5)
                    spo2_noise = random.randint(-2, 2)
                    temp_noise = random.uniform(-0.3, 0.3)
                    resp_noise = random.randint(-2, 2)

                    with self._lock:
                        self.metrics_buffer.append({
                            'timestamp': datetime.now(),
                            'patient_id': patient['patient_id'],
                            'first_name': patient['first_name'],
                            'last_name': patient['last_name'],
                            'genotype': patient['genotype'],
                            'age': patient['age'],
                            'gender': patient['gender'],
                            'spo2': max(85, min(100, int(base_spo2 + spo2_noise))),
                            'heart_rate': max(50, min(150, int(base_hr + hr_noise))),
                            'respiratory_rate': max(12, min(30, int(base_resp + resp_noise))),
                            'temperature': round(max(35.0, min(42.0, base_temp + temp_noise)), 1),
                            'pain_scale': random.randint(0, 8),
                            'activity_level': random.randint(1, 5),
                            'hydration': random.randint(70, 100),
                            'battery_percent': random.randint(30, 100),
                            'signal_quality': random.randint(80, 100),
                            'quality_score': random.randint(85, 98)
                        })

                # Générer quelques alertes de test périodiquement
                if iteration % 10 == 0:  # Alerte toutes les 20 secondes environ
                    patient = random.choice(test_patients)
                    severities = ['low', 'medium', 'high', 'critical']
                    weights = [0.5, 0.3, 0.15, 0.05]  # Plus de faibles alertes
                    severity = random.choices(severities, weights=weights)[0]

                    alert_types = [
                        ('SpO2_low', 'SpO2 Faible'),
                        ('heart_rate_high', 'FC Élevée'),
                        ('temperature_high', 'Fièvre'),
                        ('pain_high', 'Douleur Intense'),
                        ('battery_low', 'Batterie Faible')
                    ]
                    alert_type, alert_title = random.choice(alert_types)

                    with self._lock:
                        self.alerts_buffer.append({
                            'timestamp': datetime.now(),
                            'patient_id': patient['patient_id'],
                            'first_name': patient['first_name'],
                            'last_name': patient['last_name'],
                            'genotype': patient['genotype'],
                            'alert_type': alert_type,
                            'severity': severity,
                            'title': alert_title,
                            'message': f"{alert_title} détectée pour {patient['first_name']} {patient['last_name']}",
                            'escalation_level': severities.index(severity)
                        })

                # Attendre avant la prochaine génération (2 secondes)
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Erreur génération données test: {e}")
                time.sleep(5)

    def _monitor_metrics(self) -> None:
        """Monitore les métriques avec enrichissement données patients."""
        try:
            consumer = KafkaConsumer(
                'kidjamo-iot-measurements',
                bootstrap_servers=KAFKA_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )

            logger.info("📊 Started advanced metrics monitoring from Kafka")

            for message in consumer:
                if not self.running:
                    break

                try:
                    data = message.value
                    patient_id = data.get('patient_id')
                    measurements = data.get('measurements', {})
                    quality_indicators = data.get('quality_indicators', {})

                    # Enrichissement avec données patients
                    patient_info = self.patients_cache.get(patient_id, {})

                    with self._lock:
                        self.metrics_buffer.append({
                            'timestamp': datetime.now(),
                            'patient_id': patient_id,
                            'first_name': patient_info.get('first_name', 'N/A'),
                            'last_name': patient_info.get('last_name', 'N/A'),
                            'genotype': patient_info.get('genotype', 'N/A'),
                            'age': patient_info.get('age', 0),
                            'gender': patient_info.get('gender', 'N/A'),
                            'spo2': measurements.get('spo2_pct'),
                            'heart_rate': measurements.get('freq_card'),
                            'respiratory_rate': measurements.get('freq_resp'),
                            'temperature': measurements.get('temp_corp'),
                            'pain_scale': measurements.get('pain_scale'),
                            'activity_level': measurements.get('activity_level'),
                            'hydration': measurements.get('hydration_pct'),
                            'battery_percent': measurements.get('battery_pct'),
                            'signal_quality': quality_indicators.get('signal_quality'),
                            'quality_score': quality_indicators.get('confidence_score', 0)
                        })

                except Exception as e:
                    logger.warning(f"Error parsing metrics message: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Error monitoring metrics: {e}")

    def _monitor_alerts(self) -> None:
        """Monitore les alertes avec enrichissement données patients."""
        try:
            consumer = KafkaConsumer(
                'kidjamo-iot-alerts',
                bootstrap_servers=KAFKA_SERVERS,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True
            )

            logger.info("🚨 Started advanced alerts monitoring from Kafka")

            for message in consumer:
                if not self.running:
                    break

                try:
                    alert = message.value
                    patient_id = alert.get('patient_id')
                    patient_info = self.patients_cache.get(patient_id, {})

                    with self._lock:
                        self.alerts_buffer.append({
                            'timestamp': datetime.now(),
                            'patient_id': patient_id,
                            'first_name': patient_info.get('first_name', 'N/A'),
                            'last_name': patient_info.get('last_name', 'N/A'),
                            'genotype': patient_info.get('genotype', 'N/A'),
                            'alert_type': alert.get('alert_type'),
                            'severity': alert.get('severity'),
                            'title': alert.get('title'),
                            'message': alert.get('message'),
                            'escalation_level': alert.get('escalation_level', 0)
                        })

                except Exception as e:
                    logger.warning(f"Error parsing alert message: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Error monitoring alerts: {e}")

    def get_recent_metrics(self, minutes: int = 10) -> List[Dict]:
        """Récupère les métriques récentes avec thread safety."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            return [m for m in self.metrics_buffer if m['timestamp'] > cutoff]

    def get_recent_alerts(self, minutes: int = 60) -> List[Dict]:
        """Récupère les alertes récentes avec thread safety."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            return [a for a in self.alerts_buffer if a['timestamp'] > cutoff]

    def get_patients_overview(self) -> pd.DataFrame:
        """Génère vue d'ensemble des patients depuis le buffer temps réel."""
        with self._lock:
            if not self.metrics_buffer:
                return pd.DataFrame()

            # Grouper par patient et prendre dernière mesure
            patients_data = {}
            for metric in self.metrics_buffer:
                patient_id = metric.get('patient_id')
                if patient_id:
                    if patient_id not in patients_data or metric['timestamp'] > patients_data[patient_id]['timestamp']:
                        patients_data[patient_id] = metric

            # Calculer alertes par patient
            recent_alerts = self.get_recent_alerts(60)  # 1 heure
            alerts_by_patient = {}
            critical_alerts_by_patient = {}

            for alert in recent_alerts:
                patient_id = alert.get('patient_id')
                if patient_id:
                    alerts_by_patient[patient_id] = alerts_by_patient.get(patient_id, 0) + 1
                    if alert.get('severity') == 'critical':
                        critical_alerts_by_patient[patient_id] = critical_alerts_by_patient.get(patient_id, 0) + 1

            # Construire DataFrame
            overview_data = []
            for patient_id, data in patients_data.items():
                current_time = datetime.now()
                last_measurement = data['timestamp']
                time_diff = (current_time - last_measurement).total_seconds() / 60

                # Statut de connexion
                if time_diff <= 5:
                    status = 'ONLINE'
                elif time_diff <= 30:
                    status = 'WARNING'
                else:
                    status = 'OFFLINE'

                overview_data.append({
                    'patient_id': patient_id,
                    'first_name': data.get('first_name', 'N/A'),
                    'last_name': data.get('last_name', 'N/A'),
                    'genotype': data.get('genotype', 'N/A'),
                    'age': data.get('age', 0),
                    'gender': data.get('gender', 'N/A'),
                    'connection_status': status,
                    'last_measurement': last_measurement,
                    'heart_rate_bpm': data.get('heart_rate'),
                    'spo2_percent': data.get('spo2'),
                    'temperature_celsius': data.get('temperature'),
                    'pain_scale': data.get('pain_scale'),
                    'battery_percent': data.get('battery_percent'),
                    'signal_quality': data.get('signal_quality'),
                    'alerts_1h': alerts_by_patient.get(patient_id, 0),
                    'critical_alerts_1h': critical_alerts_by_patient.get(patient_id, 0)
                })

            return pd.DataFrame(overview_data)

    def get_patient_measurements(self, patient_id: str, minutes: int = 60) -> pd.DataFrame:
        """Récupère l'historique d'un patient depuis le buffer."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with self._lock:
            patient_metrics = [
                m for m in self.metrics_buffer
                if m.get('patient_id') == patient_id and m['timestamp'] > cutoff
            ]
            return pd.DataFrame(patient_metrics)

    def stop_monitoring(self) -> None:
        """Arrête le monitoring."""
        self.running = False
        logger.info("🛑 Stopped advanced monitoring")

# Instance globale du moniteur avec cache Streamlit
@st.cache_resource
def get_advanced_monitor() -> AdvancedRealTimeMonitor:
    """Factory function cached pour singleton monitor avancé."""
    monitor = AdvancedRealTimeMonitor()
    monitor.start_monitoring()
    return monitor

def create_patient_vitals_chart(df: pd.DataFrame, patient_name: str) -> go.Figure:
    """Crée graphique signes vitaux pour un patient."""
    if df.empty:
        return go.Figure()

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Température (°C)', 'Fréquence Cardiaque (bpm)',
                       'SpO2 (%)', 'Fréquence Respiratoire (/min)'),
        vertical_spacing=0.12
    )

    # Température
    if 'temperature' in df.columns and not df['temperature'].isna().all():
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['temperature'],
            mode='lines+markers', name='Température',
            line=dict(color='orange')), row=1, col=1)
        fig.add_hline(y=38.0, line_dash="dash", line_color="red", row=1, col=1)

    # Fréquence cardiaque
    if 'heart_rate' in df.columns and not df['heart_rate'].isna().all():
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['heart_rate'],
            mode='lines+markers', name='FC',
            line=dict(color='red')), row=1, col=2)
        fig.add_hline(y=150, line_dash="dash", line_color="red", row=1, col=2)
        fig.add_hline(y=50, line_dash="dash", line_color="red", row=1, col=2)

    # SpO2
    if 'spo2' in df.columns and not df['spo2'].isna().all():
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['spo2'],
            mode='lines+markers', name='SpO2',
            line=dict(color='green')), row=2, col=1)
        fig.add_hline(y=90, line_dash="dash", line_color="red", row=2, col=1)

    # Fréquence respiratoire
    if 'respiratory_rate' in df.columns and not df['respiratory_rate'].isna().all():
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['respiratory_rate'],
            mode='lines+markers', name='FR',
            line=dict(color='teal')), row=2, col=2)
        fig.add_hline(y=30, line_dash="dash", line_color="red", row=2, col=2)

    fig.update_layout(
        title=f"Signes Vitaux - {patient_name}",
        height=600,
        showlegend=False
    )

    return fig

def highlight_alerts(row):
    """Fonction de coloration pour alertes selon gravité."""
    styles = []
    for col in row.index:
        if col == 'Gravité':
            if row[col] == 'critical':
                style = 'background-color: #ffcccc; font-weight: bold; color: #721c24'
            elif row[col] == 'alert':
                style = 'background-color: #fff3cd; color: #856404'
            elif row[col] == 'warn':
                style = 'background-color: #f8f9fa; color: #6c757d'
            else:
                style = ''
        else:
            style = ''
        styles.append(style)
    return styles

def main() -> None:
    """Interface principale Streamlit avec architecture temps réel."""

    st.title("🏥 KIDJAMO IoT - Dashboard Patients Temps Réel")

    # === INDICATEUR DE STATUS ===
    monitor = get_advanced_monitor()

    # Vérifier si les données sont disponibles
    recent_metrics = monitor.get_recent_metrics(5)
    if recent_metrics:
        st.success(f"✅ Données temps réel actives - {len(recent_metrics)} mesures récentes")
    else:
        st.warning("⚠️ Aucune donnée détectée - Initialisation en cours...")
        st.info("Le système génère des données de test - Patientez 10 secondes...")

    st.markdown("---")

    # === SIDEBAR : Configuration ===
    st.sidebar.title("⚙️ Configuration")

    # Configuration fenêtre temporelle
    time_window = st.sidebar.selectbox(
        "Fenêtre temporelle (minutes)",
        [5, 10, 15, 30, 60, 120],
        index=2  # 15 min par défaut
    )

    # Configuration intervalle auto-refresh
    refresh_interval = st.sidebar.selectbox(
        "Auto-refresh (secondes)",
        [3, 5, 10, 15],
        index=0  # 3s par défaut pour plus de réactivité
    )

    # === DEBUG INFO ===
    with st.sidebar.expander("🔧 Debug Info"):
        recent_metrics = monitor.get_recent_metrics(time_window)
        recent_alerts = monitor.get_recent_alerts(60)
        patients_df = monitor.get_patients_overview()

        st.write(f"Métriques buffer: {len(monitor.metrics_buffer)}")
        st.write(f"Alertes buffer: {len(monitor.alerts_buffer)}")
        st.write(f"Patients cache: {len(monitor.patients_cache)}")
        st.write(f"Running: {monitor.running}")
        st.write(f"Dernière mesure: {datetime.now().strftime('%H:%M:%S')}")

    # === MÉTRIQUES GÉNÉRALES ===
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        active_patients = len(patients_df[patients_df['connection_status'] == 'ONLINE']) if not patients_df.empty else 0
        st.metric("Patients Actifs", active_patients)

    with col2:
        total_alerts = len(recent_alerts)
        st.metric("Alertes (1h)", total_alerts)

    with col3:
        critical_alerts = len([a for a in recent_alerts if a.get('severity') == 'critical'])
        st.metric("Alertes Critiques", critical_alerts)

    with col4:
        avg_quality = sum(m.get('quality_score', 0) for m in recent_metrics) / len(recent_metrics) if recent_metrics else 0
        st.metric("Qualité Moyenne", f"{avg_quality:.1f}%")

    st.markdown("---")

    # === TABLEAU PATIENTS ===
    st.subheader("👥 Vue d'Ensemble Patients")

    if not patients_df.empty:
        # Filtres
        col_filter1, col_filter2 = st.columns(2)

        with col_filter1:
            status_filter = st.selectbox(
                "Filtrer par statut",
                ["Tous", "ONLINE", "WARNING", "OFFLINE"]
            )

        with col_filter2:
            genotype_filter = st.selectbox(
                "Filtrer par génotype",
                ["Tous"] + list(patients_df['genotype'].unique()) if 'genotype' in patients_df.columns else ["Tous"]
            )

        # Application des filtres
        filtered_df = patients_df.copy()
        if status_filter != "Tous":
            filtered_df = filtered_df[filtered_df['connection_status'] == status_filter]
        if genotype_filter != "Tous":
            filtered_df = filtered_df[filtered_df['genotype'] == genotype_filter]

        # Affichage tableau avec colonnes sélectionnées
        display_columns = [
            'first_name', 'last_name', 'genotype', 'age', 'connection_status',
            'heart_rate_bpm', 'spo2_percent', 'temperature_celsius',
            'alerts_1h', 'critical_alerts_1h'
        ]

        available_columns = [col for col in display_columns if col in filtered_df.columns]
        st.dataframe(
            filtered_df[available_columns],
            use_container_width=True,
            height=400
        )

    else:
        st.info("⏳ Initialisation des données patients - Actualisez dans quelques secondes...")

    st.markdown("---")

    # === ALERTES RÉCENTES ===
    st.subheader("🚨 Alertes Récentes")

    if recent_alerts:
        alerts_df = pd.DataFrame(recent_alerts)

        # Formatage pour affichage
        display_alerts = alerts_df.copy()
        display_alerts['patient_name'] = display_alerts['first_name'] + ' ' + display_alerts['last_name']
        display_alerts['time_ago'] = ((datetime.now() - display_alerts['timestamp']).dt.total_seconds() / 60).round(1).astype(str) + ' min'

        # Sélection colonnes
        alert_columns = ['patient_name', 'genotype', 'severity', 'alert_type', 'title', 'time_ago']
        available_alert_columns = [col for col in alert_columns if col in display_alerts.columns]

        show_alerts = display_alerts[available_alert_columns].copy()
        show_alerts.columns = ['Patient', 'Génotype', 'Gravité', 'Type', 'Titre', 'Il y a'][:len(available_alert_columns)]

        # Tableau avec coloration
        styled_alerts = show_alerts.style.apply(highlight_alerts, axis=1)
        st.dataframe(styled_alerts, use_container_width=True)

    else:
        st.info("Aucune alerte récente")

    # === DÉTAIL PATIENT (Expandeur) ===
    if not patients_df.empty:
        with st.expander("📊 Détail Patient - Signes Vitaux"):
            patient_options = (patients_df['first_name'] + ' ' + patients_df['last_name'] + ' (' + patients_df['patient_id'].str[:8] + '...)').tolist()

            if patient_options:
                selected_patient = st.selectbox("Sélectionner un patient", patient_options)

                if selected_patient:
                    # Extraire patient_id
                    patient_idx = patient_options.index(selected_patient)
                    selected_patient_id = patients_df.iloc[patient_idx]['patient_id']
                    patient_name = f"{patients_df.iloc[patient_idx]['first_name']} {patients_df.iloc[patient_idx]['last_name']}"

                    # Charger données patient
                    patient_data = monitor.get_patient_measurements(selected_patient_id, time_window)

                    if not patient_data.empty:
                        # Graphique signes vitaux
                        chart = create_patient_vitals_chart(patient_data, patient_name)
                        st.plotly_chart(chart, use_container_width=True)

                        # Métriques récentes
                        latest = patient_data.iloc[-1] if not patient_data.empty else None
                        if latest is not None:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("SpO2", f"{latest.get('spo2', 'N/A')}%")
                            with col2:
                                st.metric("FC", f"{latest.get('heart_rate', 'N/A')} bpm")
                            with col3:
                                st.metric("T°", f"{latest.get('temperature', 'N/A')}°C")
                            with col4:
                                st.metric("Qualité", f"{latest.get('signal_quality', 'N/A')}%")
                    else:
                        st.info(f"Aucune donnée récente pour {patient_name}")

    # === AUTO-REFRESH avec feedback ===
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Actualiser maintenant"):
        st.rerun()

    # Auto-refresh automatique
    placeholder = st.empty()
    with placeholder:
        st.info(f"🔄 Prochaine actualisation dans {refresh_interval}s...")

    time.sleep(refresh_interval)
    st.rerun()

if __name__ == "__main__":
    main()
