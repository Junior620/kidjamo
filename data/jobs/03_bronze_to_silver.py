"""
Étape 3 — Affinage vers SILVER.

Rôle :
    Structuration et enrichissement des données BRONZE avec classification
    médicale par groupes d'âge, détection d'alertes vitales et combinaisons
    critiques selon protocoles médicaux.

Objectifs :
    - Appliquer seuils physiologiques spécifiques par groupe d'âge (G1-G6)
    - Classifier l'état des signes vitaux (normal, vigilance, alerte, urgence, critique)
    - Détecter les combinaisons critiques (fièvre+hypoxie, détresse respiratoire)
    - Tables affinées prêtes pour usages analytiques et alerting

Destination :
    Dossier data/lake/silver/ partitionné par ingestion_date
    Format : silver/ingestion_date=YYYY-MM-DD/*.parquet

Entrées :
    - Fichiers Parquet depuis data/lake/bronze/event_date=*/*.parquet
    - Données validées et pseudonymisées depuis étape BRONZE

Sorties :
    - Données enrichies dans data/lake/silver/ avec classifications médicales
    - Colonnes ajoutées : age_group, spo2_status, temperature_status, critical_combination
    - Partitionnement par ingestion_date et patient_id pour optimisation requêtes

Effets de bord :
    - Création répertoire silver/ avec compression Snappy
    - Application seuils médicaux reconnus par groupe d'âge
    - Logs de progression et statistiques d'enrichissement
"""

import os
import sys
from typing import Optional

from pyspark.sql import SparkSession
from pyspark.sql.functions import (col, when, avg, count, stddev, expr,
                                   current_timestamp, lag, lead,
                                   abs as spark_abs, round as spark_round,
                                   to_utc_timestamp, to_date, lit, current_date)
from pyspark.sql.window import Window

# Classification des groupes d'âge selon protocoles pédiatriques/gériatriques
AGE_GROUP_THRESHOLDS = {
    "G1": {"min": 0, "max": 1, "description": "Nourrissons 0-1 an"},
    "G2": {"min": 1, "max": 5, "description": "Jeunes enfants 1-5 ans"},
    "G3": {"min": 6, "max": 12, "description": "Enfants 6-12 ans"},
    "G4": {"min": 13, "max": 17, "description": "Adolescents 13-17 ans"},
    "G5": {"min": 18, "max": 59, "description": "Adultes 18-59 ans"},
    "G6": {"min": 60, "max": 80, "description": "Seniors 60-80 ans"}
}

# Seuils SpO2 par groupe d'âge (selon recommandations pédiatriques)
SPO2_THRESHOLDS = {
    "G1_G2": {"critical": 88, "emergency": 90, "alert": 93, "vigilance": 94, "normal": 95},
    "G3": {"critical": 88, "emergency": 89, "alert": 93, "vigilance": 94, "normal": 95},
    "G4_G5_G6": {"critical": 88, "emergency": 88, "alert": 92, "vigilance": 93, "normal": 94}
}

# Seuils température par groupe d'âge (°C)
TEMPERATURE_THRESHOLDS = {
    "G1_G6_EMERGENCY_HIGH": 38.5,  # Nourrissons et seniors : seuil bas
    "G1_G6_ALERT_HIGH": 38.0,
    "G1_G6_EMERGENCY_LOW": 36.0,
    "G2_G3_G4_G5_EMERGENCY_HIGH": 39.0,  # Enfants et adultes : seuil plus élevé
    "G2_G3_G4_G5_ALERT_HIGH": 38.0,
    "NORMAL_RANGE_MIN": 36.0,
    "NORMAL_RANGE_MAX": 37.5
}

# Seuils pour combinaisons critiques
CRITICAL_COMBINATION_THRESHOLDS = {
    "FEVER_THRESHOLD": 38.0,
    "TACHYCARDIA_THRESHOLD": 110,
    "HYPOXIA_THRESHOLD": 90
}


def _create_spark_session() -> SparkSession:
    """
    Crée une session Spark configurée pour le traitement SILVER.

    Configuration optimisée pour enrichissement :
    - Adaptive query execution pour jointures complexes
    - Coalesce automatique des partitions
    - Timezone UTC pour cohérence temporelle

    Returns:
        SparkSession: Session Spark configurée
    """
    return (SparkSession.builder
            .appName("tech4good-03-bronze-to-silver")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
            .getOrCreate())


