#!/usr/bin/env python3
"""
🚨 Kidjamo - Dashboard Temps Réel NOUVEAU
Version simplifiée qui fonctionne vraiment
"""

import streamlit as st
import boto3
import json
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
import numpy as np
import math
from config import AWS_CONFIG, ALERT_THRESHOLDS

# Configuration de la page
st.set_page_config(
    page_title="🚨 Kidjamo Dashboard",
    page_icon="🏥",
    layout="wide"
)

def get_kinesis_data():
    """Récupère les données Kinesis EN TEMPS RÉEL (nouvelles données seulement)"""
    try:
        # Connexion Kinesis
        kinesis = boto3.client('kinesis', region_name=AWS_CONFIG['region_name'])
        stream_name = AWS_CONFIG['kinesis_stream_name']

        # Obtenir les shards
        response = kinesis.describe_stream(StreamName=stream_name)
        shards = response['StreamDescription']['Shards']

        all_records = []

        # Parcourir tous les shards
        for shard in shards:
            shard_id = shard['ShardId']

            try:
                # CORRECTION: Utiliser LATEST pour les données temps réel
                # Si c'est la première fois, stocker l'iterator pour la prochaine lecture
                iterator_key = f"iterator_{shard_id}"

                if iterator_key not in st.session_state:
                    # Première fois : commencer avec LATEST
                    iterator_response = kinesis.get_shard_iterator(
                        StreamName=stream_name,
                        ShardId=shard_id,
                        ShardIteratorType='LATEST'  # Données les plus récentes uniquement
                    )
                    st.session_state[iterator_key] = iterator_response['ShardIterator']

                iterator = st.session_state[iterator_key]

                if iterator:  # Vérifier que l'iterator existe encore
                    # Récupérer seulement les NOUVEAUX records
                    records_response = kinesis.get_records(
                        ShardIterator=iterator,
                        Limit=25  # Limite réduite pour temps réel
                    )

                    records = records_response.get('Records', [])

                    # Mettre à jour l'iterator pour la prochaine lecture
                    next_iterator = records_response.get('NextShardIterator')
                    if next_iterator:
                        st.session_state[iterator_key] = next_iterator
                    else:
                        # L'iterator a expiré, en créer un nouveau
                        iterator_response = kinesis.get_shard_iterator(
                            StreamName=stream_name,
                            ShardId=shard_id,
                            ShardIteratorType='LATEST'
                        )
                        st.session_state[iterator_key] = iterator_response['ShardIterator']

                    # Décoder chaque record NOUVEAU
                    for record in records:
                        try:
                            # Décoder les données
                            data_bytes = record['Data']
                            if isinstance(data_bytes, bytes):
                                json_str = data_bytes.decode('utf-8')
                            else:
                                json_str = str(data_bytes)

                            data = json.loads(json_str)

                            # Vérifier si c'est notre bracelet
                            device_id = data.get('device_id') or data.get('deviceId') or data.get('clientId')
                            if device_id and 'MPU_Christian' in str(device_id):

                                # Créer l'enregistrement normalisé avec les VRAIS noms de champs
                                normalized_record = {
                                    'timestamp': record.get('ApproximateArrivalTimestamp', datetime.now()),
                                    'device_id': device_id,
                                    'source': 'kinesis_realtime',  # Marquer comme temps réel
                                    # CORRECTION: Utiliser les vrais noms des champs du bracelet
                                    'accelerometer_x': float(data.get('accel_x', 0)),
                                    'accelerometer_y': float(data.get('accel_y', 0)),
                                    'accelerometer_z': float(data.get('accel_z', 0)),
                                    'gyroscope_x': float(data.get('gyro_x', 0)),
                                    'gyroscope_y': float(data.get('gyro_y', 0)),
                                    'gyroscope_z': float(data.get('gyro_z', 0)),
                                    'temperature': float(data.get('temp', 25.0)),
                                    'battery_level': int(data.get('battery_level', 100))
                                }

                                all_records.append(normalized_record)

                        except Exception as decode_error:
                            continue  # Ignorer les erreurs de décodage

            except Exception as shard_error:
                # Si erreur, réinitialiser l'iterator
                iterator_key = f"iterator_{shard_id}"
                if iterator_key in st.session_state:
                    del st.session_state[iterator_key]
                continue

        # Maintenir un historique local des dernières données
        if 'data_history' not in st.session_state:
            st.session_state.data_history = []

        # Ajouter les nouvelles données à l'historique
        if all_records:
            st.session_state.data_history.extend(all_records)
            # Garder seulement les 100 dernières mesures pour la performance
            st.session_state.data_history = st.session_state.data_history[-100:]

        # Si aucune nouvelle donnée mais on a un historique, utiliser l'historique
        if not all_records and st.session_state.data_history:
            return st.session_state.data_history[-50:]  # Les 50 plus récentes
        elif all_records:
            # Retourner les nouvelles données + un peu d'historique pour le contexte
            combined = st.session_state.data_history[-30:] + all_records
            return combined[-50:]  # Maximum 50 points pour la performance
        else:
            # Première fois et aucune donnée : utiliser des données de test
            return generate_realtime_test_data()

    except Exception as e:
        st.error(f"❌ Erreur Kinesis temps réel: {str(e)}")
        return generate_realtime_test_data()

