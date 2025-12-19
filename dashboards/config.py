# Configuration pour les dashboards Kidjamo
import os
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration AWS
AWS_CONFIG = {
    'region_name': 'eu-west-1',
    'kinesis_stream_name': 'kidjamo-iot-stream-dev',  # Nom correct du stream
    'aws_access_key_id': None,  # Utilise les credentials par défaut
    'aws_secret_access_key': None  # Utilise les credentials par défaut
}

# Configuration PostgreSQL
DB_CONFIG = {
    'host': 'kidjamo-dev-postgres-fixed.crgg26e8owiz.eu-west-1.rds.amazonaws.com',
    'port': 5432,
    'database': 'kidjamo',  # Nom correct de la base
    'username': 'kidjamo_admin',
    'password': 'JBRPp5t!uLqDKJRY'
}

# Seuils d'alerte pour le bracelet MPU_Christian_8266MOD
ALERT_THRESHOLDS = {
    'fall_detection': 15.0,      # m/s² - Seuil de détection de chute (standard Kinesis)
    'hyperactivity': 8.0,        # m/s² - Seuil d'hyperactivité (standard Kinesis)
    'temperature_min': 18.0,     # °C - Température minimale
    'temperature_max': 35.0,     # °C - Température maximale
    'battery_low': 20,           # % - Batterie faible
    'gyro_threshold': 200.0      # °/s - Seuil gyroscope
}

# Configuration Streamlit
STREAMLIT_CONFIG = {
    'page_title': 'Kidjamo - Dashboards IoT',
    'page_icon': '🏥',
    'layout': 'wide',
    'initial_sidebar_state': 'expanded'
}
