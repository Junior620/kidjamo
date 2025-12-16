"""
Étape 1 — Ingestion vers la zone RAW.

Rôle :
    Capturer les données sources IoT telles quelles (schéma et valeurs brutes),
    sans enrichissement métier ni transformation des valeurs.

Objectifs :
    - Persister en format Parquet avec métadonnées minimales (horodatage, source)
    - Lecture depuis Landing Zone (CSV) ou cloud (SQS/S3)
    - Ajout uniquement des colonnes techniques : ingestion_ts, source_file

Garanties :
    Aucune transformation métier ; uniquement normalisation technique
    de types et ajout métadonnées d'ingestion.

Destination :
    Dossier data/lake/raw/ avec partitionnement par timestamp batch
    Format : raw/batch_ts={timestamp}/*.parquet

Entrées :
    - Mode local : fichiers CSV depuis data/lake/landing/*.csv
    - Mode cloud : messages SQS + objets S3

Sorties :
    - Fichiers Parquet dans data/lake/raw/batch_ts={timestamp}/
    - Colonnes ajoutées : ingestion_ts, source_file
    - Aucune modification des données source

Effets de bord :
    - Création des répertoires de sortie
    - Configuration environnement Spark/Hadoop pour Windows
    - Logs d'exécution via print() et logger
"""

import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import boto3
import pandas as pd
from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, input_file_name, to_utc_timestamp
from pyspark.sql.types import (DoubleType, IntegerType, StringType,
                               StructField, StructType, TimestampType)

# Import du gestionnaire de configuration centralisé
from config.environment import get_config, is_cloud_mode, is_local_mode, logger

# Constantes pour la configuration Spark Windows
SPARK_CANDIDATES_WINDOWS = [
    r"C:\spark-3.5.5-bin-hadoop3\spark-3.5.5-bin-hadoop3\bin\spark-submit.cmd",
    r"C:\spark-3.5.5-bin-hadoop3\bin\spark-submit.cmd",
    r"C:\spark\\bin\spark-submit.cmd"
]

DEFAULT_BATCH_SIZE = 10
CSV_FILE_EXTENSION = '.csv'


