#!/usr/bin/env python3
"""
📊 Kidjamo - Dashboard Historique (Streamlit)
Analyse des données stockées en PostgreSQL avec graphiques interactifs
"""

import streamlit as st
import psycopg2
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
from datetime import datetime, timedelta
from config import DB_CONFIG

# PAS de st.set_page_config() car déjà appelé par le main

class PostgreSQLConnector:
    """Connecteur pour PostgreSQL avec requêtes optimisées"""

    def __init__(self):
        self.connection = None
        self.connection_status = "disconnected"
        self.connect()

    def connect(self):
        """Établir la connexion à PostgreSQL"""
        try:
            self.connection = psycopg2.connect(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                database=DB_CONFIG['database'],
                user=DB_CONFIG['username'],
                password=DB_CONFIG['password']
            )
            self.connection_status = "connected"
            return True
        except Exception as e:
            st.error(f"❌ Erreur connexion PostgreSQL: {e}")
            self.connection_status = "error"
            return False

    def execute_query(self, query, params=None):
        """Exécuter une requête et retourner un DataFrame"""
        try:
            if not self.connection or self.connection.closed:
                if not self.connect():
                    return pd.DataFrame()

            df = pd.read_sql_query(query, self.connection, params=params)
            return df
        except Exception as e:
            st.error(f"❌ Erreur requête SQL: {e}")
            return pd.DataFrame()

    def get_measurements_count(self):
        """Obtenir le nombre total de mesures"""
        query = "SELECT COUNT(*) as total FROM measurements"
        df = self.execute_query(query)
        return df['total'].iloc[0] if not df.empty else 0

    def get_recent_measurements(self, limit=100):
        """Obtenir les mesures récentes"""
        query = """
        SELECT 
            device_id,
            timestamp,
            temperature,
            heart_rate,
            accelerometer_x,
            accelerometer_y,
            accelerometer_z,
            gyroscope_x,
            gyroscope_y,
            gyroscope_z,
            battery_level
        FROM measurements 
        WHERE device_id = 'MPU_Christian_8266MOD'
        ORDER BY timestamp DESC 
        LIMIT %s
        """
        return self.execute_query(query, (limit,))

    def get_measurements_by_date_range(self, start_date, end_date):
        """Obtenir les mesures par plage de dates"""
        query = """
        SELECT 
            device_id,
            timestamp,
            temperature,
            heart_rate,
            accelerometer_x,
            accelerometer_y,
            accelerometer_z,
            gyroscope_x,
            gyroscope_y,
            gyroscope_z,
            battery_level
        FROM measurements 
        WHERE device_id = 'MPU_Christian_8266MOD'
        AND timestamp BETWEEN %s AND %s
        ORDER BY timestamp DESC
        """
        return self.execute_query(query, (start_date, end_date))

    def get_daily_statistics(self, days=7):
        """Obtenir les statistiques quotidiennes"""
        query = """
        SELECT 
            DATE(timestamp) as date,
            COUNT(*) as measurements_count,
            AVG(temperature) as avg_temperature,
            MIN(temperature) as min_temperature,
            MAX(temperature) as max_temperature,
            AVG(heart_rate) as avg_heart_rate,
            AVG(battery_level) as avg_battery
        FROM measurements 
        WHERE device_id = 'MPU_Christian_8266MOD'
        AND timestamp >= NOW() - INTERVAL '%s days'
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        """
        return self.execute_query(query, (days,))

