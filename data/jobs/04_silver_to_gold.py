"""
Étape 4 — Modèles métier vers GOLD.

Rôle :
    Agrégations, indicateurs métier et features ML depuis les données SILVER
    enrichies. Production de tables finales pour BI, rapports et machine learning.

Objectifs :
    - Agrégations quotidiennes pour tableaux de bord médicaux
    - Features ML pour détection d'anomalies et prédiction
    - Alertes temps réel pour intervention immédiate
    - Tables optimisées pour consommation analytique

Destination :
    Dossier data/lake/gold/ avec sous-répertoires spécialisés :
    - facts_daily/ : agrégations quotidiennes
    - features_ml/ : caractéristiques patient pour ML
    - alerts_realtime/ : alertes critiques temps réel

Entrées :
    - Fichiers Parquet depuis data/lake/silver/ingestion_date=*/*.parquet
    - Données enrichies avec classifications médicales

Sorties :
    - facts_daily/ : métriques quotidiennes (moyennes, min/max vitaux)
    - features_ml/ : profils patients (variabilité, patterns temporels)
    - alerts_realtime/ : alertes critiques partitionnées par date
    - Format Parquet optimisé pour requêtes analytiques

Effets de bord :
    - Création sous-répertoires spécialisés GOLD
    - Calculs statistiques avancés (écart-type, variabilité)
    - Détection alertes multicritères pour intervention médicale
"""

import os
import sys
from typing import List, Optional

from pyspark.sql import SparkSession
from pyspark.sql.functions import (col, avg, stddev, min as smin, max as smax,
                                   count, sum as ssum, expr, when, lag,
                                   current_timestamp, date_format, hour,
                                   percentile_approx, variance, skewness,
                                   kurtosis, year, weekofyear, to_utc_timestamp,
                                   to_date, lit, abs as spark_abs)
from pyspark.sql.window import Window

# Seuils pour classification des alertes critiques
ALERT_THRESHOLDS = {
    "HIGH_FEVER": 39.0,
    "HYPOTHERMIA": 35.0,
    "TACHYCARDIA": 120,
    "BRADYCARDIA": 50,
    "LOW_OXYGEN": 90
}

# Configuration pour enrichissement temporel
TIME_PERIODS = {
    "MORNING": {"start": 6, "end": 11},
    "AFTERNOON": {"start": 12, "end": 17},
    "EVENING": {"start": 18, "end": 21},
    "NIGHT": {"start": 22, "end": 5}  # Cycle 22h-5h suivante
}


def _create_spark_session() -> SparkSession:
    """
    Crée une session Spark configurée pour le traitement GOLD.

    Configuration optimisée pour agrégations :
    - Adaptive query execution pour optimisation automatique
    - Coalesce automatique des partitions pour réduire overhead
    - Serializer Kryo pour performance sur objets complexes

    Returns:
        SparkSession: Session Spark configurée
    """
    return (SparkSession.builder
            .appName("tech4good-04-silver-to-gold")
            .config("spark.sql.session.timeZone", "UTC")
            .config("spark.sql.adaptive.enabled", "true")
            .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
            .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
            .getOrCreate())