def _get_data_lake_paths() -> tuple[str, str, str, str]:
    """
    Calcule les chemins absolus vers les répertoires du data lake.

    Returns:
        tuple: (base_dir, lake_dir, bronze_base, silver_base)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lake_dir = os.path.join(base_dir, "lake")
    bronze_base = os.path.join(lake_dir, "bronze")
    silver_base = os.path.join(lake_dir, "silver")

    return base_dir, lake_dir, bronze_base, silver_base


def _validate_and_read_bronze_data(spark: SparkSession, bronze_base: str):
    """
    Valide l'existence des données BRONZE et les lit avec gestion d'erreurs.

    Args:
        spark: Session Spark active
        bronze_base: Chemin vers zone BRONZE

    Returns:
        DataFrame: Données BRONZE lues et validées

    Raises:
        SystemExit: Si données manquantes ou erreur de lecture
    """
    try:
        # Lecture directe des données bronze (toutes partitions)
        bronze = spark.read.parquet(bronze_base)
        row_count = bronze.count()

        print(f"INFO: Loaded {row_count} rows from bronze")

        if row_count == 0:
            print("WARNING: No data found in bronze layer")
            return None

        print("INFO: Schema from bronze:")
        bronze.printSchema()

        # Vérification colonnes disponibles pour traçabilité
        available_cols = bronze.columns
        print(f"INFO: Available columns: {available_cols}")

        return bronze

    except Exception as e:
        print(f"ERROR: Failed to process bronze data: {e}")
        raise


def _add_age_group_classification(bronze_df):
    """
    Ajoute la classification par groupe d'âge selon seuils médicaux.

    Classification appliquée :
    - G1 : 0-1 an (nourrissons)
    - G2 : 1-5 ans (jeunes enfants)
    - G3 : 6-12 ans (enfants)
    - G4 : 13-17 ans (adolescents)
    - G5 : 18-59 ans (adultes) - groupe par défaut
    - G6 : 60-80 ans (seniors)

    Args:
        bronze_df: DataFrame BRONZE avec colonne age

    Returns:
        DataFrame: DataFrame avec colonne age_group ajoutée
    """
    thresholds = AGE_GROUP_THRESHOLDS

    return bronze_df.withColumn(
        "age_group",
        when(col("age").between(thresholds["G1"]["min"], thresholds["G1"]["max"]), "G1")
        .when(col("age").between(thresholds["G2"]["min"], thresholds["G2"]["max"]), "G2")
        .when(col("age").between(thresholds["G3"]["min"], thresholds["G3"]["max"]), "G3")
        .when(col("age").between(thresholds["G4"]["min"], thresholds["G4"]["max"]), "G4")
        .when(col("age").between(thresholds["G5"]["min"], thresholds["G5"]["max"]), "G5")
        .when(col("age").between(thresholds["G6"]["min"], thresholds["G6"]["max"]), "G6")
        .otherwise("G5")  # Défaut adulte pour valeurs hors bornes
    )


def _classify_spo2_status(bronze_enriched):
    """
    Applique la classification SpO2 selon groupes d'âge et seuils médicaux.

    Seuils différenciés par groupe :
    - G1, G2 (nourrissons/jeunes enfants) : seuils plus stricts
    - G3 (enfants) : seuils intermédiaires
    - G4, G5, G6 (adolescents/adultes/seniors) : seuils adultes

    Classification :
    - critical : < 88% (urgence vitale)
    - emergency : 88-90% (urgence)
    - alert : 90-93% (alerte)
    - vigilance : 94% (surveillance)
    - normal : ≥ 95% (normal)

    Args:
        bronze_enriched: DataFrame avec age_group

    Returns:
        DataFrame: DataFrame avec spo2_status ajouté
    """
    spo2_thresholds = SPO2_THRESHOLDS

    return bronze_enriched.withColumn(
        "spo2_status",
        # Classification pour nourrissons et jeunes enfants (G1, G2)
        when(col("age_group").isin(["G1", "G2"]) & (col("SpO2") < spo2_thresholds["G1_G2"]["critical"]), "critical")
        .when(col("age_group").isin(["G1", "G2"]) & (col("SpO2") <= spo2_thresholds["G1_G2"]["emergency"]), "emergency")
        .when(col("age_group").isin(["G1", "G2"]) & (col("SpO2") <= spo2_thresholds["G1_G2"]["alert"]), "alert")
        .when(col("age_group").isin(["G1", "G2"]) & (col("SpO2") == spo2_thresholds["G1_G2"]["vigilance"]), "vigilance")
        .when(col("age_group").isin(["G1", "G2"]) & (col("SpO2") >= spo2_thresholds["G1_G2"]["normal"]), "normal")

        # Classification pour enfants (G3)
        .when((col("age_group") == "G3") & (col("SpO2") < spo2_thresholds["G3"]["critical"]), "critical")
        .when((col("age_group") == "G3") & (col("SpO2") <= spo2_thresholds["G3"]["emergency"]), "emergency")
        .when((col("age_group") == "G3") & (col("SpO2") <= spo2_thresholds["G3"]["alert"]), "alert")
        .when((col("age_group") == "G3") & (col("SpO2") == spo2_thresholds["G3"]["vigilance"]), "vigilance")
        .when((col("age_group") == "G3") & (col("SpO2") >= spo2_thresholds["G3"]["normal"]), "normal")

        # Classification pour adolescents/adultes/seniors (G4, G5, G6)
        .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("SpO2") < spo2_thresholds["G4_G5_G6"]["critical"]), "critical")
        .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("SpO2") <= spo2_thresholds["G4_G5_G6"]["emergency"]), "emergency")
        .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("SpO2") <= spo2_thresholds["G4_G5_G6"]["alert"]), "alert")
        .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("SpO2") == spo2_thresholds["G4_G5_G6"]["vigilance"]), "vigilance")
        .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("SpO2") >= spo2_thresholds["G4_G5_G6"]["normal"]), "normal")

        .otherwise("unknown")
    )


def _classify_temperature_status(df_with_spo2):
    """
    Applique la classification température selon groupes d'âge vulnérables.

    Seuils différenciés :
    - G1, G6 (nourrissons/seniors) : seuils plus bas (vulnérabilité)
    - G2, G3, G4, G5 : seuils standards

    Classification :
    - emergency : fièvre élevée ou hypothermie selon groupe
    - alert : fièvre modérée
    - normal : température dans plage physiologique (36.0-37.5°C)
    - vigilance : autres cas (légèrement hors norme)

    Args:
        df_with_spo2: DataFrame avec spo2_status

    Returns:
        DataFrame: DataFrame avec temperature_status ajouté
    """
    temp_thresholds = TEMPERATURE_THRESHOLDS

    return df_with_spo2.withColumn(
        "temperature_status",
        # Classification pour nourrissons et seniors (vulnérables)
        when(col("age_group").isin(["G1", "G6"]) & (col("temperature_core_c") >= temp_thresholds["G1_G6_EMERGENCY_HIGH"]), "emergency")
        .when(col("age_group").isin(["G1", "G6"]) & (col("temperature_core_c") >= temp_thresholds["G1_G6_ALERT_HIGH"]), "alert")
        .when(col("age_group").isin(["G1", "G6"]) & (col("temperature_core_c") < temp_thresholds["G1_G6_EMERGENCY_LOW"]), "emergency")

        # Classification pour enfants/adolescents/adultes
        .when(col("age_group").isin(["G2", "G3", "G4", "G5"]) & (col("temperature_core_c") >= temp_thresholds["G2_G3_G4_G5_EMERGENCY_HIGH"]), "emergency")
        .when(col("age_group").isin(["G2", "G3", "G4", "G5"]) & (col("temperature_core_c") >= temp_thresholds["G2_G3_G4_G5_ALERT_HIGH"]), "alert")

        # Plage normale pour tous les groupes
        .when(col("temperature_core_c").between(temp_thresholds["NORMAL_RANGE_MIN"], temp_thresholds["NORMAL_RANGE_MAX"]), "normal")

        .otherwise("vigilance")
    )


def _detect_critical_combinations(df_with_temp):
    """
    Détecte les combinaisons critiques de signes vitaux.

    Combinaisons détectées (selon protocoles d'urgence) :
    - C1_fever_hypoxia : fièvre (≥38°C) + hypoxie (SpO2 alerte/urgence/critique)
    - C2_respiratory_distress : hypoxie sévère (≤90%) + tachycardie (>110 bpm)

    Ces combinaisons nécessitent intervention médicale immédiate.

    Args:
        df_with_temp: DataFrame avec temperature_status

    Returns:
        DataFrame: DataFrame avec critical_combination ajouté
    """
    crit_thresholds = CRITICAL_COMBINATION_THRESHOLDS

    return df_with_temp.withColumn(
        "critical_combination",
        # C1 : Combinaison fièvre + hypoxie (très dangereuse)
        when((col("temperature_core_c") >= crit_thresholds["FEVER_THRESHOLD"]) &
             (col("spo2_status").isin(["alert", "emergency", "critical"])),
             "C1_fever_hypoxia")

        # C2 : Détresse respiratoire (hypoxie + tachycardie)
        .when((col("SpO2") <= crit_thresholds["HYPOXIA_THRESHOLD"]) &
              (col("heart_rate_bpm") > crit_thresholds["TACHYCARDIA_THRESHOLD"]),
              "C2_respiratory_distress")

        .otherwise(None)
    )


def _add_silver_processing_metadata(silver_with_alerts):
    """
    Ajoute les métadonnées de traitement SILVER.

    Colonnes ajoutées :
    - ingestion_date : date courante pour partitionnement
    - processing_timestamp : timestamp UTC de traitement SILVER

    Args:
        silver_with_alerts: DataFrame avec enrichissements médicaux

    Returns:
        DataFrame: DataFrame avec métadonnées SILVER
    """
    return (silver_with_alerts
            .withColumn("ingestion_date", current_date())
            .withColumn("processing_timestamp", current_timestamp()))


def _write_silver_data_with_partitioning(final_silver_df, silver_base: str) -> None:
    """
    Écrit les données enrichies vers la zone SILVER avec optimisations.

    Configuration d'écriture :
    - Repartitionnement par ingestion_date et patient_id pour requêtes optimisées
    - Partitionnement physique par ingestion_date
    - Compression Snappy pour balance taille/performance
    - Mode overwrite pour gestion incrémentale

    Args:
        final_silver_df: DataFrame final enrichi
        silver_base: Chemin vers zone SILVER

    Raises:
        SystemExit: Si erreur d'écriture
    """
    try:
        (final_silver_df
         .repartition(col("ingestion_date"), col("patient_id"))  # Optimisation requêtes
         .write
         .mode("overwrite")
         .partitionBy("ingestion_date")
         .option("compression", "snappy")
         .parquet(silver_base))

        print("INFO: Job Bronze to Silver completed successfully")
        print(f"INFO: Données écrites dans: {silver_base}")

    except Exception as write_error:
        print(f"ERROR: Failed to write silver data: {write_error}")
        sys.exit(1)


def main() -> None:
    """
    Point d'entrée principal pour la transformation BRONZE vers SILVER.

    Pipeline d'enrichissement médical :
    1. Lecture et validation données BRONZE
    2. Classification par groupe d'âge selon seuils pédiatriques/gériatriques
    3. Application seuils SpO2 différenciés par groupe d'âge
    4. Classification température avec vulnérabilité par âge
    5. Détection combinaisons critiques nécessitant intervention immédiate
    6. Ajout métadonnées de traitement SILVER
    7. Écriture avec partitionnement optimisé pour requêtes analytiques
    """
    print("INFO: Démarrage du job Bronze to Silver")

    spark = _create_spark_session()

    try:
        # 1. Configuration chemins et validation
        base_dir, lake_dir, bronze_base, silver_base = _get_data_lake_paths()

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Lake directory: {lake_dir}")
        print(f"INFO: Bronze base: {bronze_base}")
        print(f"INFO: Silver base: {silver_base}")

        # 2. Lecture et validation données BRONZE
        print("INFO: Lecture des données bronze...")
        bronze = _validate_and_read_bronze_data(spark, bronze_base)

        if bronze is None:
            return

        # 3. Classification par groupe d'âge (base pour seuils différenciés)
        print("INFO: Application des seuils physiologiques par âge...")
        bronze_enriched = _add_age_group_classification(bronze)

        # 4. Classification SpO2 avec seuils par groupe d'âge
        silver_with_spo2 = _classify_spo2_status(bronze_enriched)

        # 5. Classification température avec vulnérabilité par âge
        silver_with_temp = _classify_temperature_status(silver_with_spo2)

        # 6. Détection combinaisons critiques
        silver_with_alerts = _detect_critical_combinations(silver_with_temp)

        # 7. Ajout métadonnées de traitement SILVER
        final_silver_df = _add_silver_processing_metadata(silver_with_alerts)

        # 8. Écriture vers zone SILVER avec optimisations
        print("INFO: Écriture vers la couche Silver...")
        _write_silver_data_with_partitioning(final_silver_df, silver_base)

    except Exception as e:
        print(f"ERROR: Job failed: {e}")
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
