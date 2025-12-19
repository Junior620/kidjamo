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
    'input_path',
    'bronze_output_path',
    'quarantine_output_path'
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

print("🚀 JOB RAW-TO-BRONZE CORRIGÉ POUR MPU CHRISTIAN")
print(f"📂 Input: {args['input_path']}")
print(f"📂 Bronze: {args['bronze_output_path']}")
print(f"📂 Quarantine: {args['quarantine_output_path']}")

try:
    # Lecture des données JSON depuis S3 raw
    input_path = args['input_path'] + "iot-measurements/"
    print(f"📖 Lecture depuis: {input_path}")

    # Lire tous les fichiers JSON
    df = spark.read.option("multiline", "true").json(input_path)

    print(f"📊 Nombre de lignes lues: {df.count()}")
    print("🔍 Schéma détecté:")
    df.printSchema()

    # Filtrer seulement les données MPU Christian (exclure les fichiers test)
    mpu_df = df.filter(
        (col("raw_data.device_id") == "MPU_Christian_8266MOD") |
        (col("raw_data.device_id").like("%test%") == False)
    )

    print(f"📊 Données MPU Christian filtrées: {mpu_df.count()}")

    if mpu_df.count() > 0:
        # Transformation vers format bronze standardisé
        bronze_df = mpu_df.select(
            # Extraction des données du raw_data
            col("raw_data.device_id").alias("device_id"),
            col("raw_data.accel_x").alias("accel_x"),
            col("raw_data.accel_y").alias("accel_y"),
            col("raw_data.accel_z").alias("accel_z"),
            col("raw_data.gyro_x").alias("gyro_x"),
            col("raw_data.gyro_y").alias("gyro_y"),
            col("raw_data.gyro_z").alias("gyro_z"),
            col("raw_data.temp").alias("temperature"),
            col("raw_data.aws_timestamp").alias("raw_timestamp"),

            # Métadonnées Kinesis
            col("kinesis_metadata.sequence_number").alias("kinesis_sequence"),
            col("kinesis_metadata.partition_key").alias("partition_key"),
            col("kinesis_metadata.arrival_timestamp").alias("arrival_timestamp"),

            # Timestamp de processing
            col("processing_timestamp").alias("processing_timestamp"),

            # Ajout de colonnes calculées
            current_timestamp().alias("bronze_processing_timestamp"),
            lit("mpu_christian").alias("source_type"),
            lit("raw_to_bronze").alias("processing_stage")
        ).filter(
            # S'assurer que les données essentielles ne sont pas nulles
            col("device_id").isNotNull() &
            col("accel_x").isNotNull() &
            col("accel_y").isNotNull() &
            col("accel_z").isNotNull()
        )

        print(f"📊 Données bronze transformées: {bronze_df.count()}")

        if bronze_df.count() > 0:
            # Ajouter partitioning par date
            bronze_with_partition = bronze_df.withColumn(
                "processing_date", to_date(col("bronze_processing_timestamp"))
            ).withColumn(
                "year", year(col("processing_date"))
            ).withColumn(
                "month", month(col("processing_date"))
            ).withColumn(
                "day", dayofmonth(col("processing_date"))
            )

            # Écriture en bronze avec partitioning
            bronze_output = args['bronze_output_path'] + "mpu_christian/"
            print(f"💾 Écriture vers: {bronze_output}")

            bronze_with_partition.write \
                .mode("append") \
                .partitionBy("year", "month", "day") \
                .option("compression", "snappy") \
                .json(bronze_output)

            print(f"✅ {bronze_with_partition.count()} enregistrements écrits en bronze")

        else:
            print("⚠️ Aucune donnée valide après transformation")
    else:
        print("⚠️ Aucune donnée MPU Christian trouvée")

except Exception as e:
    print(f"❌ ERREUR: {str(e)}")

    # En cas d'erreur, sauvegarder en quarantine
    try:
        quarantine_path = args['quarantine_output_path'] + f"failed_raw_to_bronze_{datetime.now().strftime('%Y%m%d_%H%M%S')}/"

        # Lire les données brutes pour quarantine
        raw_df = spark.read.text(input_path)
        raw_df.write.mode("append").text(quarantine_path)

        print(f"🗂️ Données sauvegardées en quarantine: {quarantine_path}")
    except Exception as quarantine_error:
        print(f"❌ Erreur quarantine: {str(quarantine_error)}")

    raise e

finally:
    job.commit()
    print("✅ Job raw-to-bronze terminé")
