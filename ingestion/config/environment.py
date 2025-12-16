"""
KIDJAMO - Gestionnaire de Configuration Environnement
Charge automatiquement les variables d'environnement selon le mode (local/cloud)
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import load_dotenv

class EnvironmentConfig:
    """Gestionnaire centralisé de la configuration environnement"""

    def __init__(self, environment: str = None):
        self.workspace_root = Path(__file__).parent
        self.environment = environment or os.getenv('ENVIRONMENT', 'development')
        self.config = {}
        self.logger = self._setup_logging()

        # Charger la configuration
        self._load_environment()
        self._validate_config()

    def _setup_logging(self) -> logging.Logger:
        """Configure le logging selon l'environnement"""
        logger = logging.getLogger('kidjamo.config')

        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        log_format = os.getenv('LOG_FORMAT', 'simple')

        if log_format == 'json':
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
            )
        else:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )

        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, log_level))

        return logger

    def _load_environment(self):
        """Charge les variables d'environnement selon l'environnement"""
        env_files = [
            f'.env.{self.environment}',
            '.env.local',
            '.env'
        ]

        loaded_files = []
        for env_file in env_files:
            env_path = self.workspace_root / env_file
            if env_path.exists():
                load_dotenv(env_path, override=True)
                loaded_files.append(env_file)
                self.logger.info(f"✅ Chargé: {env_file}")
                break

        if not loaded_files:
            self.logger.warning("⚠️ Aucun fichier .env trouvé - Utilisation des variables système")

        # Construire le dictionnaire de config
        self._build_config()

    def _build_config(self):
        """Construit le dictionnaire de configuration"""
        self.config = {
            # Environnement général
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'pipeline_mode': os.getenv('PIPELINE_MODE', 'local'),
            'debug': os.getenv('LOG_LEVEL', 'INFO').upper() == 'DEBUG',

            # AWS Configuration
            'aws': {
                'access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
                'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
                'region': os.getenv('AWS_DEFAULT_REGION', 'eu-west-1'),
                'landing_bucket': os.getenv('LANDING_BUCKET'),
                'sqs_queue_url': os.getenv('SQS_QUEUE_URL'),
                'sns_topic': os.getenv('SNS_EMERGENCY_TOPIC')
            },

            # Base de données
            'database': {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': int(os.getenv('DB_PORT', 5432)),
                'name': os.getenv('DB_NAME', 'kidjamo-db'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', 'kidjamo@'),
                'ssl_mode': os.getenv('DB_SSL_MODE', 'disable'),
                'url': self._build_database_url()
            },

            # API Configuration
            'api': {
                'jwt_secret': os.getenv('JWT_SECRET_KEY'),
                'jwt_algorithm': os.getenv('JWT_ALGORITHM', 'HS256'),
                'jwt_expire_hours': int(os.getenv('JWT_EXPIRE_HOURS', 24)),
                'api_key': os.getenv('IOT_API_KEY'),
                'rate_limit': int(os.getenv('API_RATE_LIMIT_PER_MINUTE', 60))
            },

            # Pipeline Configuration
            'pipeline': {
                'batch_size': int(os.getenv('BATCH_SIZE', 100)),
                'processing_interval': int(os.getenv('PROCESSING_INTERVAL_SECONDS', 30)),
                'local_data_path': os.getenv('LOCAL_DATA_PATH'),
                'local_output_path': os.getenv('LOCAL_OUTPUT_PATH'),
                'enable_alerts': os.getenv('ENABLE_EMERGENCY_ALERTS', 'true').lower() == 'true',
                'alert_cooldown': int(os.getenv('ALERT_COOLDOWN_SECONDS', 300))
            },

            # Simulation IoT
            'simulation': {
                'enabled': os.getenv('SIMULATE_IOT_DATA', 'false').lower() == 'true',
                'device_count': int(os.getenv('SIMULATE_DEVICE_COUNT', 5)),
                'interval_seconds': int(os.getenv('SIMULATE_INTERVAL_SECONDS', 60))
            }
        }

    def _build_database_url(self) -> str:
        """Construit l'URL de connexion PostgreSQL"""
        host = os.getenv('DB_HOST', 'localhost')
        port = os.getenv('DB_PORT', 5432)
        name = os.getenv('DB_NAME', 'kidjamo-db')
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', 'kidjamo@')

        return f"postgresql://{user}:{password}@{host}:{port}/{name}"

    def _validate_config(self):
        """Valide la configuration selon l'environnement"""
        errors = []

        # Validation base de données
        if not self.config['database']['password']:
            errors.append("DB_PASSWORD requis")

        # Validation cloud (si mode cloud)
        if self.is_cloud_mode():
            if not self.config['aws']['access_key_id']:
                errors.append("AWS_ACCESS_KEY_ID requis en mode cloud")
            if not self.config['aws']['secret_access_key']:
                errors.append("AWS_SECRET_ACCESS_KEY requis en mode cloud")
            if not self.config['aws']['landing_bucket']:
                errors.append("LANDING_BUCKET requis en mode cloud")
            if not self.config['aws']['sqs_queue_url']:
                errors.append("SQS_QUEUE_URL requis en mode cloud")

        # Validation production
        if self.is_production():
            if not self.config['api']['jwt_secret'] or len(self.config['api']['jwt_secret']) < 32:
                errors.append("JWT_SECRET_KEY doit avoir au moins 32 caractères en production")

        if errors:
            error_msg = "Erreurs de configuration:\n" + "\n".join(f"- {err}" for err in errors)
            self.logger.error(error_msg)
            raise ValueError(error_msg)

        self.logger.info(f"✅ Configuration validée pour l'environnement: {self.environment}")

    def is_local_mode(self) -> bool:
        """Vérifie si on est en mode local"""
        return self.config['pipeline_mode'] == 'local'

    def is_cloud_mode(self) -> bool:
        """Vérifie si on est en mode cloud"""
        return self.config['pipeline_mode'] == 'cloud'

    def is_production(self) -> bool:
        """Vérifie si on est en production"""
        return self.environment == 'production'

    def is_development(self) -> bool:
        """Vérifie si on est en développement"""
        return self.environment in ['development', 'dev']

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Récupère une valeur de configuration avec notation pointée

        Exemples:
        - config.get('database.host')
        - config.get('aws.landing_bucket')
        - config.get('pipeline.batch_size')
        """
        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def get_database_config(self) -> Dict[str, Any]:
        """Retourne la configuration base de données complète"""
        return self.config['database']

    def get_aws_config(self) -> Dict[str, Any]:
        """Retourne la configuration AWS complète"""
        return self.config['aws']

    def summary(self) -> Dict[str, Any]:
        """Retourne un résumé de la configuration (sans secrets)"""
        summary = self.config.copy()

        # Masquer les secrets
        if summary['database']['password']:
            summary['database']['password'] = '***masked***'
        if summary['aws']['secret_access_key']:
            summary['aws']['secret_access_key'] = '***masked***'
        if summary['api']['jwt_secret']:
            summary['api']['jwt_secret'] = '***masked***'

        return summary

# Instance globale de configuration
config = EnvironmentConfig()

# Fonctions utilitaires pour un accès facile
def get_config() -> EnvironmentConfig:
    """Retourne l'instance de configuration"""
    return config

def is_local_mode() -> bool:
    """Raccourci pour vérifier le mode local"""
    return config.is_local_mode()

def is_cloud_mode() -> bool:
    """Raccourci pour vérifier le mode cloud"""
    return config.is_cloud_mode()

def get_database_url() -> str:
    """Raccourci pour l'URL de base de données"""
    return config.get('database.url')

# Logger configuré
logger = config.logger

if __name__ == "__main__":
    # Test de la configuration
    print("🔧 KIDJAMO - Test Configuration Environnement")
    print("=" * 50)

    try:
        config = EnvironmentConfig()

        print(f"Environnement: {config.environment}")
        print(f"Mode pipeline: {config.get('pipeline_mode')}")
        print(f"Mode local: {config.is_local_mode()}")
        print(f"Mode cloud: {config.is_cloud_mode()}")
        print(f"Base de données: {config.get('database.host')}:{config.get('database.port')}")

        if config.is_cloud_mode():
            print(f"Bucket S3: {config.get('aws.landing_bucket')}")
            print(f"Région AWS: {config.get('aws.region')}")

        print("\n✅ Configuration chargée avec succès !")

    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