def generate_realtime_test_data():
    """Génère des données de test qui changent à chaque appel pour simuler le temps réel"""
    import random

    # Utiliser un compteur pour simuler l'évolution temporelle
    if 'test_counter' not in st.session_state:
        st.session_state.test_counter = 0

    st.session_state.test_counter += 1

    records = []
    base_time = datetime.now()

    # Générer quelques nouveaux points de données
    for i in range(3):  # Seulement 3 nouveaux points à chaque fois
        timestamp = base_time - timedelta(seconds=i)

        # Valeurs qui évoluent avec le temps pour simuler le mouvement
        time_factor = st.session_state.test_counter * 0.1

        accel_x = round(2.0 * math.sin(time_factor + i), 2)
        accel_y = round(1.5 * math.cos(time_factor + i * 0.7), 2)
        accel_z = round(9.8 + 1.0 * math.sin(time_factor * 0.5), 2)

        # Parfois des pics pour tester les alertes
        if st.session_state.test_counter % 20 == 0:
            accel_x *= 4
            accel_y *= 4

        record = {
            'timestamp': timestamp,
            'device_id': 'MPU_Christian_8266MOD',
            'source': 'simulation_realtime',
            'accelerometer_x': accel_x,
            'accelerometer_y': accel_y,
            'accelerometer_z': accel_z,
            'gyroscope_x': round(20 * math.sin(time_factor * 2), 2),
            'gyroscope_y': round(15 * math.cos(time_factor * 1.5), 2),
            'gyroscope_z': round(10 * math.sin(time_factor * 3), 2),
            'temperature': round(30.0 + 2.0 * math.sin(time_factor * 0.1), 1),
            'battery_level': max(80, 100 - int(st.session_state.test_counter * 0.1))
        }

        records.append(record)

    return records

def detect_alerts(records):
    """Détecte les alertes dans les données"""
    alerts = []

    for record in records[:5]:  # Seulement les 5 plus récents
        try:
            accel_magnitude = math.sqrt(
                record.get('accelerometer_x', 0)**2 +
                record.get('accelerometer_y', 0)**2 +
                record.get('accelerometer_z', 0)**2
            )

            if accel_magnitude > ALERT_THRESHOLDS['fall_detection']:
                alerts.append({
                    'type': 'FALL_DETECTION',
                    'severity': 'HIGH',
                    'message': f'🚨 Chute détectée - Accélération: {accel_magnitude:.2f} m/s²',
                    'timestamp': record['timestamp']
                })
            elif accel_magnitude > ALERT_THRESHOLDS['hyperactivity']:
                alerts.append({
                    'type': 'HYPERACTIVITY',
                    'severity': 'MEDIUM',
                    'message': f'⚡ Hyperactivité - Accélération: {accel_magnitude:.2f} m/s²',
                    'timestamp': record['timestamp']
                })
        except Exception:
            continue

    return alerts

