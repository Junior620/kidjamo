#!/usr/bin/env python3
"""
Test Simple de Connexion PostgreSQL pour Debugging
"""

import json
import boto3
import psycopg2
import logging

# Configuration logging simple
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def test_postgres_connection():
    """Test direct de connexion PostgreSQL"""
    try:
        # 1. Test récupération credentials
        logger.info("1. Test recuperation credentials AWS Secrets Manager...")

        session = boto3.Session(region_name='eu-west-1')
        secrets_client = session.client('secretsmanager')

        response = secrets_client.get_secret_value(SecretId='kidjamo-rds-credentials')

        # Gestion encoding robuste
        secret_string = response['SecretString']
        logger.info(f"Type secret: {type(secret_string)}")
        logger.info(f"Longueur secret: {len(secret_string) if secret_string else 'None'}")

        if isinstance(secret_string, bytes):
            logger.info("Secret est en bytes, conversion...")
            secret_string = secret_string.decode('utf-8', errors='replace')

        # Parse JSON avec gestion d'erreur
        try:
            credentials = json.loads(secret_string)
            logger.info("Credentials JSON parse avec succes")
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON decode: {e}")
            # Essayer de nettoyer le string
            secret_string = secret_string.replace('\x00', '').strip()
            credentials = json.loads(secret_string)

        logger.info(f"Host: {credentials.get('host', 'MISSING')}")
        logger.info(f"Database: {credentials.get('dbname', 'MISSING')}")
        logger.info(f"User: {credentials.get('username', 'MISSING')}")

        # 2. Test connexion PostgreSQL
        logger.info("2. Test connexion PostgreSQL...")

        connection = psycopg2.connect(
            host=credentials['host'],
            port=credentials['port'],
            database=credentials['dbname'],
            user=credentials['username'],
            password=credentials['password']
        )

        logger.info("SUCCESS: Connexion PostgreSQL etablie!")

        # 3. Test requête simple
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, version()")
            result = cursor.fetchone()
            logger.info(f"Database: {result[0]}")
            logger.info(f"User: {result[1]}")
            logger.info(f"Version: {result[2][:50]}...")

        connection.close()
        logger.info("SUCCESS: Test complet reussi!")
        return True

    except Exception as e:
        logger.error(f"ERREUR: {type(e).__name__}: {str(e)}")
        return False

if __name__ == "__main__":
    test_postgres_connection()