class IoTDataProcessor:
    """
    Processeur pour l'ingestion des données IoT depuis le cloud ou local.

    Gère deux modes d'exécution :
    - Mode local : lecture de fichiers CSV depuis le répertoire landing
    - Mode cloud : récupération via SQS + téléchargement S3
    """

    def __init__(self) -> None:
        """Initialise le processeur avec la configuration centralisée."""
        self.config = get_config()
        self.s3_client: Optional[boto3.client] = None
        self.sqs_client: Optional[boto3.client] = None

        # Initialisation des clients AWS uniquement en mode cloud
        if is_cloud_mode() and self.config.get('aws.access_key_id'):
            self._initialize_aws_clients()

        self.landing_bucket = self.config.get('aws.landing_bucket')
        self.queue_url = self.config.get('aws.sqs_queue_url')

    def _initialize_aws_clients(self) -> None:
        """Initialise les clients AWS S3 et SQS avec gestion d'erreurs."""
        try:
            aws_config = {
                'aws_access_key_id': self.config.get('aws.access_key_id'),
                'aws_secret_access_key': self.config.get('aws.secret_access_key'),
                'region_name': self.config.get('aws.region')
            }

            self.s3_client = boto3.client('s3', **aws_config)
            self.sqs_client = boto3.client('sqs', **aws_config)
            logger.info("✅ Clients AWS initialisés pour mode cloud")

        except Exception as e:
            logger.error(f"❌ Erreur initialisation AWS: {e}")

    def process_iot_messages_from_cloud(self) -> pd.DataFrame:
        """
        Point d'entrée principal pour le traitement des messages IoT.

        Détermine automatiquement le mode (local/cloud) et traite les données
        selon la configuration environnement.

        Returns:
            pd.DataFrame: DataFrame avec les données IoT, vide si aucune donnée
        """
        if is_local_mode() or not self.sqs_client:
            logger.info("📁 Mode local - Traitement depuis fichiers CSV")
            return self._process_local_csv_files()

        logger.info("☁️ Mode cloud - Traitement depuis SQS + S3")
        return self._process_from_sqs_s3()

    def _process_local_csv_files(self) -> pd.DataFrame:
        """
        Traite les fichiers CSV depuis le répertoire local landing.

        Lecture de tous les fichiers *.csv du répertoire landing,
        concaténation sans transformation des données.

        Returns:
            pd.DataFrame: Données concaténées de tous les CSV
        """
        local_data_path = self._get_landing_directory_path()

        if not os.path.exists(local_data_path):
            logger.warning(f"⚠️ Chemin local non trouvé: {local_data_path}")
            return pd.DataFrame()

        csv_files = [f for f in os.listdir(local_data_path)
                     if f.endswith(CSV_FILE_EXTENSION)]

        if not csv_files:
            logger.info("📭 Aucun fichier CSV trouvé")
            return pd.DataFrame()

        # Lecture et concaténation de tous les fichiers CSV
        all_data = []
        for csv_file in csv_files:
            file_path = os.path.join(local_data_path, csv_file)
            try:
                # Lecture brute du CSV sans transformation des données
                df = pd.read_csv(file_path)
                all_data.append(df)
                logger.info(f"📄 Traité: {csv_file}")
            except Exception as e:
                logger.error(f"❌ Erreur lecture {csv_file}: {e}")

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    def _get_landing_directory_path(self) -> str:
        """
        Détermine le chemin du répertoire landing selon la configuration.

        Returns:
            str: Chemin absolu vers le répertoire landing
        """
        local_data_path = self.config.get('pipeline.local_data_path')
        if not local_data_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            local_data_path = os.path.join(base_dir, "lake", "landing")
            logger.info(f"📁 LOCAL_DATA_PATH non défini, utilisation du défaut: {local_data_path}")

        return local_data_path

    def _process_from_sqs_s3(self) -> pd.DataFrame:
        """
        Traite les données depuis SQS et S3 (mode production cloud).

        Processus :
        1. Récupère les messages de la file d'attente SQS
        2. Télécharge les objets JSON depuis S3
        3. Convertit au format pipeline
        4. Supprime les messages traités

        Returns:
            pd.DataFrame: Données traitées depuis le cloud
        """
        all_vitals = []
        batch_size = self.config.get('pipeline.batch_size', DEFAULT_BATCH_SIZE)

        try:
            # 1. Récupération des messages SQS
            response = self.sqs_client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=batch_size,
                WaitTimeSeconds=5
            )

            messages = response.get('Messages', [])
            logger.info(f"📬 {len(messages)} messages reçus de SQS")

            # 2. Traitement de chaque message
            for message in messages:
                try:
                    vitals_row = self._process_single_sqs_message(message)
                    if vitals_row:
                        all_vitals.append(vitals_row)

                    # 3. Suppression du message traité
                    self._delete_processed_message(message)

                except Exception as e:
                    logger.error(f"❌ Erreur traitement message SQS: {e}")
                    continue

            # 4. Conversion en DataFrame
            if all_vitals:
                logger.info(f"✅ {len(all_vitals)} mesures traitées depuis le cloud")
                return pd.DataFrame(all_vitals)

        except Exception as e:
            logger.error(f"❌ Erreur accès SQS/S3: {e}")

        return pd.DataFrame()

    def _process_single_sqs_message(self, message: Dict) -> Optional[Dict]:
        """
        Traite un message SQS individuel et télécharge les données S3.

        Args:
            message: Message SQS contenant les références S3

        Returns:
            Dict: Données IoT converties au format pipeline, None si erreur
        """
        body = json.loads(message['Body'])
        s3_bucket = body['s3_bucket']
        s3_key = body['s3_key']

        # Téléchargement depuis S3
        obj = self.s3_client.get_object(Bucket=s3_bucket, Key=s3_key)
        iot_data = json.loads(obj['Body'].read())

        # Conversion au format pipeline (sans transformation métier)
        return self._convert_iot_to_pipeline_format(iot_data)

    def _delete_processed_message(self, message: Dict) -> None:
        """Supprime un message SQS après traitement réussi."""
        self.sqs_client.delete_message(
            QueueUrl=self.queue_url,
            ReceiptHandle=message['ReceiptHandle']
        )

    def _convert_iot_to_pipeline_format(self, iot_data: Dict) -> Dict:
        """
        Convertit le format IoT vers le format pipeline standard.

        Transformation no-op : mappage des champs sans modification des valeurs.
        Seuls les noms de colonnes sont normalisés selon le schéma pipeline.

        Args:
            iot_data: Données IoT au format source

        Returns:
            Dict: Données au format pipeline standardisé
        """
        vitals = iot_data.get('vitals', {})
        metadata = iot_data.get('metadata', {})

        return {
            # Identifiants (pas de transformation)
            'device_id': iot_data['device_id'],
            'patient_id': iot_data['patient_id'],
            'message_id': iot_data.get('ingestion_id'),

            # Timestamps (format ISO conservé)
            'recorded_at': iot_data['timestamp'],
            'received_at': iot_data.get('received_at', datetime.utcnow().isoformat()),

            # Données vitales (mapping colonnes uniquement)
            'heart_rate_bpm': vitals.get('heart_rate'),
            'respiratory_rate_min': vitals.get('respiratory_rate'),
            'spo2_percent': vitals.get('spo2'),
            'temperature_celsius': vitals.get('temperature'),
            'ambient_temp_celsius': vitals.get('ambient_temp_celsius'),
            'hydration_percent': vitals.get('hydration_percent'),
            'activity_level': vitals.get('activity_level'),
            'pain_scale': vitals.get('pain_scale'),

            # Métadonnées device (pas de transformation)
            'battery_percent': metadata.get('battery_level'),
            'signal_quality': metadata.get('signal_quality'),
            'firmware_version': metadata.get('firmware_version'),

            # Marqueurs qualité par défaut (sera affiné en BRONZE)
            'quality_flag': 'ok',
            'data_source': 'device'
        }