def main():
    # Titre
    st.title("🚨 Kidjamo - Dashboard Temps Réel")
    st.markdown("**Surveillance Bracelet MPU Christian**")

    # Initialisation des variables de session persistantes
    if 'total_records_received' not in st.session_state:
        st.session_state.total_records_received = 0
    if 'total_alerts_generated' not in st.session_state:
        st.session_state.total_alerts_generated = 0
    if 'session_start_time' not in st.session_state:
        st.session_state.session_start_time = datetime.now()

    # Sidebar
    with st.sidebar:
        st.header("🎛️ Contrôles")

        # Auto-actualisation temps réel (1 seconde par défaut)
        auto_refresh = st.checkbox("🔄 Actualisation temps réel", value=True)

        if auto_refresh:
            refresh_rate = st.selectbox(
                "Fréquence d'actualisation",
                [1, 2, 3, 5, 10],
                index=0,  # 1 seconde par défaut
                format_func=lambda x: f"Toutes les {x} seconde{'s' if x > 1 else ''}"
            )
            st.success(f"⚡ Actualisation toutes les {refresh_rate} seconde{'s' if refresh_rate > 1 else ''}")
        else:
            refresh_rate = 10

        # Bouton manuel
        if st.button("🔄 Actualiser maintenant", type="primary"):
            st.rerun()

        # Bouton reset des compteurs
        if st.button("🔄 Reset compteurs", help="Remet les compteurs à zéro"):
            st.session_state.total_records_received = 0
            st.session_state.total_alerts_generated = 0
            st.session_state.session_start_time = datetime.now()
            if 'data_history' in st.session_state:
                st.session_state.data_history = []
            st.rerun()

        st.divider()

        # Afficher les statistiques de session
        session_duration = datetime.now() - st.session_state.session_start_time
        st.info(f"💡 Session active depuis: {str(session_duration).split('.')[0]}")
        st.metric("📊 Total reçu", st.session_state.total_records_received)
        st.metric("🚨 Total alertes", st.session_state.total_alerts_generated)

    # Récupérer les données
    with st.spinner("📡 Streaming données..."):
        records = get_kinesis_data()

    if not records:
        st.error("❌ Aucune donnée disponible")
        # Auto-actualisation même sans données
        if auto_refresh:
            time.sleep(refresh_rate)
            st.rerun()
        return

    # Mettre à jour les compteurs de session avec les nouvelles données
    # CORRECTION: Compter les vraies nouvelles données qui arrivent
    if 'processed_sequences' not in st.session_state:
        st.session_state.processed_sequences = set()

    # Compter les nouvelles données réelles (pas déjà traitées)
    new_data_count = 0
    for record in records:
        if record.get('source') in ['kinesis', 'kinesis_realtime']:
            sequence = record.get('sequence_number', f"seq_{record.get('timestamp', '')}")
            if sequence not in st.session_state.processed_sequences:
                st.session_state.processed_sequences.add(sequence)
                new_data_count += 1

    # Mettre à jour le compteur total
    if new_data_count > 0:
        st.session_state.total_records_received += new_data_count
        st.info(f"🆕 {new_data_count} nouvelles données ajoutées au total")

    # Statistiques sur les données actuelles
    real_count = sum(1 for r in records if r.get('source') in ['kinesis', 'kinesis_realtime'])
    sim_count = len(records) - real_count

    if real_count > 0:
        st.success(f"✅ {real_count} données temps réel du bracelet MPU Christian")
        if sim_count > 0:
            st.info(f"➕ {sim_count} données simulées")
    else:
        st.warning(f"🎮 Mode simulation - {sim_count} données générées")

    # Traitement des données
    df = pd.DataFrame(records)
    latest_record = records[0] if records else {}

    # Calcul de la magnitude d'accélération
    df['accel_magnitude'] = np.sqrt(
        df['accelerometer_x']**2 +
        df['accelerometer_y']**2 +
        df['accelerometer_z']**2
    )

    # Détection d'alertes
    alerts = detect_alerts(records)

    # CORRECTION: Compteur d'alertes plus simple et efficace
    if 'processed_alert_timestamps' not in st.session_state:
        st.session_state.processed_alert_timestamps = set()

    # Compter les nouvelles alertes (pas déjà traitées)
    new_alerts_count = 0
    for alert in alerts:
        alert_key = f"{alert['type']}_{alert['timestamp']}"
        if alert_key not in st.session_state.processed_alert_timestamps:
            st.session_state.processed_alert_timestamps.add(alert_key)
            new_alerts_count += 1

    # Mettre à jour le compteur total d'alertes
    if new_alerts_count > 0:
        st.session_state.total_alerts_generated += new_alerts_count
        st.warning(f"🚨 {new_alerts_count} nouvelles alertes détectées!")

    # Limiter la taille des sets pour éviter la croissance infinie
    if len(st.session_state.processed_sequences) > 1000:
        # Garder seulement les 500 plus récents
        sequences_list = list(st.session_state.processed_sequences)
        st.session_state.processed_sequences = set(sequences_list[-500:])

    if len(st.session_state.processed_alert_timestamps) > 1000:
        alerts_list = list(st.session_state.processed_alert_timestamps)
        st.session_state.processed_alert_timestamps = set(alerts_list[-500:])

    # Métriques principales - AVEC DESCRIPTIONS PLUS CLAIRES
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "📊 Données reçues (session)",
            st.session_state.total_records_received,
            delta=f"{real_count} dans le buffer",
            help="Total cumulé de données reçues depuis le début de cette session"
        )

    with col2:
        st.metric(
            "🚨 Alertes générées (session)",
            st.session_state.total_alerts_generated,
            delta=f"{len(alerts)} actuelles",
            help="Total cumulé d'alertes détectées depuis le début de cette session"
        )

    with col3:
        temp = latest_record.get('temperature', 0)
        st.metric(
            "🌡️ Température",
            f"{temp:.1f}°C",
            help="Température actuelle du bracelet MPU"
        )

    with col4:
        battery = latest_record.get('battery_level', 0)
        st.metric(
            "🔋 Batterie",
            f"{battery}%",
            help="Niveau de batterie du bracelet"
        )

    # Affichage des alertes
    if alerts:
        st.subheader("🚨 Alertes récentes")
        for alert in alerts[:3]:
            if alert['severity'] == 'HIGH':
                st.error(f"**{alert['message']}** - {alert['timestamp'].strftime('%H:%M:%S')}")
            else:
                st.warning(f"**{alert['message']}** - {alert['timestamp'].strftime('%H:%M:%S')}")

    # Graphique d'accélération temps réel
    st.subheader("📊 Accélération temps réel")

    fig = go.Figure()

    # Courbe d'accélération avec animation
    fig.add_trace(go.Scatter(
        x=list(range(len(df))),
        y=df['accel_magnitude'],
        mode='lines+markers',
        name='Magnitude accélération',
        line=dict(color='#e74c3c', width=3),
        marker=dict(size=5, color='#e74c3c')
    ))

    # Seuils d'alerte
    fig.add_hline(
        y=ALERT_THRESHOLDS['fall_detection'],
        line_dash="dash",
        line_color="red",
        annotation_text="Seuil chute"
    )

    fig.add_hline(
        y=ALERT_THRESHOLDS['hyperactivity'],
        line_dash="dash",
        line_color="orange",
        annotation_text="Seuil hyperactivité"
    )

    fig.update_layout(
        xaxis_title="Échantillons (temps →)",
        yaxis_title="Accélération (m/s²)",
        height=400,
        showlegend=True,
        # Animation pour le temps réel
        transition_duration=500
    )

    st.plotly_chart(fig, use_container_width=True)

    # Graphique de température temps réel
    st.subheader("🌡️ Température temps réel")

    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(
        x=list(range(len(df))),
        y=df['temperature'],
        mode='lines+markers',
        name='Température',
        line=dict(color='#f39c12', width=3),
        marker=dict(size=5, color='#f39c12')
    ))

    fig_temp.update_layout(
        xaxis_title="Échantillons",
        yaxis_title="Température (°C)",
        height=300,
        transition_duration=500
    )

    st.plotly_chart(fig_temp, use_container_width=True)

    # Tableau des données récentes
    st.subheader("📋 Données streaming")

    # Préparer le tableau avec horodatage précis
    display_df = df[['timestamp', 'accelerometer_x', 'accelerometer_y', 'accelerometer_z', 'temperature', 'battery_level']].head(5).copy()
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%H:%M:%S')
    display_df.columns = ['Heure', 'Accel X', 'Accel Y', 'Accel Z', 'Temp (°C)', 'Batterie (%)']

    st.dataframe(display_df.round(2), use_container_width=True)

    # Informations techniques en temps réel
    with st.expander("🔧 Informations streaming"):
        current_time = datetime.now().strftime('%H:%M:%S.%f')[:-3]  # Millisecondes
        st.write(f"**Stream Kinesis:** {AWS_CONFIG['kinesis_stream_name']}")
        st.write(f"**Région AWS:** {AWS_CONFIG['region_name']}")
        st.write(f"**Streaming actif:** {current_time}")
        st.write(f"**Device ID:** {latest_record.get('device_id', 'N/A')}")
        st.write(f"**Source:** {latest_record.get('source', 'N/A')}")
        st.write(f"**Session depuis:** {st.session_state.session_start_time.strftime('%H:%M:%S')}")

        if latest_record:
            st.json(latest_record)

    # Auto-actualisation avec st.rerun() au lieu de while True
    if auto_refresh:
        # Attendre avant la prochaine actualisation
        time.sleep(refresh_rate)
        st.rerun()

if __name__ == "__main__":
    main()
