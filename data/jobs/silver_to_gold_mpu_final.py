import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql import DataFrame
from pyspark.sql.functions import *
from pyspark.sql.types import *
import boto3
from datetime import datetime

# Initialisation
args = getResolvedOptions(sys.argv, [
    'JOB_NAME',
    'silver_input_path',
    'gold_output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("🚀 JOB SILVER-TO-GOLD FINAL POUR MPU CHRISTIAN")
print(f"📂 Silver Input: {args['silver_input_path']}")
print(f"📂 Gold Output: {args['gold_output_path']}")

try:
    # Lecture des données silver
    silver_path = args['silver_input_path'] + "mpu_christian_enriched/"
    print(f"📖 Lecture depuis: {silver_path}")

    df = spark.read.json(silver_path)

    print(f"📊 Nombre de lignes silver: {df.count()}")

    if df.count() > 0:
        # Window functions pour calculs temporels
        from pyspark.sql.window import Window

        # Fenêtre glissante pour moyennes mobiles (par device)
        window_spec = Window.partitionBy("device_id").orderBy("silver_processing_timestamp").rowsBetween(-4, 0)

        gold_df = df.select(
            # Identifiants
            col("device_id"),
            col("aws_timestamp"),
            col("silver_processing_timestamp"),

            # Métriques principales
            col("acceleration_magnitude"),
            col("gyro_magnitude"),
            col("temperature"),
            col("activity_level"),
            col("temperature_status"),
            col("movement_type"),

            # Moyennes mobiles (5 dernières mesures)
            avg("acceleration_magnitude").over(window_spec).alias("avg_acceleration_5min"),
            avg("gyro_magnitude").over(window_spec).alias("avg_gyro_5min"),
            avg("temperature").over(window_spec).alias("avg_temperature_5min"),

            # Score de santé composite (0-100)
            (
                when(col("temperature") > 37.5, 20)
                .when(col("temperature") < 35.0, 20)
                .otherwise(100) +

                when(col("acceleration_magnitude") > 20.0, -30)
                .when(col("acceleration_magnitude") < 1.0, -20)
                .otherwise(0)
            ).alias("health_score"),

            # Classification du patient (basée sur l'activité)
            when(
                avg("acceleration_magnitude").over(window_spec) > 12.0, "high_activity_patient"
            ).when(
                avg("acceleration_magnitude").over(window_spec) > 8.0, "moderate_activity_patient"
            ).otherwise("low_activity_patient").alias("patient_profile"),

            # Business KPIs
            when(col("movement_type") == "potential_fall", 1).otherwise(0).alias("fall_alert_flag"),
            when(col("temperature_status") != "normal", 1).otherwise(0).alias("temp_alert_flag"),
            when(col("activity_level") == "high_activity", 1).otherwise(0).alias("high_activity_flag"),

            # Timestamps et métadonnées Gold
            current_timestamp().alias("gold_processing_timestamp"),
            lit("silver_to_gold").alias("processing_stage"),
            lit("v2.0").alias("gold_schema_version")
        )

        print(f"📊 Données gold transformées: {gold_df.count()}")

        if gold_df.count() > 0:
            # Ajouter partitioning par date business
            gold_with_partition = gold_df.withColumn(
                "processing_date", to_date(col("gold_processing_timestamp"))
            ).withColumn(
                "year", year(col("processing_date"))
            ).withColumn(
                "month", month(col("processing_date"))
            ).withColumn(
                "day", dayofmonth(col("processing_date"))
            ).withColumn(
                "hour", hour(col("gold_processing_timestamp"))
            )

            # Écriture en gold avec partitioning détaillé
            gold_output = args['gold_output_path'] + "mpu_christian_analytics/"
            print(f"💾 Écriture vers: {gold_output}")

            gold_with_partition.write \
                .mode("append") \
                .partitionBy("year", "month", "day", "hour") \
                .option("compression", "snappy") \
                .json(gold_output)

            print(f"✅ {gold_with_partition.count()} enregistrements écrits en gold")

            # Créer aussi une vue agrégée quotidienne
            daily_summary = gold_df.groupBy(
                to_date(col("gold_processing_timestamp")).alias("measurement_date"),
                col("device_id")
            ).agg(
                count("*").alias("total_measurements"),
                avg("acceleration_magnitude").alias("avg_daily_acceleration"),
                max("acceleration_magnitude").alias("max_daily_acceleration"),
                avg("temperature").alias("avg_daily_temperature"),
                sum("fall_alert_flag").alias("daily_fall_alerts"),
                sum("temp_alert_flag").alias("daily_temp_alerts"),
                sum("high_activity_flag").alias("daily_high_activity_count"),
                avg("health_score").alias("avg_daily_health_score")
            ).withColumn(
                "summary_timestamp", current_timestamp()
            ).withColumn(
                "year", year(col("measurement_date"))
            ).withColumn(
                "month", month(col("measurement_date"))
            )

            # Sauvegarder le résumé quotidien
            summary_output = args['gold_output_path'] + "mpu_christian_daily_summary/"
            daily_summary.write \
                .mode("append") \
                .partitionBy("year", "month") \
                .json(summary_output)

            print(f"✅ Résumé quotidien créé avec {daily_summary.count()} entrées")

        else:
            print("⚠️ Aucune donnée après transformation gold")
    else:
        print("⚠️ Aucune donnée silver trouvée")

except Exception as e:
    print(f"❌ ERREUR: {str(e)}")
    raise e

finally:
    job.commit()
    print("✅ Job silver-to-gold terminé")
