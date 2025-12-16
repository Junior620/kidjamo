"""
Ingestion des données IoT depuis la Landing Zone cloud
Modifié pour s'intégrer avec l'API d'ingestion IoT
"""

import pandas as pd
import boto3
import json
from datetime import datetime
import os
from typing import List, Dict
import logging

# ✅ NOUVEAU: Import du gestionnaire de configuration
from config.environment import get_config, is_cloud_mode, is_local_mode, logger
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name, to_utc_timestamp
from pyspark.sql.types import (StructType, StructField, StringType, DoubleType, IntegerType, TimestampType)
import time
import sys

class IoTDataProcessor:
    def __init__(self):
        # ✅ NOUVEAU: Utilise la configuration centralisée
        self.config = get_config()

        # Configuration cloud depuis les variables d'environnement
        self.s3_client = None
        self.sqs_client = None

        if is_cloud_mode() and self.config.get('aws.access_key_id'):
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.config.get('aws.access_key_id'),
                    aws_secret_access_key=self.config.get('aws.secret_access_key'),
                    region_name=self.config.get('aws.region')
                )
                self.sqs_client = boto3.client(
                    'sqs',
                    aws_access_key_id=self.config.get('aws.access_key_id'),
                    aws_secret_access_key=self.config.get('aws.secret_access_key'),
                    region_name=self.config.get('aws.region')
                )
                logger.info("✅ Clients AWS initialisés pour mode cloud")
            except Exception as e:
                logger.error(f"❌ Erreur initialisation AWS: {e}")

        self.landing_bucket = self.config.get('aws.landing_bucket')
        self.queue_url = self.config.get('aws.sqs_queue_url')

    def process_iot_messages_from_cloud(self) -> pd.DataFrame:
        """
        ✅ MODIFIÉ: Traite les messages IoT depuis la file d'attente cloud ou local
        """
        if is_local_mode() or not self.sqs_client:
            logger.info("📁 Mode local - Traitement depuis fichiers CSV")
            return self.process_local_csv_files()

        logger.info("☁️ Mode cloud - Traitement depuis SQS + S3")
        return self.process_from_sqs_s3()

    def process_local_csv_files(self) -> pd.DataFrame:
        """✅ NOUVEAU: Traite les fichiers CSV locaux"""
        local_data_path = self.config.get('pipeline.local_data_path')

        if not local_data_path or not os.path.exists(local_data_path):
            logger.warning(f"⚠️ Chemin local non trouvé: {local_data_path}")
            return pd.DataFrame()

        csv_files = [f for f in os.listdir(local_data_path) if f.endswith('.csv')]

        if not csv_files:
            logger.info("📭 Aucun fichier CSV trouvé")
            return pd.DataFrame()

        all_data = []
        for csv_file in csv_files:
            file_path = os.path.join(local_data_path, csv_file)
            try:
                df = pd.read_csv(file_path)
                all_data.append(df)
                logger.info(f"📄 Traité: {csv_file}")
            except Exception as e:
                logger.error(f"❌ Erreur lecture {csv_file}: {e}")

        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()

    def process_from_sqs_s3(self) -> pd.DataFrame:
        """Traite les données depuis SQS et S3 (production)"""
        all_vitals = []
        batch_size = self.config.get('pipeline.batch_size', 10)

        try:
            # 1. Récupérer les messages de la file d'attente
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=batch_size,
                WaitTimeSeconds=5
            )

            messages = response.get('Messages', [])
            logger.info(f"📬 {len(messages)} messages reçus de SQS")

            for message in messages:
                try:
                    # 2. Parser le message SQS
                    body = json.loads(message['Body'])
                    s3_bucket = body['s3_bucket']
                    s3_key = body['s3_key']

                    # 3. Télécharger depuis S3
                    obj = self.s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
                    iot_data = json.loads(obj['Body'].read())

                    # 4. Convertir au format pipeline
                    vitals_row = self.convert_iot_to_pipeline_format(iot_data)
                    all_vitals.append(vitals_row)

                    # 5. Supprimer le message traité
                    self.sqs_client.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )

                except Exception as e:
                    logger.error(f"❌ Erreur traitement message SQS: {e}")
                    continue

            # 6. Convertir en DataFrame pour la pipeline
            if all_vitals:
                logger.info(f"✅ {len(all_vitals)} mesures traitées depuis le cloud")
                return pd.DataFrame(all_vitals)
            else:
                return pd.DataFrame()

        except Exception as e:
            logger.error(f"❌ Erreur accès SQS/S3: {e}")
            return pd.DataFrame()

    def convert_iot_to_pipeline_format(self, iot_data: Dict) -> Dict:
        """
        ✅ NOUVEAU: Convertit le format IoT vers le format pipeline
        """
        vitals = iot_data.get('vitals', {})
        metadata = iot_data.get('metadata', {})

        return {
            # Identifiants
            'device_id': iot_data['device_id'],
            'patient_id': iot_data['patient_id'],
            'message_id': iot_data.get('ingestion_id'),

            # Timestamps
            'recorded_at': iot_data['timestamp'],
            'received_at': iot_data.get('received_at', datetime.utcnow().isoformat()),

            # Données vitales (format pipeline)
            'heart_rate_bpm': vitals.get('heart_rate'),
            'respiratory_rate_min': vitals.get('respiratory_rate'),
            'spo2_percent': vitals.get('spo2'),
            'temperature_celsius': vitals.get('temperature'),
            'ambient_temp_celsius': vitals.get('ambient_temp_celsius'),
            'hydration_percent': vitals.get('hydration_percent'),
            'activity_level': vitals.get('activity_level'),
            'pain_scale': vitals.get('pain_scale'),

            # Métadonnées device
            'battery_percent': metadata.get('battery_level'),
            'signal_quality': metadata.get('signal_quality'),
            'firmware_version': metadata.get('firmware_version'),

            # Qualité par défaut (sera affinée en BRONZE)
            'quality_flag': 'ok',
            'data_source': 'device'
        }