def _setup_spark_session() -> SparkSession:
    """
    Configure et initialise la session Spark pour Windows avec gestion d'erreurs.

    Configuration spécifique Windows :
    - Nettoyage HADOOP_HOME invalide
    - Configuration SPARK_HOME si manquant
    - Configuration filesystem par défaut

    Returns:
        SparkSession: Session Spark configurée et initialisée
    """
    # Nettoyage environnement Windows pour éviter erreurs winutils
    if os.name == 'nt':
        _cleanup_windows_hadoop_environment()
        _setup_windows_spark_environment()

    # Diagnostics environnement
    _print_environment_diagnostics()

    # Configuration et création session Spark
    spark = (SparkSession.builder
             .appName("tech4good-01-to-raw")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
             .config("spark.sql.adaptive.enabled", "true")
             .config("spark.hadoop.fs.defaultFS", "file:///")  # Force filesystem local
             .getOrCreate())

    return spark


def _cleanup_windows_hadoop_environment() -> None:
    """Nettoie HADOOP_HOME invalide sur Windows pour éviter erreurs winutils."""
    hadoop_home = os.environ.get('HADOOP_HOME')
    if hadoop_home and not os.path.isdir(hadoop_home):
        print(f"INFO: Removing invalid HADOOP_HOME={hadoop_home}")
        os.environ.pop('HADOOP_HOME', None)


