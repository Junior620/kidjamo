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
    'bronze_input_path',
    'silver_output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("🚀 JOB BRONZE-TO-SILVER CORRIGÉ POUR MPU CHRISTIAN")
print(f"📂 Bronze Input: {args['bronze_input_path']}")
print(f"📂 Silver Output: {args['silver_output_path']}")

try:
    # Lecture des données bronze
    bronze_path = args['bronze_input_path'] + "mpu_christian/"
    print(f"📖 Lecture depuis: {bronze_path}")

    df = spark.read.json(bronze_path)

    print(f"📊 Nombre de lignes bronze: {df.count()}")

    if df.count() > 0:
        # Transformation et enrichissement pour Silver
        silver_df = df.select(
            # Données principales
            col("device_id"),
            col("accel_x"),
            col("accel_y"),
            col("accel_z"),
            col("gyro_x"),
            col("gyro_y"),
            col("gyro_z"),
            col("temperature"),
            col("raw_timestamp"),

            # Métadonnées
            col("kinesis_sequence"),
            col("partition_key"),
            col("arrival_timestamp"),
            col("processing_timestamp"),
            col("bronze_processing_timestamp"),

            # Nouvelles colonnes calculées pour Silver
            sqrt(
                col("accel_x") * col("accel_x") +
                col("accel_y") * col("accel_y") +
                col("accel_z") * col("accel_z")
            ).alias("acceleration_magnitude"),

            sqrt(
                col("gyro_x") * col("gyro_x") +
                col("gyro_y") * col("gyro_y") +
                col("gyro_z") * col("gyro_z")
            ).alias("gyro_magnitude"),

            # Classification de mouvement basique
            when(
                sqrt(col("accel_x") * col("accel_x") +
                     col("accel_y") * col("accel_y") +
                     col("accel_z") * col("accel_z")) > 15.0, "high_activity"
            ).when(
                sqrt(col("accel_x") * col("accel_x") +
                     col("accel_y") * col("accel_y") +
                     col("accel_z") * col("accel_z")) > 12.0, "medium_activity"
            ).otherwise("low_activity").alias("activity_level"),

            # Classification température
            when(col("temperature") > 37.5, "fever")
            .when(col("temperature") < 35.0, "hypothermia")
            .otherwise("normal").alias("temperature_status"),

            # Qualité des données
            when(
                col("accel_x").isNotNull() &
                col("accel_y").isNotNull() &
                col("accel_z").isNotNull() &
                col("gyro_x").isNotNull() &
                col("gyro_y").isNotNull() &
                col("gyro_z").isNotNull() &
                col("temperature").isNotNull(),
                "complete"
            ).otherwise("incomplete").alias("data_quality"),

            # Timestamps Silver
            current_timestamp().alias("silver_processing_timestamp"),
            lit("bronze_to_silver").alias("processing_stage"),
            lit("v1.0").alias("schema_version")

        ).filter(
            # Filtrer les données de qualité
            col("data_quality") == "complete"
        )

        print(f"📊 Données silver transformées: {silver_df.count()}")

        if silver_df.count() > 0:
            # Ajouter partitioning par date
            silver_with_partition = silver_df.withColumn(
                "processing_date", to_date(col("silver_processing_timestamp"))
            ).withColumn(
                "year", year(col("processing_date"))
            ).withColumn(
                "month", month(col("processing_date"))
            ).withColumn(
                "day", dayofmonth(col("processing_date"))
            )

            # Écriture en silver avec partitioning
            silver_output = args['silver_output_path'] + "mpu_christian_enriched/"
            print(f"💾 Écriture vers: {silver_output}")

            silver_with_partition.write \
                .mode("append") \
                .partitionBy("year", "month", "day") \
                .option("compression", "snappy") \
                .json(silver_output)

            print(f"✅ {silver_with_partition.count()} enregistrements écrits en silver")

        else:
            print("⚠️ Aucune donnée de qualité complète")
    else:
        print("⚠️ Aucune donnée bronze trouvée")

except Exception as e:
    print(f"❌ ERREUR: {str(e)}")
    raise e

finally:
    job.commit()
    print("✅ Job bronze-to-silver terminé")