def main():
    """
    Point d'entrée principal modifié pour IoT cloud
    """
    spark = (SparkSession.builder
             .appName("tech4good-01-to-raw")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
             .config("spark.sql.adaptive.enabled", "true")
             .getOrCreate())

    try:
        logger.info("🚀 Démarrage ingestion IoT cloud vers RAW")

        # ✅ NOUVEAU: Afficher la configuration
        config = get_config()
        logger.info(f"📋 Environnement: {config.environment}")
        logger.info(f"📋 Mode: {config.get('pipeline_mode')}")

        # ✅ NOUVEAU: Initialiser le processeur IoT
        iot_processor = IoTDataProcessor()

        # ✅ NOUVEAU: Traiter depuis cloud ou local selon environnement
        df_vitals = iot_processor.process_iot_messages_from_cloud()

        if df_vitals.empty:
            logger.info("📭 Aucune nouvelle donnée IoT à traiter")
            return

        logger.info(f"📊 {len(df_vitals)} nouvelles mesures IoT reçues")

        # ✅ CHEMINS ABSOLUS POUR ÉVITER LES PROBLÈMES DE RÉPERTOIRE
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        landing_path = os.path.join(base_dir, "landing", "*.csv")
        raw_base = os.path.join(base_dir, "raw")

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Landing path: {landing_path}")
        print(f"INFO: Raw base: {raw_base}")

        # Vérifier que le répertoire landing existe
        landing_dir = os.path.join(base_dir, "landing")
        if not os.path.exists(landing_dir):
            print(f"ERROR: Landing directory not found: {landing_dir}")
            sys.exit(1)

        # Lister les fichiers disponibles
        landing_files = [f for f in os.listdir(landing_dir) if f.endswith('.csv')]
        if not landing_files:
            print(f"ERROR: No CSV files found in {landing_dir}")
            sys.exit(1)

        print(f"INFO: Found {len(landing_files)} CSV file(s): {landing_files}")

        # ✅ LECTURE EN MODE TOLÉRANT POUR ÉVITER LES ERREURS DE SCHÉMA
        try:
            df = (spark.read
                  .option("header", "true")
                  .option("encoding", "UTF-8")
                  .option("multiline", "true")
                  .option("escape", '"')
                  .option("inferSchema", "true")  # Utiliser inferSchema pour la robustesse
                  .csv(landing_path))

            print(f"INFO: CSV lu avec succès, {df.count()} lignes détectées")
            print("INFO: Schéma détecté:")
            df.printSchema()

        except Exception as csv_error:
            print(f"ERROR: Problème de lecture CSV - {str(csv_error)}")
            sys.exit(1)

        # Vérification que le DataFrame n'est pas vide
        row_count = df.count()
        if row_count == 0:
            print("ERROR: Aucune donnée trouvée dans les fichiers CSV")
            sys.exit(1)

        # ✅ AJOUT DES MÉTADONNÉES D'INGESTION
        df_raw = (df
                  .withColumn("ingestion_ts", to_utc_timestamp(current_timestamp(), "UTC"))
                  .withColumn("source_file", input_file_name()))

        # Horodatage pour versionner le batch
        ts = int(time.time())
        out_path = os.path.join(raw_base, f"batch_ts={ts}")

        # Créer le répertoire de sortie s'il n'existe pas
        os.makedirs(raw_base, exist_ok=True)

        # Écriture avec gestion d'erreurs
        try:
            (df_raw
             .write
             .mode("overwrite")
             .parquet(out_path))

            print(f"SUCCESS: Wrote RAW -> {out_path}")
            print(f"STATS: Rows processed: {row_count}")
            print("INFO: Données ingérées avec succès")

        except Exception as write_error:
            print(f"ERROR: Problème d'écriture - {str(write_error)}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Erreur pipeline IoT: {e}")
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
