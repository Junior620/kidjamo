"""
Étape 2 — Normalisation initiale vers BRONZE.

Rôle :
    Nettoyage basique des données RAW : déduplication technique,
    cohérence de types, validation contraintes médicales,
    pseudonymisation RGPD.

Objectifs :
    - Rendre les données exploitables tout en restant proches du brut
    - Appliquer les contraintes médicales pour identifier données aberrantes
    - Sécuriser les identifiants patients (hachage SHA-256)
    - Partitionner par date d'événement pour optimiser l'accès

Destination :
    Dossier data/lake/bronze/ partitionné par event_date
    Format : bronze/event_date=YYYY-MM-DD/*.parquet

Entrées :
    - Fichiers Parquet depuis data/lake/raw/batch_ts=*/*.parquet
    - Schéma source avec colonnes techniques ajoutées en RAW

Sorties :
    - Données valides dans data/lake/bronze/ (partitionnées par event_date)
    - Données invalides dans data/lake/quarantine/ (partitionnées par ingestion_date)
    - Colonnes ajoutées : event_ts, event_date, ingestion_date, bronze_processed_ts
    - patient_id pseudonymisé (SHA-256 + salt)

Effets de bord :
    - Création répertoires bronze/ et quarantine/
    - Logs de qualité des données et statistiques de validation
    - Normalisation noms de colonnes selon schéma standard
"""

import os
import sys
from typing import Dict, List, Optional

from pyspark.sql import SparkSession
from pyspark.sql.functions import (col, concat, current_timestamp, lit,
                                   regexp_replace, sha2, to_date, to_timestamp,
                                   to_utc_timestamp, coalesce)
from pyspark.sql.types import (DoubleType, IntegerType, StringType,
                               StructField, StructType, TimestampType)

# Constantes pour validation médicale (seuils reconnus médicalement)
MEDICAL_CONSTRAINTS = {
    "heart_rate_bpm": {"min": 40, "max": 200, "unit": "bpm"},
    "SpO2": {"min": 70, "max": 100, "unit": "%"},
    "temperature_core_c": {"min": 35.0, "max": 42.0, "unit": "°C"},
    "hydration_pct": {"min": 0, "max": 100, "unit": "%"},
    "respiratory_rate": {"min": 8, "max": 40, "unit": "/min"},
    "age": {"min": 0, "max": 120, "unit": "years"}
}

# Configuration pour pseudonymisation RGPD
PATIENT_ID_SALT = "kidjamo_salt_2025"
QUARANTINE_REASON_VALIDATION_FAILED = "validation_failed"


def _create_spark_session() -> SparkSession:
    """
    Crée une session Spark configurée pour le traitement BRONZE.

    Configuration optimisée :
    - Timezone UTC pour cohérence temporelle
    - Serializer Kryo pour performance
    - Adaptive query execution pour optimisation automatique

    Returns:
        SparkSession: Session Spark configurée
    """
    return (SparkSession.builder
            .appName("tech4good-02-raw-to-bronze")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
            .config("spark.sql.adaptive.enabled", "true")
            .getOrCreate())


