#!/usr/bin/env python3
"""
🚨 Kidjamo - Dashboard Temps Réel (Streamlit)
Surveillance IoT en temps réel via AWS Kinesis avec détection d'alertes
VERSION RÉVISÉE COMPLÈTEMENT
"""

import streamlit as st
import boto3
import json
import base64
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time
import numpy as np
import math
from config import AWS_CONFIG, ALERT_THRESHOLDS

class KinesisRealtimeProcessor:
    """Processeur temps réel pour les données Kinesis - VERSION SIMPLIFIÉE"""

    def __init__(self):
        try:
            self.kinesis_client = boto3.client(
                'kinesis',
                region_name=AWS_CONFIG['region_name']
            )
            self.stream_name = AWS_CONFIG['kinesis_stream_name']
            self.connection_status = "connected"
        except Exception as e:
            st.error(f"❌ Erreur connexion Kinesis: {str(e)}")
            self.connection_status = "error"

    def get_recent_records_simple(self, limit=50):
        """Version simplifiée et rapide pour récupérer les données"""
        try:
            # Récupération directe avec LATEST pour les données les plus récentes
            stream_description = self.kinesis_client.describe_stream(StreamName=self.stream_name)
            shards = stream_description['StreamDescription']['Shards']

            all_records = []

            for shard in shards[:1]:  # Premier shard seulement pour accélérer
                shard_id = shard['ShardId']

                # Essayer LATEST d'abord
                try:
                    shard_iterator_response = self.kinesis_client.get_shard_iterator(
                        StreamName=self.stream_name,
                        ShardId=shard_id,
                        ShardIteratorType='LATEST'
                    )

                    shard_iterator = shard_iterator_response['ShardIterator']

                    # Un seul appel rapide
                    records_response = self.kinesis_client.get_records(
                        ShardIterator=shard_iterator,
                        Limit=50
                    )

                    records = records_response.get('Records', [])

                    for record in records:
                        decoded_data = self._decode_record_simple(record)
                        if decoded_data:
                            all_records.append(decoded_data)

                except Exception:
                    pass

                # Si pas assez de données avec LATEST, essayer TRIM_HORIZON
                if len(all_records) < 10:
                    try:
                        shard_iterator_response = self.kinesis_client.get_shard_iterator(
                            StreamName=self.stream_name,
                            ShardId=shard_id,
                            ShardIteratorType='TRIM_HORIZON'
                        )

                        shard_iterator = shard_iterator_response['ShardIterator']

                        records_response = self.kinesis_client.get_records(
                            ShardIterator=shard_iterator,
                            Limit=limit
                        )

                        records = records_response.get('Records', [])

                        for record in records:
                            decoded_data = self._decode_record_simple(record)
                            if decoded_data and len(all_records) < limit:
                                all_records.append(decoded_data)

                    except Exception:
                        pass

            if all_records:
                # Trier par timestamp
                all_records.sort(key=lambda x: x.get('timestamp', datetime.min), reverse=True)
                return all_records[:limit]
            else:
                return self._generate_test_data(limit)

        except Exception:
            return self._generate_test_data(limit)

    def _decode_record_simple(self, record):
        """Décodage simplifié et rapide"""
        try:
            data_bytes = record['Data']

            # UTF-8 direct (format de votre bracelet)
            if isinstance(data_bytes, bytes):
                json_str = data_bytes.decode('utf-8')
            else:
                json_str = str(data_bytes)

            data = json.loads(json_str)

            # Vérifier si c'est le bracelet MPU Christian
            device_id = data.get('device_id') or data.get('deviceId') or data.get('clientId')
            if not device_id or 'MPU_Christian' not in str(device_id):
                return None

            # Normalisation rapide
            normalized = {
                'timestamp': record.get('ApproximateArrivalTimestamp', datetime.now()),
                'device_id': device_id,
                'sequence_number': record.get('SequenceNumber'),
                'source': 'kinesis',
                'accelerometer_x': data.get('accelerometer_x', 0),
                'accelerometer_y': data.get('accelerometer_y', 0),
                'accelerometer_z': data.get('accelerometer_z', 0),
                'gyroscope_x': data.get('gyroscope_x', 0),
                'gyroscope_y': data.get('gyroscope_y', 0),
                'gyroscope_z': data.get('gyroscope_z', 0),
                'temperature': data.get('temperature', 25.0),
                'battery_level': data.get('battery_level', 100)
            }

            return normalized

        except Exception:
            return None

    def _generate_test_data(self, limit=50):
        """Génération de données de test réalistes"""
        import random

        records = []
        base_time = datetime.now()

        for i in range(limit):
            timestamp = base_time - timedelta(seconds=i * 2)

            # Valeurs réalistes basées sur votre bracelet
            record = {
                'device_id': 'MPU_Christian_8266MOD',
                'timestamp': timestamp,
                'sequence_number': f'test-{i:04d}',
                'source': 'simulation',
                'accelerometer_x': round(random.uniform(-2.0, 2.0), 2),
                'accelerometer_y': round(random.uniform(-2.0, 2.0), 2),
                'accelerometer_z': round(random.uniform(8.0, 11.0), 2),
                'gyroscope_x': round(random.uniform(-50, 50), 2),
                'gyroscope_y': round(random.uniform(-50, 50), 2),
                'gyroscope_z': round(random.uniform(-50, 50), 2),
                'temperature': round(random.uniform(24.0, 28.0), 1),
                'battery_level': max(20, int(100 - (i * 0.1)))
            }

            # Parfois des valeurs élevées pour tester les alertes
            if random.random() < 0.1:
                record['accelerometer_x'] *= random.uniform(2, 5)
                record['accelerometer_y'] *= random.uniform(2, 5)

            records.append(record)

        return records

    def detect_alerts(self, data):
        """Détection d'alertes simplifiée"""
        alerts = []

        try:
            accel_magnitude = math.sqrt(
                data.get('accelerometer_x', 0)**2 +
                data.get('accelerometer_y', 0)**2 +
                data.get('accelerometer_z', 0)**2
            )

            if accel_magnitude > ALERT_THRESHOLDS['fall_detection']:
                alerts.append({
                    'type': 'FALL_DETECTION',
                    'severity': 'HIGH',
                    'message': f'🚨 Chute détectée - Accélération: {accel_magnitude:.2f} m/s²',
                    'value': accel_magnitude,
                    'timestamp': datetime.now()
                })
            elif accel_magnitude > ALERT_THRESHOLDS['hyperactivity']:
                alerts.append({
                    'type': 'HYPERACTIVITY',
                    'severity': 'MEDIUM',
                    'message': f'⚡ Hyperactivité - Accélération: {accel_magnitude:.2f} m/s²',
                    'value': accel_magnitude,
                    'timestamp': datetime.now()
                })
        except Exception:
            pass

        return alerts

