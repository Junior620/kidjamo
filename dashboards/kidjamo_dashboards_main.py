#!/usr/bin/env python3
"""
🏥 Kidjamo - Application Dashboards Principale (Streamlit)
Navigation entre Dashboard Temps Réel et Dashboard Historique
"""

import streamlit as st
from streamlit_option_menu import option_menu
import sys
import os

# Ajouter le dossier dashboards au path pour les imports
sys.path.append(os.path.dirname(__file__))

from config import STREAMLIT_CONFIG

# Configuration de la page
st.set_page_config(
    page_title=STREAMLIT_CONFIG['page_title'],
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout=STREAMLIT_CONFIG['layout'],
    initial_sidebar_state='collapsed'
)

def main():
    # En-tête principal
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0;">
        <h1 style="color: #2c3e50; font-size: 3rem; margin-bottom: 0.5rem;">
            🏥 Kidjamo - Dashboards IoT
        </h1>
        <p style="color: #7f8c8d; font-size: 1.2rem; margin-bottom: 2rem;">
            Système de Surveillance Drépanocytose - Tech4Good Cameroun
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Menu de navigation horizontal
    selected = option_menu(
        menu_title=None,
        options=["🚨 Temps Réel", "📊 Historique", "⚙️ Configuration"],
        icons=["activity", "graph-up", "gear"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#fafafa"},
            "icon": {"color": "orange", "font-size": "25px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "center",
                "margin": "0px",
                "--hover-color": "#eee"
            },
            "nav-link-selected": {"background-color": "#3498db"},
        }
    )

    # Affichage du dashboard sélectionné
    if selected == "🚨 Temps Réel":
        st.markdown("---")
        try:
            import realtime_dashboard_streamlit
            realtime_dashboard_streamlit.main()
        except ImportError as e:
            st.error(f"❌ Erreur d'import du dashboard temps réel: {e}")
            st.info("Vérifiez que tous les modules sont installés correctement.")
        except Exception as e:
            st.error(f"❌ Erreur dashboard temps réel: {e}")

    elif selected == "📊 Historique":
        st.markdown("---")
        try:
            import database_dashboard_streamlit
            database_dashboard_streamlit.main()
        except ImportError as e:
            st.error(f"❌ Erreur d'import du dashboard historique: {e}")
            st.info("Vérifiez que tous les modules sont installés correctement.")
        except Exception as e:
            st.error(f"❌ Erreur dashboard historique: {e}")

    elif selected == "⚙️ Configuration":
        show_configuration_page()

def show_configuration_page():
    """Page de configuration et vérification du système"""
    st.header("⚙️ Configuration Système")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("🔧 Configuration AWS")

        # Vérification des variables d'environnement AWS
        aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')

        if aws_access_key and aws_secret_key:
            st.success("✅ Credentials AWS configurés")
            st.info(f"🌍 Région: {aws_region}")

            # Test de connexion Kinesis
            if st.button("🧪 Tester Kinesis"):
                try:
                    import boto3
                    kinesis = boto3.client('kinesis', region_name=aws_region)
                    response = kinesis.describe_stream(StreamName='kidjamo-dev-iot-measurements')
                    st.success("✅ Connexion Kinesis réussie")
                    st.json({"StreamStatus": response['StreamDescription']['StreamStatus']})
                except Exception as e:
                    st.error(f"❌ Erreur Kinesis: {e}")
        else:
            st.error("❌ Credentials AWS manquants")
            st.info("Configurez AWS_ACCESS_KEY_ID et AWS_SECRET_ACCESS_KEY")

    with col2:
        st.subheader("🗄️ Configuration PostgreSQL")

        # Vérification de la configuration DB
        db_host = os.getenv('DB_HOST')
        db_name = os.getenv('DB_NAME', 'kidjamo')
        db_user = os.getenv('DB_USER', 'kidjamo_admin')

        if db_host and db_user:
            st.success("✅ Configuration DB trouvée")
            st.info(f"🏠 Host: {db_host}")
            st.info(f"📊 Database: {db_name}")
            st.info(f"👤 User: {db_user}")

            # Test de connexion PostgreSQL
            if st.button("🧪 Tester PostgreSQL"):
                try:
                    import psycopg2
                    from config import DB_CONFIG

                    conn = psycopg2.connect(
                        host=DB_CONFIG['host'],
                        port=DB_CONFIG['port'],
                        database=DB_CONFIG['database'],
                        user=DB_CONFIG['user'],
                        password=DB_CONFIG['password']
                    )

                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM measurements")
                    count = cursor.fetchone()[0]

                    st.success("✅ Connexion PostgreSQL réussie")
                    st.info(f"📊 Mesures disponibles: {count:,}")

                    cursor.close()
                    conn.close()

                except Exception as e:
                    st.error(f"❌ Erreur PostgreSQL: {e}")
        else:
            st.error("❌ Configuration DB manquante")
            st.info("Vérifiez les variables DB_HOST, DB_USER, etc.")

    # Instructions d'installation
    st.markdown("---")
    st.subheader("📋 Instructions d'Installation")

    st.markdown("""
    ### 1. Installation des dépendances
    ```bash
    pip install -r requirements.txt
    ```
    
    ### 2. Configuration des variables d'environnement
    ```bash
    # Copier le fichier exemple
    cp .env.example .env
    
    # Éditer .env avec vos vraies valeurs
    # AWS_ACCESS_KEY_ID=votre_cle_aws
    # AWS_SECRET_ACCESS_KEY=votre_secret_aws
    # DB_PASSWORD=votre_mot_de_passe_db
    ```
    
    ### 3. Lancement de l'application
    ```bash
    streamlit run kidjamo_dashboards_main.py
    ```
    """)

    # Informations système
    with st.expander("🔍 Informations Système"):
        st.write("**Python Version:**", sys.version)
        st.write("**Streamlit Version:**", st.__version__)
        st.write("**Working Directory:**", os.getcwd())

        # Liste des modules installés
        try:
            import pkg_resources
            installed_packages = [d.project_name for d in pkg_resources.working_set]
            required_packages = ['streamlit', 'boto3', 'psycopg2-binary', 'pandas', 'plotly']

            st.write("**Modules Requis:**")
            for package in required_packages:
                if package in installed_packages or package.replace('-', '_') in installed_packages:
                    st.write(f"✅ {package}")
                else:
                    st.write(f"❌ {package} - Non installé")
        except:
            st.write("Impossible de vérifier les modules installés")

if __name__ == "__main__":
    main()