def _get_data_lake_paths() -> tuple[str, str, str, str, str]:
    """
    Calcule les chemins absolus vers les répertoires du data lake.

    Returns:
        tuple: (base_dir, lake_dir, raw_base, bronze_base, quarantine_base)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # data/ chemin du script
    lake_dir = os.path.join(base_dir, "lake") # data/lake
    raw_base = os.path.join(lake_dir, "raw") # data/lake/raw
    bronze_base = os.path.join(lake_dir, "bronze") # data/lake/bronze
    quarantine_base = os.path.join(lake_dir, "quarantine") # data/lake/quarantine

    return base_dir, lake_dir, raw_base, bronze_base, quarantine_base


def _validate_raw_directory_and_read_data(spark: SparkSession, raw_base: str):
    """
    Valide l'existence du répertoire RAW et lit les données Parquet.

    Pattern de lecture : raw/*/��.parquet pour supporter partitionnement par timestamp.

    Args:
        spark: Session Spark active
        raw_base: Chemin vers le répertoire RAW

    Returns:
        DataFrame: Données lues depuis la zone RAW

    Raises:
        SystemExit: Si répertoire manquant ou erreur de lecture
    """
    if not os.path.exists(raw_base):
        print(f"ERROR: Raw directory not found: {raw_base}")
        sys.exit(1)

    # Pattern pour lire tous les fichiers Parquet dans les sous-répertoires
    raw_pattern = os.path.join(raw_base, "*", "*.parquet")
    print(f"INFO: Looking for parquet files: {raw_pattern}")

    try:
        df = spark.read.parquet(raw_pattern)
        row_count = df.count()

        print(f"INFO: Loaded {row_count} rows from raw")
        print("INFO: Schema from raw data:")
        df.printSchema()

        if row_count == 0:
            print("ERROR: No data found in raw layer")
            sys.exit(1)

        return df

    except Exception as read_error:
        print(f"ERROR: Failed to read raw data - {str(read_error)}")
        sys.exit(1)


def _add_canonical_timestamps(df):
    """
    Ajoute les timestamps canoniques UTC et dates dérivées.

    Transformations appliquées :
    - event_ts : conversion ingestion_ts vers UTC (format canonique)
    - event_date : extraction date depuis event_ts pour partitionnement
    - ingestion_date : extraction date depuis ingestion_ts pour traçabilité

    Args:
        df: DataFrame avec colonne ingestion_ts

    Returns:
        DataFrame: DataFrame avec timestamps canoniques ajoutés
    """
    return (df
            .withColumn("event_ts", to_utc_timestamp(col("ingestion_ts"), "UTC"))
            .withColumn("event_date", to_date(col("event_ts")))
            .withColumn("ingestion_date", to_date(col("ingestion_ts"))))


def _normalize_column_names(df):
    """
    Normalise les noms de colonnes selon le schéma standard pipeline.

    Mappings appliqués uniquement si les colonnes sources existent :
    - temp_c → temperature_core_c (température corporelle)
    - fc → heart_rate_bpm (fréquence cardiaque)
    - hy_pct → hydration_pct (niveau hydratation)
    - fr → respiratory_rate (fréquence respiratoire)

    Args:
        df: DataFrame avec colonnes potentiellement à renommer

    Returns:
        DataFrame: DataFrame avec noms de colonnes normalisés
    """
    columns = df.columns
    renamed_df = df

    # Mapping conditionnel selon colonnes présentes
    column_mappings = {
        "temp_c": "temperature_core_c",
        "fc": "heart_rate_bpm",
        "hy_pct": "hydration_pct",
        "fr": "respiratory_rate"
    }

    for old_name, new_name in column_mappings.items():
        if old_name in columns:
            renamed_df = renamed_df.withColumnRenamed(old_name, new_name)

    print("INFO: Column normalization completed")
    return renamed_df


def _build_medical_validation_conditions(bronze_columns: List[str]) -> List:
    """
    Construit les conditions de validation médicale selon colonnes disponibles.

    Conditions appliquées :
    - Obligatoires : patient_id, device_id, age (si présents)
    - Optionnelles : vitaux avec tolérance aux valeurs nulles

    Args:
        bronze_columns: Liste des colonnes disponibles dans le DataFrame

    Returns:
        List: Liste des conditions de validation Spark
    """
    valid_conditions = []
    constraints = MEDICAL_CONSTRAINTS

    # Conditions obligatoires (si colonnes présentes)
    mandatory_checks = {
        "patient_id": col("patient_id").isNotNull(),
        "device_id": col("device_id").isNotNull(),
        "age": col("age").between(constraints["age"]["min"], constraints["age"]["max"])
    }

    for column, condition in mandatory_checks.items():
        if column in bronze_columns:
            valid_conditions.append(condition)

    # Conditions optionnelles avec tolérance aux nulls
    optional_checks = {
        "heart_rate_bpm": col("heart_rate_bpm").between(
            constraints["heart_rate_bpm"]["min"],
            constraints["heart_rate_bpm"]["max"]
        ),
        "SpO2": col("SpO2").between(
            constraints["SpO2"]["min"],
            constraints["SpO2"]["max"]
        ),
        "temperature_core_c": col("temperature_core_c").between(
            constraints["temperature_core_c"]["min"],
            constraints["temperature_core_c"]["max"]
        )
    }

    for column, condition in optional_checks.items():
        if column in bronze_columns:
            # Accepter valeurs nulles OU valeurs dans la plage valide
            valid_conditions.append((col(column).isNull()) | condition)

    return valid_conditions


def _apply_medical_validation(bronze_df) -> tuple:
    """
    Applique la validation médicale et sépare données valides/quarantaine.

    Logique de validation :
    - Combine toutes les conditions avec opérateur AND
    - Données valides : respectent toutes les contraintes
    - Quarantaine : échouent à au moins une contrainte

    Args:
        bronze_df: DataFrame avec colonnes normalisées

    Returns:
        tuple: (bronze_valid, bronze_quarantine) DataFrames séparés
    """
    bronze_columns = bronze_df.columns
    valid_conditions = _build_medical_validation_conditions(bronze_columns)

    if valid_conditions:
        # Combiner toutes les conditions avec AND logique
        final_condition = valid_conditions[0]
        for condition in valid_conditions[1:]:
            final_condition = final_condition & condition

        bronze_valid = bronze_df.filter(final_condition)
        bronze_quarantine = bronze_df.filter(~final_condition)
    else:
        # Si aucune condition : toutes les données sont considérées valides
        bronze_valid = bronze_df
        bronze_quarantine = bronze_df.sql_ctx.createDataFrame([], bronze_df.schema)

    return bronze_valid, bronze_quarantine


def _pseudonymize_patient_ids(bronze_valid):
    """
    Applique la pseudonymisation RGPD des identifiants patients.

    Méthode :
    - Hachage SHA-256 avec salt fixe pour cohérence
    - Remplacement patient_id original par hash
    - Conformité RGPD : impossible de retrouver l'ID original sans salt

    Args:
        bronze_valid: DataFrame avec patient_id en clair

    Returns:
        DataFrame: DataFrame avec patient_id pseudonymisé
    """
    if "patient_id" in bronze_valid.columns:
        bronze_valid = (bronze_valid
            .withColumn("patient_id_hash",
                       sha2(concat(col("patient_id"), lit(PATIENT_ID_SALT)), 256))
            .drop("patient_id")
            .withColumnRenamed("patient_id_hash", "patient_id"))
        print("INFO: Patient IDs pseudonymisés pour conformité RGPD")

    return bronze_valid


def _add_bronze_processing_metadata(bronze_valid):
    """
    Ajoute les métadonnées de traitement BRONZE.

    Colonnes ajoutées :
    - bronze_processed_ts : timestamp UTC du traitement BRONZE

    Args:
        bronze_valid: DataFrame validé

    Returns:
        DataFrame: DataFrame avec métadonnées de traitement
    """
    return bronze_valid.withColumn("bronze_processed_ts",
                                  to_utc_timestamp(current_timestamp(), "UTC"))


def _deduplicate_records(bronze_valid) -> object:
    """
    Supprime les doublons techniques selon clés métier.

    Clés de déduplication (si colonnes présentes) :
    - patient_id + event_ts (combinaison temporelle unique)
    - + device_id si disponible (précision device)

    Args:
        bronze_valid: DataFrame avec métadonnées complètes

    Returns:
        DataFrame: DataFrame dédupliqué
    """
    # Détermination des colonnes de déduplication
    dedup_columns = ["event_ts"]  # Colonne temporelle toujours présente

    if "patient_id" in bronze_valid.columns:
        dedup_columns.append("patient_id")
    if "device_id" in bronze_valid.columns:
        dedup_columns.append("device_id")

    return bronze_valid.dropDuplicates(dedup_columns)


def _write_bronze_data(bronze_final, bronze_base: str) -> int:
    """
    Écrit les données valides vers la zone BRONZE avec partitionnement.

    Configuration d'écriture :
    - Partitionnement par event_date pour accès optimisé
    - Mode overwrite pour gestion incrémentale
    - Format Parquet pour compression et performance

    Args:
        bronze_final: DataFrame final validé et dédupliqué
        bronze_base: Chemin de base vers zone BRONZE

    Returns:
        int: Nombre de lignes écrites

    Raises:
        SystemExit: Si erreur d'écriture
    """
    os.makedirs(bronze_base, exist_ok=True)

    try:
        (bronze_final
         .write
         .mode("overwrite")
         .partitionBy("event_date")
         .parquet(bronze_base))

        valid_count = bronze_final.count()
        print(f"SUCCESS: Wrote BRONZE -> {bronze_base}")
        return valid_count

    except Exception as write_error:
        print(f"ERROR: Failed to write bronze data - {str(write_error)}")
        sys.exit(1)


def _write_quarantine_data(bronze_quarantine, quarantine_base: str) -> int:
    """
    Écrit les données en quarantaine avec métadonnées de rejet.

    Colonnes ajoutées pour traçabilité :
    - quarantine_reason : motif de mise en quarantaine
    - quarantine_ts : timestamp de mise en quarantaine

    Args:
        bronze_quarantine: DataFrame des données rejetées
        quarantine_base: Chemin vers zone quarantaine

    Returns:
        int: Nombre de lignes mises en quarantaine
    """
    quarantine_count = bronze_quarantine.count()

    if quarantine_count > 0:
        os.makedirs(os.path.dirname(quarantine_base), exist_ok=True)

        try:
            (bronze_quarantine
             .withColumn("quarantine_reason", lit(QUARANTINE_REASON_VALIDATION_FAILED))
             .withColumn("quarantine_ts", to_utc_timestamp(current_timestamp(), "UTC"))
             .write
             .mode("overwrite")
             .partitionBy("ingestion_date")
             .parquet(quarantine_base))
            print(f"WARNING: {quarantine_count} enregistrements mis en quarantaine")

        except Exception as q_error:
            print(f"WARNING: Failed to write quarantine data - {str(q_error)}")

    return quarantine_count


def _print_quality_statistics(valid_count: int, quarantine_count: int) -> None:
    """
    Affiche les statistiques de qualité des données.

    Métriques calculées :
    - Nombre total d'enregistrements traités
    - Pourcentage de qualité des données
    - Répartition valides/quarantaine

    Args:
        valid_count: Nombre d'enregistrements valides
        quarantine_count: Nombre d'enregistrements en quarantaine
    """
    total_records = valid_count + quarantine_count
    data_quality = (valid_count / total_records * 100) if total_records > 0 else 0

    print(f"INFO: Données valides: {valid_count}")
    print(f"INFO: Données en quarantaine: {quarantine_count}")
    print(f"STATS: Valid rows processed: {valid_count}")
    print(f"STATS: Data quality: {data_quality:.1f}%")


def main() -> None:
    """
    Point d'entrée principal pour la transformation RAW vers BRONZE.

    Pipeline de traitement :
    1. Lecture données RAW avec validation existence
    2. Ajout timestamps canoniques UTC
    3. Normalisation noms de colonnes
    4. Application validation médicale et séparation valides/quarantaine
    5. Pseudonymisation RGPD des patient_id
    6. Ajout métadonnées traitement BRONZE
    7. Déduplication technique
    8. Écriture zones BRONZE et quarantaine
    9. Affichage statistiques qualité
    """
    spark = _create_spark_session()

    try:
        # 1. Configuration chemins et validation répertoires
        base_dir, lake_dir, raw_base, bronze_base, quarantine_base = _get_data_lake_paths()

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Lake directory: {lake_dir}")
        print(f"INFO: Raw base: {raw_base}")
        print(f"INFO: Bronze base: {bronze_base}")

        # 2. Lecture et validation données RAW
        df = _validate_raw_directory_and_read_data(spark, raw_base)

        # 3. Ajout timestamps canoniques UTC
        bronze = _add_canonical_timestamps(df)

        # 4. Normalisation noms de colonnes selon schéma standard
        bronze = _normalize_column_names(bronze)

        # 5. Application validation médicale
        bronze_valid, bronze_quarantine = _apply_medical_validation(bronze)

        # 6. Pseudonymisation RGPD des identifiants patients
        bronze_valid = _pseudonymize_patient_ids(bronze_valid)

        # 7. Ajout métadonnées de traitement BRONZE
        bronze_valid = _add_bronze_processing_metadata(bronze_valid)

        # 8. Déduplication technique selon clés métier
        bronze_final = _deduplicate_records(bronze_valid)

        # 9. Écriture données valides vers BRONZE
        valid_count = _write_bronze_data(bronze_final, bronze_base)

        # 10. Écriture données rejetées vers quarantaine
        quarantine_count = _write_quarantine_data(bronze_quarantine, quarantine_base)

        # 11. Affichage statistiques finales
        _print_quality_statistics(valid_count, quarantine_count)

    except Exception as e:
        print(f"ERROR in 02_raw_to_bronze: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