def main():
    # Titre principal
    st.title("📊 Kidjamo - Dashboard Historique")
    st.markdown("**Analyse des Données PostgreSQL - Bracelet MPU_Christian_8266MOD**")

    # Initialiser le connecteur PostgreSQL
    if 'db_connector' not in st.session_state:
        st.session_state.db_connector = PostgreSQLConnector()

    db = st.session_state.db_connector

    # Sidebar pour les contrôles
    with st.sidebar:
        st.header("🎛️ Contrôles")

        # Statut de connexion
        if db.connection_status == "connected":
            st.success("🟢 Connecté à PostgreSQL")
        else:
            st.error("🔴 Déconnecté de PostgreSQL")
            if st.button("🔄 Reconnecter"):
                db.connect()
                st.rerun()

        # Paramètres d'analyse
        st.subheader("⚙️ Paramètres")

        # Plage de dates
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)

        date_range = st.date_input(
            "Plage de dates",
            value=(start_date, end_date),
            max_value=end_date
        )

        # Nombre de mesures à afficher
        limit_measurements = st.selectbox(
            "Nombre de mesures récentes",
            [50, 100, 200, 500, 1000],
            index=1
        )

        # Bouton de rafraîchissement
        if st.button("🔄 Actualiser"):
            st.rerun()

    if db.connection_status != "connected":
        st.error("❌ Impossible de se connecter à la base de données")
        st.info("Vérifiez la configuration de la base dans config.py")
        return

    # Métriques principales
    col1, col2, col3, col4 = st.columns(4)

    with st.spinner("📊 Chargement des statistiques..."):
        total_measurements = db.get_measurements_count()
        daily_stats = db.get_daily_statistics(7)

    with col1:
        st.metric(
            "📊 Total Mesures",
            f"{total_measurements:,}",
            delta=None
        )

    with col2:
        if not daily_stats.empty:
            today_count = daily_stats.iloc[0]['measurements_count'] if len(daily_stats) > 0 else 0
            st.metric(
                "📅 Aujourd'hui",
                f"{int(today_count):,}",
                delta=None
            )
        else:
            st.metric("📅 Aujourd'hui", "0", delta=None)

    with col3:
        if not daily_stats.empty:
            avg_temp = daily_stats['avg_temperature'].mean()
            st.metric(
                "🌡️ Temp. Moyenne",
                f"{avg_temp:.1f}°C" if not pd.isna(avg_temp) else "N/A",
                delta=None
            )
        else:
            st.metric("🌡️ Temp. Moyenne", "N/A", delta=None)

    with col4:
        if not daily_stats.empty:
            avg_battery = daily_stats['avg_battery'].mean()
            st.metric(
                "🔋 Batterie Moy.",
                f"{avg_battery:.0f}%" if not pd.isna(avg_battery) else "N/A",
                delta=None
            )
        else:
            st.metric("🔋 Batterie Moy.", "N/A", delta=None)

    # Graphiques d'analyse
    if not daily_stats.empty:
        st.subheader("📈 Évolution Quotidienne (7 derniers jours)")

        # Graphique des mesures quotidiennes
        fig_daily = go.Figure()

        fig_daily.add_trace(go.Bar(
            x=daily_stats['date'],
            y=daily_stats['measurements_count'],
            name='Mesures par jour',
            marker_color='#3498db'
        ))

        fig_daily.update_layout(
            title="Nombre de Mesures par Jour",
            xaxis_title="Date",
            yaxis_title="Nombre de Mesures",
            height=400
        )

        st.plotly_chart(fig_daily, use_container_width=True)

        # Graphique de température
        fig_temp = go.Figure()

        fig_temp.add_trace(go.Scatter(
            x=daily_stats['date'],
            y=daily_stats['avg_temperature'],
            mode='lines+markers',
            name='Température Moyenne',
            line=dict(color='#e74c3c', width=2)
        ))

        fig_temp.update_layout(
            title="Évolution de la Température Moyenne",
            xaxis_title="Date",
            yaxis_title="Température (°C)",
            height=400
        )

        st.plotly_chart(fig_temp, use_container_width=True)

    # Données récentes détaillées
    st.subheader(f"📋 Mesures Récentes ({limit_measurements} dernières)")

    with st.spinner("📡 Chargement des mesures récentes..."):
        recent_data = db.get_recent_measurements(limit_measurements)

    if not recent_data.empty:
        # Calculer les magnitudes d'accélération
        recent_data['accel_magnitude'] = np.sqrt(
            recent_data['accelerometer_x']**2 +
            recent_data['accelerometer_y']**2 +
            recent_data['accelerometer_z']**2
        )

        recent_data['gyro_magnitude'] = np.sqrt(
            recent_data['gyroscope_x']**2 +
            recent_data['gyroscope_y']**2 +
            recent_data['gyroscope_z']**2
        )

        # Graphiques de données récentes
        col1, col2 = st.columns(2)

        with col1:
            # Graphique accélération
            fig_accel = go.Figure()

            fig_accel.add_trace(go.Scatter(
                x=recent_data.index,
                y=recent_data['accel_magnitude'],
                mode='lines',
                name='Magnitude Accélération',
                line=dict(color='#e74c3c', width=1)
            ))

            # Seuils d'alerte
            fig_accel.add_hline(y=15.0, line_dash="dash", line_color="red", annotation_text="Seuil Chute")
            fig_accel.add_hline(y=8.0, line_dash="dash", line_color="orange", annotation_text="Seuil Hyperactivité")

            fig_accel.update_layout(
                title="Magnitude d'Accélération",
                xaxis_title="Échantillons",
                yaxis_title="Accélération (m/s²)",
                height=300
            )

            st.plotly_chart(fig_accel, use_container_width=True)

        with col2:
            # Graphique température
            fig_temp_recent = go.Figure()

            fig_temp_recent.add_trace(go.Scatter(
                x=recent_data.index,
                y=recent_data['temperature'],
                mode='lines',
                name='Température',
                line=dict(color='#f39c12', width=1)
            ))

            fig_temp_recent.update_layout(
                title="Évolution Température",
                xaxis_title="Échantillons",
                yaxis_title="Température (°C)",
                height=300
            )

            st.plotly_chart(fig_temp_recent, use_container_width=True)

        # Tableau des données
        st.subheader("📋 Tableau des Données")

        # Colonnes à afficher
        display_columns = [
            'timestamp', 'temperature', 'heart_rate', 'battery_level',
            'accelerometer_x', 'accelerometer_y', 'accelerometer_z',
            'accel_magnitude'
        ]

        # Filtrer les colonnes qui existent
        available_columns = [col for col in display_columns if col in recent_data.columns]

        if available_columns:
            display_df = recent_data[available_columns].head(20).round(2)
            st.dataframe(display_df, use_container_width=True)

        # Statistiques descriptives
        st.subheader("📊 Statistiques Descriptives")

        numeric_columns = recent_data.select_dtypes(include=[np.number]).columns
        if len(numeric_columns) > 0:
            stats_df = recent_data[numeric_columns].describe().round(2)
            st.dataframe(stats_df, use_container_width=True)

    else:
        st.warning("⚠️ Aucune donnée trouvée dans la base de données")
        st.info("💡 Vérifications suggérées:")
        st.write("1. Le pipeline Glue a-t-il traité des données récemment ?")
        st.write("2. La table 'measurements' existe-t-elle ?")
        st.write("3. Les données Gold-to-PostgreSQL sont-elles fonctionnelles ?")

    # Informations de débogage
    with st.expander("🔧 Informations Techniques"):
        st.write(f"**Base de données:** {DB_CONFIG['database']}")
        st.write(f"**Host:** {DB_CONFIG['host']}")
        st.write(f"**Port:** {DB_CONFIG['port']}")
        st.write(f"**Statut connexion:** {db.connection_status}")
        st.write(f"**Dernière mise à jour:** {datetime.now().strftime('%H:%M:%S')}")

        # Test de requête simple
        if st.button("🧪 Test Connexion"):
            test_query = "SELECT version()"
            result = db.execute_query(test_query)
            if not result.empty:
                st.success("✅ Test connexion réussi!")
                st.write(result.iloc[0]['version'])
            else:
                st.error("❌ Test connexion échoué")

if __name__ == "__main__":
    main()
