"""
Dashboard Temps Réel IoT Patients - Interface Streamlit CORRIGÉE

Version corrigée avec :
- Vrai temps réel avec auto-refresh fonctionnel
- Graphiques d'évolution qui s'affichent correctement
- Filtres opérationnels
- Performance optimisée
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import altair as alt

# Optional auto-refresh helper (preferred if available)
try:
    from streamlit_autorefresh import st_autorefresh  # type: ignore
    HAS_AUTOREFRESH = True
except Exception:
    HAS_AUTOREFRESH = False

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

# =====================================================
# CONFIGURATION ET CONNEXION BASE DE DONNÉES
# =====================================================

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

# Cache de connexion Streamlit
@st.cache_resource
def init_database_connection():
    """Initialise connexion PostgreSQL avec cache Streamlit"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True  # Évite les problèmes de transaction
        return conn
    except Exception as e:
        st.error(f"❌ Erreur connexion base de données: {e}")
        return None

def get_fresh_connection():
    """Obtient une nouvelle connexion fraîche pour chaque requête"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"❌ Erreur nouvelle connexion: {e}")
        return None

# =====================================================
# FONCTIONS D'ACCÈS AUX DONNÉES - TEMPS RÉEL CORRIGÉES
# =====================================================

def load_patients_overview() -> pd.DataFrame:
    """Charge vue d'ensemble des patients - TEMPS RÉEL CORRIGÉ"""
    conn = get_fresh_connection()  # Nouvelle connexion à chaque fois
    if not conn:
        return pd.DataFrame()

    query = """
    SELECT 
        p.patient_id,
        u.first_name,
        u.last_name,
        p.genotype,
        EXTRACT(YEAR FROM AGE(p.birth_date)) as age,
        u.gender,
        p.current_device_id,
        
        -- Dernière mesure (temps réel) avec timezone UTC
        m.recorded_at AT TIME ZONE 'UTC' as last_measurement,
        m.heart_rate_bpm,
        m.spo2_percent,
        m.temperature_celsius,
        m.pain_scale,
        m.battery_percent,
        m.signal_quality,
        
        -- Alertes récentes
        COALESCE(recent_alerts.alert_count, 0) as alerts_1h,
        COALESCE(recent_alerts.critical_count, 0) as critical_alerts_1h,
        COALESCE(alerts_24h.alert_count, 0) as alerts_24h,
        COALESCE(alerts_24h.critical_count, 0) as critical_alerts_24h
        
    FROM patients p
    JOIN users u ON p.user_id = u.user_id
    LEFT JOIN LATERAL (
        SELECT DISTINCT ON (patient_id) 
            patient_id, recorded_at, heart_rate_bpm, spo2_percent, 
            temperature_celsius, pain_scale, battery_percent, signal_quality
        FROM measurements 
        WHERE patient_id = p.patient_id
        ORDER BY patient_id, recorded_at DESC
        LIMIT 1
    ) m ON m.patient_id = p.patient_id
    LEFT JOIN (
        SELECT 
            patient_id,
            COUNT(*) as alert_count,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_count
        FROM alerts 
        WHERE created_at >= NOW() - INTERVAL '1 hour'
        GROUP BY patient_id
    ) recent_alerts ON recent_alerts.patient_id = p.patient_id
    LEFT JOIN (
        SELECT 
            patient_id,
            COUNT(*) as alert_count,
            COUNT(*) FILTER (WHERE severity = 'critical') as critical_count
        FROM alerts 
        WHERE created_at >= NOW() - INTERVAL '24 hours'
        GROUP BY patient_id
    ) alerts_24h ON alerts_24h.patient_id = p.patient_id
    
    ORDER BY u.first_name, u.last_name
    """

    try:
        df = pd.read_sql_query(query, conn)

        if not df.empty:
            # Conversion timezone-aware
            if 'last_measurement' in df.columns:
                df['last_measurement'] = pd.to_datetime(df['last_measurement'], utc=True)

                # Calcul du statut de connexion avec datetime timezone-aware
                current_time = pd.Timestamp.now(tz='UTC')

                def calculate_status(last_measurement):
                    if pd.isna(last_measurement):
                        return 'OFFLINE'

                    # Conversion en timezone-aware si nécessaire
                    if last_measurement.tz is None:
                        last_measurement = last_measurement.tz_localize('UTC')

                    time_diff = (current_time - last_measurement).total_seconds() / 60  # en minutes

                    if time_diff <= 5:
                        return 'ONLINE'
                    elif time_diff <= 30:
                        return 'WARNING'
                    else:
                        return 'OFFLINE'

                df['connection_status'] = df['last_measurement'].apply(calculate_status)
            else:
                # Si pas de mesures, tous les patients sont OFFLINE
                df['connection_status'] = 'OFFLINE'

        return df

    except Exception as e:
        st.error(f"Erreur chargement patients: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def load_patient_measurements(patient_id: str, hours: int = 24) -> pd.DataFrame:
    """Charge mesures d'un patient - TEMPS RÉEL avec diagnostic CORRIGÉ"""
    conn = get_fresh_connection()  # Utilise une connexion fraîche
    if not conn:
        return pd.DataFrame()

    # Debug: Vérifier d'abord si le patient existe
    debug_query = """
    SELECT COUNT(*) as total_measurements,
           MIN(recorded_at) as first_measurement,
           MAX(recorded_at) as last_measurement
    FROM measurements 
    WHERE patient_id = %s
    """

    try:
        debug_df = pd.read_sql_query(debug_query, conn, params=[patient_id])
        if not debug_df.empty:
            total = debug_df.iloc[0]['total_measurements']
            if total > 0:
                st.info(f"🔍 Debug: Patient {patient_id[:8]}... a {total} mesures totales")
            else:
                st.warning(f"⚠️ Aucune mesure trouvée pour le patient {patient_id[:8]}...")
    except Exception as e:
        st.error(f"❌ Erreur debug: {e}")

    query = """
    SELECT 
        recorded_at AT TIME ZONE 'UTC' as recorded_at,
        heart_rate_bpm,
        respiratory_rate_min,
        spo2_percent,
        temperature_celsius,
        ambient_temp_celsius,
        hydration_percent,
        activity_level,
        pain_scale,
        battery_percent,
        signal_quality,
        quality_flag
    FROM measurements 
    WHERE patient_id = %s 
        AND recorded_at >= NOW() - make_interval(hours => %s)
    ORDER BY recorded_at ASC
    LIMIT 1000
    """

    try:
        df = pd.read_sql_query(query, conn, params=[patient_id, hours])
        if not df.empty:
            df['recorded_at'] = pd.to_datetime(df['recorded_at'], utc=True)
            # Tri chronologique pour graphiques
            df = df.sort_values('recorded_at')
            st.success(f"✅ {len(df)} mesures chargées pour {patient_id[:8]}... sur {hours}h")
        else:
            st.warning(f"⚠️ Aucune mesure dans les {hours} dernières heures pour patient {patient_id[:8]}...")
        return df
    except Exception as e:
        st.error(f"Erreur chargement mesures: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def load_active_alerts(limit: int = 50) -> pd.DataFrame:
    """Charge alertes actives récentes - TEMPS RÉEL CORRIGÉ"""
    conn = get_fresh_connection()  # Utilise une connexion fraîche
    if not conn:
        return pd.DataFrame()

    query = """
    SELECT 
        a.alert_id,
        a.patient_id,
        u.first_name,
        u.last_name,
        p.genotype,
        a.alert_type,
        a.severity,
        a.title,
        a.message,
        a.created_at AT TIME ZONE 'UTC' as created_at,
        a.ack_deadline AT TIME ZONE 'UTC' as ack_deadline,
        a.escalation_level,
        a.vitals_snapshot,
        -- Temps écoulé depuis création
        EXTRACT(EPOCH FROM (NOW() - a.created_at))/60 as minutes_ago
    FROM alerts a
    JOIN patients p ON a.patient_id = p.patient_id
    JOIN users u ON p.user_id = u.user_id
    WHERE a.resolved_at IS NULL
        AND a.created_at >= NOW() - INTERVAL '2 hours'
    ORDER BY 
        CASE a.severity 
            WHEN 'critical' THEN 1 
            WHEN 'alert' THEN 2 
            WHEN 'warn' THEN 3 
            ELSE 4 
        END,
        a.created_at DESC
    LIMIT %s
    """

    try:
        df = pd.read_sql_query(query, conn, params=[limit])
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
            if 'ack_deadline' in df.columns:
                df['ack_deadline'] = pd.to_datetime(df['ack_deadline'], utc=True)
        return df
    except Exception as e:
        st.error(f"Erreur chargement alertes: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def load_system_metrics() -> Dict:
    """Charge métriques système globales - TEMPS RÉEL CORRIGÉ"""
    conn = get_fresh_connection()  # Utilise une connexion fraîche
    if not conn:
        return {}

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Patients total et actifs
        cursor.execute("""
            SELECT 
                COUNT(*) as total_patients,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM measurements m 
                        WHERE m.patient_id = p.patient_id 
                            AND m.recorded_at >= NOW() - INTERVAL '5 minutes'
                    )
                ) as active_patients,
                COUNT(*) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM measurements m 
                        WHERE m.patient_id = p.patient_id 
                            AND m.recorded_at >= NOW() - INTERVAL '30 minutes'
                    )
                ) as recently_active
            FROM patients p
        """)
        patients_stats = cursor.fetchone()

        # Mesures récentes
        cursor.execute("""
            SELECT 
                COUNT(*) as measurements_1h,
                COUNT(*) FILTER (WHERE recorded_at >= NOW() - INTERVAL '10 minutes') as measurements_10min,
                COUNT(*) FILTER (WHERE recorded_at >= NOW() - INTERVAL '24 hours') as measurements_24h
            FROM measurements 
            WHERE recorded_at >= NOW() - INTERVAL '24 hours'
        """)
        measurements_stats = cursor.fetchone()

        # Alertes par gravité
        cursor.execute("""
            SELECT 
                severity,
                COUNT(*) as count,
                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour') as recent_count
            FROM alerts 
            WHERE created_at >= NOW() - INTERVAL '24 hours'
                AND resolved_at IS NULL
            GROUP BY severity
        """)
        alerts_data = cursor.fetchall()
        alerts_by_severity = {row['severity']: {'total': row['count'], 'recent': row['recent_count']} for row in alerts_data}

        return {
            'total_patients': patients_stats['total_patients'],
            'active_patients': patients_stats['active_patients'],
            'recently_active': patients_stats['recently_active'],
            'measurements_24h': measurements_stats['measurements_24h'],
            'measurements_1h': measurements_stats['measurements_1h'],
            'measurements_10min': measurements_stats['measurements_10min'],
            'critical_alerts': alerts_by_severity.get('critical', {}).get('total', 0),
            'alert_alerts': alerts_by_severity.get('alert', {}).get('total', 0),
            'warn_alerts': alerts_by_severity.get('warn', {}).get('total', 0),
            'critical_alerts_recent': alerts_by_severity.get('critical', {}).get('recent', 0),
            'total_alerts': sum([data.get('total', 0) for data in alerts_by_severity.values()]),
            'measurement_rate_per_hour': measurements_stats['measurements_1h'],
            'last_updated': datetime.now(),
            'system_health': 'GOOD' if patients_stats['active_patients'] > 0 else 'WARNING'
        }

    except Exception as e:
        st.error(f"Erreur métriques système: {e}")
        return {}
    finally:
        if conn:
            conn.close()

# =====================================================
# COMPOSANTS INTERFACE UTILISATEUR CORRIGÉS
# =====================================================

def render_main_dashboard(patients_df: pd.DataFrame):
    """Rendu du dashboard principal avec tous les composants"""

    # Sidebar avec filtres
    sidebar_config = render_sidebar()

    # Utilisation des patients filtrés
    if not sidebar_config['filtered_patients'].empty:
        patients_df = sidebar_config['filtered_patients']

    # Métriques système
    with st.spinner("Chargement métriques système..."):
        metrics = load_system_metrics()

    # Affichage KPIs
    render_kpi_cards(metrics)

    # Séparateur
    st.markdown("---")

    # Tableau patients et sélection
    selected_patient_ids = render_patients_table(patients_df)

    # Graphiques détaillés si patients sélectionnés
    if selected_patient_ids:
        st.markdown("---")
        render_patient_vitals_charts(selected_patient_ids, sidebar_config['time_hours'])

    # Section alertes actives
    st.markdown("---")
    render_alerts_section()

def render_alerts_section():
    """Rendu section alertes actives"""
    st.subheader("🚨 Alertes Actives")

    alerts_df = load_active_alerts()

    if alerts_df.empty:
        st.success("✅ Aucune alerte active en cours")
        return

    # Statistiques alertes
    critical_count = len(alerts_df[alerts_df['severity'] == 'critical'])
    alert_count = len(alerts_df[alerts_df['severity'] == 'alert'])
    warn_count = len(alerts_df[alerts_df['severity'] == 'warn'])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("🔴 Critiques", critical_count)
    with col2:
        st.metric("🟡 Alertes", alert_count)
    with col3:
        st.metric("⚠️ Avertissements", warn_count)

    # Tableau alertes avec coloration
    display_alerts = alerts_df.copy()

    # Formatage des colonnes pour l'affichage
    display_alerts['patient_name'] = display_alerts['first_name'] + ' ' + display_alerts['last_name']
    display_alerts['time_ago'] = display_alerts['minutes_ago'].round(1).astype(str) + ' min'

    # Sélection colonnes d'affichage
    alert_columns = ['patient_name', 'genotype', 'severity', 'alert_type', 'title', 'time_ago']
    show_alerts = display_alerts[alert_columns].copy()
    show_alerts.columns = ['Patient', 'Génotype', 'Gravité', 'Type', 'Titre', 'Il y a']

    # Fonction de coloration pour alertes
    def highlight_alerts(row):
        styles = []
        for col in row.index:
            if col == 'Gravité':
                if row[col] == 'critical':
                    style = 'background-color: #ffcccc; font-weight: bold; color: #721c24'
                elif row[col] == 'alert':
                    style = 'background-color: #fff3cd; color: #856404'
                elif row[col] == 'warn':
                    style = 'background-color: #e2e3e5; color: #6c757d'
                else:
                    style = ''
            else:
                style = ''
            styles.append(style)
        return styles

    # Affichage tableau alertes avec style
    st.dataframe(
        show_alerts.style.apply(highlight_alerts, axis=1),
        use_container_width=True,
        height=300
    )

def render_sidebar():
    """Rendu sidebar avec filtres et configuration - CORRIGÉ"""
    st.sidebar.header("🏥 KIDJAMO IoT Dashboard")

    # Auto-refresh CORRIGÉ - Mécanisme non-bloquant
    st.sidebar.subheader("⏱️ Temps Réel")
    auto_refresh = st.sidebar.checkbox("Rafraîchissement automatique", value=True)

    refresh_interval = 10  # Valeur par défaut

    if auto_refresh:
        refresh_interval = st.sidebar.selectbox(
            "Intervalle (secondes)",
            [5, 10, 15, 30, 60],
            index=1
        )

        # Mécanisme auto-refresh NON-BLOQUANT
        if 'refresh_counter' not in st.session_state:
            st.session_state.refresh_counter = 0

        # Marqueur de dernière exécution
        if 'last_auto_refresh' not in st.session_state:
            st.session_state.last_auto_refresh = time.time()

        time_since_last = time.time() - st.session_state.last_auto_refresh

        if time_since_last >= refresh_interval:
            st.session_state.last_auto_refresh = time.time()
            st.session_state.refresh_counter += 1
            st.rerun()
        else:
            remaining = max(0, int(refresh_interval - time_since_last))
            st.sidebar.write(f"⏰ Refresh dans: {remaining}s")

        # Bouton de rafraîchissement manuel (filet de sécurité)
        if st.sidebar.button("Rafraîchir maintenant", key="manual_refresh"):
            st.session_state.last_auto_refresh = time.time()
            st.session_state.refresh_counter += 1
            st.rerun()

    # Filtres temporels
    st.sidebar.subheader("📅 Période d'analyse")
    time_range = st.sidebar.selectbox(
        "Plage temporelle",
        ["30 minutes", "1 heure", "3 heures", "6 heures", "12 heures", "24 heures"],
        index=3
    )

    time_mapping = {
        "30 minutes": 0.5,
        "1 heure": 1,
        "3 heures": 3,
        "6 heures": 6,
        "12 heures": 12,
        "24 heures": 24
    }

    # Filtres patients CORRIGÉ - Initialisation des variables
    st.sidebar.subheader("👥 Filtres Patients")

    # Chargement patients pour filtres
    patients_df = load_patients_overview()
    filtered_patients = patients_df.copy()

    # Initialisation des variables de filtre avec valeurs par défaut
    connection_filter = "Tous"
    selected_genotype = "Tous"
    alert_filter = "Tous"
    age_range = (0, 100)

    if not patients_df.empty:
        # Filtre par statut connexion
        connection_filter = st.sidebar.selectbox(
            "Statut connexion",
            ["Tous", "En ligne", "Déconnectés", "Alerte connexion"]
        )

        if connection_filter == "En ligne":
            filtered_patients = filtered_patients[filtered_patients['connection_status'] == 'ONLINE']
        elif connection_filter == "Déconnectés":
            filtered_patients = filtered_patients[filtered_patients['connection_status'] == 'OFFLINE']
        elif connection_filter == "Alerte connexion":
            filtered_patients = filtered_patients[filtered_patients['connection_status'] == 'WARNING']

        # Filtre par génotype CORRIGÉ
        available_genotypes = filtered_patients['genotype'].dropna().unique().tolist()
        if available_genotypes:
            genotypes = ['Tous'] + sorted(available_genotypes)
            selected_genotype = st.sidebar.selectbox("Génotype", genotypes)

            if selected_genotype != 'Tous':
                filtered_patients = filtered_patients[filtered_patients['genotype'] == selected_genotype]

        # Filtre par âge CORRIGÉ
        if 'age' in filtered_patients.columns and not filtered_patients.empty:
            ages = filtered_patients['age'].dropna()
            if not ages.empty:
                age_min, age_max = int(ages.min()), int(ages.max())
                if age_min < age_max:
                    age_range = st.sidebar.slider(
                        "Tranche d'âge",
                        age_min, age_max,
                        (age_min, age_max)
                    )
                    filtered_patients = filtered_patients[
                        (filtered_patients['age'] >= age_range[0]) &
                        (filtered_patients['age'] <= age_range[1])
                    ]

        # Filtre par alertes CORRIGÉ
        alert_filter = st.sidebar.selectbox(
            "État alertes",
            ["Tous", "Sans alerte", "Avec alertes récentes", "Alertes critiques"]
        )

        if alert_filter == "Sans alerte":
            filtered_patients = filtered_patients[filtered_patients['alerts_1h'] == 0]
        elif alert_filter == "Avec alertes récentes":
            filtered_patients = filtered_patients[filtered_patients['alerts_1h'] > 0]
        elif alert_filter == "Alertes critiques":
            filtered_patients = filtered_patients[filtered_patients['critical_alerts_1h'] > 0]

    # Statistiques filtres
    st.sidebar.markdown("---")
    st.sidebar.write(f"**Patients trouvés:** {len(filtered_patients)}")
    if not filtered_patients.empty and 'connection_status' in filtered_patients.columns:
        online_count = len(filtered_patients[filtered_patients['connection_status'] == 'ONLINE'])
        st.sidebar.write(f"**En ligne:** {online_count}")

    return {
        'time_hours': time_mapping.get(time_range, 6),
        'filtered_patients': filtered_patients,
        'auto_refresh': auto_refresh,
        'refresh_interval': refresh_interval if auto_refresh else 0,
        'connection_filter': connection_filter,
        'alert_filter': alert_filter,
        'selected_genotype': selected_genotype,
        'age_range': age_range
    }

def render_kpi_cards(metrics: Dict):
    """Rendu cartes KPI principales - AMÉLIORÉ"""
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        # Patients actifs avec indicateur santé
        active_ratio = metrics.get('active_patients', 0) / max(metrics.get('total_patients', 1), 1)
        color = "normal" if active_ratio > 0.8 else "inverse"

        st.metric(
            label="👥 Patients Actifs",
            value=f"{metrics.get('active_patients', 0)}/{metrics.get('total_patients', 0)}",
            delta=f"{active_ratio:.1%}",
            delta_color=color
        )

    with col2:
        # Taux de mesures avec évolution
        rate_10min = metrics.get('measurements_10min', 0) * 6  # Extrapolation sur 1h
        rate_1h = metrics.get('measurement_rate_per_hour', 0)

        st.metric(
            label="📊 Mesures/h",
            value=f"{rate_1h:,}",
            delta=f"{rate_10min - rate_1h:+,}" if rate_1h > 0 else None
        )

    with col3:
        # Alertes avec distinction récentes
        total_alerts = metrics.get('total_alerts', 0)
        recent_critical = metrics.get('critical_alerts_recent', 0)

        st.metric(
            label="🚨 Alertes Actives",
            value=total_alerts,
            delta=f"🔴 {recent_critical} critiques" if recent_critical > 0 else "✅ 0 critique"
        )

    with col4:
        # Santé système
        health = metrics.get('system_health', 'UNKNOWN')
        health_score = 100 if health == 'GOOD' else 50 if health == 'WARNING' else 0

        st.metric(
            label="⚡ Santé Système",
            value=f"{health_score}%",
            delta=health
        )

    with col5:
        # Dernière mise à jour
        last_update = metrics.get('last_updated', datetime.now())
        seconds_ago = (datetime.now() - last_update).total_seconds()

        st.metric(
            label="🕐 Dernière MàJ",
            value=f"{int(seconds_ago)}s",
            delta="Temps réel" if seconds_ago < 30 else "Retard"
        )

def render_patients_table(patients_df: pd.DataFrame):
    """Rendu tableau patients avec métriques - CORRIGÉ"""
    if patients_df.empty:
        st.warning("Aucun patient trouvé avec les filtres sélectionnés")
        return None

    st.subheader("👥 Patients Monitorés")

    # Préparation données pour affichage
    display_df = patients_df.copy()

    # Calcul temps depuis dernière mesure (UTC-aware pour éviter erreurs tz-naive vs tz-aware)
    if 'last_measurement' in display_df.columns:
        current_time_utc = pd.Timestamp.now(tz='UTC')
        lm = pd.to_datetime(display_df['last_measurement'], utc=True, errors='coerce')
        display_df['last_measurement_ago'] = (current_time_utc - lm).dt.total_seconds() / 60  # en minutes

    # Sélection et renommage colonnes
    columns_mapping = {
        'first_name': 'Prénom',
        'last_name': 'Nom',
        'age': 'Âge',
        'genotype': 'Génotype',
        'connection_status': 'Statut',
        'spo2_percent': 'SpO2 (%)',
        'heart_rate_bpm': 'FC (bpm)',
        'temperature_celsius': 'T°C',
        'pain_scale': 'Douleur',
        'battery_percent': 'Batterie (%)',
        'alerts_1h': 'Alertes 1h',
        'critical_alerts_1h': 'Critiques 1h'
    }

    # Création df d'affichage
    available_cols = [col for col in columns_mapping.keys() if col in display_df.columns]
    show_df = display_df[available_cols].copy()
    show_df = show_df.rename(columns=columns_mapping)

    # Formatage des valeurs
    numeric_cols = ['SpO2 (%)', 'FC (bpm)', 'T°C', 'Douleur', 'Batterie (%)']
    for col in numeric_cols:
        if col in show_df.columns:
            show_df[col] = show_df[col].round(1)

    # Fonction de coloration
    def highlight_critical_values(row):
        styles = []
        for col in row.index:
            style = ''
            val = row[col]

            if pd.isna(val):
                style = 'color: gray'
            elif col == 'Statut':
                if val == 'ONLINE':
                    style = 'background-color: #d4edda; color: #155724'
                elif val == 'WARNING':
                    style = 'background-color: #fff3cd; color: #856404'
                elif val == 'OFFLINE':
                    style = 'background-color: #f8d7da; color: #721c24'
            elif col == 'SpO2 (%)' and isinstance(val, (int, float)):
                if val < 88:
                    style = 'background-color: #ffcccc; font-weight: bold'
                elif val < 92:
                    style = 'background-color: #ffffcc'
            elif col == 'FC (bpm)' and isinstance(val, (int, float)):
                if val > 120 or val < 50:
                    style = 'background-color: #ffffcc'
            elif col == 'T°C' and isinstance(val, (int, float)):
                if val >= 38.0:
                    style = 'background-color: #ffcccc'
            elif col == 'Douleur' and isinstance(val, (int, float)):
                if val >= 7:
                    style = 'background-color: #ffcccc'
            elif col == 'Batterie (%)' and isinstance(val, (int, float)):
                if val <= 15:
                    style = 'background-color: #ffffcc'
            elif col in ['Critiques 1h'] and isinstance(val, (int, float)):
                if val > 0:
                    style = 'background-color: #ff9999; font-weight: bold'

            styles.append(style)
        return styles

    # Affichage avec style
    st.dataframe(
        show_df.style.apply(highlight_critical_values, axis=1),
        use_container_width=True,
        height=400
    )

    # Sélection patients pour graphiques
    if not patients_df.empty:
        patient_options = [
            f"{row['first_name']} {row['last_name']} ({row['genotype']})"
            for _, row in patients_df.iterrows()
        ]

        selected_patients = st.multiselect(
            "🔍 Sélectionner patients pour analyse détaillée (max 5):",
            options=patient_options,
            max_selections=5,
            help="Choisissez jusqu'à 5 patients pour voir leurs graphiques d'évolution"
        )

        # Retourner les IDs des patients sélectionnés
        if selected_patients:
            selected_ids = []
            for selection in selected_patients:
                # Parse nom du format "Prénom Nom (Génotype)"
                name_part = selection.split(' (')[0]  # Retire la partie génotype
                name_parts = name_part.split(' ')
                if len(name_parts) >= 2:
                    first_name = name_parts[0]
                    last_name = ' '.join(name_parts[1:])

                    patient_row = patients_df[
                        (patients_df['first_name'] == first_name) &
                        (patients_df['last_name'] == last_name)
                    ]
                    if not patient_row.empty:
                        selected_ids.append(patient_row.iloc[0]['patient_id'])

            return selected_ids

    return None

def render_patient_vitals_charts(patient_ids: List[str], time_hours: int):
    """Rendu graphiques signes vitaux multi-patients - CORRIGÉ"""
    if not patient_ids:
        st.info("👆 Sélectionnez des patients dans le tableau ci-dessus pour voir leurs graphiques d'évolution")
        return

    st.subheader("📈 Évolution Temps Réel des Signes Vitaux")

    # Chargement des données pour tous les patients sélectionnés
    all_measurements = pd.DataFrame()
    patients_info = {}

    with st.spinner("Chargement des données temps réel..."):
        patients_df = load_patients_overview()

        for patient_id in patient_ids:
            measurements = load_patient_measurements(patient_id, time_hours)
            if not measurements.empty:
                # Informations patient
                patient_info = patients_df[patients_df['patient_id'] == patient_id]
                if not patient_info.empty:
                    patient_name = f"{patient_info.iloc[0]['first_name']} {patient_info.iloc[0]['last_name']}"
                    genotype = patient_info.iloc[0]['genotype']
                    patients_info[patient_id] = {'name': patient_name, 'genotype': genotype}

                    measurements['patient_name'] = patient_name
                    measurements['patient_id'] = patient_id
                    measurements['genotype'] = genotype
                    all_measurements = pd.concat([all_measurements, measurements], ignore_index=True)

    if all_measurements.empty:
        st.warning("⚠️ Aucune donnée de mesure trouvée pour les patients sélectionnés sur la période choisie")
        st.info(f"Période analysée: {time_hours} heures")
        return

    st.success(f"✅ {len(all_measurements)} mesures chargées pour {len(patient_ids)} patients")

    # Organisation en onglets avec graphiques FONCTIONNELS
    tab1, tab2, tab3, tab4 = st.tabs(["🫁 SpO2 & Fréquence Cardiaque", "🌡️ Température", "💧 Hydratation & Douleur", "🔋 Indicateurs Techniques"])

    with tab1:
        st.subheader("SpO2 et Fréquence Cardiaque")

        # Graphique SpO2
        fig_spo2 = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            fig_spo2.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['spo2_percent'],
                    mode='lines+markers',
                    name=f"{patient_name} ({genotype})",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>SpO2: %{y}%<extra></extra>'
                )
            )

        # Lignes de seuil SpO2
        fig_spo2.add_hline(y=88, line_dash="dash", line_color="red",
                          annotation_text="Seuil critique (88%)")
        fig_spo2.add_hline(y=95, line_dash="dash", line_color="green",
                          annotation_text="Normal (95%)")

        fig_spo2.update_layout(
            title=f"Évolution SpO2 - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="SpO2 (%)",
            height=400,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_spo2, use_container_width=True)

        # Graphique Fréquence Cardiaque
        fig_hr = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            fig_hr.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['heart_rate_bpm'],
                    mode='lines+markers',
                    name=f"{patient_name} ({genotype})",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>FC: %{y} bpm<extra></extra>'
                )
            )

        # Lignes de seuil FC
        fig_hr.add_hline(y=120, line_dash="dash", line_color="orange",
                        annotation_text="Tachycardie adulte (120 bpm)")
        fig_hr.add_hline(y=50, line_dash="dash", line_color="blue",
                        annotation_text="Bradycardie (50 bpm)")

        fig_hr.update_layout(
            title=f"Évolution Fréquence Cardiaque - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="Fréquence Cardiaque (bpm)",
            height=400,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_hr, use_container_width=True)

    with tab2:
        st.subheader("Température Corporelle")

        fig_temp = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            # Température corporelle
            fig_temp.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['temperature_celsius'],
                    mode='lines+markers',
                    name=f"{patient_name} - T° Corps",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>Température: %{y}°C<extra></extra>'
                )
            )

            # Température ambiante (ligne plus fine)
            if 'ambient_temp_celsius' in patient_data.columns:
                fig_temp.add_trace(
                    go.Scatter(
                        x=patient_data['recorded_at'],
                        y=patient_data['ambient_temp_celsius'],
                        mode='lines',
                        name=f"{patient_name} - T° Ambiante",
                        line=dict(width=1, dash='dot'),
                        opacity=0.6,
                        hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>T° Ambiante: %{y}°C<extra></extra>'
                    )
                )

        # Seuils température
        fig_temp.add_hline(y=38.0, line_dash="dash", line_color="orange",
                          annotation_text="Fièvre (38°C)")
        fig_temp.add_hline(y=39.5, line_dash="dash", line_color="red",
                          annotation_text="Fièvre élevée (39.5°C)")

        fig_temp.update_layout(
            title=f"Évolution Température - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="Température (°C)",
            height=400,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_temp, use_container_width=True)

    with tab3:
        st.subheader("Hydratation et Douleur")

        # Graphique Hydratation
        fig_hyd = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            fig_hyd.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['hydration_percent'],
                    mode='lines+markers',
                    name=f"{patient_name} - Hydratation",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>Hydratation: %{y}%<extra></extra>'
                )
            )

        # Seuils hydratation
        fig_hyd.add_hline(y=40, line_dash="dash", line_color="red",
                         annotation_text="Déshydratation critique (40%)")
        fig_hyd.add_hline(y=55, line_dash="dash", line_color="orange",
                         annotation_text="Déshydratation modérée (55%)")

        fig_hyd.update_layout(
            title=f"Évolution Hydratation - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="Hydratation (%)",
            height=300,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_hyd, use_container_width=True)

        # Graphique Douleur
        fig_pain = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            fig_pain.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['pain_scale'],
                    mode='lines+markers',
                    name=f"{patient_name} - Douleur",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>Douleur: %{y}/10<extra></extra>'
                )
            )

        # Seuils douleur
        fig_pain.add_hline(y=7, line_dash="dash", line_color="red",
                          annotation_text="Douleur sévère (7/10)")
        fig_pain.add_hline(y=4, line_dash="dash", line_color="orange",
                          annotation_text="Douleur modérée (4/10)")

        fig_pain.update_layout(
            title=f"Évolution Douleur - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="Échelle Douleur (/10)",
            height=300,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_pain, use_container_width=True)

    with tab4:
        st.subheader("Indicateurs Techniques")

        # Graphique Batterie
        fig_bat = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            fig_bat.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['battery_percent'],
                    mode='lines+markers',
                    name=f"{patient_name} - Batterie",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>Batterie: %{y}%<extra></extra>'
                )
            )

        # Seuils batterie
        fig_bat.add_hline(y=15, line_dash="dash", line_color="red",
                         annotation_text="Batterie critique (15%)")
        fig_bat.add_hline(y=30, line_dash="dash", line_color="orange",
                         annotation_text="Batterie faible (30%)")

        fig_bat.update_layout(
            title=f"Évolution Batterie - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="Batterie (%)",
            height=300,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_bat, use_container_width=True)

        # Graphique Qualité Signal
        fig_signal = go.Figure()
        for patient_name in all_measurements['patient_name'].unique():
            patient_data = all_measurements[all_measurements['patient_name'] == patient_name]
            genotype = patient_data['genotype'].iloc[0]

            fig_signal.add_trace(
                go.Scatter(
                    x=patient_data['recorded_at'],
                    y=patient_data['signal_quality'],
                    mode='lines+markers',
                    name=f"{patient_name} - Signal",
                    line=dict(width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>Temps: %{x}<br>Signal: %{y}%<extra></extra>'
                )
            )

        # Seuils qualité signal
        fig_signal.add_hline(y=50, line_dash="dash", line_color="red",
                           annotation_text="Signal faible (50%)")
        fig_signal.add_hline(y=75, line_dash="dash", line_color="orange",
                           annotation_text="Signal moyen (75%)")

        fig_signal.update_layout(
            title=f"Évolution Qualité Signal - Dernières {time_hours}h",
            xaxis_title="Temps",
            yaxis_title="Qualité Signal (%)",
            height=300,
            showlegend=True,
            hovermode='x unified'
        )
        st.plotly_chart(fig_signal, use_container_width=True)

# =====================================================
# FONCTION PRINCIPALE AVEC AUTO-REFRESH TEMPS RÉEL
# =====================================================

def main():
    """Fonction principale du dashboard avec auto-refresh temps réel"""

    # Configuration auto-refresh avec timer visible
    if HAS_AUTOREFRESH:
        # Auto-refresh toutes les 10 secondes avec compteur
        refresh_count = st_autorefresh(interval=10 * 1000, key="dashboard_refresh")

        # Affichage du statut temps réel
        with st.container():
            current_time = datetime.now().strftime("%H:%M:%S")
            if refresh_count > 0:
                st.success(f"🔄 **TEMPS RÉEL ACTIF** | Dernière mise à jour: {current_time} | Refresh #{refresh_count}")
            else:
                st.info(f"🔄 **TEMPS RÉEL ACTIF** | Première charge: {current_time}")
    else:
        # Fallback sans auto-refresh
        st.warning("⚠️ Auto-refresh non disponible. Actualisez manuellement la page.")
        if st.button("🔄 Actualiser maintenant"):
            st.experimental_rerun()

    # Titre principal avec horodatage
    st.title("🏥 KIDJAMO IoT - Dashboard Patients Temps Réel")

    # Affichage de l'état de la connexion
    conn_test = get_fresh_connection()
    if conn_test:
        st.success("✅ Connexion base de données active")
        conn_test.close()
    else:
        st.error("❌ Problème de connexion base de données")
        return

    # Chargement des données en temps réel
    with st.spinner("🔄 Chargement des données temps réel..."):
        patients_df = load_patients_overview()

    if patients_df.empty:
        st.error("❌ Aucune donnée patient disponible")
        return

    # Affichage du dashboard principal
    render_main_dashboard(patients_df)

# =====================================================
# EXÉCUTION DU DASHBOARD
# =====================================================

if __name__ == "__main__":
    main()
else:
    # Exécution directe pour Streamlit
    main()