def _setup_windows_spark_environment() -> None:
    """Configure SPARK_HOME et PATH si manquants (convenience Windows)."""
    if not os.environ.get('SPARK_HOME'):
        for candidate in SPARK_CANDIDATES_WINDOWS:
            if os.path.exists(candidate):
                spark_home = os.path.abspath(os.path.join(os.path.dirname(candidate), ".."))
                os.environ['SPARK_HOME'] = spark_home

                spark_bin = os.path.join(spark_home, 'bin')
                current_path = os.environ.get('PATH', '')
                if spark_bin not in current_path:
                    os.environ['PATH'] = spark_bin + os.pathsep + current_path
                break


def _print_environment_diagnostics() -> None:
    """Affiche les diagnostics d'environnement pour debugging."""
    print(f"INFO: JAVA_HOME={os.environ.get('JAVA_HOME')}")
    print(f"INFO: HADOOP_HOME={os.environ.get('HADOOP_HOME')}")
    print(f"INFO: SPARK_HOME={os.environ.get('SPARK_HOME')}")
    print(f"INFO: java in PATH={shutil.which('java')}")


def _get_data_lake_paths() -> tuple[str, str, str, str]:
    """
    Calcule les chemins absolus vers les répertoires du data lake.

    Returns:
        tuple: (base_dir, lake_dir, landing_dir, raw_base)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lake_dir = os.path.join(base_dir, "lake")
    landing_dir = os.path.join(lake_dir, "landing")
    raw_base = os.path.join(lake_dir, "raw")

    return base_dir, lake_dir, landing_dir, raw_base


def _validate_landing_directory(landing_dir: str) -> list[str]:
    """
    Valide l'existence du répertoire landing et liste les fichiers CSV.

    Args:
        landing_dir: Chemin vers le répertoire landing

    Returns:
        list[str]: Liste des fichiers CSV trouvés

    Raises:
        SystemExit: Si répertoire manquant ou aucun fichier CSV
    """
    if not os.path.exists(landing_dir):
        print(f"ERROR: Landing directory not found: {landing_dir}")
        sys.exit(1)

    landing_files = [f for f in os.listdir(landing_dir) if f.endswith(CSV_FILE_EXTENSION)]
    if not landing_files:
        print(f"ERROR: No CSV files found in {landing_dir}")
        sys.exit(1)

    return landing_files


def _read_csv_data_with_spark(spark: SparkSession, landing_dir: str):
    """
    Lit les données CSV avec Spark en mode tolérant aux erreurs.

    Options de lecture robustes :
    - header=true : première ligne comme en-têtes
    - encoding=UTF-8 : gestion caractères spéciaux
    - multiline=true : support CSV multi-lignes
    - inferSchema=true : détection automatique types

    Args:
        spark: Session Spark active
        landing_dir: Répertoire contenant les fichiers CSV

    Returns:
        DataFrame: Données lues depuis les CSV

    Raises:
        SystemExit: Si erreur de lecture ou DataFrame vide
    """
    try:
        csv_pattern = os.path.join(landing_dir, "*.csv")
        print(f"INFO: Reading CSV pattern: {csv_pattern}")

        # Lecture CSV avec options robustes (pas de transformation des données)
        df = (spark.read
              .option("header", "true")
              .option("encoding", "UTF-8")
              .option("multiline", "true")
              .option("escape", '"')
              .option("inferSchema", "true")  # Détection automatique types
              .csv(csv_pattern))

        row_count = df.count()
        print(f"INFO: CSV lu avec succès, {row_count} lignes détectées")
        print("INFO: Schéma détecté:")
        df.printSchema()

        if row_count == 0:
            print("ERROR: Aucune donnée trouvée dans les fichiers CSV")
            sys.exit(1)

        return df

    except Exception as csv_error:
        print(f"ERROR: Problème de lecture CSV - {str(csv_error)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _add_ingestion_metadata(df):
    """
    Ajoute les métadonnées d'ingestion au DataFrame.

    Colonnes ajoutées (seules transformations autorisées en RAW) :
    - ingestion_ts : timestamp UTC d'ingestion
    - source_file : nom du fichier source

    Args:
        df: DataFrame Spark avec données source

    Returns:
        DataFrame: DataFrame enrichi avec métadonnées techniques
    """
    return (df
            .withColumn("ingestion_ts", to_utc_timestamp(current_timestamp(), "UTC"))
            .withColumn("source_file", input_file_name()))


def _write_raw_data(df_raw, raw_base: str) -> None:
    """
    Écrit les données vers la zone RAW avec gestion d'erreurs.

    Format de sortie :
    - Parquet avec compression Snappy
    - Partitionnement par timestamp de batch
    - Coalesce(1) pour éviter fragmentation

    Args:
        df_raw: DataFrame avec métadonnées d'ingestion
        raw_base: Chemin de base pour la zone RAW

    Raises:
        SystemExit: Si erreur d'écriture
    """
    # Génération timestamp pour versioning du batch
    ts = int(time.time())
    out_path = os.path.join(raw_base, f"batch_ts={ts}")

    # Création répertoire de sortie
    os.makedirs(out_path, exist_ok=True)
    print(f"INFO: Writing to: {out_path}")

    try:
        (df_raw
         .coalesce(1)  # Éviter fragmentation en petits fichiers
         .write
         .mode("overwrite")
         .option("compression", "snappy")
         .parquet(out_path))

        row_count = df_raw.count()
        print(f"SUCCESS: Wrote RAW -> {out_path}")
        print(f"STATS: Rows processed: {row_count}")
        print("INFO: Données ingérées avec succès")

    except Exception as write_error:
        print(f"ERROR: Problème d'écriture - {str(write_error)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main() -> None:
    """
    Point d'entrée principal pour l'ingestion vers la zone RAW.

    Orchestration :
    1. Initialisation processeur IoT et configuration
    2. Traitement données depuis cloud ou local
    3. Configuration session Spark
    4. Lecture et validation données landing
    5. Ajout métadonnées techniques
    6. Écriture vers zone RAW
    """
    spark = None

    try:
        logger.info("🚀 Démarrage ingestion IoT cloud vers RAW")

        # 1. Configuration et initialisation processeur
        config = get_config()
        logger.info(f"📋 Environnement: {config.environment}")
        logger.info(f"📋 Mode: {config.get('pipeline_mode')}")

        iot_processor = IoTDataProcessor()

        # 2. Traitement des données IoT selon mode
        df_vitals = iot_processor.process_iot_messages_from_cloud()
        if df_vitals.empty:
            logger.info("📭 Aucune nouvelle donnée IoT à traiter")
            return

        logger.info(f"📊 {len(df_vitals)} nouvelles mesures IoT reçues")

        # 3. Configuration chemins data lake
        base_dir, lake_dir, landing_dir, raw_base = _get_data_lake_paths()

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Lake directory: {lake_dir}")
        print(f"INFO: Landing directory: {landing_dir}")
        print(f"INFO: Raw base: {raw_base}")

        # 4. Validation et lecture données landing
        landing_files = _validate_landing_directory(landing_dir)
        print(f"INFO: Found {len(landing_files)} CSV file(s): {landing_files}")

        # 5. Configuration session Spark
        spark = _setup_spark_session()

        # 6. Lecture des données CSV
        df = _read_csv_data_with_spark(spark, landing_dir)

        # 7. Ajout métadonnées d'ingestion (seule transformation autorisée)
        df_raw = _add_ingestion_metadata(df)

        # 8. Écriture vers zone RAW
        _write_raw_data(df_raw, raw_base)

    except Exception as e:
        logger.error(f"❌ Erreur pipeline IoT: {e}")
        raise
    finally:
        if spark is not None:
            try:
                spark.stop()
            except Exception:
                pass


if __name__ == "__main__":
    main()
