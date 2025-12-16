"""
Étape Traitement Streaming — Lecture Kafka via PySpark, parsing JSON et traitements configurés.

Rôle :
    Processeur PySpark Structured Streaming pour consommation topics Kafka IoT.
    Applique parsing, validation, enrichissement et écriture vers sinks multiples
    (Parquet, console) avec gestion d'état et checkpointing.

Objectifs :
    - Lecture topics Kafka temps réel (measurements, alerts, device_status)
    - Parsing JSON avec schémas StructType définis
    - Validation médicale et nettoyage des données
    - Agrégations fenêtrées (5 min) avec détection d'anomalies
    - Écriture vers data lake local (raw, bronze, silver) selon sinks configurés

Entrées :
    - Topics Kafka : kidjamo-iot-measurements, kidjamo-iot-alerts, kidjamo-iot-device-status
    - Configuration : startingOffsets, failOnDataLoss, maxOffsetsPerTrigger
    - Variables d'environnement : KAFKA_STARTING_OFFSETS, KAFKA_FAIL_ON_DATA_LOSS

Sorties :
    - Fichiers Parquet dans ./data_lake/ (raw/iot_measurements, bronze/iot_aggregations, etc.)
    - Checkpoints dans ./checkpoints/ pour reprise sur incident
    - Logs console pour debugging anomalies détectées

Effets de bord :
    - Création SparkSession avec package Kafka auto-sélectionné selon version PySpark
    - Vérification environnement Java (compatibilité PySpark 3.x/4.x)
    - Création arborescence data_lake et checkpoints
    - Configuration watermarks pour agrégations append mode

Garanties :
    Triggers, watermarks, checkpoints et logique de validation inchangés ;
    auto-sélection connecteur Kafka compatible ; aucune modification des
    seuils de détection d'anomalies ni des sinks de sortie.
"""

# Imports standard library (triés alphabétiquement)
import json
import logging
import math
import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Optional, Tuple

# Imports PySpark (groupés par module)
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.functions import (
    avg, col, count, current_timestamp, expr, from_json, lit,
    max as spark_max, min as spark_min, round as spark_round,
    to_timestamp, when, window
)
from pyspark.sql.streaming import StreamingQuery
from pyspark.sql.types import (
    BooleanType, DoubleType, IntegerType, StringType, StructField,
    StructType, TimestampType
)

# Configuration logging avec logger nommé
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration Kafka par défaut - ne pas modifier ces valeurs
DEFAULT_KAFKA_SERVERS = "localhost:9092"
DEFAULT_CHECKPOINT_LOCATION = "./checkpoints"

# Seuils médicaux pour détection d'anomalies (inchangés)
MEDICAL_THRESHOLDS = {
    "spo2_critical": 90,      # SpO2 critique
    "spo2_warning": 92,       # SpO2 alerte
    "heart_rate_max": 150,    # FC maximale
    "heart_rate_min": 50,     # FC minimale
    "heart_rate_normal_max": 120,  # FC normale haute
    "heart_rate_normal_min": 60,   # FC normale basse
    "temperature_high_fever": 39.0,  # Fièvre élevée
    "temperature_fever": 38.0        # Fièvre
}


