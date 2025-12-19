# jobs/03_bronze_to_silver.py
import parquet
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, avg, count, stddev, expr, current_timestamp,
    lag, lead, abs as spark_abs, round as spark_round,
    to_utc_timestamp, to_date, lit, current_date
)
from pyspark.sql.window import Window
import sys
import os

def main():
    print("INFO: Démarrage du job Bronze to Silver")

    spark = (SparkSession.builder
             .appName("tech4good-03-bronze-to-silver")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.adaptive.enabled", "true")
             .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
             .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
             .getOrCreate())

    try:
        # ✅ CORRECTION CRITIQUE: Éviter le conflit bronze/quarantine
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bronze_base = os.path.join(base_dir, "bronze")
        silver_base = os.path.join(base_dir, "silver")
        quarantine_base = os.path.join(base_dir, "bronze", "quarantine")

        print(f"INFO: Base directory: {base_dir}")
        print(f"INFO: Bronze base: {bronze_base}")
        print(f"INFO: Silver base: {silver_base}")

        # ✅ LECTURE SPÉCIFIQUE DES PARTITIONS VALIDES (EXCLURE QUARANTINE)
        print("INFO: Lecture des données bronze (exclusion quarantine)...")
        try:
            # Lecture avec basePath pour éviter le conflit structurel
                     .option("basePath", bronze_base)
                     .parquet(f"{bronze_base}/event_date=*/*.parquet"))
            
            # Filtrer explicitement les données non-quarantine
            bronze = bronze.filter(~col("_file_path").contains("quarantine"))
            
            row_count = bronze.count()
            print(f"INFO: Loaded {row_count} rows from bronze (quarantine excluded)")
            if row_count == 0:
                print("WARNING: No data found in bronze layer")
                return

            print("INFO: Schema from bronze:")
            bronze.printSchema()
            # ✅ INTÉGRATION DU MOTEUR D'ALERTES OFFLINE
            from offline_alerts_engine import OfflineAlertsEngine, process_batch_alerts
            
            print("INFO: Initialisation du moteur d'alertes offline...")
            alerts_engine = OfflineAlertsEngine("../conf/medical_thresholds.json")
            # ✅ ENRICHISSEMENT AVEC CLASSIFICATION DES SEUILS PAR ÂGE
            print("INFO: Application des seuils physiologiques par âge...")
            
            # Ajouter le groupe d'âge
            bronze_enriched = bronze.withColumn(
                "age_group",
                when(col("age_years").between(0, 1), "G1")
                .when(col("age_years").between(1, 5), "G2")
                .when(col("age_years").between(6, 12), "G3")
                .when(col("age_years").between(13, 17), "G4")
                .when(col("age_years").between(18, 59), "G5")
                .when(col("age_years").between(60, 80), "G6")
                .otherwise("G5")  # Défaut adulte
            # ✅ CLASSIFICATION DES VITAUX PAR SEUILS
            silver_with_alerts = bronze_enriched.withColumn(
                # SpO₂ classification
                "spo2_status",
                when(col("age_group").isin(["G1", "G2"]) & (col("spo2") < 88), "critical")
                .when(col("age_group").isin(["G1", "G2"]) & (col("spo2") <= 90), "emergency")
                .when(col("age_group").isin(["G1", "G2"]) & (col("spo2") <= 93), "alert")
                .when(col("age_group").isin(["G1", "G2"]) & (col("spo2") == 94), "vigilance")
                .when(col("age_group").isin(["G1", "G2"]) & (col("spo2") >= 95), "normal")
                # G3
                .when((col("age_group") == "G3") & (col("spo2") < 88), "critical")
                .when((col("age_group") == "G3") & (col("spo2") <= 89), "emergency")
                .when((col("age_group") == "G3") & (col("spo2") <= 93), "alert")
                .when((col("age_group") == "G3") & (col("spo2") == 94), "vigilance")
                .when((col("age_group") == "G3") & (col("spo2") >= 95), "normal")
                # G4-G6 (adultes/seniors)
                .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("spo2") < 88), "critical")
                .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("spo2") <= 88), "emergency")
                .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("spo2") <= 92), "alert")
                .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("spo2") == 93), "vigilance")
                .when(col("age_group").isin(["G4", "G5", "G6"]) & (col("spo2") >= 94), "normal")
                .otherwise("unknown")
            ).withColumn(
                # Température classification
                "temperature_status",
                when(col("age_group").isin(["G1", "G6"]) & (col("temperature") >= 38.5), "emergency")
                .when(col("age_group").isin(["G1", "G6"]) & (col("temperature") >= 38.0), "alert")
                .when(col("age_group").isin(["G1", "G6"]) & (col("temperature") < 36.0), "emergency")
                .when(col("age_group").isin(["G2", "G3", "G4", "G5"]) & (col("temperature") >= 39.0), "emergency")
                .when(col("age_group").isin(["G2", "G3", "G4", "G5"]) & (col("temperature") >= 38.0), "alert")
                .when(col("temperature").between(36.0, 37.5), "normal")
                .otherwise("vigilance")
            ).withColumn(
                # Combinaisons critiques
                "critical_combination",
                when((col("temperature") >= 38.0) & (col("spo2_status").isin(["alert", "emergency", "critical"])), "C1_fever_hypoxia")
                .when((col("spo2") <= 90) & (col("heart_rate") > 110), "C2_respiratory_distress")
                .when((col("pain_score") >= 7) & (col("spo2") <= 92), "C3_pain_hypoxia")
                .otherwise(None)
            )
            # ✅ CALCUL DES MÉTRIQUES DE QUALITÉ
            print("INFO: Calcul des métriques de qualité des données...")
            
            # Métriques par patient/jour
            daily_quality = silver_with_alerts.groupBy("patient_id", "event_date").agg(
                count("*").alias("total_readings"),
                count(when(col("spo2").isNotNull() & 
                          col("temperature").isNotNull() & 
                          col("heart_rate").isNotNull(), 1)).alias("complete_readings"),
                count(when(col("spo2_status") == "critical", 1)).alias("critical_alerts"),
                count(when(col("temperature_status") == "emergency", 1)).alias("temp_emergencies"),
                count(when(col("critical_combination").isNotNull(), 1)).alias("combination_alerts")
            ).withColumn(
                "completeness_pct", 
                spark_round((col("complete_readings") / col("total_readings")) * 100, 2)
            )
            # ✅ EXPORT VERS SILVER AVEC PARTITIONNEMENT OPTIMISÉ
            print("INFO: Écriture vers la couche Silver...")
            
            (silver_with_alerts
             .withColumn("ingestion_date", current_date())
             .withColumn("processing_timestamp", current_timestamp())
             .repartition(col("ingestion_date"), col("patient_id"))
             .write
             .mode("overwrite")
             .partitionBy("ingestion_date")
             .option("compression", "snappy")
             .parquet(silver_base))
            # ✅ EXPORT DES MÉTRIQUES DE QUALITÉ
            print("INFO: Export des métriques de qualité...")
            
            metrics_summary = daily_quality.agg(
                avg("completeness_pct").alias("avg_completeness_pct"),
                count(when(col("completeness_pct") >= 95, 1)).alias("patients_above_95pct"),
                count("patient_id").alias("total_patient_days"),
                sum("critical_alerts").alias("total_critical_alerts"),
                sum("combination_alerts").alias("total_combination_alerts")
            )

            metrics_summary.show()
            
            # Sauvegarder les métriques
            (metrics_summary
             .coalesce(1)
             .write
             .mode("overwrite")
             .option("header", "true")
             .csv(os.path.join(base_dir, "evidence", "quality_metrics")))
            print("✅ Job Bronze to Silver completed successfully")
            print(f"✅ Données écrites dans: {silver_base}")
        except Exception as e:
            print(f"ERROR: Failed to process bronze data: {e}")
            raise
        print(f"ERROR: Job failed: {e}")

        except Exception as write_error:
            print(f"ERROR: Failed to write silver data - {str(write_error)}")
            sys.exit(1)

        # Affichage des enrichissements ajoutés
        enriched_cols = [col for col in final_silver.columns if col not in bronze.columns]
        if enriched_cols:
            print(f"INFO: New enriched columns: {enriched_cols}")

    except Exception as e:
        print(f"ERROR in 03_bronze_to_silver: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
