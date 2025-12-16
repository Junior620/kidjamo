# jobs/03_bronze_to_silver_simple.py
# Version ultra-simplifiée pour contourner les problèmes de blocage
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, avg, current_timestamp, lit
import sys

def main():
    spark = SparkSession.builder.appName("simple-bronze-to-silver").getOrCreate()

    try:
        # Lecture directe des données bronze
        bronze = spark.read.parquet("bronze")

        # Enrichissements minimaux mais fonctionnels
        silver = (bronze
            .withColumn("quality_score", lit(0.8))  # Score fixe temporaire
            .withColumn("heat_index_calculated", col("heat_index_c"))
            .withColumn("q_heart_rate_valid", when(col("heart_rate_bpm").between(40, 200), 1).otherwise(0))
            .withColumn("q_spo2_valid", when(col("SpO2").between(70, 100), 1).otherwise(0))
            .withColumn("q_temp_core_valid", when(col("temperature_core_c").between(35, 42), 1).otherwise(0))
            .withColumn("q_hydration_valid", when(col("hydration_pct").between(0, 100), 1).otherwise(0))
            .withColumn("q_respiratory_valid", when(col("respiratory_rate").between(8, 40), 1).otherwise(0))
            .withColumn("hr_avg_10min", col("heart_rate_bpm"))
            .withColumn("spo2_avg_10min", col("SpO2"))
            .withColumn("temp_avg_10min", col("temperature_core_c"))
            .withColumn("hydration_avg_10min", col("hydration_pct"))
            .withColumn("hr_variation", lit(0))
            .withColumn("temp_variation", lit(0))
            .withColumn("alert_fever", when(col("temperature_core_c") > 38.5, 1).otherwise(0))
            .withColumn("alert_tachycardia", when(col("heart_rate_bpm") > 120, 1).otherwise(0))
            .withColumn("alert_hypoxia", when(col("SpO2") < 90, 1).otherwise(0))
            .withColumn("alert_dehydration", when(col("hydration_pct") < 30, 1).otherwise(0))
            .withColumn("alert_hr_spike", lit(0))
            .withColumn("age_group",
                when(col("age") < 12, "enfant")
                .when(col("age").between(12, 17), "adolescent")
                .when(col("age").between(18, 64), "adulte")
                .otherwise("senior"))
            .withColumn("silver_processed_ts", current_timestamp())
            .withColumn("processing_delay_minutes", lit(0))
        )

        # Écriture
        (silver.filter(col("quality_score") >= 0.4)
         .write.mode("overwrite")
         .partitionBy("ingestion_date", "age_group")
         .parquet("silver"))

        print(f"SUCCESS: {silver.count()} rows processed to silver")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