class IoTStreamingProcessor:
    """
    Processeur streaming PySpark pour données IoT médicales temps réel.

    Gère l'auto-détection version Java/PySpark, configuration connecteur Kafka,
    lecture topics multiples et écriture vers data lake local avec checkpointing.
    """

    def __init__(self, kafka_servers: str = DEFAULT_KAFKA_SERVERS,
                 checkpoint_location: str = DEFAULT_CHECKPOINT_LOCATION) -> None:
        """
        Initialise le processeur avec vérification environnement.

        Args:
            kafka_servers: Serveurs Kafka bootstrap (localhost:9092)
            checkpoint_location: Répertoire checkpoints Spark Streaming
        """
        self.kafka_servers = kafka_servers
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.checkpoint_location = self._to_abs_path(checkpoint_location)

        # Configuration Kafka depuis variables d'environnement (inchangée)
        self.kafka_starting_offsets = os.environ.get("KAFKA_STARTING_OFFSETS", "latest")
        fail_flag = os.environ.get("KAFKA_FAIL_ON_DATA_LOSS", "false").strip().lower()
        self.kafka_fail_on_data_loss = fail_flag in ("1", "true", "yes")

        logger.info(f"Kafka read options -> startingOffsets={self.kafka_starting_offsets}, "
                   f"failOnDataLoss={'true' if self.kafka_fail_on_data_loss else 'false'}")

        # Vérification proactive Java/PySpark avant initialisation Spark
        self._check_environment()
        self.spark = self._create_spark_session()
        self.schemas = self._define_schemas()

    def _to_abs_path(self, path: str) -> str:
        """
        Convertit un chemin relatif en absolu basé sur le répertoire du script.

        Args:
            path: Chemin relatif ou absolu

        Returns:
            str: Chemin absolu Windows-safe
        """
        try:
            return path if os.path.isabs(path) else os.path.abspath(os.path.join(self.base_dir, path))
        except Exception:
            return path  # Fallback, ne pas bloquer

    def _detect_java_version(self) -> Optional[int]:
        """
        Détecte la version majeure de Java installée.

        Returns:
            int: Version majeure Java (8, 11, 17) ou None si introuvable
        """
        try:
            # java -version écrit sur stderr
            completed = subprocess.run(["java", "-version"], capture_output=True, text=True)
            output = completed.stderr.strip() + "\n" + completed.stdout.strip()

            # Pattern pour version format "1.8.0_xx" ou "17.0.x"
            match = re.search(r'version\s+"(\d+)(?:\.(\d+)\.\d+)?', output)
            if match:
                major = int(match.group(1))
                # Ancien format Java 8 : "1.8.0_xx"
                if major == 1 and match.group(2):
                    return int(match.group(2))
                return major
        except Exception:
            return None
        return None

    def _normalize_java_home(self, path: str) -> str:
        """
        Nettoie et normalise un chemin JAVA_HOME.

        Supprime guillemets, remonte depuis .../bin ou .../bin/java.exe
        vers le répertoire racine JDK.

        Args:
            path: Chemin JAVA_HOME brut

        Returns:
            str: Chemin JAVA_HOME normalisé
        """
        if not path:
            return ""

        normalized = path.strip().strip('"').strip("'")
        try:
            normalized = os.path.normpath(normalized)
        except Exception:
            pass

        lower_path = normalized.lower()

        # Si pointe vers .../bin/java.exe, remonter de 2 niveaux
        if lower_path.endswith(os.path.join("bin", "java.exe").lower()):
            try:
                normalized = os.path.dirname(os.path.dirname(normalized))
            except Exception:
                pass

        # Si pointe vers .../bin, remonter d'1 niveau
        try:
            if os.path.basename(normalized).lower() == "bin":
                normalized = os.path.dirname(normalized)
        except Exception:
            pass

        return normalized

    def _is_valid_java_home(self, dir_path: str) -> bool:
        """
        Vérifie qu'un répertoire est un JAVA_HOME valide.

        Args:
            dir_path: Chemin vers répertoire JDK candidat

        Returns:
            bool: True si contient bin/java.exe
        """
        if not dir_path:
            return False
        return os.path.exists(os.path.join(dir_path, "bin", "java.exe"))

    def _discover_java_home_from_runtime(self) -> Optional[str]:
        """
        Déduit JAVA_HOME depuis la propriété java.home de la JVM en cours.

        Returns:
            str: Chemin JAVA_HOME détecté ou None
        """
        try:
            completed = subprocess.run([
                "java", "-XshowSettings:properties", "-version"
            ], capture_output=True, text=True)

            output = (completed.stderr or "") + "\n" + (completed.stdout or "")
            match = re.search(r"^\s*java\.home\s*=\s*(.+)$", output, re.MULTILINE)

            if match:
                java_home_prop = self._normalize_java_home(match.group(1))
                candidate = java_home_prop

                # Pour JDK8, java.home peut être <JDK>/jre
                if not self._is_valid_java_home(candidate):
                    parent = os.path.dirname(candidate)
                    if self._is_valid_java_home(parent):
                        candidate = parent

                if self._is_valid_java_home(candidate):
                    return candidate
        except Exception:
            return None
        return None

    def _check_environment(self) -> None:
        """
        Vérifie la compatibilité Java/PySpark pour éviter UnsupportedClassVersionError.

        Règles de compatibilité :
        - PySpark 4.x → Java 17 minimum
        - PySpark 3.4.x → Java 8/11 recommandé

        Raises:
            SystemExit: Si incompatibilité détectée avec instructions
        """
        try:
            import pyspark
            pyspark_version = getattr(pyspark, "__version__", "0")
        except Exception:
            return  # Si PySpark absent, erreur se produira plus tard

        def parse_version(v):
            parts = v.split(".")
            return tuple(int(p) for p in parts[:3] if p.isdigit())

        parsed_version = parse_version(pyspark_version)
        major = parsed_version[0] if parsed_version else 0
        java_major = self._detect_java_version()

        # Règles de compatibilité strictes
        required_java = 17 if major >= 4 else 8

        if java_major is None:
            message = (
                "Java n'est pas détecté dans le PATH.\n"
                "- Installez JDK 17 si vous utilisez PySpark 4.x.\n"
                "- Sinon pour PySpark 3.4.x, installez Java 8/11 (JDK 8/11).\n"
                "Ensuite, relancez le script."
            )
            logger.error(message)
            raise SystemExit(message)

        # Incompatibilité critique PySpark 4.x + Java < 17
        if major >= 4 and java_major < 17:
            message = (
                f"Incompatibilité détectée: PySpark {pyspark_version} nécessite Java 17, "
                f"mais Java {java_major} est installé.\n"
                "Solution: installez JDK 17 et assurez-vous que JAVA_HOME/PATH pointent vers Java 17."
            )
            logger.error(message)
            raise SystemExit(message)

        # Avertissement pour versions sous-optimales
        if major <= 3 and parsed_version >= (3, 4, 0) and java_major not in (8, 11, 17):
            logger.warning(
                f"Vous utilisez PySpark {pyspark_version} avec Java {java_major}. "
                "Pour une compatibilité optimale avec Spark 3.4.x, utilisez Java 8 ou 11."
            )

        # Tentative d'auto-configuration JAVA_HOME si invalide
        self._auto_configure_java_home()

    def _auto_configure_java_home(self) -> None:
        """
        Auto-configure JAVA_HOME si invalide en testant plusieurs candidats.

        Sources testées :
        1. JAVA_HOME environnement (normalisé)
        2. java.home depuis JVM courante
        3. Déduction depuis binaire PATH
        """
        try:
            env_java_home = os.environ.get("JAVA_HOME")
            candidates = []
            tested = []

            # 1. JAVA_HOME fourni par environnement
            if env_java_home:
                normalized = self._normalize_java_home(env_java_home)
                if normalized:
                    candidates.append(normalized)

                    # Variante JDK8 : JAVA_HOME peut pointer vers .../jre
                    try:
                        if os.path.basename(normalized).lower() == "jre":
                            candidates.append(os.path.dirname(normalized))
                    except Exception:
                        pass

            # 2. Déduction depuis JVM runtime
            runtime_java_home = self._discover_java_home_from_runtime()
            if runtime_java_home:
                candidates.append(runtime_java_home)

            # 3. Déduction depuis binaire PATH
            java_path = shutil.which("java")
            if java_path:
                try:
                    # java_path est .../bin/java.exe -> remonter de 2 niveaux
                    path_candidate = os.path.dirname(os.path.dirname(java_path))
                    candidates.append(path_candidate)
                except Exception:
                    pass

            # Test des candidats et configuration du premier valide
            seen = set()
            unique_candidates = []
            for candidate in candidates:
                if candidate and candidate not in seen:
                    unique_candidates.append(candidate)
                    seen.add(candidate)

            java_configured = False
            for candidate in unique_candidates:
                tested.append(candidate)
                if self._is_valid_java_home(candidate):
                    os.environ["JAVA_HOME"] = candidate
                    bin_path = os.path.join(candidate, "bin")
                    os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
                    java_configured = True
                    logger.info(f"JAVA_HOME validé: {candidate}")
                    break

            if not java_configured:
                tested_str = "\n - ".join(tested) if tested else "aucun candidat"
                message = (
                    "JAVA_HOME est absent ou invalide après tentative d'auto-configuration.\n"
                    "Spark ne peut pas démarrer correctement sur Windows sans un JAVA_HOME valide.\n\n"
                    "Actions recommandées:\n"
                    "- Installez un JDK approprié (JDK 17 pour PySpark 4.x; JDK 8/11 pour Spark 3.4.x).\n"
                    "- Définissez JAVA_HOME vers le dossier d'installation du JDK et ajoutez %JAVA_HOME%\\bin au PATH.\n\n"
                    f"JAVA_HOME actuel: {env_java_home or 'non défini'}\n"
                    f"Candidats testés:\n - {tested_str}"
                )
                logger.error(message)
                raise SystemExit(message)

        except Exception:
            # Ne pas bloquer si auto-fix échoue
            pass

    def _create_spark_session(self) -> SparkSession:
        """
        Crée la session Spark avec auto-sélection du connecteur Kafka.

        Auto-détecte la version PySpark et sélectionne le package Kafka compatible :
        - PySpark 4.x → fallback vers 3.5.3 (4.0.0 non disponible)
        - PySpark 3.x → version correspondante

        Configuration streaming optimisée pour développement local.

        Returns:
            SparkSession: Session configurée avec package Kafka

        Raises:
            Exception: Si erreur UnsupportedClassVersionError ou chemins
        """
        try:
            # Auto-détection version PySpark pour sélection package Kafka
            try:
                import pyspark
                pyspark_version = getattr(pyspark, "__version__", "3.4.0")
            except Exception:
                pyspark_version = "3.4.0"

            # Override possible via variables d'environnement
            env_override_version = (os.environ.get("KAFKA_CONNECTOR_VERSION") or
                                   os.environ.get("SPARK_KAFKA_PACKAGE_VERSION"))

            # Sélection suffixe Scala : Spark 4.x utilise Scala 2.13
            try:
                pv_major = int(str(pyspark_version).split(".")[0])
            except Exception:
                pv_major = 0

            default_scala = "2.13" if pv_major >= 4 else "2.12"
            scala_suffix = os.environ.get("KAFKA_CONNECTOR_SCALA_SUFFIX", default_scala)

            # Détermination version connecteur Kafka
            parts = [int(p) for p in pyspark_version.split(".")[:2] if p.isdigit()]

            if env_override_version:
                kafka_pkg_version = env_override_version.strip()
                logger.info(f"Version du connecteur Kafka (override via env) utilisée: {kafka_pkg_version}")
            else:
                if len(parts) >= 2:
                    major, minor = parts[0], parts[1]
                    # Fallback PySpark 4.x vers 3.5.3 (4.0.0 non publié)
                    if major >= 4:
                        kafka_pkg_version = "3.5.3"
                        logger.warning(
                            "PySpark 4.x détecté: le connecteur Kafka 'org.apache.spark:spark-sql-kafka-0-10' "
                            "en version 4.0.0 n'est pas disponible sur Maven. Fallback automatique vers 3.5.3 "
                            "(configurable via KAFKA_CONNECTOR_VERSION)."
                        )
                    else:
                        kafka_pkg_version = f"{major}.{minor}.0"
                else:
                    kafka_pkg_version = "3.4.0"

            kafka_package = f"org.apache.spark:spark-sql-kafka-0-10_{scala_suffix}:{kafka_pkg_version}"
            logger.info(f"Initialisation Spark avec package Kafka: {kafka_package}")

            # Configuration session Spark optimisée pour streaming local
            return (SparkSession.builder
                    .appName("Kidjamo-IoT-Streaming")
                    .config("spark.sql.adaptive.enabled", "true")
                    .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
                    .config("spark.sql.streaming.checkpointLocation", self.checkpoint_location)
                    .config("spark.sql.streaming.stateStore.maintenanceInterval", "60s")
                    .config("spark.sql.shuffle.partitions", "4")  # Optimisé pour dev local
                    .config("spark.jars.packages", kafka_package)
                    .getOrCreate())

        except Exception as e:
            error_msg = str(e)

            # Messages d'erreur spécifiques pour debugging
            if "UnsupportedClassVersionError" in error_msg or "class file version" in error_msg:
                logger.error(
                    "Java incompatible: votre environnement Java est trop ancien pour la version de Spark/PySpark installée.\n"
                    "- Si vous utilisez PySpark 4.x, installez JDK 17 (Java 17).\n"
                    "- Sinon, assurez-vous que PySpark 3.4.x est installé avec Java 8/11, puis relancez le script."
                )
            elif ("Le chemin d'accès spécifié est introuvable" in error_msg or
                  "The system cannot find the path specified" in error_msg):
                logger.error(
                    "Erreur Windows: chemin introuvable lors du démarrage de Spark.\n"
                    "Causes probables: JAVA_HOME pointe vers un dossier inexistant ou Java non installé.\n"
                    "Actions: installez JDK approprié (17 pour PySpark 4.x), et vérifiez JAVA_HOME et PATH.\n"
                    f"JAVA_HOME actuel: {os.environ.get('JAVA_HOME', 'non défini')}"
                )
            raise

    def _define_schemas(self) -> Dict[str, StructType]:
        """
        Définit les schémas StructType pour parsing JSON Kafka.

        Schémas fixes correspondant aux messages publiés par l'API d'ingestion :
        - measurements : mesures IoT complètes
        - alerts : alertes critiques
        - device_status : statut technique dispositifs

        Returns:
            dict: Dictionnaire des schémas par type de message
        """
        # Schéma des mesures médicales (sous-structure)
        measurements_schema = StructType([
            StructField("freq_card", IntegerType(), True),
            StructField("freq_resp", IntegerType(), True),
            StructField("spo2_pct", DoubleType(), True),
            StructField("temp_corp", DoubleType(), True),
            StructField("temp_ambiente", DoubleType(), True),
            StructField("pct_hydratation", DoubleType(), True),
            StructField("activity", IntegerType(), True),
            StructField("heat_index", DoubleType(), True)
        ])

        # Schéma des informations dispositif (sous-structure)
        device_info_schema = StructType([
            StructField("device_id", StringType(), True),
            StructField("firmware_version", StringType(), True),
            StructField("battery_level", IntegerType(), True),
            StructField("signal_strength", IntegerType(), True),
            StructField("status", StringType(), True),
            StructField("last_sync", StringType(), True)
        ])

        # Schéma des indicateurs qualité (sous-structure)
        quality_schema = StructType([
            StructField("quality_flag", StringType(), True),
            StructField("confidence_score", DoubleType(), True),
            StructField("data_completeness", DoubleType(), True),
            StructField("sensor_contact_quality", DoubleType(), True)
        ])

        # Schéma principal des mesures IoT (message Kafka complet)
        iot_measurement_schema = StructType([
            StructField("device_id", StringType(), True),
            StructField("patient_id", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("measurements", measurements_schema, True),
            StructField("device_info", device_info_schema, True),
            StructField("quality_indicators", quality_schema, True),
            # Métadonnées ajoutées par l'API
            StructField("ingestion_timestamp", StringType(), True),
            StructField("api_version", StringType(), True),
            StructField("message_id", StringType(), True)
        ])

        # Schéma des alertes (topic alerts)
        alert_schema = StructType([
            StructField("patient_id", StringType(), True),
            StructField("device_id", StringType(), True),
            StructField("alert_type", StringType(), True),
            StructField("severity", StringType(), True),
            StructField("message", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("measurements", measurements_schema, True),
            StructField("quality_score", DoubleType(), True)
        ])

        return {
            "measurements": iot_measurement_schema,
            "alerts": alert_schema,
            "device_status": device_info_schema
        }

    def read_kafka_stream(self, topic: str) -> DataFrame:
        """
        Lit un stream depuis un topic Kafka avec configuration robuste.

        Configuration :
        - startingOffsets : latest (configurable via KAFKA_STARTING_OFFSETS)
        - failOnDataLoss : false (configurable via KAFKA_FAIL_ON_DATA_LOSS)
        - maxOffsetsPerTrigger : 1000 (limite pour dev local)

        Args:
            topic: Nom du topic Kafka à consommer

        Returns:
            DataFrame: Stream Kafka brut (colonnes : key, value, timestamp, partition, offset)
        """
        return (self.spark
                .readStream
                .format("kafka")
                .option("kafka.bootstrap.servers", self.kafka_servers)
                .option("subscribe", topic)
                .option("startingOffsets", self.kafka_starting_offsets)
                .option("failOnDataLoss", "true" if self.kafka_fail_on_data_loss else "false")
                .option("maxOffsetsPerTrigger", "1000")  # Limite pour dev local
                .load())

    def process_measurements_stream(self) -> Tuple[StreamingQuery, StreamingQuery, StreamingQuery]:
        """
        Traite le stream des mesures IoT avec parsing, validation et agrégations.

        Pipeline de traitement :
        1. Lecture topic kidjamo-iot-measurements
        2. Parsing JSON selon schéma measurements
        3. Validation médicale (SpO2 70-100%, FC 30-250, T° 30-45°C)
        4. Écriture raw layer (append mode)
        5. Agrégations fenêtrées 5 minutes avec watermark 10 minutes
        6. Détection anomalies selon seuils médicaux
        7. Écriture bronze layer et console pour debugging

        Returns:
            tuple: (raw_query, bronze_query, console_query) streaming queries
        """
        logger.info("Starting measurements stream processing...")

        # 1. Lecture depuis Kafka
        raw_stream = self.read_kafka_stream("kidjamo-iot-measurements")

        # 2. Parsing JSON et enrichissement avec métadonnées Kafka
        parsed_stream = (raw_stream
                        .select(
                            from_json(col("value").cast("string"),
                                     self.schemas["measurements"]).alias("data"),
                            col("timestamp").alias("kafka_timestamp"),
                            col("partition"),
                            col("offset")
                        )
                        .select("data.*", "kafka_timestamp", "partition", "offset")
                        .withColumn("processing_timestamp", current_timestamp())
                        .withColumn("event_timestamp",
                                   to_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"))
                        )

        # 3. Validation médicale et nettoyage + watermark pour agrégations
        thresholds = MEDICAL_THRESHOLDS
        validated_stream = (parsed_stream
                           .filter(col("measurements.spo2_pct").between(70, 100))  # SpO2 viable
                           .filter(col("measurements.freq_card").between(30, 250))  # FC physiologique étendue
                           .filter(col("measurements.temp_corp").between(30, 45))   # Température survivable
                           .withColumn("is_valid_quality",
                                     col("quality_indicators.confidence_score") > 50)
                           .withWatermark("event_timestamp", "10 minutes")  # Nécessaire pour append mode
                           )

        # 4. Écriture vers Raw Layer (données brutes validées)
        raw_query = (validated_stream
                    .writeStream
                    .format("parquet")
                    .outputMode("append")
                    .option("path", self._to_abs_path("./data_lake/raw/iot_measurements"))
                    .option("checkpointLocation",
                           self._to_abs_path(os.path.join(self.checkpoint_location, "raw_measurements")))
                    .partitionBy("patient_id")
                    .trigger(processingTime="30 seconds")
                    .start())

        # 5. Agrégations temps réel (fenêtres glissantes 5 min, incrément 1 min)
        windowed_aggregations = (validated_stream
                               .filter(col("is_valid_quality") == True)
                               .groupBy(
                                   window(col("event_timestamp"), "5 minutes", "1 minute"),
                                   col("patient_id"),
                                   col("device_id")
                               )
                               .agg(
                                   count("*").alias("measurement_count"),
                                   avg("measurements.spo2_pct").alias("avg_spo2"),
                                   spark_min("measurements.spo2_pct").alias("min_spo2"),
                                   spark_max("measurements.spo2_pct").alias("max_spo2"),
                                   avg("measurements.freq_card").alias("avg_heart_rate"),
                                   spark_min("measurements.freq_card").alias("min_heart_rate"),
                                   spark_max("measurements.freq_card").alias("max_heart_rate"),
                                   avg("measurements.temp_corp").alias("avg_temperature"),
                                   spark_max("measurements.temp_corp").alias("max_temperature"),
                                   avg("measurements.activity").alias("avg_activity"),
                                   avg("quality_indicators.confidence_score").alias("avg_quality_score")
                               )
                               .withColumn("window_start", col("window.start"))
                               .withColumn("window_end", col("window.end"))
                               .drop("window")
                               )

        # 6. Détection d'anomalies selon seuils médicaux (inchangés)
        anomaly_detection = (windowed_aggregations
                           .withColumn("spo2_anomaly",
                                     when(col("min_spo2") < thresholds["spo2_critical"], "CRITICAL")
                                     .when(col("avg_spo2") < thresholds["spo2_warning"], "WARNING")
                                     .otherwise("NORMAL"))
                           .withColumn("heart_rate_anomaly",
                                     when((col("max_heart_rate") > thresholds["heart_rate_max"]) |
                                          (col("min_heart_rate") < thresholds["heart_rate_min"]), "CRITICAL")
                                     .when((col("avg_heart_rate") > thresholds["heart_rate_normal_max"]) |
                                           (col("avg_heart_rate") < thresholds["heart_rate_normal_min"]), "WARNING")
                                     .otherwise("NORMAL"))
                           .withColumn("fever_alert",
                                     when(col("max_temperature") > thresholds["temperature_high_fever"], "HIGH_FEVER")
                                     .when(col("avg_temperature") > thresholds["temperature_fever"], "FEVER")
                                     .otherwise("NORMAL"))
                           )

        # 7. Écriture agrégations vers Bronze Layer
        bronze_query = (anomaly_detection
                       .writeStream
                       .format("parquet")
                       .outputMode("append")
                       .option("path", self._to_abs_path("./data_lake/bronze/iot_aggregations"))
                       .option("checkpointLocation",
                              self._to_abs_path(os.path.join(self.checkpoint_location, "bronze_aggregations")))
                       .partitionBy("patient_id")
                       .trigger(processingTime="1 minute")
                       .start())

        # 8. Console output pour debugging anomalies détectées
        console_query = (anomaly_detection
                        .filter((col("spo2_anomaly") != "NORMAL") |
                               (col("heart_rate_anomaly") != "NORMAL") |
                               (col("fever_alert") != "NORMAL"))
                        .writeStream
                        .outputMode("append")
                        .format("console")
                        .option("truncate", False)
                        .trigger(processingTime="30 seconds")
                        .start())

        return raw_query, bronze_query, console_query

    def process_alerts_stream(self) -> Tuple[StreamingQuery, StreamingQuery]:
        """
        Traite le stream des alertes avec enrichissement et routage selon criticité.

        Pipeline d'alertes :
        1. Lecture topic kidjamo-iot-alerts
        2. Parsing JSON et enrichissement contextuel
        3. Classification criticité (requires_immediate_attention)
        4. Routage différentiel :
           - Alertes critiques → silver/critical_alerts (trigger 10s)
           - Toutes alertes → bronze/iot_alerts (trigger 30s)

        Returns:
            tuple: (critical_alerts_query, all_alerts_query) streaming queries
        """
        logger.info("Starting alerts stream processing...")

        raw_stream = self.read_kafka_stream("kidjamo-iot-alerts")

        # Parsing JSON avec schéma alerts
        parsed_alerts = (raw_stream
                        .select(
                            from_json(col("value").cast("string"),
                                     self.schemas["alerts"]).alias("alert"),
                            col("timestamp").alias("kafka_timestamp")
                        )
                        .select("alert.*", "kafka_timestamp")
                        .withColumn("processing_timestamp", current_timestamp())
                        )

        # Enrichissement alertes avec classification criticité
        enriched_alerts = (parsed_alerts
                          .withColumn("alert_id", expr("uuid()"))
                          .withColumn("is_critical",
                                    col("severity").isin(["critical", "high"]))
                          .withColumn("requires_immediate_attention",
                                    (col("severity") == "critical") &
                                    (col("alert_type").isin(["CRITICAL_SPO2", "SICKLE_CELL_CRISIS"])))
                          )

        # Écriture alertes critiques pour action immédiate (10s trigger)
        critical_alerts_query = (enriched_alerts
                               .filter(col("requires_immediate_attention") == True)
                               .writeStream
                               .format("parquet")
                               .outputMode("append")
                               .option("path", self._to_abs_path("./data_lake/silver/critical_alerts"))
                               .option("checkpointLocation",
                                      self._to_abs_path(os.path.join(self.checkpoint_location, "critical_alerts")))
                               .trigger(processingTime="10 seconds")  # Très rapide pour critiques
                               .start())

        # Toutes alertes vers Bronze (30s trigger)
        all_alerts_query = (enriched_alerts
                          .writeStream
                          .format("parquet")
                          .outputMode("append")
                          .option("path", self._to_abs_path("./data_lake/bronze/iot_alerts"))
                          .option("checkpointLocation",
                                 self._to_abs_path(os.path.join(self.checkpoint_location, "bronze_alerts")))
                          .partitionBy("patient_id", "severity")
                          .trigger(processingTime="30 seconds")
                          .start())

        return critical_alerts_query, all_alerts_query

    def process_device_status_stream(self) -> StreamingQuery:
        """
        Traite le stream du statut des dispositifs avec détection problèmes techniques.

        Pipeline device status :
        1. Lecture topic kidjamo-iot-device-status
        2. Parsing et enrichissement avec flag needs_attention
        3. Écriture vers bronze/device_status partitionné par device_id

        Conditions needs_attention :
        - battery_level < 20%
        - signal_strength < 50%
        - status != "connected"

        Returns:
            StreamingQuery: Query de traitement device status
        """
        logger.info("Starting device status stream processing...")

        raw_stream = self.read_kafka_stream("kidjamo-iot-device-status")

        # Parsing et enrichissement avec détection problèmes
        processed_status = (raw_stream
                           .select(
                               from_json(col("value").cast("string"),
                                        self.schemas["device_status"]).alias("status"),
                               col("timestamp").alias("kafka_timestamp")
                           )
                           .select("status.*", "kafka_timestamp")
                           .withColumn("processing_timestamp", current_timestamp())
                           .withColumn("needs_attention",
                                     (col("battery_level") < 20) |
                                     (col("signal_strength") < 50) |
                                     (col("status") != "connected"))
                           )

        # Écriture vers Bronze Layer
        return (processed_status
                .writeStream
                .format("parquet")
                .outputMode("append")
                .option("path", self._to_abs_path("./data_lake/bronze/device_status"))
                .option("checkpointLocation",
                       self._to_abs_path(os.path.join(self.checkpoint_location, "device_status")))
                .partitionBy("device_id")
                .trigger(processingTime="1 minute")
                .start())

    def run_all_streams(self) -> None:
        """
        Lance tous les streams de traitement et attend leur arrêt.

        Démarre séquentiellement :
        1. Stream measurements (3 queries)
        2. Stream alerts (2 queries)
        3. Stream device status (1 query)

        Attend tous les streams avec awaitTermination().
        """
        logger.info("🚀 Starting all IoT streaming processes...")

        try:
            # Création répertoires de sortie
            os.makedirs(self._to_abs_path("./data_lake/raw"), exist_ok=True)
            os.makedirs(self._to_abs_path("./data_lake/bronze"), exist_ok=True)
            os.makedirs(self._to_abs_path("./data_lake/silver"), exist_ok=True)
            os.makedirs(self.checkpoint_location, exist_ok=True)

            # Démarrage des streams
            raw_q, bronze_q, console_q = self.process_measurements_stream()
            critical_alerts_q, all_alerts_q = self.process_alerts_stream()
            device_status_q = self.process_device_status_stream()

            logger.info("✅ All streams started successfully!")
            logger.info("📊 Monitoring console output for anomalies...")
            logger.info("⏹️  Press Ctrl+C to stop all streams")

            # Attente de tous les streams
            queries = [raw_q, bronze_q, console_q, critical_alerts_q, all_alerts_q, device_status_q]
            for query in queries:
                query.awaitTermination()

        except KeyboardInterrupt:
            logger.info("🛑 Arrêt demandé par utilisateur")
        except Exception as e:
            logger.error(f"❌ Erreur dans le traitement streaming: {e}")
            raise
        finally:
            # Arrêt propre de toutes les queries actives
            for query in self.spark.streams.active:
                try:
                    query.stop()
                except Exception:
                    pass
            self.spark.stop()
            logger.info("🏁 Streaming processor stopped")


# === POINT D'ENTRÉE PRINCIPAL ===

if __name__ == "__main__":
    # Configuration depuis variables d'environnement
    kafka_servers = os.environ.get("KAFKA_SERVERS", DEFAULT_KAFKA_SERVERS)
    checkpoint_location = os.environ.get("CHECKPOINT_LOCATION", DEFAULT_CHECKPOINT_LOCATION)

    # Initialisation et démarrage du processeur
    processor = IoTStreamingProcessor(
        kafka_servers=kafka_servers,
        checkpoint_location=checkpoint_location
    )

    try:
        processor.run_all_streams()
    except Exception as e:
        logger.error(f"Failed to start streaming processor: {e}")
        raise SystemExit(1)
