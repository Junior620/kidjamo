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

print("🚀 JOB RAW-TO-BRONZE FINAL CORRIGÉ POUR MPU CHRISTIAN")
print(f"📂 Input: {args['input_path']}")
print(f"📂 Bronze: {args['bronze_output_path']}")
print(f"📂 Quarantine: {args['quarantine_output_path']}")

try:
    # Lecture des données JSON depuis S3 raw - STRUCTURE DIRECTE
    input_path = args['input_path'] + "iot-measurements/"
    print(f"📖 Lecture depuis: {input_path}")

    # Lire tous les fichiers JSON avec structure directe
    df = spark.read.option("multiline", "true").json(input_path)

    print(f"📊 Nombre de lignes lues: {df.count()}")
    print("🔍 Schéma détecté:")
    df.printSchema()

    # Filtrer SEULEMENT les données MPU Christian - COLONNES DIRECTES
    mpu_df = df.filter(
        col("device_id") == "MPU_Christian_8266MOD"
    ).filter(
        # S'assurer que les données essentielles ne sont pas nulles
        col("device_id").isNotNull() &
        col("accel_x").isNotNull() &
        col("accel_y").isNotNull() &
        col("accel_z").isNotNull() &
        col("temp").isNotNull()
    )

    print(f"📊 Données MPU Christian filtrées: {mpu_df.count()}")

    if mpu_df.count() > 0:
        # Transformation vers format bronze standardisé - STRUCTURE DIRECTE
        bronze_df = mpu_df.select(
            # Données MPU directes (pas d'imbrication!)
            col("device_id"),
            col("accel_x"),
            col("accel_y"),
            col("accel_z"),
            col("gyro_x"),
            col("gyro_y"),
            col("gyro_z"),
            col("temp").alias("temperature"),
            col("aws_timestamp"),

            # Ajout de colonnes calculées
            current_timestamp().alias("bronze_processing_timestamp"),
            lit("mpu_christian").alias("source_type"),
            lit("raw_to_bronze").alias("processing_stage"),
            lit("v2.0").alias("schema_version")
        )

        print(f"📊 Données bronze transformées: {bronze_df.count()}")

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

        print(f"✅ {bronze_with_partition.count()} enregistrements MPU Christian écrits en bronze")

        # Afficher quelques exemples
        print("📊 EXEMPLE DE DONNÉES TRAITÉES:")
        bronze_df.select("device_id", "accel_x", "accel_y", "accel_z", "temperature").show(5)

    else:
        print("⚠️ Aucune donnée MPU Christian trouvée - vérifiez le device_id")

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