def main():
    # Configuration Streamlit
    st.set_page_config(
        page_title="🚨 Kidjamo Dashboard",
        page_icon="🏥",
        layout="wide"
    )

    # Interface principale
    st.title("🚨 Kidjamo - Dashboard Temps Réel")
    st.markdown("**Surveillance IoT - Bracelet MPU Christian**")

    # Initialisation
    if 'processor' not in st.session_state:
        st.session_state.processor = KinesisRealtimeProcessor()
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 10

    processor = st.session_state.processor

    # Sidebar avec contrôles simplifiés
    with st.sidebar:
        st.header("🎛️ Contrôles")

        # Statut connexion
        if processor.connection_status == "connected":
            st.success("🟢 Kinesis connecté")
        else:
            st.error("🔴 Kinesis déconnecté")

        # Paramètres
        max_records = st.slider("Nombre d'enregistrements", 10, 100, 50)

        # Auto-actualisation avec logique simple
        auto_refresh = st.checkbox("🔄 Auto-actualisation", value=st.session_state.auto_refresh)
        st.session_state.auto_refresh = auto_refresh

        if auto_refresh:
            refresh_interval = st.selectbox(
                "Intervalle (secondes)",
                [5, 10, 15, 30],
                index=1,
                format_func=lambda x: f"{x}s"
            )
            st.session_state.refresh_interval = refresh_interval
            st.success(f"⏱️ Actualisation toutes les {refresh_interval}s")

        # Bouton actualisation manuelle
        if st.button("🔄 Actualiser maintenant", type="primary"):
            st.rerun()

    # Container principal pour les données
    main_container = st.container()

    with main_container:
        # Récupération des données
        with st.spinner("📡 Chargement des données..."):
            records = processor.get_recent_records_simple(limit=max_records)

        if not records:
            st.error("❌ Aucune donnée disponible")
            st.stop()

        # Statistiques
        real_count = sum(1 for r in records if r.get('source') == 'kinesis')
        sim_count = len(records) - real_count

        if real_count > 0:
            st.success(f"✅ {real_count} données réelles du bracelet + {sim_count} simulées")
        else:
            st.info(f"🎮 {sim_count} données simulées (aucune donnée réelle trouvée)")

        # Traitement des données
        df = pd.DataFrame(records)
        latest_record = records[0] if records else {}

        # Calculs
        if 'accelerometer_x' in df.columns:
            df['accel_magnitude'] = np.sqrt(
                df['accelerometer_x']**2 +
                df['accelerometer_y']**2 +
                df['accelerometer_z']**2
            )
        if 'gyroscope_x' in df.columns:
            df['gyro_magnitude'] = np.sqrt(
                df['gyroscope_x']**2 +
                df['gyroscope_y']**2 +
                df['gyroscope_z']**2
            )

        # Détection d'alertes
        all_alerts = []
        for record in records[:5]:  # Seulement les 5 plus récents
            alerts = processor.detect_alerts(record)
            all_alerts.extend(alerts)

        # Métriques
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("📊 Mesures", len(records))
        with col2:
            st.metric("🚨 Alertes", len(all_alerts))
        with col3:
            temp = latest_record.get('temperature', 0)
            st.metric("🌡️ Température", f"{temp:.1f}°C")
        with col4:
            battery = latest_record.get('battery_level', 0)
            st.metric("🔋 Batterie", f"{battery}%")

        # Alertes récentes
        if all_alerts:
            st.subheader("🚨 Alertes récentes")
            for alert in all_alerts[:3]:
                if alert['severity'] == 'HIGH':
                    st.error(alert['message'])
                else:
                    st.warning(alert['message'])

        # Graphiques
        if 'accel_magnitude' in df.columns and len(df) > 0:
            # Graphique accélération
            st.subheader("📊 Accélération")
            fig_accel = go.Figure()
            fig_accel.add_trace(go.Scatter(
                x=list(range(len(df))),
                y=df['accel_magnitude'],
                mode='lines+markers',
                name='Accélération',
                line=dict(color='#e74c3c', width=2)
            ))

            # Seuils
            fig_accel.add_hline(y=ALERT_THRESHOLDS['fall_detection'],
                              line_dash="dash", line_color="red",
                              annotation_text="Seuil chute")
            fig_accel.add_hline(y=ALERT_THRESHOLDS['hyperactivity'],
                              line_dash="dash", line_color="orange",
                              annotation_text="Seuil hyperactivité")

            fig_accel.update_layout(
                xaxis_title="Échantillons",
                yaxis_title="Accélération (m/s²)",
                height=300
            )
            st.plotly_chart(fig_accel, use_container_width=True)

            # Graphique température
            if 'temperature' in df.columns:
                st.subheader("🌡️ Température")
                fig_temp = go.Figure()
                fig_temp.add_trace(go.Scatter(
                    x=list(range(len(df))),
                    y=df['temperature'],
                    mode='lines+markers',
                    name='Température',
                    line=dict(color='#f39c12', width=2)
                ))
                fig_temp.update_layout(
                    xaxis_title="Échantillons",
                    yaxis_title="Température (°C)",
                    height=300
                )
                st.plotly_chart(fig_temp, use_container_width=True)

        # Tableau des données récentes
        st.subheader("📋 Données récentes")
        display_columns = ['timestamp', 'accelerometer_x', 'accelerometer_y', 'accelerometer_z', 'temperature']
        available_columns = [col for col in display_columns if col in df.columns]

        if available_columns:
            recent_df = df[available_columns].head(10)
            if 'timestamp' in recent_df.columns:
                recent_df['timestamp'] = recent_df['timestamp'].dt.strftime('%H:%M:%S')
            st.dataframe(recent_df.round(2), use_container_width=True)

        # Informations de debug
        with st.expander("🔧 Debug"):
            st.write(f"Stream: {processor.stream_name}")
            st.write(f"Région: {AWS_CONFIG['region_name']}")
            st.write(f"Dernière MAJ: {datetime.now().strftime('%H:%M:%S')}")
            if latest_record:
                st.json(latest_record)

    # AUTO-ACTUALISATION - NOUVELLE LOGIQUE SIMPLE
    if st.session_state.auto_refresh:
        # Utiliser st.empty() avec un placeholder
        refresh_placeholder = st.empty()

        # Timer simple
        time.sleep(1)  # Pause d'1 seconde

        # Forcer le redémarrage après l'intervalle défini
        if 'last_run' not in st.session_state:
            st.session_state.last_run = time.time()

        if time.time() - st.session_state.last_run > st.session_state.refresh_interval:
            st.session_state.last_run = time.time()
            with refresh_placeholder:
                st.info("🔄 Actualisation...")
            time.sleep(0.5)
            st.rerun()

if __name__ == "__main__":
    main()
