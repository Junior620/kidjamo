#!/usr/bin/env python3
"""
Connecteur PostgreSQL Simplifié pour Pipeline IoT Temps Réel
Connecteur léger sans dépendances AWS Glue pour traitement Kinesis
"""

import json
import boto3
import psycopg2
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)

class SimplePostgreSQLConnector:
    """Connecteur PostgreSQL simplifié pour streaming IoT"""

    def __init__(self, secret_id: str = "kidjamo-rds-credentials", region: str = "eu-west-1"):
        self.secret_id = secret_id
        self.region = region
        self.connection = None
        self._credentials = None

    def _get_credentials(self):
        """Récupère les credentials depuis AWS Secrets Manager"""
        if self._credentials:
            return self._credentials

        try:
            session = boto3.Session(region_name=self.region)
            secrets_client = session.client('secretsmanager')

            response = secrets_client.get_secret_value(SecretId=self.secret_id)

            # Gestion robuste de l'encodage
            secret_string = response['SecretString']
            if isinstance(secret_string, bytes):
                secret_string = secret_string.decode('utf-8', errors='replace')

            self._credentials = json.loads(secret_string)

            logger.info(f"Credentials recuperes depuis {self.secret_id}")
            return self._credentials

        except Exception as e:
            logger.error(f"Erreur recuperation credentials: {str(e)}")
            raise

    def connect(self):
        """Établit la connexion PostgreSQL"""
        try:
            creds = self._get_credentials()

            # Connexion avec gestion explicite de l'encodage
            self.connection = psycopg2.connect(
                host=creds['host'],
                port=creds['port'],
                database=creds['dbname'],
                user=creds['username'],
                password=creds['password'],
                client_encoding='utf8'
            )

            # Configuration pour autocommit désactivé (gestion manuelle transactions)
            self.connection.autocommit = False

            # Forcer l'encodage UTF-8
            self.connection.set_client_encoding('UTF8')

            logger.info(f"Connexion PostgreSQL etablie: {creds['host']}")

        except Exception as e:
            logger.error(f"Erreur connexion PostgreSQL: {str(e)}")
            raise

    def close(self):
        """Ferme la connexion proprement"""
        if self.connection:
            try:
                self.connection.close()
                logger.info("✅ Connexion PostgreSQL fermée")
            except Exception as e:
                logger.warning(f"⚠️ Erreur fermeture connexion: {e}")

    def test_connection(self) -> bool:
        """Test la connexion PostgreSQL"""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception as e:
            logger.error(f"❌ Test connexion échoué: {e}")
            return False