def _get_data_lake_paths() -> tuple[str, str, str, str]:
    """
    Calcule les chemins absolus vers les répertoires du data lake.

    Returns:
        tuple: (base_dir, lake_dir, silver_base, gold_base)
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lake_dir = os.path.join(base_dir, "lake")
    silver_base = os.path.join(lake_dir, "silver")
    gold_base = os.path.join(lake_dir, "gold")

    return base_dir, lake_dir, silver_base, gold_base


def _validate_and_read_silver_data(spark: SparkSession, silver_base: str):
    """
    Valide l'existence des données SILVER et les lit avec gestion d'erreurs.

    Args:
        spark: Session Spark active
        silver_base: Chemin vers zone SILVER

    Returns:
        DataFrame: Données SILVER lues et validées

    Raises:
        SystemExit: Si données manquantes ou erreur de lecture
    """
    if not os.path.exists(silver_base):
        print(f"ERROR: Silver directory not found: {silver_base}")
        sys.exit(1)

    try:
        df = spark.read.parquet(silver_base)
        row_count = df.count()

        print(f"INFO: Loaded {row_count} rows from silver")
        print("INFO: Schema from silver data:")
        df.printSchema()

        if row_count == 0:
            print("ERROR: No data found in silver layer")
            sys.exit(1)

        # Vérification colonnes disponibles pour adaptation du traitement
        available_cols = df.columns
        print(f"INFO: Available columns: {available_cols}")

        return df

    except Exception as read_error:
        print(f"ERROR: Failed to read silver data - {str(read_error)}")
        sys.exit(1)


def _add_temporal_enrichment(df):
    """
    Ajoute l'enrichissement temporel pour analyser les patterns par période.

    Enrichissements ajoutés :
    - hour_of_day : heure d'ingestion (0-23)
    - day_period : période de la journée (morning, afternoon, evening, night)

    Utilité médicale : identifier patterns circadiens et optimiser monitoring.

    Args:
        df: DataFrame avec colonne ingestion_ts

    Returns:
        DataFrame: DataFrame avec enrichissements temporels
    """
    if "ingestion_ts" not in df.columns:
        print("WARNING: ingestion_ts column not found, skipping temporal enrichment")
        return df

    periods = TIME_PERIODS

    enriched_df = df.withColumn("hour_of_day", hour("ingestion_ts"))

    return enriched_df.withColumn(
        "day_period",
        when(col("hour_of_day").between(periods["MORNING"]["start"], periods["MORNING"]["end"]), "morning")
        .when(col("hour_of_day").between(periods["AFTERNOON"]["start"], periods["AFTERNOON"]["end"]), "afternoon")
        .when(col("hour_of_day").between(periods["EVENING"]["start"], periods["EVENING"]["end"]), "evening")
        .otherwise("night")
    )


def _compute_daily_facts(df) -> Optional[object]:
    """
    Calcule les agrégations quotidiennes pour tableaux de bord médicaux.

    Métriques calculées :
    - Compteurs : nombre total mesures, patients uniques
    - Vitaux moyens/min/max : FC, température, SpO2 selon disponibilité
    - Métadonnées : niveau d'agrégation, timestamp traitement

    Args:
        df: DataFrame avec enrichissements temporels

    Returns:
        DataFrame: Faits quotidiens agrégés ou None si erreur
    """
    try:
        required_cols = ["patient_id", "ingestion_date"]
        if not all(col_name in df.columns for col_name in required_cols):
            print("WARNING: Required columns for daily facts not found")
            return None

        # Construction dynamique des agrégations selon colonnes disponibles
        agg_expressions = [
            count("*").alias("total_measurements"),
            count("patient_id").alias("unique_patients")
        ]

        # Ajout agrégations conditionnelles selon colonnes présentes
        vital_aggregations = {
            "heart_rate_bpm": ["avg_heart_rate", "min_heart_rate", "max_heart_rate"],
            "temperature_core_c": ["avg_temperature", "min_temperature", "max_temperature"],
            "SpO2": ["avg_spo2", "min_spo2"]
        }

        for vital_col, aliases in vital_aggregations.items():
            if vital_col in df.columns:
                agg_expressions.extend([
                    avg(vital_col).alias(aliases[0]),
                    smin(vital_col).alias(aliases[1]),
                    smax(vital_col).alias(aliases[2]) if len(aliases) > 2 else smin(vital_col).alias(aliases[1])
                ])

        daily_facts = (df
            .groupBy("ingestion_date")
            .agg(*agg_expressions)
            .withColumn("aggregation_level", lit("daily"))
            .withColumn("gold_processed_ts", to_utc_timestamp(current_timestamp(), "UTC"))
        )

        print("INFO: Daily aggregations computed")
        return daily_facts

    except Exception as agg_error:
        print(f"WARNING: Daily aggregations failed - {str(agg_error)}")
        return None


def _compute_ml_features(df) -> Optional[object]:
    """
    Calcule les features ML pour détection d'anomalies et prédiction.

    Features calculées par patient :
    - Compteurs : nombre de mesures, patterns temporels
    - Variabilité : écart-type des vitaux, variabilité FC
    - Patterns : heure moyenne de mesure, features lag temporelles

    Args:
        df: DataFrame avec enrichissements

    Returns:
        DataFrame: Features ML par patient ou None si erreur
    """
    try:
        if "patient_id" not in df.columns or df.count() <= 10:
            print("WARNING: Insufficient data for ML features computation")
            return None

        # Window par patient pour features temporelles
        patient_window = Window.partitionBy("patient_id").orderBy("ingestion_ts")

        # Calcul features de variabilité (si colonne FC disponible)
        ml_df = df
        if "heart_rate_bpm" in df.columns:
            ml_df = (ml_df
                .withColumn("hr_lag_1", lag("heart_rate_bpm", 1).over(patient_window))
                .withColumn("hr_variability",
                    when(col("hr_lag_1").isNotNull(),
                         spark_abs(col("heart_rate_bpm") - col("hr_lag_1"))).otherwise(0))
            )

        # Construction agrégations par patient selon colonnes disponibles
        patient_agg_expressions = [
            count("*").alias("measurement_count"),
            avg("hour_of_day").alias("avg_measurement_hour")
        ]

        # Features vitaux conditionnelles
        if "heart_rate_bpm" in ml_df.columns:
            patient_agg_expressions.extend([
                avg("heart_rate_bpm").alias("patient_avg_hr"),
                stddev("heart_rate_bpm").alias("patient_hr_std"),
                avg("hr_variability").alias("patient_hr_variability")
            ])

        if "temperature_core_c" in ml_df.columns:
            patient_agg_expressions.extend([
                avg("temperature_core_c").alias("patient_avg_temp"),
                stddev("temperature_core_c").alias("patient_temp_std")
            ])

        ml_features = (ml_df
            .groupBy("patient_id")
            .agg(*patient_agg_expressions)
            .withColumn("feature_type", lit("patient_profile"))
            .withColumn("gold_processed_ts", to_utc_timestamp(current_timestamp(), "UTC"))
        )

        print("INFO: ML features computed")
        return ml_features

    except Exception as ml_error:
        print(f"WARNING: ML features computation failed - {str(ml_error)}")
        return None


def _detect_realtime_alerts(df) -> Optional[object]:
    """
    Détecte les alertes temps réel selon seuils médicaux critiques.

    Alertes détectées :
    - HIGH_FEVER : température > 39°C (urgence)
    - HYPOTHERMIA : température < 35°C (urgence)
    - TACHYCARDIA : FC > 120 bpm (surveillance)
    - BRADYCARDIA : FC < 50 bpm (surveillance)
    - LOW_OXYGEN : SpO2 < 90% (critique)

    Args:
        df: DataFrame avec vitaux

    Returns:
        DataFrame: Alertes détectées ou None si aucune alerte
    """
    try:
        thresholds = ALERT_THRESHOLDS
        alert_conditions = []

        # Construction conditions d'alerte selon colonnes disponibles
        if "temperature_core_c" in df.columns:
            alert_conditions.extend([
                (col("temperature_core_c") > thresholds["HIGH_FEVER"], "HIGH_FEVER", "critical"),
                (col("temperature_core_c") < thresholds["HYPOTHERMIA"], "HYPOTHERMIA", "critical")
            ])

        if "heart_rate_bpm" in df.columns:
            alert_conditions.extend([
                (col("heart_rate_bpm") > thresholds["TACHYCARDIA"], "TACHYCARDIA", "warning"),
                (col("heart_rate_bpm") < thresholds["BRADYCARDIA"], "BRADYCARDIA", "warning")
            ])

        if "SpO2" in df.columns:
            alert_conditions.append(
                (col("SpO2") < thresholds["LOW_OXYGEN"], "LOW_OXYGEN", "critical")
            )

        if not alert_conditions:
            print("WARNING: No vital columns available for alert detection")
            return None

        # Ajout colonnes d'alerte au DataFrame
        alerts_df = df
        for condition, alert_type, severity in alert_conditions:
            alerts_df = alerts_df.withColumn(
                f"alert_{alert_type.lower()}",
                when(condition, lit(True)).otherwise(lit(False))
            )

        # Filtrage des lignes avec au moins une alerte
        alert_filters = [
            col(f"alert_{alert_type.lower()}") == True
            for _, alert_type, _ in alert_conditions
        ]

        if alert_filters:
            final_filter = alert_filters[0]
            for filter_cond in alert_filters[1:]:
                final_filter = final_filter | filter_cond

            alerts = (alerts_df
                .filter(final_filter)
                .withColumn("alert_processed_ts", to_utc_timestamp(current_timestamp(), "UTC"))
                .withColumn("alert_severity", lit("computed"))
            )

            alert_count = alerts.count() if alerts else 0
            print(f"INFO: {alert_count} alerts detected")

            return alerts if alert_count > 0 else None

    except Exception as alert_error:
        print(f"WARNING: Alert processing failed - {str(alert_error)}")
        return None


def _write_gold_dataset(dataset, output_path: str, dataset_name: str,
                       partition_by: Optional[List[str]] = None) -> None:
    """
    Écrit un dataset vers la zone GOLD avec gestion d'erreurs.

    Args:
        dataset: DataFrame à écrire
        output_path: Chemin de sortie
        dataset_name: Nom du dataset pour logging
        partition_by: Colonnes de partitionnement optionnelles
    """
    if dataset is None:
        print(f"INFO: No data to write for {dataset_name}")
        return

    try:
        os.makedirs(output_path, exist_ok=True)

        writer = dataset.write.mode("overwrite")

        if partition_by:
            writer = writer.partitionBy(*partition_by)

        writer.parquet(output_path)

        print(f"SUCCESS: {dataset_name} written to {output_path}")

    except Exception as write_error:
        print(f"WARNING: Failed to write {dataset_name} - {str(write_error)}")


def main() -> None:
    """
    Point d'entrée principal pour la transformation SILVER vers GOLD.

    Pipeline de production de données métier :
    1. Lecture et validation données SILVER enrichies
    2. Enrichissement temporel pour analyser patterns circadiens
    3. Calcul agrégations quotidiennes pour tableaux de bord médicaux
    4. Génération features ML pour détection d'anomalies
    5. Détection alertes temps réel pour intervention immédiate
    6. Écriture datasets spécialisés GOLD avec partitionnement optimisé
    """
    spark = _create_spark_session()

    try:
        # 1. Configuration chemins et validation
        base_dir, lake_dir, silver_base, gold_base = _get_data_lake_paths()

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Lake directory: {lake_dir}")
        print(f"INFO: Silver base: {silver_base}")
        print(f"INFO: Gold base: {gold_base}")

        # 2. Lecture et validation données SILVER
        df = _validate_and_read_silver_data(spark, silver_base)

        # 3. Enrichissement temporel pour patterns circadiens
        df_enriched = _add_temporal_enrichment(df)
        print("INFO: Temporal enrichment added")

        # 4. Calcul agrégations quotidiennes
        daily_facts = _compute_daily_facts(df_enriched)

        # 5. Génération features ML
        ml_features = _compute_ml_features(df_enriched)

        # 6. Détection alertes temps réel
        alerts = _detect_realtime_alerts(df_enriched)

        # 7. Écriture datasets GOLD spécialisés
        os.makedirs(gold_base, exist_ok=True)
        
        # Faits quotidiens pour tableaux de bord
        facts_daily_path = os.path.join(gold_base, "facts_daily")
        _write_gold_dataset(daily_facts, facts_daily_path, "Daily facts")

        # Features ML pour algorithmes prédictifs
        features_ml_path = os.path.join(gold_base, "features_ml")
        _write_gold_dataset(ml_features, features_ml_path, "ML features")

        # Alertes temps réel partitionnées par date
        alerts_realtime_path = os.path.join(gold_base, "alerts_realtime")
        _write_gold_dataset(alerts, alerts_realtime_path, "Alerts",
                          partition_by=["ingestion_date"])

        # 8. Affichage statistiques finales
        row_count = df.count()
        print(f"SUCCESS: Gold layer processing completed")
        print(f"STATS: Input rows processed: {row_count}")

    except Exception as e:
        print(f"ERROR in 04_silver_to_gold: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
