# jobs/04_silver_to_gold.py
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, avg, stddev, min as smin, max as smax, count, sum as ssum,
    expr, when, lag, current_timestamp, date_format, hour,
    percentile_approx, variance, skewness, kurtosis, year, weekofyear,
    to_utc_timestamp, to_date, lit
)
from pyspark.sql.window import Window
import sys
import os

def main():
    spark = (SparkSession.builder
             .appName("tech4good-04-silver-to-gold")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.adaptive.enabled", "true")
             .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
             .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
             .getOrCreate())

    try:
        # ✅ CHEMINS ABSOLUS POUR ÉVITER LES PROBLÈMES DE RÉPERTOIRE
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        silver_base = os.path.join(base_dir, "silver")
        gold_base = os.path.join(base_dir, "gold")
        
        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Silver base: {silver_base}")
        print(f"INFO: Gold base: {gold_base}")

        # Vérifier que le répertoire silver existe
        if not os.path.exists(silver_base):
            print(f"ERROR: Silver directory not found: {silver_base}")
            sys.exit(1)

        # ✅ LECTURE ROBUSTE DES DONNÉES SILVER
        try:
            df = spark.read.parquet(silver_base)
            row_count = df.count()
            
            print(f"INFO: Loaded {row_count} rows from silver")
            print("INFO: Schema from silver data:")
            df.printSchema()

            if row_count == 0:
                print("ERROR: No data found in silver layer")
                sys.exit(1)

        except Exception as read_error:
            print(f"ERROR: Failed to read silver data - {str(read_error)}")
            sys.exit(1)

        # ✅ VÉRIFICATION DES COLONNES DISPONIBLES
        available_cols = df.columns
        print(f"INFO: Available columns: {available_cols}")

        # ===== ENRICHISSEMENT TEMPOREL =====
        if "ingestion_ts" in available_cols:
            df = (df
                .withColumn("hour_of_day", hour("ingestion_ts"))
                .withColumn("day_period",
                    when(col("hour_of_day").between(6, 11), "morning")
                    .when(col("hour_of_day").between(12, 17), "afternoon")
                    .when(col("hour_of_day").between(18, 21), "evening")
                    .otherwise("night"))
            )
            print("INFO: Temporal enrichment added")

        # ===== AGRÉGATIONS QUOTIDIENNES =====
        try:
            daily_facts = None
            
            if "patient_id" in available_cols and "ingestion_date" in available_cols:
                agg_exprs = [
                    count("*").alias("total_measurements"),
                    count("patient_id").alias("unique_patients")
                ]
                
                # Ajouter les agrégations selon les colonnes disponibles
                if "heart_rate_bpm" in available_cols:
                    agg_exprs.extend([
                        avg("heart_rate_bpm").alias("avg_heart_rate"),
                        smin("heart_rate_bpm").alias("min_heart_rate"),
                        smax("heart_rate_bpm").alias("max_heart_rate")
                    ])
                
                if "temperature_core_c" in available_cols:
                    agg_exprs.extend([
                        avg("temperature_core_c").alias("avg_temperature"),
                        smin("temperature_core_c").alias("min_temperature"),
                        smax("temperature_core_c").alias("max_temperature")
                    ])
                
                if "SpO2" in available_cols:
                    agg_exprs.extend([
                        avg("SpO2").alias("avg_spo2"),
                        smin("SpO2").alias("min_spo2")
                    ])

                daily_facts = (df
                    .groupBy("ingestion_date")
                    .agg(*agg_exprs)
                    .withColumn("aggregation_level", lit("daily"))
                    .withColumn("gold_processed_ts", to_utc_timestamp(current_timestamp(), "UTC"))
                )
                
                print("INFO: Daily aggregations computed")

        except Exception as agg_error:
            print(f"WARNING: Daily aggregations failed - {str(agg_error)}")

        # ===== FEATURES ML (STATISTIQUES AVANCÉES) =====
        try:
            ml_features = None
            
            if "patient_id" in available_cols and row_count > 10:
                # Window par patient pour calculer des features temporelles
                patient_window = Window.partitionBy("patient_id").orderBy("ingestion_ts")
                
                ml_df = df
                
                # Features de base
                if "heart_rate_bpm" in available_cols:
                    ml_df = ml_df.withColumn("hr_lag_1", lag("heart_rate_bpm", 1).over(patient_window))
                    ml_df = ml_df.withColumn("hr_variability", 
                        when(col("hr_lag_1").isNotNull(), 
                             abs(col("heart_rate_bpm") - col("hr_lag_1"))).otherwise(0))

                # Agrégations par patient
                patient_agg_exprs = [
                    count("*").alias("measurement_count"),
                    avg("hour_of_day").alias("avg_measurement_hour")
                ]
                
                if "heart_rate_bpm" in available_cols:
                    patient_agg_exprs.extend([
                        avg("heart_rate_bpm").alias("patient_avg_hr"),
                        stddev("heart_rate_bpm").alias("patient_hr_std"),
                        avg("hr_variability").alias("patient_hr_variability")
                    ])
                
                if "temperature_core_c" in available_cols:
                    patient_agg_exprs.extend([
                        avg("temperature_core_c").alias("patient_avg_temp"),
                        stddev("temperature_core_c").alias("patient_temp_std")
                    ])

                ml_features = (ml_df
                    .groupBy("patient_id")
                    .agg(*patient_agg_exprs)
                    .withColumn("feature_type", lit("patient_profile"))
                    .withColumn("gold_processed_ts", to_utc_timestamp(current_timestamp(), "UTC"))
                )
                
                print("INFO: ML features computed")

        except Exception as ml_error:
            print(f"WARNING: ML features computation failed - {str(ml_error)}")

        # ===== ALERTES TEMPS RÉEL =====
        try:
            alerts = None
            
            alert_conditions = []
            
            if "temperature_core_c" in available_cols:
                alert_conditions.append(
                    (col("temperature_core_c") > 39.0, "HIGH_FEVER", "critical")
                )
                alert_conditions.append(
                    (col("temperature_core_c") < 35.0, "HYPOTHERMIA", "critical")
                )
            
            if "heart_rate_bpm" in available_cols:
                alert_conditions.append(
                    (col("heart_rate_bpm") > 120, "TACHYCARDIA", "warning")
                )
                alert_conditions.append(
                    (col("heart_rate_bpm") < 50, "BRADYCARDIA", "warning")
                )
            
            if "SpO2" in available_cols:
                alert_conditions.append(
                    (col("SpO2") < 90, "LOW_OXYGEN", "critical")
                )

            if alert_conditions:
                # Créer un DataFrame d'alertes
                alerts_df = df
                
                for condition, alert_type, severity in alert_conditions:
                    alerts_df = alerts_df.withColumn(f"alert_{alert_type.lower()}", 
                        when(condition, lit(True)).otherwise(lit(False)))

                # Filtrer seulement les lignes avec au moins une alerte
                alert_filters = [col(f"alert_{alert_type.lower()}") == True for _, alert_type, _ in alert_conditions]
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

        except Exception as alert_error:
            print(f"WARNING: Alert processing failed - {str(alert_error)}")

        # ===== ÉCRITURE DES COUCHES GOLD =====
        
        # Créer les répertoires de sortie
        os.makedirs(gold_base, exist_ok=True)
        
        facts_daily_path = os.path.join(gold_base, "facts_daily")
        features_ml_path = os.path.join(gold_base, "features_ml")
        alerts_realtime_path = os.path.join(gold_base, "alerts_realtime")

        # Écriture des faits quotidiens
        if daily_facts is not None:
            try:
                os.makedirs(facts_daily_path, exist_ok=True)
                (daily_facts
                 .write
                 .mode("overwrite")
                 .parquet(facts_daily_path))
                print(f"SUCCESS: Daily facts written to {facts_daily_path}")
            except Exception as write_error:
                print(f"WARNING: Failed to write daily facts - {str(write_error)}")

        # Écriture des features ML
        if ml_features is not None:
            try:
                os.makedirs(features_ml_path, exist_ok=True)
                (ml_features
                 .write
                 .mode("overwrite")
                 .parquet(features_ml_path))
                print(f"SUCCESS: ML features written to {features_ml_path}")
            except Exception as write_error:
                print(f"WARNING: Failed to write ML features - {str(write_error)}")

        # Écriture des alertes
        if alerts is not None and alerts.count() > 0:
            try:
                os.makedirs(alerts_realtime_path, exist_ok=True)
                (alerts
                 .write
                 .mode("overwrite")
                 .partitionBy("ingestion_date")
                 .parquet(alerts_realtime_path))
                print(f"SUCCESS: Alerts written to {alerts_realtime_path}")
            except Exception as write_error:
                print(f"WARNING: Failed to write alerts - {str(write_error)}")

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
